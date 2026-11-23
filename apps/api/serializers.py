"""Serializadores manuales (dict) para la API básica."""

from apps.students.models import Grupo, Estudiante
from apps.questionnaires.models import Cuestionario, Pregunta, Opcion
from apps.assessments.models import Evaluacion, Respuesta, SeleccionRespuesta
from apps.results.models import Resultado, PuntajeDimension


def _iso(value):
    return value.isoformat() if value else None


# ---------- students ----------

def grupo_to_dict(obj):
    return {
        "id": obj.id,
        "clave": obj.clave,
        "nombre": obj.nombre,
        "activo": obj.activo,
        "creado_en": _iso(obj.creado_en),
    }


def estudiante_to_dict(obj):
    return {
        "id": obj.id,
        "matricula": obj.matricula,
        "nombres": obj.nombres,
        "apellidos": obj.apellidos,
        "correo": obj.correo,
        "grupo": obj.grupo_id,
        "activo": obj.activo,
        "creado_en": _iso(obj.creado_en),
    }


# ---------- questionnaires ----------

def cuestionario_to_dict(obj):
    return {
        "id": obj.id,
        "titulo": obj.titulo,
        "descripcion": obj.descripcion,
        "instrucciones": obj.instrucciones,
        "tipo": obj.tipo,
        "activo": obj.activo,
        "creado_en": _iso(obj.creado_en),
    }


def pregunta_to_dict(obj):
    return {
        "id": obj.id,
        "cuestionario": obj.cuestionario_id,
        "texto": obj.texto,
        "orden": obj.orden,
    }


def opcion_to_dict(obj):
    return {
        "id": obj.id,
        "pregunta": obj.pregunta_id,
        "texto": obj.texto,
        "dimension": obj.dimension,
        "orden": obj.orden,
    }


# ---------- assessments ----------

def evaluacion_to_dict(obj):
    return {
        "id": obj.id,
        "estudiante": obj.estudiante_id,
        "cuestionario": obj.cuestionario_id,
        "estado": obj.estado,
        "iniciada_en": _iso(obj.iniciada_en),
        "finalizada_en": _iso(obj.finalizada_en),
    }


def respuesta_to_dict(obj):
    return {
        "id": obj.id,
        "evaluacion": obj.evaluacion_id,
        "pregunta": obj.pregunta_id,
    }


def seleccion_to_dict(obj):
    return {
        "id": obj.id,
        "respuesta": obj.respuesta_id,
        "opcion": obj.opcion_id,
    }


# ---------- results ----------

def resultado_to_dict(obj):
    return {
        "id": obj.id,
        "evaluacion": obj.evaluacion_id,
        "preguntas_contestadas": obj.preguntas_contestadas,
        "preguntas_omitidas": obj.preguntas_omitidas,
        "interpretacion": obj.interpretacion,
        "calculado_en": _iso(obj.calculado_en),
    }


def puntaje_to_dict(obj):
    return {
        "id": obj.id,
        "resultado": obj.resultado_id,
        "dimension": obj.dimension,
        "puntaje": obj.puntaje,
    }