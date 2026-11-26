from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sincronizar_roles_tras_migrar(**kwargs):
    # Tras cada migración se pueden crear permisos nuevos (p. ej. un modelo nuevo):
    # se vuelven a aplicar las plantillas para que cada rol existente quede igual a su definición.
    from apps.dashboard.roles import sincronizar_roles

    sincronizar_roles()


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dashboard'

    def ready(self):
        post_migrate.connect(_sincronizar_roles_tras_migrar, dispatch_uid="brujuela_sincronizar_roles")
