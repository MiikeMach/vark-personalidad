from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import Truncator

from apps.dashboard.admin_actions import DashboardAdminMixin, insignia
from .models import Evaluacion, Respuesta, SeleccionRespuesta


def nombre_estudiante(estudiante):
    return f"{estudiante.nombres} {estudiante.apellidos} ({estudiante.matricula})"


@admin.register(Evaluacion)
class EvaluacionAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("folio", "estudiante_nombre", "cuestionario", "estado_insignia", "iniciada_en", "finalizada_en", "ver_resultado")
    list_display_links = ("folio", "estudiante_nombre")
    list_filter = ("estado", "cuestionario")
    search_fields = ("estudiante__matricula", "estudiante__nombres", "estudiante__apellidos")
    ordering = ("-iniciada_en",)
    list_select_related = ("estudiante", "cuestionario", "resultado")
    readonly_fields = ("iniciada_en",)
    fieldsets = (
        ("Evaluación", {"fields": ("estudiante", "cuestionario")}),
        ("Seguimiento", {
            "fields": ("estado", "iniciada_en", "finalizada_en"),
            "description": "La fecha de inicio se registra automáticamente.",
        }),
    )

    @admin.display(description="Folio", ordering="id")
    def folio(self, evaluacion):
        return f"#{evaluacion.pk}"

    @admin.display(description="Estudiante", ordering="estudiante__apellidos")
    def estudiante_nombre(self, evaluacion):
        return nombre_estudiante(evaluacion.estudiante)

    @admin.display(description="Estado", ordering="estado")
    def estado_insignia(self, evaluacion):
        tono = "ok" if evaluacion.estado == Evaluacion.Estado.FINALIZADA else "warn"
        return insignia(evaluacion.get_estado_display(), tono)

    @admin.display(description="Resultado")
    def ver_resultado(self, evaluacion):
        resultado = getattr(evaluacion, "resultado", None)
        if resultado is None:
            return "—"
        url = reverse(f"{self.admin_site.name}:results_resultado_change", args=[resultado.pk])
        return format_html('<a class="bru-row-edit" href="{}">Ver resultado</a>', url)


@admin.register(Respuesta)
class RespuestaAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("estudiante", "cuestionario", "pregunta_corta")
    list_filter = ("pregunta__cuestionario",)
    search_fields = ("evaluacion__estudiante__nombres", "evaluacion__estudiante__apellidos", "pregunta__texto")
    list_select_related = ("evaluacion__estudiante", "pregunta__cuestionario")
    fieldsets = (("Respuesta", {"fields": ("evaluacion", "pregunta")}),)

    @admin.display(description="Estudiante", ordering="evaluacion__estudiante__apellidos")
    def estudiante(self, respuesta):
        return nombre_estudiante(respuesta.evaluacion.estudiante)

    @admin.display(description="Cuestionario", ordering="pregunta__cuestionario__titulo")
    def cuestionario(self, respuesta):
        return respuesta.pregunta.cuestionario.titulo

    @admin.display(description="Pregunta", ordering="pregunta__orden")
    def pregunta_corta(self, respuesta):
        return f"{respuesta.pregunta.orden}. {Truncator(respuesta.pregunta.texto).chars(80)}"


@admin.register(SeleccionRespuesta)
class SeleccionRespuestaAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("id", "respuesta", "opcion")
    search_fields = ("respuesta__evaluacion__estudiante__nombres", "opcion__texto")
    list_select_related = (
        "respuesta__evaluacion__estudiante", "respuesta__pregunta__cuestionario", "opcion",
    )
    fieldsets = (
        ("Opción seleccionada", {
            "fields": ("respuesta", "opcion", "puntos"),
            "description": "Los puntos solo se usan en preguntas con escala; déjalos vacíos si no aplica.",
        }),
    )
