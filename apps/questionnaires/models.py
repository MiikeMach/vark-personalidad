
from django.db import models


class Cuestionario(models.Model):
    class Tipo(models.TextChoices):
        VARK = "VARK", "VARK"
        PERSONALIDAD = "PERSONALIDAD", "Personalidad"

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    instrucciones = models.TextField(blank=True)
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "titulo"]
        verbose_name = "Cuestionario"
        verbose_name_plural = "Cuestionarios"

    def __str__(self):
        return self.titulo


class Pregunta(models.Model):
    cuestionario = models.ForeignKey(
        Cuestionario,
        on_delete=models.CASCADE,
        related_name="preguntas",
    )
    texto = models.TextField()
    orden = models.PositiveIntegerField()

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["cuestionario", "orden"],
                name="pregunta_orden_unico",
            )
        ]

    def __str__(self):
        return f"Pregunta {self.orden} - {self.cuestionario.titulo}"


class Opcion(models.Model):
    class Dimension(models.TextChoices):
        VISUAL = "V", "Visual"
        AUDITIVO = "A", "Auditivo"
        LECTURA = "R", "Lectura/Escritura"
        KINESTESICO = "K", "Kinestésico"
        EXTROVERSION = "E", "Extroversión"
        INTROVERSION = "I", "Introversión"
        SENSACION = "S", "Sensación"
        INTUICION = "N", "Intuición"
        PENSAMIENTO = "T", "Pensamiento"
        SENTIMIENTO = "F", "Sentimiento"
        JUICIO = "J", "Juicio"
        PERCEPCION = "P", "Percepción"

    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name="opciones",
    )
    texto = models.TextField()
    dimension = models.CharField(
        max_length=1,
        choices=Dimension.choices,
    )
    orden = models.PositiveIntegerField()

    class Meta:
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["pregunta", "orden"],
                name="opcion_orden_unico",
            )
        ]

    def __str__(self):
        return f"Opción {self.orden} - {self.dimension}"
