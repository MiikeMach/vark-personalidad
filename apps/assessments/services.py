
from django.core.exceptions import ValidationError

from apps.questionnaires.models import Cuestionario, Opcion, Pregunta


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
