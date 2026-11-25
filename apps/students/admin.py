from django.contrib import admin
from apps.dashboard.admin_actions import DashboardAdminMixin
from .models import Grupo, Estudiante


@admin.register(Grupo)
class GrupoAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("clave", "nombre", "activo", "creado_en")
    list_filter = ("activo",)
    search_fields = ("clave", "nombre")
    ordering = ("nombre",)
    list_editable = ("activo",)


@admin.register(Estudiante)
class EstudianteAdmin(DashboardAdminMixin, admin.ModelAdmin):
    list_display = ("matricula", "nombres", "apellidos", "grupo", "correo", "activo")
    list_filter = ("activo", "grupo")
    search_fields = ("matricula", "nombres", "apellidos", "correo")
    ordering = ("apellidos", "nombres")
    list_editable = ("activo",)
