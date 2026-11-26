"""Aplica las plantillas de rol a los roles existentes.

Uso:
    python manage.py sincronizar_roles

Cada rol de plantilla (Administrador, Coordinador, Docente, Consultor / Psicopedagogo
y Estudiante) queda con exactamente los permisos definidos en apps/dashboard/roles.py;
los que falten se crean. También ajusta el acceso al panel de las cuentas de cada rol
(los superusuarios no se modifican).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dashboard.roles import sincronizar_roles


class Command(BaseCommand):
    help = "Deja cada rol con los permisos de su plantilla y ajusta el acceso al panel de sus cuentas."

    @transaction.atomic
    def handle(self, *args, **options):
        cambios = sincronizar_roles(crear=True, ajustar_usuarios=True)
        self.stdout.write(f"{'Rol':<28}{'Agregados':>10}{'Quitados':>10}{'Cuentas ajustadas':>19}")
        self.stdout.write("-" * 67)
        for nombre, agregados, quitados, ajustadas in cambios:
            self.stdout.write(f"{nombre:<28}{agregados:>10}{quitados:>10}{ajustadas:>19}")
        self.stdout.write(self.style.SUCCESS("Roles sincronizados con sus plantillas."))
