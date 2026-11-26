
from django.db import models
from apps.questionnaires.models import Opcion


class Resultado(models.Model):
    evaluacion = models.OneToOneField(
        "assessments.Evaluacion",
        on_delete=models.CASCADE,
        related_name="resultado",
    )
    preguntas_contestadas = models.PositiveIntegerField(default=0)
    preguntas_omitidas = models.PositiveIntegerField(default=0)
    interpretacion = models.TextField(blank=True)
    calculado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resultado"
        verbose_name_plural = "Resultados"

    def __str__(self):
        return f"Resultado de evaluación {self.evaluacion_id}"


class PuntajeDimension(models.Model):
    resultado = models.ForeignKey(
        Resultado,
        on_delete=models.CASCADE,
        related_name="puntajes",
    )
    dimension = models.CharField(
        max_length=1,
        choices=Opcion.Dimension.choices,
    )
    puntaje = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["dimension"]
        constraints = [
            models.UniqueConstraint(
                fields=["resultado", "dimension"],
                name="puntaje_resultado_dimension_unico",
            ),
        ]

    def __str__(self):
        return f"{self.dimension}: {self.puntaje}"
