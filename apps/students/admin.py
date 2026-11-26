from django.contrib import admin
from django.db.models import Count

from apps.dashboard.admin_actions import DashboardAdminMixin, insignia
from .models import Grupo, Estudiante


@admin.register(Grupo)
class GrupoAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("clave", "nombre", "total_estudiantes", "activo")
    list_filter = ("activo",)
    search_fields = ("clave", "nombre")
    ordering = ("nombre",)
    list_editable = ("activo",)
    fieldsets = (
        ("Datos del grupo", {
            "fields": ("clave", "nombre", "activo"),
            "description": "La clave identifica al grupo y debe ser única (por ejemplo, 3A-2026).",
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total_estudiantes=Count("estudiantes"))

    @admin.display(description="Estudiantes", ordering="_total_estudiantes")
    def total_estudiantes(self, grupo):
        return grupo._total_estudiantes


@admin.register(Estudiante)
class EstudianteAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("matricula", "nombre_completo", "grupo", "correo", "cuenta", "activo")
    list_filter = ("activo", "grupo")
    search_fields = ("matricula", "nombres", "apellidos", "correo")
    ordering = ("apellidos", "nombres")
    list_editable = ("activo",)
    list_select_related = ("grupo", "usuario")
    fieldsets = (
        ("Datos personales", {"fields": ("nombres", "apellidos", "correo")}),
        ("Datos escolares", {
            "fields": ("matricula", "grupo", "activo"),
            "description": "La matrícula debe ser única. Desmarca «Activo» si el estudiante ya no participa.",
        }),
    )

    @admin.display(description="Nombre completo", ordering="apellidos")
    def nombre_completo(self, estudiante):
        return f"{estudiante.nombres} {estudiante.apellidos}"

    @admin.display(description="Cuenta")
    def cuenta(self, estudiante):
        if estudiante.usuario_id:
            return insignia(estudiante.usuario.get_username(), "ok")
        return insignia("Sin cuenta")
