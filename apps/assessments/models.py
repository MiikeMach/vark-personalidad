
from django.db import models


class Evaluacion(models.Model):
    class Estado(models.TextChoices):
        EN_PROGRESO = "EN_PROGRESO", "En progreso"
        FINALIZADA = "FINALIZADA", "Finalizada"

    estudiante = models.ForeignKey(
        "students.Estudiante",
        on_delete=models.PROTECT,
        related_name="evaluaciones",
    )
    cuestionario = models.ForeignKey(
        "questionnaires.Cuestionario",
        on_delete=models.PROTECT,
        related_name="evaluaciones",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.EN_PROGRESO,
    )
    iniciada_en = models.DateTimeField(auto_now_add=True)
    finalizada_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-iniciada_en"]
        verbose_name = "Evaluación"
        verbose_name_plural = "Evaluaciones"

    def __str__(self):
        return (
            f"Evaluación {self.pk} - "
            f"{self.estudiante.matricula}"
        )


class Respuesta(models.Model):
    evaluacion = models.ForeignKey(
        Evaluacion,
        on_delete=models.CASCADE,
        related_name="respuestas",
    )
    pregunta = models.ForeignKey(
        "questionnaires.Pregunta",
        on_delete=models.PROTECT,
        related_name="respuestas",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evaluacion", "pregunta"],
                name="respuesta_evaluacion_pregunta_unica",
            ),
        ]

    def __str__(self):
        return (
            f"Evaluación {self.evaluacion_id} - "
            f"Pregunta {self.pregunta_id}"
        )


class SeleccionRespuesta(models.Model):
    respuesta = models.ForeignKey(
        Respuesta,
        on_delete=models.CASCADE,
        related_name="selecciones",
    )
    opcion = models.ForeignKey(
        "questionnaires.Opcion",
        on_delete=models.PROTECT,
        related_name="selecciones",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["respuesta", "opcion"],
                name="seleccion_respuesta_opcion_unica",
            ),
        ]

    def __str__(self):
        return (
            f"Respuesta {self.respuesta_id} - "
            f"Opción {self.opcion_id}"
        )
