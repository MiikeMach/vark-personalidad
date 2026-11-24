"""Endpoints CRUD básicos (View de Django + JsonResponse) con auth por sesión."""

import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Prefetch
from django.contrib.auth import authenticate, login, logout

from apps.students.models import Grupo, Estudiante
from apps.questionnaires.models import Cuestionario, Pregunta, Opcion
from apps.assessments.models import Evaluacion, Respuesta, SeleccionRespuesta
from apps.results.models import Resultado, PuntajeDimension

from . import serializers as s
from .auth import require_staff, user_to_dict


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


def _bool_param(request, name):
    raw = request.GET.get(name)
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes", "y", "t")


def _int_param(request, name):
    raw = request.GET.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _str_param(request, name):
    raw = request.GET.get(name)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip()


# =====================================================================
# Auth (login/logout/me)
# =====================================================================

@method_decorator(csrf_exempt, name="dispatch")
class LoginView(View):
    """POST /api/auth/login/  {"username": "...", "password": "..."}"""

    def post(self, request, *args, **kwargs):
        try:
            body = _payload(request)
        except ValidationError as e:
            return _json_error(e.messages[0])
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        if not username or not password:
            return _json_error("username y password son obligatorios.")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return _json_error("Credenciales inválidas.", status=401)
        if not user.is_active:
            return _json_error("Usuario inactivo.", status=403)
        login(request, user)
        return JsonResponse({"user": user_to_dict(user)})


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(View):
    """POST /api/auth/logout/"""

    def post(self, request, *args, **kwargs):
        logout(request)
        return JsonResponse({"detail": "Sesión cerrada."})


@method_decorator(csrf_exempt, name="dispatch")
class MeView(View):
    """GET /api/auth/me/"""

    def get(self, request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return JsonResponse({"user": None}, status=401)
        return JsonResponse({"user": user_to_dict(request.user)})


# =====================================================================
# Base genérica
# =====================================================================

@method_decorator(csrf_exempt, name="dispatch")
class BaseListView(View):
    """
    GET  -> lista (público, con filtros)
    POST -> crea (solo staff)
    """
    model = None
    to_dict = None
    fields = ()
    ordering = None

    def get_queryset(self, request):
        qs = self.model.objects.all()
        if self.ordering:
            if isinstance(self.ordering, (tuple, list)):
                qs = qs.order_by(*self.ordering)
            else:
                qs = qs.order_by(self.ordering)
        return qs

    def get(self, request, *args, **kwargs):
        qs = self.get_queryset(request)
        data = [self.to_dict(o) for o in qs]
        return JsonResponse(data, safe=False)

    @require_staff
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
    GET    -> detalle (público)
    PUT    -> actualiza (staff)
    PATCH  -> actualiza parcial (staff)
    DELETE -> elimina (staff)
    """
    model = None
    to_dict = None
    fields = ()

    def _get(self, pk):
        return get_object_or_404(self.model, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        return JsonResponse(self.to_dict(self._get(pk)))

    @require_staff
    def put(self, request, pk, *args, **kwargs):
        return self._update(request, pk, partial=False)

    @require_staff
    def patch(self, request, pk, *args, **kwargs):
        return self._update(request, pk, partial=True)

    @require_staff
    def delete(self, request, pk, *args, **kwargs):
        obj = self._get(pk)
        try:
            obj.delete()
        except IntegrityError as e:
            return _json_error(str(e), status=409)
        return JsonResponse({}, status=204)

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


# =====================================================================
# students
# =====================================================================

class GrupoListView(BaseListView):
    model = Grupo
    to_dict = staticmethod(s.grupo_to_dict)
    fields = ("clave", "nombre", "activo")
    ordering = "nombre"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        activo = _bool_param(request, "activo")
        if activo is not None:
            qs = qs.filter(activo=activo)
        q = _str_param(request, "q")
        if q:
            qs = qs.filter(Q(clave__icontains=q) | Q(nombre__icontains=q))
        return qs


class GrupoDetailView(BaseDetailView):
    model = Grupo
    to_dict = staticmethod(s.grupo_to_dict)
    fields = ("clave", "nombre", "activo")


class EstudianteListView(BaseListView):
    model = Estudiante
    to_dict = staticmethod(s.estudiante_to_dict)
    fields = ("matricula", "nombres", "apellidos", "correo", "grupo", "activo")
    ordering = "apellidos", "nombres"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        grupo = _int_param(request, "grupo")
        if grupo is not None:
            qs = qs.filter(grupo_id=grupo)
        activo = _bool_param(request, "activo")
        if activo is not None:
            qs = qs.filter(activo=activo)
        q = _str_param(request, "q")
        if q:
            qs = qs.filter(
                Q(matricula__icontains=q)
                | Q(nombres__icontains=q)
                | Q(apellidos__icontains=q)
                | Q(correo__icontains=q)
            )
        return qs


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
    ordering = "tipo", "titulo"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        tipo = _str_param(request, "tipo")
        if tipo:
            qs = qs.filter(tipo__iexact=tipo)
        activo = _bool_param(request, "activo")
        if activo is not None:
            qs = qs.filter(activo=activo)
        q = _str_param(request, "q")
        if q:
            qs = qs.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q))
        return qs


class CuestionarioDetailView(BaseDetailView):
    model = Cuestionario
    to_dict = staticmethod(s.cuestionario_to_dict)
    fields = ("titulo", "descripcion", "instrucciones", "tipo", "activo")


class PreguntaListView(BaseListView):
    model = Pregunta
    to_dict = staticmethod(s.pregunta_to_dict)
    fields = ("cuestionario", "texto", "orden")
    ordering = "orden"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        cuestionario = _int_param(request, "cuestionario")
        if cuestionario is not None:
            qs = qs.filter(cuestionario_id=cuestionario)
        return qs


class PreguntaDetailView(BaseDetailView):
    model = Pregunta
    to_dict = staticmethod(s.pregunta_to_dict)
    fields = ("cuestionario", "texto", "orden")


class OpcionListView(BaseListView):
    model = Opcion
    to_dict = staticmethod(s.opcion_to_dict)
    fields = ("pregunta", "texto", "dimension", "orden")
    ordering = "orden"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        pregunta = _int_param(request, "pregunta")
        if pregunta is not None:
            qs = qs.filter(pregunta_id=pregunta)
        dimension = _str_param(request, "dimension")
        if dimension:
            qs = qs.filter(dimension__iexact=dimension)
        return qs


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        estudiante = _int_param(request, "estudiante")
        if estudiante is not None:
            qs = qs.filter(estudiante_id=estudiante)
        grupo = _int_param(request, "grupo")
        if grupo is not None:
            qs = qs.filter(estudiante__grupo_id=grupo)
        cuestionario = _int_param(request, "cuestionario")
        if cuestionario is not None:
            qs = qs.filter(cuestionario_id=cuestionario)
        tipo = _str_param(request, "tipo")
        if tipo:
            qs = qs.filter(cuestionario__tipo__iexact=tipo)
        estado = _str_param(request, "estado")
        if estado:
            qs = qs.filter(estado__iexact=estado)
        return qs


class EvaluacionDetailView(BaseDetailView):
    model = Evaluacion
    to_dict = staticmethod(s.evaluacion_to_dict)
    fields = ("estudiante", "cuestionario", "estado", "finalizada_en")


class RespuestaListView(BaseListView):
    model = Respuesta
    to_dict = staticmethod(s.respuesta_to_dict)
    fields = ("evaluacion", "pregunta")
    ordering = "id"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        evaluacion = _int_param(request, "evaluacion")
        if evaluacion is not None:
            qs = qs.filter(evaluacion_id=evaluacion)
        pregunta = _int_param(request, "pregunta")
        if pregunta is not None:
            qs = qs.filter(pregunta_id=pregunta)
        return qs


class RespuestaDetailView(BaseDetailView):
    model = Respuesta
    to_dict = staticmethod(s.respuesta_to_dict)
    fields = ("evaluacion", "pregunta")


class SeleccionListView(BaseListView):
    model = SeleccionRespuesta
    to_dict = staticmethod(s.seleccion_to_dict)
    fields = ("respuesta", "opcion")
    ordering = "id"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        respuesta = _int_param(request, "respuesta")
        if respuesta is not None:
            qs = qs.filter(respuesta_id=respuesta)
        opcion = _int_param(request, "opcion")
        if opcion is not None:
            qs = qs.filter(opcion_id=opcion)
        return qs


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        evaluacion = _int_param(request, "evaluacion")
        if evaluacion is not None:
            qs = qs.filter(evaluacion_id=evaluacion)
        estudiante = _int_param(request, "estudiante")
        if estudiante is not None:
            qs = qs.filter(evaluacion__estudiante_id=estudiante)
        grupo = _int_param(request, "grupo")
        if grupo is not None:
            qs = qs.filter(evaluacion__estudiante__grupo_id=grupo)
        tipo = _str_param(request, "tipo")
        if tipo:
            qs = qs.filter(evaluacion__cuestionario__tipo__iexact=tipo)
        return qs


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        resultado = _int_param(request, "resultado")
        if resultado is not None:
            qs = qs.filter(resultado_id=resultado)
        dimension = _str_param(request, "dimension")
        if dimension:
            qs = qs.filter(dimension__iexact=dimension)
        return qs


class PuntajeDetailView(BaseDetailView):
    model = PuntajeDimension
    to_dict = staticmethod(s.puntaje_to_dict)
    fields = ("dimension", "puntaje")

# =====================================================================
# acciones: cálculo de resultados
# =====================================================================

from apps.scoring.service import ScoringService


@method_decorator(csrf_exempt, name="dispatch")
class EvaluacionCalcularView(View):
    """
    POST /api/evaluaciones/{id}/calcular/
    Body opcional: {"interpretacion": "texto manual"}
    """

    @require_staff
    def post(self, request, pk, *args, **kwargs):
        evaluacion = get_object_or_404(Evaluacion, pk=pk)
        try:
            body = _payload(request)
        except ValidationError as e:
            return _json_error(e.messages[0])
        interpretacion = body.get("interpretacion", "") or ""
        try:
            resultado = ScoringService.instance().calculate(
                evaluacion, interpretacion=interpretacion
            )
        except Exception as e:
            return _json_error(f"Error al calcular: {e}", status=500)
        return JsonResponse(s.resultado_con_puntajes_to_dict(resultado))

# =====================================================================
# acciones: cuestionario completo + iniciar evaluación
# =====================================================================

@method_decorator(csrf_exempt, name="dispatch")
class CuestionarioCompletoView(View):
    """GET /api/cuestionarios/{id}/completo/  (público)"""

    def get(self, request, pk, *args, **kwargs):
        cuestionario = get_object_or_404(
            Cuestionario.objects.prefetch_related(
                Prefetch(
                    "preguntas",
                    queryset=Pregunta.objects.prefetch_related("opciones"),
                )
            ),
            pk=pk,
        )
        return JsonResponse(s.cuestionario_completo_to_dict(cuestionario))


@method_decorator(csrf_exempt, name="dispatch")
class EvaluacionIniciarView(View):
    """
    POST /api/evaluaciones/iniciar/
    Body: {"estudiante": <id>, "cuestionario": <id>}
    Requiere autenticación (cualquier usuario activo en esta fase).
    """

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Autenticación requerida."}, status=401
            )

        try:
            body = _payload(request)
        except ValidationError as e:
            return _json_error(e.messages[0])

        estudiante_id = body.get("estudiante")
        cuestionario_id = body.get("cuestionario")
        if estudiante_id is None or cuestionario_id is None:
            return _json_error("estudiante y cuestionario son obligatorios.")

        estudiante = Estudiante.objects.filter(pk=estudiante_id).first()
        if estudiante is None:
            return _json_error("Estudiante no encontrado.", status=404)

        cuestionario = Cuestionario.objects.filter(pk=cuestionario_id).first()
        if cuestionario is None:
            return _json_error("Cuestionario no encontrado.", status=404)
        if not cuestionario.activo:
            return _json_error("El cuestionario no está activo.")

        # Reutilizar evaluación en progreso si existe (idempotente)
        evaluacion = (
            Evaluacion.objects
            .filter(
                estudiante=estudiante,
                cuestionario=cuestionario,
                estado=Evaluacion.Estado.EN_PROGRESO,
            )
            .order_by("-iniciada_en")
            .first()
        )
        created = False
        if evaluacion is None:
            try:
                with transaction.atomic():
                    evaluacion = Evaluacion.objects.create(
                        estudiante=estudiante,
                        cuestionario=cuestionario,
                        estado=Evaluacion.Estado.EN_PROGRESO,
                    )
                created = True
            except (ValidationError, IntegrityError) as e:
                return _json_error(str(e), status=400)

        # Releer el cuestionario con anidamiento optimizado
        cuestionario_full = get_object_or_404(
            Cuestionario.objects.prefetch_related(
                Prefetch(
                    "preguntas",
                    queryset=Pregunta.objects.prefetch_related("opciones"),
                )
            ),
            pk=cuestionario.pk,
        )

        payload = {
            "evaluacion": s.evaluacion_to_dict(evaluacion),
            "cuestionario": s.cuestionario_completo_to_dict(cuestionario_full),
        }
        return JsonResponse(payload, status=201 if created else 200)

# =====================================================================
# acciones: envío bulk de respuestas
# =====================================================================

@method_decorator(csrf_exempt, name="dispatch")
class EvaluacionResponderView(View):
    """
    POST /api/evaluaciones/{id}/responder/
    Body:
      {
        "respuestas": [
          {"pregunta": 10, "opciones": [40, 41]},
          ...
        ],
        "calcular": false
      }
    """

    def post(self, request, pk, *args, **kwargs):
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Autenticación requerida."}, status=401
            )

        evaluacion = Evaluacion.objects.filter(pk=pk).first()
        if evaluacion is None:
            return _json_error("Evaluación no encontrada.", status=404)
        if evaluacion.estado != Evaluacion.Estado.EN_PROGRESO:
            return _json_error(
                "La evaluación ya está finalizada.", status=409
            )

        try:
            body = _payload(request)
        except ValidationError as e:
            return _json_error(e.messages[0])

        items = body.get("respuestas")
        if not isinstance(items, list):
            return _json_error("'respuestas' debe ser una lista.")
        calcular = bool(body.get("calcular", False))

        # -------- validación previa (sin escribir nada) --------
        cuestionario = evaluacion.cuestionario
        preguntas_ids = set(
            cuestionario.preguntas.values_list("id", flat=True)
        )
        vistos = set()
        errores = []
        plan = []  # [(pregunta_id, [opcion_ids])]

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                errores.append(f"Item {idx}: debe ser un objeto.")
                continue
            pregunta_id = item.get("pregunta")
            opciones = item.get("opciones", [])
            if not isinstance(pregunta_id, int):
                errores.append(f"Item {idx}: 'pregunta' debe ser entero.")
                continue
            if pregunta_id not in preguntas_ids:
                errores.append(
                    f"Item {idx}: pregunta {pregunta_id} no pertenece al cuestionario."
                )
                continue
            if pregunta_id in vistos:
                errores.append(f"Item {idx}: pregunta {pregunta_id} duplicada.")
                continue
            vistos.add(pregunta_id)
            if not isinstance(opciones, list):
                errores.append(f"Item {idx}: 'opciones' debe ser lista.")
                continue
            opciones_int = []
            for o in opciones:
                if not isinstance(o, int):
                    errores.append(
                        f"Item {idx}: opción {o!r} no es entero."
                    )
                    break
                opciones_int.append(o)
            else:
                plan.append((pregunta_id, opciones_int))

        # Validar que cada opción pertenezca a su pregunta
        if not errores and plan:
            pares = [(pid, oid) for pid, oids in plan for oid in oids]
            if pares:
                opciones_validas = set(
                    Opcion.objects
                    .filter(pregunta_id__in=[p for p, _ in pares])
                    .values_list("pregunta_id", "id")
                )
                for pid, oid in pares:
                    if (pid, oid) not in opciones_validas:
                        errores.append(
                            f"Opción {oid} no pertenece a la pregunta {pid}."
                        )

        if errores:
            return JsonResponse({"detail": errores}, status=400)

        # -------- escritura transaccional --------
        guardadas = 0
        omitidas = 0
        try:
            with transaction.atomic():
                for pregunta_id, opcion_ids in plan:
                    respuesta, _ = Respuesta.objects.update_or_create(
                        evaluacion=evaluacion,
                        pregunta_id=pregunta_id,
                        defaults={},
                    )
                    # reemplazar selecciones
                    SeleccionRespuesta.objects.filter(
                        respuesta=respuesta
                    ).delete()
                    if opcion_ids:
                        SeleccionRespuesta.objects.bulk_create(
                            [
                                SeleccionRespuesta(
                                    respuesta=respuesta,
                                    opcion_id=oid,
                                )
                                for oid in opcion_ids
                            ]
                        )
                        guardadas += 1
                    else:
                        omitidas += 1
        except IntegrityError as e:
            return _json_error(str(e), status=409)

        resultado_payload = None
        if calcular:
            try:
                resultado = ScoringService.instance().calculate(evaluacion)
                resultado_payload = s.resultado_con_puntajes_to_dict(resultado)
            except Exception as e:
                return _json_error(f"Error al calcular: {e}", status=500)

        return JsonResponse(
            {
                "evaluacion": s.evaluacion_to_dict(evaluacion),
                "guardadas": guardadas,
                "omitidas": omitidas,
                "resultado": resultado_payload,
            }
        )