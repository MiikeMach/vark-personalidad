from django.core.exceptions import ValidationError
from django.db import transaction

from apps.assessments.models import Evaluacion
from apps.questionnaires.models import Cuestionario, Pregunta
from apps.results.models import Resultado, PuntajeDimension
from django.utils import timezone

from apps.scoring.services import (
    calcular_puntajes_personalidad,
    calcular_puntajes_vark,
    generar_perfil_personalidad,
)

from apps.assessments.services import (
    validar_distribucion_personalidad,
    validar_par_personalidad,
)


def validar_respuestas_para_finalizar(evaluacion):
    """
    Verifica la integridad de las respuestas
    antes de finalizar una evaluación.
    """

    preguntas = set(
        Pregunta.objects.filter(
            cuestionario_id=evaluacion.cuestionario_id
        ).values_list("id", flat=True)
    )

    if not preguntas:
        raise ValidationError(
            "El cuestionario no contiene preguntas."
        )

    respuestas = (
        evaluacion.respuestas
        .prefetch_related("selecciones__opcion")
    )

    preguntas_contestadas = set()

    for respuesta in respuestas:
        if respuesta.pregunta_id not in preguntas:
            raise ValidationError(
                "Existe una respuesta de otro cuestionario."
            )

        selecciones = list(respuesta.selecciones.all())

        for seleccion in selecciones:
            if seleccion.opcion.pregunta_id != respuesta.pregunta_id:
                raise ValidationError(
                    "Una opción pertenece a otra pregunta."
                )

        if evaluacion.cuestionario.tipo == Cuestionario.Tipo.VARK:
            for seleccion in selecciones:
                if seleccion.opcion.dimension not in ("V", "A", "R", "K"):
                    raise ValidationError(
                        "La respuesta contiene una dimensión no válida."
                    )

                if seleccion.puntos is not None:
                    raise ValidationError(
                        "Las respuestas VARK no deben tener puntos."
                    )

        elif evaluacion.cuestionario.tipo == Cuestionario.Tipo.PERSONALIDAD:
            if len(selecciones) != 2:
                raise ValidationError(
                    "Cada pregunta de personalidad requiere dos opciones."
                )

            primera, segunda = selecciones

            validar_par_personalidad(
                primera.opcion.dimension,
                segunda.opcion.dimension,
            )

            validar_distribucion_personalidad(
                primera.puntos,
                segunda.puntos,
            )

        else:
            raise ValidationError(
                "Tipo de cuestionario no compatible."
            )

        if selecciones:
            preguntas_contestadas.add(respuesta.pregunta_id)

    if evaluacion.cuestionario.tipo == Cuestionario.Tipo.PERSONALIDAD:
        if preguntas_contestadas != preguntas:
            raise ValidationError(
                "Faltan preguntas de personalidad por contestar."
            )

    return True

@transaction.atomic
def guardar_resultado(evaluacion_id):
    evaluacion = (
        Evaluacion.objects.select_for_update()
        .select_related("cuestionario")
        .get(pk=evaluacion_id)
    )

    if evaluacion.estado != Evaluacion.Estado.EN_PROGRESO:
        raise ValidationError(
            "No se puede recalcular una evaluación finalizada."
        )

    if evaluacion.cuestionario.tipo == Cuestionario.Tipo.VARK:
        puntajes = calcular_puntajes_vark(evaluacion)
        interpretacion = ""

    elif evaluacion.cuestionario.tipo == Cuestionario.Tipo.PERSONALIDAD:
        puntajes = calcular_puntajes_personalidad(evaluacion)

        perfil = generar_perfil_personalidad(puntajes)

        if perfil is None:
            interpretacion = "Perfil no determinado"
        else:
            interpretacion = perfil

    else:
        raise ValidationError(
            "Tipo de cuestionario no compatible."
        )


    total_preguntas = Pregunta.objects.filter(
        cuestionario=evaluacion.cuestionario
    ).count()

    contestadas = (
        evaluacion.respuestas.filter(
            selecciones__isnull=False
        )
        .distinct()
        .count()
    )

    omitidas = total_preguntas - contestadas

    if omitidas < 0:
        raise ValidationError(
            "La evaluación contiene más respuestas que preguntas."
        )

    resultado, _ = Resultado.objects.update_or_create(
        evaluacion=evaluacion,
        defaults={
            "preguntas_contestadas": contestadas,
            "preguntas_omitidas": omitidas,
            "interpretacion": interpretacion,
        },
    )

    for dimension, puntaje in puntajes.items():
        PuntajeDimension.objects.update_or_create(
            resultado=resultado,
            dimension=dimension,
            defaults={"puntaje": puntaje},
        )

    resultado.puntajes.exclude(
        dimension__in=puntajes.keys()
    ).delete()

    return resultado


@transaction.atomic
def finalizar_evaluacion(evaluacion_id):
    """
    Valida las respuestas, calcula y guarda
    los resultados, y finaliza la evaluación
    dentro de una única transacción.
    """

    evaluacion = (
        Evaluacion.objects
        .select_for_update()
        .select_related("cuestionario")
        .get(pk=evaluacion_id)
    )

    if evaluacion.estado != Evaluacion.Estado.EN_PROGRESO:
        raise ValidationError(
            "La evaluación ya fue finalizada."
        )

    # Comprobar la integridad antes de modificar el estado.
    validar_respuestas_para_finalizar(evaluacion)

    # Calcular y almacenar los resultados.
    resultado = guardar_resultado(evaluacion.pk)

    # Cambiar el estado únicamente después de guardar.
    evaluacion.estado = Evaluacion.Estado.FINALIZADA
    evaluacion.finalizada_en = timezone.now()

    evaluacion.save(
        update_fields=["estado", "finalizada_en"]
    )

    return resultado
