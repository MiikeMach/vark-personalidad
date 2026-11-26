
from django.conf import settings
from django.db import models


class Grupo(models.Model):
    clave = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"

    def __str__(self):
        return f"{self.clave} - {self.nombre}"


class Estudiante(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="perfil_estudiante",
        null=True,
        blank=True,
    )
    matricula = models.CharField(max_length=30, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    correo = models.EmailField(blank=True)
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.PROTECT,
        related_name="estudiantes",
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["apellidos", "nombres"]
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"

    def __str__(self):
        return f"{self.matricula} - {self.nombres} {self.apellidos}"
