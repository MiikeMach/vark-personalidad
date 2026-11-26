from django.contrib import admin

from apps.assessments.admin import nombre_estudiante
from apps.dashboard.admin_actions import DashboardAdminMixin, insignia
from .models import Resultado, PuntajeDimension


class PuntajeInline(admin.TabularInline):
    model = PuntajeDimension
    extra = 0
    fields = ("dimension", "puntaje")
    verbose_name = "puntaje"
    verbose_name_plural = "Puntajes por dimensión"


@admin.register(Resultado)
class ResultadoAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("estudiante", "cuestionario", "dominante", "preguntas_contestadas", "preguntas_omitidas", "calculado_en")
    list_display_links = ("estudiante",)
    search_fields = (
        "evaluacion__estudiante__matricula",
        "evaluacion__estudiante__nombres",
        "evaluacion__estudiante__apellidos",
        "interpretacion",
    )
    ordering = ("-calculado_en",)
    list_select_related = ("evaluacion__estudiante", "evaluacion__cuestionario")
    readonly_fields = ("calculado_en",)
    inlines = (PuntajeInline,)
    fieldsets = (
        ("Evaluación", {"fields": ("evaluacion", "calculado_en")}),
        ("Resumen", {"fields": ("preguntas_contestadas", "preguntas_omitidas", "interpretacion")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("puntajes")

    @admin.display(description="Estudiante", ordering="evaluacion__estudiante__apellidos")
    def estudiante(self, resultado):
        return nombre_estudiante(resultado.evaluacion.estudiante)

    @admin.display(description="Cuestionario", ordering="evaluacion__cuestionario__titulo")
    def cuestionario(self, resultado):
        return resultado.evaluacion.cuestionario.titulo

    @admin.display(description="Dimensión dominante")
    def dominante(self, resultado):
        puntajes = list(resultado.puntajes.all())
        if not puntajes:
            return "—"
        mayor = max(puntajes, key=lambda p: p.puntaje)
        return insignia(f"{mayor.get_dimension_display()} · {mayor.puntaje}", "ok")


@admin.register(PuntajeDimension)
class PuntajeDimensionAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("estudiante", "dimension_insignia", "puntaje")
    list_display_links = ("estudiante",)
    list_filter = ("dimension",)
    ordering = ("resultado", "dimension")
    list_select_related = ("resultado__evaluacion__estudiante",)
    fieldsets = (("Puntaje", {"fields": ("resultado", "dimension", "puntaje")}),)

    @admin.display(description="Estudiante", ordering="resultado__evaluacion__estudiante__apellidos")
    def estudiante(self, puntaje):
        return nombre_estudiante(puntaje.resultado.evaluacion.estudiante)

    @admin.display(description="Dimensión", ordering="dimension")
    def dimension_insignia(self, puntaje):
        return insignia(puntaje.get_dimension_display())
