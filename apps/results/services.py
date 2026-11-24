
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.assessments.models import Evaluacion
from apps.questionnaires.models import Cuestionario, Pregunta
from apps.results.models import Resultado, PuntajeDimension
from apps.scoring.services import (
    calcular_puntajes_personalidad,
    calcular_puntajes_vark,
    generar_perfil_personalidad,
)


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
