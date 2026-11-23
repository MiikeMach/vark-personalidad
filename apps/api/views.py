"""Endpoints CRUD básicos (View de Django + JsonResponse), sin CSRF por ahora."""

import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.students.models import Grupo, Estudiante
from apps.questionnaires.models import Cuestionario, Pregunta, Opcion
from apps.assessments.models import Evaluacion, Respuesta, SeleccionRespuesta
from apps.results.models import Resultado, PuntajeDimension

from . import serializers as s


# ---------- utilidades ----------

def _json_error(message, status=400):
    return JsonResponse({"detail": message}, status=status)


def _payload(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise ValidationError("JSON inválido.")


# =====================================================================
# Base genérica (con CSRF exento mientras no haya auth)
# =====================================================================

@method_decorator(csrf_exempt, name="dispatch")
class BaseListView(View):
    """
    GET  -> lista
    POST -> crea
    """
    model = None
    to_dict = None
    fields = ()
    ordering = None

    def get_queryset(self):
        qs = self.model.objects.all()
        if self.ordering:
            qs = qs.order_by(self.ordering)
        return qs

    def get(self, request, *args, **kwargs):
        data = [self.to_dict(o) for o in self.get_queryset()]
        return JsonResponse(data, safe=False)

    def post(self, request, *args, **kwargs):
        try:
            body = _payload(request)
        except ValidationError as e:
            return _json_error(e.messages[0])
        try:
            with transaction.atomic():
                obj = self.model(**{f: body[f] for f in self.fields if f in body})
                obj.full_clean()
                obj.save()
        except ValidationError as e:
            return _json_error(e.message_dict)
        except IntegrityError as e:
            return _json_error(str(e), status=409)
        return JsonResponse(self.to_dict(obj), status=201)


@method_decorator(csrf_exempt, name="dispatch")
class BaseDetailView(View):
    """
    GET    -> detalle
    PUT    -> actualiza (requiere todos los campos editables)
    PATCH  -> actualiza parcial
    DELETE -> elimina
    """
    model = None
    to_dict = None
    fields = ()

    def _get(self, pk):
        return get_object_or_404(self.model, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        return JsonResponse(self.to_dict(self._get(pk)))

    def put(self, request, pk, *args, **kwargs):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk, *args, **kwargs):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        obj = self._get(pk)
        try:
            body = _payload(request)
        except ValidationError as e:
            return _json_error(e.messages[0])
        if not partial:
            missing = [f for f in self.fields if f not in body]
            if missing:
                return _json_error(f"Faltan campos: {', '.join(missing)}")
        try:
            for f in self.fields:
                if f in body:
                    setattr(obj, f, body[f])
            with transaction.atomic():
                obj.full_clean()
                obj.save()
        except ValidationError as e:
            return _json_error(e.message_dict)
        except IntegrityError as e:
            return _json_error(str(e), status=409)
        return JsonResponse(self.to_dict(obj))

    def delete(self, request, pk, *args, **kwargs):
        obj = self._get(pk)
        try:
            obj.delete()
        except IntegrityError as e:
            return _json_error(str(e), status=409)
        return JsonResponse({}, status=204)


# =====================================================================
# students
# =====================================================================

class GrupoListView(BaseListView):
    model = Grupo
    to_dict = staticmethod(s.grupo_to_dict)
    fields = ("clave", "nombre", "activo")
    ordering = "nombre"


class GrupoDetailView(BaseDetailView):
    model = Grupo
    to_dict = staticmethod(s.grupo_to_dict)
    fields = ("clave", "nombre", "activo")


class EstudianteListView(BaseListView):
    model = Estudiante
    to_dict = staticmethod(s.estudiante_to_dict)
    fields = ("matricula", "nombres", "apellidos", "correo", "grupo", "activo")
    ordering = ("apellidos", "nombres")


class EstudianteDetailView(BaseDetailView):
    model = Estudiante
    to_dict = staticmethod(s.estudiante_to_dict)
    fields = ("matricula", "nombres", "apellidos", "correo", "grupo", "activo")


# =====================================================================
# questionnaires
# =====================================================================

class CuestionarioListView(BaseListView):
    model = Cuestionario
    to_dict = staticmethod(s.cuestionario_to_dict)
    fields = ("titulo", "descripcion", "instrucciones", "tipo", "activo")
    ordering = ("tipo", "titulo")


class CuestionarioDetailView(BaseDetailView):
    model = Cuestionario
    to_dict = staticmethod(s.cuestionario_to_dict)
    fields = ("titulo", "descripcion", "instrucciones", "tipo", "activo")


class PreguntaListView(BaseListView):
    model = Pregunta
    to_dict = staticmethod(s.pregunta_to_dict)
    fields = ("cuestionario", "texto", "orden")
    ordering = "orden"


class PreguntaDetailView(BaseDetailView):
    model = Pregunta
    to_dict = staticmethod(s.pregunta_to_dict)
    fields = ("cuestionario", "texto", "orden")


class OpcionListView(BaseListView):
    model = Opcion
    to_dict = staticmethod(s.opcion_to_dict)
    fields = ("pregunta", "texto", "dimension", "orden")
    ordering = "orden"


class OpcionDetailView(BaseDetailView):
    model = Opcion
    to_dict = staticmethod(s.opcion_to_dict)
    fields = ("pregunta", "texto", "dimension", "orden")


# =====================================================================
# assessments
# =====================================================================

class EvaluacionListView(BaseListView):
    model = Evaluacion
    to_dict = staticmethod(s.evaluacion_to_dict)
    fields = ("estudiante", "cuestionario", "estado")
    ordering = "-iniciada_en"


class EvaluacionDetailView(BaseDetailView):
    model = Evaluacion
    to_dict = staticmethod(s.evaluacion_to_dict)
    fields = ("estudiante", "cuestionario", "estado", "finalizada_en")


class RespuestaListView(BaseListView):
    model = Respuesta
    to_dict = staticmethod(s.respuesta_to_dict)
    fields = ("evaluacion", "pregunta")
    ordering = "id"


class RespuestaDetailView(BaseDetailView):
    model = Respuesta
    to_dict = staticmethod(s.respuesta_to_dict)
    fields = ("evaluacion", "pregunta")


class SeleccionListView(BaseListView):
    model = SeleccionRespuesta
    to_dict = staticmethod(s.seleccion_to_dict)
    fields = ("respuesta", "opcion")
    ordering = "id"


class SeleccionDetailView(BaseDetailView):
    model = SeleccionRespuesta
    to_dict = staticmethod(s.seleccion_to_dict)
    fields = ("respuesta", "opcion")


# =====================================================================
# results
# =====================================================================

class ResultadoListView(BaseListView):
    model = Resultado
    to_dict = staticmethod(s.resultado_to_dict)
    fields = (
        "evaluacion",
        "preguntas_contestadas",
        "preguntas_omitidas",
        "interpretacion",
    )
    ordering = "-calculado_en"


class ResultadoDetailView(BaseDetailView):
    model = Resultado
    to_dict = staticmethod(s.resultado_to_dict)
    fields = (
        "preguntas_contestadas",
        "preguntas_omitidas",
        "interpretacion",
    )


class PuntajeListView(BaseListView):
    model = PuntajeDimension
    to_dict = staticmethod(s.puntaje_to_dict)
    fields = ("resultado", "dimension", "puntaje")
    ordering = "dimension"


class PuntajeDetailView(BaseDetailView):
    model = PuntajeDimension
    to_dict = staticmethod(s.puntaje_to_dict)
    fields = ("dimension", "puntaje")