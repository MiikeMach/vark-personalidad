
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
