
from collections import Counter

from django.core.exceptions import ValidationError

from apps.assessments.models import SeleccionRespuesta
from apps.questionnaires.models import Cuestionario


def calcular_puntajes_vark(evaluacion):
    """
    Calcula los puntajes VARK a partir de las
    opciones seleccionadas en una evaluación.

    Devuelve los cuatro puntajes, incluyendo
    dimensiones que no recibieron selecciones.
    """

    if evaluacion.cuestionario.tipo != Cuestionario.Tipo.VARK:
        raise ValidationError(
            "La evaluación no corresponde a un cuestionario VARK."
        )

    dimensiones = ("V", "A", "R", "K")

    selecciones = SeleccionRespuesta.objects.filter(
        respuesta__evaluacion=evaluacion
    ).values_list(
        "opcion__dimension",
        flat=True,
    )

    conteo = Counter(selecciones)

    if any(dimension not in dimensiones for dimension in conteo):
        raise ValidationError(
            "La evaluación contiene dimensiones incompatibles con VARK."
        )

    return {
        dimension: conteo.get(dimension, 0)
        for dimension in dimensiones
    }
