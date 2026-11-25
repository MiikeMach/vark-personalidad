from django.contrib import admin
from apps.dashboard.admin_actions import DashboardAdminMixin
from .models import Resultado, PuntajeDimension


class PuntajeInline(admin.TabularInline):
    model = PuntajeDimension
    extra = 0
    fields = ("dimension", "puntaje")


@admin.register(Resultado)
class ResultadoAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("id", "evaluacion", "preguntas_contestadas", "preguntas_omitidas", "calculado_en")
    search_fields = (
        "evaluacion__estudiante__matricula",
        "evaluacion__estudiante__nombres",
        "evaluacion__estudiante__apellidos",
        "interpretacion",
    )
    ordering = ("-calculado_en",)
    inlines = (PuntajeInline,)


@admin.register(PuntajeDimension)
class PuntajeDimensionAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("resultado", "dimension", "puntaje")
    list_filter = ("dimension",)
    ordering = ("resultado", "dimension")
