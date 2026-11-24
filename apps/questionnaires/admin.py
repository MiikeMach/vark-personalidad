from django.contrib import admin
from apps.dashboard.admin_actions import DashboardAdminMixin
from .models import Cuestionario, Pregunta, Opcion


class PreguntaInline(admin.TabularInline):
    model = Pregunta
    extra = 1
    fields = ("orden", "texto")
    ordering = ("orden",)


@admin.register(Cuestionario)
class CuestionarioAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("titulo", "tipo", "activo", "creado_en")
    list_filter = ("tipo", "activo")
    search_fields = ("titulo", "descripcion")
    ordering = ("tipo", "titulo")
    list_editable = ("activo",)
    inlines = (PreguntaInline,)


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1
    fields = ("orden", "texto", "dimension")
    ordering = ("orden",)


@admin.register(Pregunta)
class PreguntaAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("texto", "cuestionario", "orden")
    list_filter = ("cuestionario",)
    search_fields = ("texto",)
    ordering = ("cuestionario", "orden")
    inlines = (OpcionInline,)


@admin.register(Opcion)
class OpcionAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("texto", "pregunta", "dimension", "orden")
    list_filter = ("dimension",)
    search_fields = ("texto",)
    ordering = ("pregunta", "orden")
