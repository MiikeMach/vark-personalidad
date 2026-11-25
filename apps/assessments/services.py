from django.core.exceptions import ValidationError
from apps.assessments.models import Evaluacion

from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from django.db import transaction
from apps.assessments.models import Respuesta, SeleccionRespuesta


def validar_selecciones(evaluacion, pregunta_id, opcion_ids):
    """
    Valida que las opciones seleccionadas correspondan
    a la pregunta y al cuestionario de la evaluación.
    """

    if not isinstance(pregunta_id, int) or isinstance(pregunta_id, bool):
        raise ValidationError("El identificador de pregunta no es válido.")

    if not isinstance(opcion_ids, list):
        raise ValidationError("Las opciones deben enviarse en una lista.")

    if any(
        not isinstance(opcion_id, int) or isinstance(opcion_id, bool)
        for opcion_id in opcion_ids
    ):
        raise ValidationError("Los identificadores de opción deben ser enteros.")

    if len(opcion_ids) != len(set(opcion_ids)):
        raise ValidationError("No se permite repetir una opción.")

    try:
        pregunta = Pregunta.objects.get(
            pk=pregunta_id,
            cuestionario_id=evaluacion.cuestionario_id,
        )
    except Pregunta.DoesNotExist as exc:
        raise ValidationError(
            "La pregunta no pertenece al cuestionario."
        ) from exc

    if (
        evaluacion.cuestionario.tipo == Cuestionario.Tipo.PERSONALIDAD
        and len(opcion_ids) > 1
    ):
        raise ValidationError(
            "En personalidad solo se permite una opción por pregunta."
        )

    opciones = list(
        Opcion.objects.filter(
            pregunta=pregunta,
            pk__in=opcion_ids,
        )
    )

    if len(opciones) != len(opcion_ids):
        raise ValidationError(
            "Una o más opciones no pertenecen a la pregunta."
        )

    return opciones

def validar_evaluacion_editable(evaluacion):
    """
    Comprueba que una evaluación todavía pueda modificarse.

    Una evaluación finalizada no debe admitir cambios
    en sus respuestas.
    """
    if evaluacion.estado != Evaluacion.Estado.EN_PROGRESO:
        raise ValidationError(
            "No se pueden modificar respuestas de una evaluación finalizada."
        )

@transaction.atomic
def guardar_respuesta(evaluacion_id, pregunta_id, opcion_ids):
    """
    Guarda o actualiza las opciones seleccionadas
    para una pregunta dentro de una evaluación.

    Permite una lista vacía para registrar una omisión.
    """

    evaluacion = (
        Evaluacion.objects
        .select_for_update()
        .select_related("cuestionario")
        .get(pk=evaluacion_id)
    )

    validar_evaluacion_editable(evaluacion)

    if evaluacion.cuestionario.tipo != Cuestionario.Tipo.VARK:
        raise ValidationError(
            "Este servicio solo admite respuestas VARK. "
            "Para personalidad utiliza guardar_respuesta_personalidad()."
        )

    opciones = validar_selecciones(
        evaluacion,
        pregunta_id,
        opcion_ids,
    )

    respuesta, _ = Respuesta.objects.get_or_create(
        evaluacion=evaluacion,
        pregunta_id=pregunta_id,
    )

    # Reemplazamos las selecciones anteriores.
    respuesta.selecciones.all().delete()

    SeleccionRespuesta.objects.bulk_create(
        [
            SeleccionRespuesta(
                respuesta=respuesta,
                opcion=opcion,
            )
            for opcion in opciones
        ]
    )

    return respuesta

def validar_distribucion_personalidad(puntos_1, puntos_2):
    """
    Valida que dos dimensiones opuestas reciban
    exactamente 10 puntos, sin reparto 5/5.
    """

    for puntos in (puntos_1, puntos_2):
        if type(puntos) is not int:
            raise ValidationError(
                "Los puntos deben ser números enteros."
            )

        if not 0 <= puntos <= 10:
            raise ValidationError(
                "Cada puntuación debe estar entre 0 y 10."
            )

    if puntos_1 + puntos_2 != 10:
        raise ValidationError(
            "Las dos puntuaciones deben sumar 10."
        )

    if puntos_1 == 5 and puntos_2 == 5:
        raise ValidationError(
            "No se permite distribuir 5 puntos a cada dimensión."
        )

    return True


def validar_par_personalidad(dimension_1, dimension_2):
    """
    Comprueba que dos dimensiones de personalidad
    formen uno de los cuatro pares permitidos.
    """

    pares_permitidos = {
        frozenset(("E", "I")),
        frozenset(("S", "N")),
        frozenset(("T", "F")),
        frozenset(("J", "P")),
    }

    dimensiones = frozenset(
        (dimension_1, dimension_2)
    )

    if dimensiones not in pares_permitidos:
        raise ValidationError(
            "Las dimensiones no forman un par "
            "válido de personalidad."
        )

    return True


@transaction.atomic
def guardar_respuesta_personalidad(
    evaluacion_id,
    pregunta_id,
    opcion_1_id,
    puntos_1,
    opcion_2_id,
    puntos_2,
):
    """
    Guarda o actualiza una distribución de puntos
    entre dos dimensiones opuestas de personalidad.
    """

    evaluacion = (
        Evaluacion.objects
        .select_for_update()
        .select_related("cuestionario")
        .get(pk=evaluacion_id)
    )

    validar_evaluacion_editable(evaluacion)

    if evaluacion.cuestionario.tipo != Cuestionario.Tipo.PERSONALIDAD:
        raise ValidationError(
            "La evaluación no corresponde a personalidad."
        )

    # Comprobar primero la distribución numérica.
    validar_distribucion_personalidad(puntos_1, puntos_2)

    # Rechazar identificadores duplicados.
    if opcion_1_id == opcion_2_id:
        raise ValidationError(
            "Las dos opciones deben ser diferentes."
        )

    # Comprobar que la pregunta pertenece al cuestionario.
    try:
        pregunta = Pregunta.objects.get(
            pk=pregunta_id,
            cuestionario_id=evaluacion.cuestionario_id,
        )
    except Pregunta.DoesNotExist as exc:
        raise ValidationError(
            "La pregunta no pertenece al cuestionario."
        ) from exc

    opciones = list(
        Opcion.objects.filter(
            pregunta=pregunta,
            pk__in=[opcion_1_id, opcion_2_id],
        )
    )

    if len(opciones) != 2:
        raise ValidationError(
            "Las dos opciones deben pertenecer a la pregunta."
        )

    opciones_por_id = {
        opcion.pk: opcion
        for opcion in opciones
    }

    opcion_1 = opciones_por_id[opcion_1_id]
    opcion_2 = opciones_por_id[opcion_2_id]

    validar_par_personalidad(
        opcion_1.dimension,
        opcion_2.dimension,
    )

    respuesta, _ = Respuesta.objects.get_or_create(
        evaluacion=evaluacion,
        pregunta=pregunta,
    )

    # Reemplazar la distribución anterior.
    respuesta.selecciones.all().delete()

    SeleccionRespuesta.objects.bulk_create(
        [
            SeleccionRespuesta(
                respuesta=respuesta,
                opcion=opcion_1,
                puntos=puntos_1,
            ),
            SeleccionRespuesta(
                respuesta=respuesta,
                opcion=opcion_2,
                puntos=puntos_2,
            ),
        ]
    )

    return respuesta
