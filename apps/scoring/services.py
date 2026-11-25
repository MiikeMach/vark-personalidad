from collections import Counter

from django.core.exceptions import ValidationError

from apps.assessments.models import SeleccionRespuesta
from apps.questionnaires.models import Cuestionario
from django.core.exceptions import ValidationError

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


def calcular_puntajes_personalidad(evaluacion):
    """
    Suma los puntos almacenados para cada una
    de las ocho dimensiones de personalidad.
    """

    if evaluacion.cuestionario.tipo != Cuestionario.Tipo.PERSONALIDAD:
        raise ValidationError(
            "La evaluación no corresponde a personalidad."
        )

    dimensiones = ("E", "I", "S", "N", "T", "F", "J", "P")
    puntajes = {dimension: 0 for dimension in dimensiones}

    selecciones = SeleccionRespuesta.objects.filter(
        respuesta__evaluacion=evaluacion
    ).select_related("opcion")

    for seleccion in selecciones:
        dimension = seleccion.opcion.dimension
        puntos = seleccion.puntos

        if dimension not in puntajes:
            raise ValidationError(
                "La evaluación contiene una dimensión incompatible."
            )

        if puntos is None:
            raise ValidationError(
                "Una selección de personalidad no tiene puntos."
            )

        puntajes[dimension] += puntos

    return puntajes

def generar_perfil_personalidad(puntajes):
    """
    Genera un perfil de cuatro letras a partir
    de las puntuaciones de personalidad.

    Devuelve None si faltan datos o hay empates.
    """

    pares = [
        ("E", "I"),
        ("S", "N"),
        ("T", "F"),
        ("J", "P"),
    ]

    perfil = []

    for primera, segunda in pares:
        puntos_1 = puntajes.get(primera, 0)
        puntos_2 = puntajes.get(segunda, 0)

        if (
            type(puntos_1) is not int
            or type(puntos_2) is not int
            or puntos_1 < 0
            or puntos_2 < 0
        ):
            raise ValidationError(
                "Las puntuaciones de personalidad son inválidas."
            )

        if puntos_1 == puntos_2:
            return None

        if puntos_1 > puntos_2:
            perfil.append(primera)
        else:
            perfil.append(segunda)

    return "".join(perfil)