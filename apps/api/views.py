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

    ordering = ("apellidos", "nombres")

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
    ordering = ("tipo", "titulo")

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


def filtrar_resultados(request):
    """Filtros compartidos por ResultadoListView y el endpoint PDF (#8, #14).

    Devuelve (qs, error_response). error_response es None si todo OK.
    """
    qs = (
        Resultado.objects
        .select_related(
            "evaluacion__estudiante__grupo",
            "evaluacion__cuestionario",
        )
        .prefetch_related("puntajes")
    )

    evaluacion = _int_param(request, "evaluacion")
    if evaluacion is not None:
        qs = qs.filter(evaluacion_id=evaluacion)

    estudiante = _int_param(request, "estudiante")
    if estudiante is not None:
        qs = qs.filter(evaluacion__estudiante_id=estudiante)

    grupo = _int_param(request, "grupo")
    if grupo is not None:
        qs = qs.filter(evaluacion__estudiante__grupo_id=grupo)

    cuestionario = _int_param(request, "cuestionario")
    if cuestionario is not None:
        qs = qs.filter(evaluacion__cuestionario_id=cuestionario)

    tipo = _str_param(request, "tipo")
    if tipo:
        qs = qs.filter(evaluacion__cuestionario__tipo__iexact=tipo)

    q = _str_param(request, "q")
    if q:
        qs = qs.filter(
            Q(evaluacion__estudiante__matricula__icontains=q)
            | Q(evaluacion__estudiante__nombres__icontains=q)
            | Q(evaluacion__estudiante__apellidos__icontains=q)
            | Q(evaluacion__estudiante__grupo__clave__icontains=q)
            | Q(evaluacion__estudiante__grupo__nombre__icontains=q)
        )

    alcance = _str_param(request, "alcance")
    if alcance is not None and alcance not in ("individual", "grupal", "total"):
        return None, _json_error(
            "Parámetro 'alcance' inválido (individual|grupal|total)."
        )
    if alcance == "individual" and estudiante is None and not q:
        return qs.none(), None
    if alcance == "grupal" and grupo is None and not q:
        return qs.none(), None

    return qs, None
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


    def get(self, request, *args, **kwargs):
        alcance = _str_param(request, "alcance")
        if alcance is not None and alcance not in ("individual", "grupal", "total"):
            return _json_error(
                "Parámetro 'alcance' inválido (individual|grupal|total)."
            )
        return super().get(request, *args, **kwargs)

    def get_queryset(self, request):
        qs, error = filtrar_resultados(request)
        if error is not None:
            return Resultado.objects.none()
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

        except ValidationError as e:
            return _json_error(e.messages[0], status=400)
        except Exception as e:
            return _json_error("Error interno al calcular la evaluación.", status=500)


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
    """POST /api/evaluaciones/{id}/responder/.

    VARK: {"respuestas": [{"pregunta": 1, "opciones": [2, 3]}], "calcular": true}
    Personalidad: {"respuestas": [{"pregunta": 1, "selecciones":
      [{"opcion": 2, "puntos": 7}, {"opcion": 3, "puntos": 3}]}], "calcular": true}

    Por seguridad esta ruta es administrativa hasta definir propiedad de
    evaluaciones para cuentas de estudiantes.
    """

    @require_staff
    def post(self, request, pk, *args, **kwargs):
        try:
            body = _payload(request)
        except ValidationError as exc:
            return _json_error(exc.messages[0])
        if not isinstance(body, dict):
            return _json_error("El cuerpo JSON debe ser un objeto.")

        items = body.get("respuestas")
        if not isinstance(items, list):
            return _json_error("'respuestas' debe ser una lista.")
        calcular = body.get("calcular", False)
        if type(calcular) is not bool:
            return _json_error("'calcular' debe ser booleano.")

        try:
            with transaction.atomic():
                evaluacion = get_object_or_404(
                    Evaluacion.objects.select_for_update().select_related("cuestionario"),
                    pk=pk,
                )
                from apps.assessments.services import (
                    guardar_respuesta,
                    guardar_respuesta_personalidad,
                )
                from apps.results.services import finalizar_evaluacion

                if evaluacion.estado != Evaluacion.Estado.EN_PROGRESO:
                    raise ValidationError("La evaluación ya está finalizada.")

                preguntas_vistas = set()
                guardadas = 0
                omitidas = 0
                for indice, item in enumerate(items):
                    if not isinstance(item, dict):
                        raise ValidationError(f"Item {indice}: debe ser un objeto.")
                    pregunta = item.get("pregunta")
                    if type(pregunta) is not int:
                        raise ValidationError(f"Item {indice}: pregunta inválida.")
                    if pregunta in preguntas_vistas:
                        raise ValidationError(f"Item {indice}: pregunta duplicada.")
                    preguntas_vistas.add(pregunta)

                    if evaluacion.cuestionario.tipo == Cuestionario.Tipo.VARK:
                        if "selecciones" in item:
                            raise ValidationError("VARK utiliza 'opciones', no 'selecciones'.")
                        opciones = item.get("opciones", [])
                        guardar_respuesta(evaluacion.pk, pregunta, opciones)
                        if opciones:
                            guardadas += 1
                        else:
                            omitidas += 1
                    elif evaluacion.cuestionario.tipo == Cuestionario.Tipo.PERSONALIDAD:
                        selecciones = item.get("selecciones")
                        if not isinstance(selecciones, list) or len(selecciones) != 2:
                            raise ValidationError(
                                "Personalidad requiere exactamente dos selecciones con puntos."
                            )
                        if any(not isinstance(s, dict) for s in selecciones):
                            raise ValidationError("Selección de personalidad inválida.")
                        uno, dos = selecciones
                        if type(uno.get("opcion")) is not int or type(dos.get("opcion")) is not int:
                            raise ValidationError("Los identificadores de opción deben ser enteros.")
                        guardar_respuesta_personalidad(
                            evaluacion.pk, pregunta,
                            uno["opcion"], uno.get("puntos"),
                            dos["opcion"], dos.get("puntos"),
                        )
                        guardadas += 1
                    else:
                        raise ValidationError("Tipo de cuestionario no compatible.")

                resultado_payload = None
                if calcular:
                    resultado = finalizar_evaluacion(evaluacion.pk)
                    resultado_payload = s.resultado_con_puntajes_to_dict(resultado)
                    evaluacion.refresh_from_db()

        except ValidationError as exc:
            return _json_error(exc.messages[0] if hasattr(exc, "messages") else str(exc), status=400)
        except IntegrityError as exc:
            return _json_error(str(exc), status=409)

        return JsonResponse({
            "evaluacion": s.evaluacion_to_dict(evaluacion),
            "guardadas": guardadas,
            "omitidas": omitidas,
            "resultado": resultado_payload,
        })

# =====================================================================
# agregaciones / dashboards (#4, #7, #15)
# =====================================================================

from apps.api.aggregations import agregar_resultados


def _validar_alcance_tipo(request):
    alcance = _str_param(request, "alcance")
    tipo = _str_param(request, "tipo")
    if alcance not in ("individual", "grupal", "total"):
        return None, None, _json_error(
            "Parámetro 'alcance' inválido (individual|grupal|total)."
        )
    if tipo not in ("VARK", "PERSONALIDAD"):
        return None, None, _json_error(
            "Parámetro 'tipo' inválido (VARK|PERSONALIDAD)."
        )
    return alcance, tipo, None


def _resultados_filtrados(request, alcance, tipo):
    """Devuelve (qs, error_response)."""
    qs = (
        Resultado.objects
        .select_related("evaluacion__cuestionario", "evaluacion__estudiante")
        .filter(evaluacion__cuestionario__tipo=tipo)
    )

    cuestionario = _int_param(request, "cuestionario")
    if cuestionario is not None:
        if not Cuestionario.objects.filter(pk=cuestionario).exists():
            return None, _json_error("Cuestionario no encontrado.", status=404)
        qs = qs.filter(evaluacion__cuestionario_id=cuestionario)

    if alcance == "individual":
        estudiante = _int_param(request, "estudiante")
        if estudiante is None:
            return None, _json_error(
                "Parámetro 'estudiante' requerido para alcance=individual."
            )
        if not Estudiante.objects.filter(pk=estudiante).exists():
            return None, _json_error("Estudiante no encontrado.", status=404)
        qs = qs.filter(evaluacion__estudiante_id=estudiante)

    elif alcance == "grupal":
        grupo = _int_param(request, "grupo")
        if grupo is None:
            return None, _json_error(
                "Parámetro 'grupo' requerido para alcance=grupal."
            )
        if not Grupo.objects.filter(pk=grupo).exists():
            return None, _json_error("Grupo no encontrado.", status=404)
        qs = qs.filter(evaluacion__estudiante__grupo_id=grupo)

    # alcance == "total": sin filtro adicional

    return qs, None


@method_decorator(csrf_exempt, name="dispatch")
class ResultadoAgregadosView(View):
    """GET /api/resultados/agregados/?alcance=…&tipo=…[&estudiante|grupo|cuestionario]"""

    def get(self, request, *args, **kwargs):
        alcance, tipo, error = _validar_alcance_tipo(request)
        if error is not None:
            return error
        qs, error = _resultados_filtrados(request, alcance, tipo)
        if error is not None:
            return error
        return JsonResponse(agregar_resultados(qs, alcance, tipo))


@method_decorator(csrf_exempt, name="dispatch")
class DashboardGrupalView(View):
    """GET /api/dashboard/grupal/?grupo=…&tipo=… (alias de agregados/grupal)"""

    def get(self, request, *args, **kwargs):
        alcance = "grupal"
        tipo = _str_param(request, "tipo")
        if tipo not in ("VARK", "PERSONALIDAD"):
            return _json_error("Parámetro 'tipo' inválido (VARK|PERSONALIDAD).")
        qs, error = _resultados_filtrados(request, alcance, tipo)
        if error is not None:
            return error
        return JsonResponse(agregar_resultados(qs, alcance, tipo))

# =====================================================================
# #8: búsqueda de alumnos y grupos para autocompletado
# =====================================================================

@method_decorator(csrf_exempt, name="dispatch")
class BuscarView(View):
    """GET /api/buscar/?q=...  → estudiantes y grupos que coinciden.

    Público. Requiere q con al menos 2 caracteres.
    """

    LIMITE = 20
    MIN_LEN = 2

    def get(self, request, *args, **kwargs):
        q = _str_param(request, "q")
        if not q or len(q) < self.MIN_LEN:
            return _json_error(
                f"Parámetro 'q' requerido (mínimo {self.MIN_LEN} caracteres)."
            )

        estudiantes_qs = (
            Estudiante.objects
            .filter(
                Q(matricula__icontains=q)
                | Q(nombres__icontains=q)
                | Q(apellidos__icontains=q)
            )
            .order_by("apellidos", "nombres")[: self.LIMITE]
        )
        grupos_qs = (
            Grupo.objects
            .filter(
                Q(clave__icontains=q)
                | Q(nombre__icontains=q)
            )
            .order_by("nombre")[: self.LIMITE]
        )

        return JsonResponse({
            "q": q,
            "estudiantes": [s.estudiante_to_dict(e) for e in estudiantes_qs],
            "grupos": [s.grupo_to_dict(g) for g in grupos_qs],
        })

# =====================================================================
# #14: PDF de ficha técnica (individual / grupal / total)
# =====================================================================

from django.http import HttpResponse
from apps.api.pdf import construir_pdf_individual, construir_pdf_multiple


@method_decorator(csrf_exempt, name="dispatch")
class ResultadoPdfView(View):
    """GET /api/resultados/{pk}/pdf/  → ficha individual."""

    def get(self, request, pk, *args, **kwargs):
        resultado = get_object_or_404(
            Resultado.objects
            .select_related(
                "evaluacion__estudiante__grupo",
                "evaluacion__cuestionario",
            )
            .prefetch_related("puntajes"),
            pk=pk,
        )
        contenido = construir_pdf_individual(resultado)
        response = HttpResponse(contenido, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="ficha_resultado_{resultado.id}.pdf"'
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class ResultadosPdfView(View):
    """GET /api/resultados/pdf/?…  → portada agregada + fichas individuales.

    Acepta los mismos parámetros que ResultadoListView (q, alcance, grupo,
    estudiante, tipo, cuestionario).
    """

    def get(self, request, *args, **kwargs):
        qs, error = filtrar_resultados(request)
        if error is not None:
            return error

        alcance = _str_param(request, "alcance") or "total"
        tipo = _str_param(request, "tipo") or ""
        if not tipo:
            # Si no se especifica tipo, inferimos del primer resultado, o
            # exigimos el parámetro para no mezclar VARK con personalidad.
            primero = qs.first()
            if primero is not None:
                tipo = primero.evaluacion.cuestionario.tipo
            else:
                return _json_error(
                    "Parámetro 'tipo' requerido (VARK|PERSONALIDAD) cuando no hay resultados."
                )
        if tipo not in ("VARK", "PERSONALIDAD"):
            return _json_error("Parámetro 'tipo' inválido (VARK|PERSONALIDAD).")

        # Si el qs mezclara tipos (no debería, por el filtro), lo restringimos.
        qs = qs.filter(evaluacion__cuestionario__tipo=tipo)

        contenido = construir_pdf_multiple(qs, alcance, tipo)

        partes = ["ficha", alcance, tipo.lower()]
        grupo = _int_param(request, "grupo")
        if grupo is not None:
            partes.append(f"grupo{grupo}")
        nombre = "_".join(partes) + ".pdf"

        response = HttpResponse(contenido, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return response

# =====================================================================
# #11: formulario de contacto por correo
# =====================================================================

import logging

from django.core.mail import send_mail
from django.core.validators import validate_email
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)


def _validar_contacto(body):
    """Devuelve (datos, errores). errores es {} si todo OK."""
    errores = {}

    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        errores["nombre"] = ["Este campo es obligatorio."]
    elif len(nombre) > 100:
        errores["nombre"] = ["Máximo 100 caracteres."]

    correo = (body.get("correo") or "").strip()
    if not correo:
        errores["correo"] = ["Este campo es obligatorio."]
    else:
        try:
            validate_email(correo)
        except Exception:
            errores["correo"] = ["Introduce una dirección de correo válida."]

    asunto = (body.get("asunto") or "").strip()
    if not asunto:
        errores["asunto"] = ["Este campo es obligatorio."]
    elif len(asunto) > 150:
        errores["asunto"] = ["Máximo 150 caracteres."]

    mensaje = (body.get("mensaje") or "").strip()
    if not mensaje:
        errores["mensaje"] = ["Este campo es obligatorio."]
    elif len(mensaje) < 10:
        errores["mensaje"] = ["Mínimo 10 caracteres."]
    elif len(mensaje) > 5000:
        errores["mensaje"] = ["Máximo 5000 caracteres."]

    if errores:
        return None, errores
    return {
        "nombre": nombre,
        "correo": correo,
        "asunto": asunto,
        "mensaje": mensaje,
    }, {}


@method_decorator(csrf_exempt, name="dispatch")
class ContactoView(View):
    """POST /api/contacto/  → envía un correo de contacto.

    Público. No persiste en BD (sin modelo). En desarrollo el correo se
    imprime en consola (console.EmailBackend); en producción se configura
    SMTP vía variables de entorno.
    """

    def post(self, request, *args, **kwargs):
        try:
            body = _payload(request)
        except ValidationError as e:
            return _json_error(e.messages[0])

        datos, errores = _validar_contacto(body)
        if errores:
            return _json_error(errores)

        asunto = f"[Contacto VARK] {datos['asunto']}"
        cuerpo = (
            f"Nombre: {datos['nombre']}\n"
            f"Correo: {datos['correo']}\n\n"
            f"{datos['mensaje']}\n"
        )

        try:
            send_mail(
                subject=asunto,
                message=cuerpo,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[django_settings.CONTACT_EMAIL],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Fallo al enviar correo de contacto.")
            return _json_error(
                "No se pudo enviar el mensaje. Intenta más tarde.",
                status=500,
            )

        return JsonResponse(
            {"detail": "Mensaje enviado correctamente."},
            status=201,
        )