from django.contrib import admin
from django.db.models import Count
from django.utils.text import Truncator

from apps.dashboard.admin_actions import DashboardAdminMixin, insignia
from .models import Cuestionario, Pregunta, Opcion


class PreguntaInline(admin.TabularInline):
    model = Pregunta
    extra = 1
    fields = ("orden", "texto")
    ordering = ("orden",)
    verbose_name = "pregunta"
    verbose_name_plural = "Preguntas del cuestionario"
    show_change_link = True  # Abre la pregunta para editar sus opciones.


@admin.register(Cuestionario)
class CuestionarioAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("titulo", "tipo_insignia", "total_preguntas", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("titulo", "descripcion")
    ordering = ("tipo", "titulo")
    list_editable = ("activo",)
    inlines = (PreguntaInline,)
    fieldsets = (
        ("Datos generales", {
            "fields": ("titulo", "tipo", "activo"),
            "description": "Solo los cuestionarios activos se pueden aplicar a los estudiantes.",
        }),
        ("Textos para el estudiante", {
            "fields": ("descripcion", "instrucciones"),
            "description": "Se muestran antes de comenzar la evaluación.",
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total_preguntas=Count("preguntas"))

    @admin.display(description="Tipo", ordering="tipo")
    def tipo_insignia(self, cuestionario):
        return insignia(cuestionario.get_tipo_display(), "ok" if cuestionario.tipo == "VARK" else "")

    @admin.display(description="Preguntas", ordering="_total_preguntas")
    def total_preguntas(self, cuestionario):
        return cuestionario._total_preguntas


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1
    fields = ("orden", "texto", "dimension")
    ordering = ("orden",)
    verbose_name = "opción"
    verbose_name_plural = "Opciones de respuesta"


@admin.register(Pregunta)
class PreguntaAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("orden", "texto_corto", "cuestionario", "total_opciones")
    list_display_links = ("texto_corto",)
    list_filter = ("cuestionario",)
    search_fields = ("texto",)
    ordering = ("cuestionario", "orden")
    list_select_related = ("cuestionario",)
    inlines = (OpcionInline,)

    def has_module_permission(self, request):
        # Se editan desde la ficha de cada cuestionario; no aparecen en el panel ni en el menú.
        return False

    fieldsets = (
        ("Pregunta", {
            "fields": ("cuestionario", "orden", "texto"),
            "description": "El orden define en qué posición aparece dentro del cuestionario.",
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total_opciones=Count("opciones"))

    @admin.display(description="Pregunta", ordering="texto")
    def texto_corto(self, pregunta):
        return Truncator(pregunta.texto).chars(90)

    @admin.display(description="Opciones", ordering="_total_opciones")
    def total_opciones(self, pregunta):
        return pregunta._total_opciones


@admin.register(Opcion)
class OpcionAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("texto_corto", "pregunta_corta", "dimension_insignia", "orden")
    list_filter = ("dimension",)
    search_fields = ("texto",)
    ordering = ("pregunta", "orden")
    list_select_related = ("pregunta__cuestionario",)

    def has_module_permission(self, request):
        # Se editan desde la ficha de cada pregunta; no aparecen en el panel ni en el menú.
        return False

    fieldsets = (
        ("Opción de respuesta", {
            "fields": ("pregunta", "orden", "texto", "dimension"),
            "description": "La dimensión indica qué rasgo suma esta opción al elegirla.",
        }),
    )

    @admin.display(description="Opción", ordering="texto")
    def texto_corto(self, opcion):
        return Truncator(opcion.texto).chars(70)

    @admin.display(description="Pregunta", ordering="pregunta__orden")
    def pregunta_corta(self, opcion):
        return f"{opcion.pregunta.cuestionario.titulo} · {Truncator(opcion.pregunta.texto).chars(50)}"

    @admin.display(description="Dimensión", ordering="dimension")
    def dimension_insignia(self, opcion):
        return insignia(opcion.get_dimension_display())
