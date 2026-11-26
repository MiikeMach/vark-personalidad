"""Crea (o actualiza) una cuenta de prueba por cada plantilla de rol.

Uso:
    python manage.py crear_cuentas_roles
    python manage.py crear_cuentas_roles --password "UnaClaveSegura123!"

Las cuentas se llaman «demo.<rol>». Cada vez que se ejecuta asigna una
contraseña nueva (aleatoria si no se indica una) y la muestra en pantalla.
"""

import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.dashboard.roles import PLANTILLAS_ROL, obtener_rol_de_plantilla, sincronizar_roles

NOMBRES = {
    "administrador": ("Ana", "Administradora"),
    "coordinador": ("Carlos", "Coordinador"),
    "docente": ("Diana", "Docente"),
    "consultor": ("Raúl", "Consultor"),
    "estudiante": ("Elena", "Estudiante"),
}


def nombre_de_usuario(clave):
    return f"demo.{clave}"


class Command(BaseCommand):
    help = "Crea una cuenta de prueba por cada plantilla de rol y muestra sus contraseñas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Contraseña para todas las cuentas. Si se omite, se genera una aleatoria por cuenta.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        fija = options.get("password")
        sincronizar_roles(crear=True)
        filas = []
        for clave, plantilla in PLANTILLAS_ROL.items():
            nombre, apellido = NOMBRES.get(clave, ("Demo", plantilla["name"]))
            usuario, creado = User.objects.get_or_create(
                username=nombre_de_usuario(clave),
                defaults={"first_name": nombre, "last_name": apellido, "email": f"{nombre_de_usuario(clave)}@example.com"},
            )
            contrasena = fija or secrets.token_urlsafe(9)
            try:
                validate_password(contrasena, usuario)
            except ValidationError as error:
                raise CommandError(f"Contraseña no válida: {' '.join(error.messages)}")
            usuario.set_password(contrasena)
            usuario.is_active = True
            usuario.is_staff = plantilla["staff"]
            usuario.is_superuser = False
            usuario.save()
            usuario.groups.set([obtener_rol_de_plantilla(clave)])
            filas.append((plantilla["name"], usuario.username, contrasena, plantilla["staff"], creado))

        self.stdout.write("")
        self.stdout.write(f"{'Rol':<28}{'Usuario':<22}{'Contraseña':<20}Panel")
        self.stdout.write("-" * 76)
        for rol, usuario, contrasena, staff, creado in filas:
            estado = "sí" if staff else "no (sin acceso al panel)"
            nueva = "" if creado else "  [actualizada]"
            self.stdout.write(f"{rol:<28}{usuario:<22}{contrasena:<20}{estado}{nueva}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Cuentas listas. Inicia sesión en /admin/ con estos datos."))
