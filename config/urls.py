
"""Configuración de las rutas principales del proyecto Brújula."""

from django.contrib import admin
from django.urls import include, path

from apps.dashboard.views import home


# Personalización del panel administrativo.
admin.site.site_header = "Administración · Brújula"
admin.site.site_title = "Brújula"
admin.site.index_title = "Panel de gestión"


urlpatterns = [
    # Página principal del frontend.
    path("", home, name="home"),

    # Panel administrativo de Django.
    path("admin/", admin.site.urls),

    # API para evaluaciones, cuestionarios y resultados.
    path("api/", include("apps.api.urls")),
]
