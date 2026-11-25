"""Fachada Singleton para el cálculo y cierre de evaluaciones.

Centraliza el acceso desde la API a las reglas del backend; no duplica
algoritmos ni permite recalcular evaluaciones ya finalizadas.
"""
from django.core.exceptions import ValidationError
from apps.results.services import finalizar_evaluacion


class ScoringService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def calculate(self, evaluacion, interpretacion=""):
        if interpretacion and str(interpretacion).strip():
            raise ValidationError(
                "La interpretación manual no está habilitada; se genera automáticamente."
            )
        return finalizar_evaluacion(evaluacion.pk)
