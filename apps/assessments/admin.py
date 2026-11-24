from django.contrib import admin
from apps.dashboard.admin_actions import DashboardAdminMixin
from .models import Evaluacion, Respuesta, SeleccionRespuesta


@admin.register(Evaluacion)
class EvaluacionAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("id", "estudiante", "cuestionario", "estado", "iniciada_en", "finalizada_en")
    list_filter = ("estado", "cuestionario")
    search_fields = ("estudiante__matricula", "estudiante__nombres", "estudiante__apellidos")
    ordering = ("-iniciada_en",)


@admin.register(Respuesta)
class RespuestaAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("id", "evaluacion", "pregunta")
    list_filter = ("pregunta__cuestionario",)
    search_fields = ("evaluacion__estudiante__nombres", "evaluacion__estudiante__apellidos", "pregunta__texto")


@admin.register(SeleccionRespuesta)
class SeleccionRespuestaAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("id", "respuesta", "opcion")
    search_fields = ("respuesta__evaluacion__estudiante__nombres", "opcion__texto")
