"""Servicio de cálculo de resultados (VARK y Jung/MBTI).

Implementa el patrón Singleton: una única instancia sin estado
reutilizada por todos los endpoints.
"""

from django.db import transaction
from django.utils import timezone

from apps.questionnaires.models import Opcion
from apps.results.models import Resultado, PuntajeDimension
from apps.assessments.models import Evaluacion


class ScoringService:
    """Singleton. Contiene la lógica de cálculo de puntajes e interpretación."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def calculate(self, evaluacion: Evaluacion, interpretacion: str = "") -> Resultado:
        """
        Calcula (o recalcula) el resultado de una evaluación.
        Devuelve el Resultado persistido.
        """
        if evaluacion.estado == Evaluacion.Estado.FINALIZADA and \
                hasattr(evaluacion, "resultado"):
            # Recalcular de todos modos: se sobrescribe.
            pass

        with transaction.atomic():
            puntajes = self._compute_scores(evaluacion)
            contestadas, omitidas = self._count_answers(evaluacion)
            interpretacion_final = interpretacion.strip() or self._build_interpretation(
                evaluacion, puntajes
            )

            resultado, _ = Resultado.objects.update_or_create(
                evaluacion=evaluacion,
                defaults={
                    "preguntas_contestadas": contestadas,
                    "preguntas_omitidas": omitidas,
                    "interpretacion": interpretacion_final,
                },
            )

            # Recrear puntajes
            PuntajeDimension.objects.filter(resultado=resultado).delete()
            PuntajeDimension.objects.bulk_create(
                [
                    PuntajeDimension(
                        resultado=resultado,
                        dimension=dim,
                        puntaje=score,
                    )
                    for dim, score in puntajes.items()
                ]
            )

            if evaluacion.estado != Evaluacion.Estado.FINALIZADA:
                evaluacion.estado = Evaluacion.Estado.FINALIZADA
            if evaluacion.finalizada_en is None:
                evaluacion.finalizada_en = timezone.now()
            evaluacion.save(update_fields=["estado", "finalizada_en"])

            return resultado

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _compute_scores(self, evaluacion: Evaluacion) -> dict:
        """Devuelve {dimension: puntaje} para las dimensiones relevantes."""
        tipo = evaluacion.cuestionario.tipo
        dimensiones = self._dimensions_for_type(tipo)
        scores = {d: 0 for d in dimensiones}

        respuestas = (
            evaluacion.respuestas
            .select_related("pregunta")
            .prefetch_related("selecciones__opcion")
        )

        es_personalidad = (tipo == "PERSONALIDAD")

        for respuesta in respuestas:
            for seleccion in respuesta.selecciones.all():
                dim = seleccion.opcion.dimension
                if dim not in scores:
                    continue
                if es_personalidad:
                    # En personalidad cada selección aporta la distribución
                    # de 10 puntos validada en assessments.services.
                    if seleccion.puntos is None:
                        continue
                    scores[dim] += seleccion.puntos
                else:
                    # VARK: cada selección cuenta 1 (multiselección).
                    scores[dim] += 1
        return scores

    def _count_answers(self, evaluacion: Evaluacion):
        """(contestadas, omitidas). Una pregunta cuenta como contestada si
        tiene al menos una selección."""
        total_preguntas = evaluacion.cuestionario.preguntas.count()
        contestadas = (
            evaluacion.respuestas
            .filter(selecciones__isnull=False)
            .distinct()
            .count()
        )
        omitidas = max(total_preguntas - contestadas, 0)
        return contestadas, omitidas

    def _dimensions_for_type(self, tipo: str) -> list:
        if tipo == "VARK":
            return [
                Opcion.Dimension.VISUAL,
                Opcion.Dimension.AUDITIVO,
                Opcion.Dimension.LECTURA,
                Opcion.Dimension.KINESTESICO,
            ]
        # PERSONALIDAD (Jung/MBTI)
        return [
            Opcion.Dimension.EXTROVERSION,
            Opcion.Dimension.INTROVERSION,
            Opcion.Dimension.SENSACION,
            Opcion.Dimension.INTUICION,
            Opcion.Dimension.PENSAMIENTO,
            Opcion.Dimension.SENTIMIENTO,
            Opcion.Dimension.JUICIO,
            Opcion.Dimension.PERCEPCION,
        ]

    # ------------------------------------------------------------------
    # Interpretación automática
    # ------------------------------------------------------------------

    def _build_interpretation(self, evaluacion: Evaluacion, puntajes: dict) -> str:
        if evaluacion.cuestionario.tipo == "VARK":
            return self._interpret_vark(puntajes)
        return self._interpret_personality(puntajes)

    def _interpret_vark(self, puntajes: dict) -> str:
        if not puntajes or all(v == 0 for v in puntajes.values()):
            return "Sin respuestas registradas para calcular un perfil VARK."

        max_score = max(puntajes.values())
        dominantes = [d for d, v in puntajes.items() if v == max_score]

        etiquetas = {
            "V": "Visual",
            "A": "Auditivo",
            "R": "Lectura/Escritura",
            "K": "Kinestésico",
        }
        nombres = [etiquetas.get(d, d) for d in dominantes]
        if len(nombres) == 1:
            perfil = nombres[0]
        else:
            perfil = " y ".join(nombres[:-1]) + " + " + nombres[-1] \
                if len(nombres) > 2 else " y ".join(nombres)

        detalle = ", ".join(
            f"{etiquetas.get(d, d)}={v}" for d, v in puntajes.items()
        )
        return f"Perfil VARK dominante: {perfil}. Puntajes: {detalle}."

    def _interpret_personality(self, puntajes: dict) -> str:
        if not puntajes or all(v == 0 for v in puntajes.values()):
            return "Sin respuestas registradas para calcular un tipo de personalidad."

        pares = [
            ("E", "I", "E/I"),
            ("S", "N", "S/N"),
            ("T", "F", "T/F"),
            ("J", "P", "J/P"),
        ]
        letras = []
        detalle = []
        for a, b, label in pares:
            va, vb = puntajes.get(a, 0), puntajes.get(b, 0)
            if va == 0 and vb == 0:
                detalle.append(f"{label}=sin datos")
                continue
            elegido = a if va >= vb else b
            letras.append(elegido)
            detalle.append(f"{label}: {a}={va}, {b}={vb} → {elegido}")

        tipo = "".join(letras) if letras else "----"
        return f"Tipo de personalidad (Jung/MBTI): {tipo}. Detalle: {'; '.join(detalle)}."