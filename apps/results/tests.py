
from django.test import TestCase

from apps.assessments.models import (
    Evaluacion,
    Respuesta,
    SeleccionRespuesta,
)
from apps.questionnaires.models import (
    Cuestionario,
    Pregunta,
    Opcion,
)
from apps.results.models import Resultado, PuntajeDimension
from apps.results.services import guardar_resultado
from apps.students.models import Grupo, Estudiante


class GuardarResultadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.grupo = Grupo.objects.create(
            clave="RESULTADOS-TEST",
            nombre="Grupo de resultados",
        )

        cls.estudiante = Estudiante.objects.create(
            matricula="RESULTADOS-001",
            nombres="Alumno",
            apellidos="Resultados",
            grupo=cls.grupo,
        )

        cls.vark = Cuestionario.objects.create(
            titulo="VARK de prueba",
            tipo=Cuestionario.Tipo.VARK,
        )

        cls.personalidad = Cuestionario.objects.create(
            titulo="Personalidad de prueba",
            tipo=Cuestionario.Tipo.PERSONALIDAD,
        )

    def crear_evaluacion(self, cuestionario):
        return Evaluacion.objects.create(
            estudiante=self.estudiante,
            cuestionario=cuestionario,
        )

    def crear_pregunta(self, cuestionario, orden, dimensiones):
        pregunta = Pregunta.objects.create(
            cuestionario=cuestionario,
            texto=f"Pregunta {orden}",
            orden=orden,
        )

        opciones = {}

        for posicion, dimension in enumerate(
            dimensiones,
            start=1,
        ):
            opciones[dimension] = Opcion.objects.create(
                pregunta=pregunta,
                texto=f"Opción {dimension}",
                dimension=dimension,
                orden=posicion,
            )

        return pregunta, opciones

    def seleccionar(
        self,
        evaluacion,
        pregunta,
        opcion,
        puntos=None,
    ):
        respuesta, _ = Respuesta.objects.get_or_create(
            evaluacion=evaluacion,
            pregunta=pregunta,
        )

        return SeleccionRespuesta.objects.create(
            respuesta=respuesta,
            opcion=opcion,
            puntos=puntos,
        )

    def test_guarda_resultado_vark(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta_1, opciones_1 = self.crear_pregunta(
            self.vark, 1, ["V", "A"]
        )

        self.crear_pregunta(
            self.vark, 2, ["R", "K"]
        )

        self.seleccionar(
            evaluacion, pregunta_1, opciones_1["V"]
        )
        self.seleccionar(
            evaluacion, pregunta_1, opciones_1["A"]
        )

        resultado = guardar_resultado(evaluacion.pk)

        self.assertEqual(resultado.preguntas_contestadas, 1)
        self.assertEqual(resultado.preguntas_omitidas, 1)

        puntajes = dict(
            resultado.puntajes.values_list(
                "dimension", "puntaje"
            )
        )

        self.assertEqual(
            puntajes,
            {"V": 1, "A": 1, "R": 0, "K": 0},
        )

    def test_guarda_resultado_personalidad(self):
        evaluacion = self.crear_evaluacion(
            self.personalidad
        )

        pregunta, opciones = self.crear_pregunta(
            self.personalidad, 1, ["E", "I"]
        )

        self.seleccionar(
            evaluacion, pregunta, opciones["E"], puntos=7
        )
        self.seleccionar(
            evaluacion, pregunta, opciones["I"], puntos=3
        )

        resultado = guardar_resultado(evaluacion.pk)

        self.assertEqual(resultado.preguntas_contestadas, 1)
        self.assertEqual(resultado.preguntas_omitidas, 0)

        puntajes = dict(
            resultado.puntajes.values_list(
                "dimension", "puntaje"
            )
        )

        self.assertEqual(
            puntajes,
            {
                "E": 7, "I": 3,
                "S": 0, "N": 0,
                "T": 0, "F": 0,
                "J": 0, "P": 0,
            },
        )

    def test_recalcular_no_duplica_resultados(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta, opciones = self.crear_pregunta(
            self.vark, 1, ["V", "A"]
        )

        self.seleccionar(
            evaluacion, pregunta, opciones["V"]
        )

        primer_resultado = guardar_resultado(
            evaluacion.pk
        )

        segundo_resultado = guardar_resultado(
            evaluacion.pk
        )

        self.assertEqual(
            primer_resultado.pk,
            segundo_resultado.pk,
        )

        self.assertEqual(
            Resultado.objects.filter(
                evaluacion=evaluacion
            ).count(),
            1,
        )

        self.assertEqual(
            PuntajeDimension.objects.filter(
                resultado=segundo_resultado
            ).count(),
            4,
        )

    def test_actualiza_puntajes_existentes(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta, opciones = self.crear_pregunta(
            self.vark, 1, ["V", "A"]
        )

        self.seleccionar(
            evaluacion, pregunta, opciones["V"]
        )

        resultado = guardar_resultado(evaluacion.pk)

        self.seleccionar(
            evaluacion, pregunta, opciones["A"]
        )

        resultado = guardar_resultado(evaluacion.pk)

        puntajes = dict(
            resultado.puntajes.values_list(
                "dimension", "puntaje"
            )
        )

        self.assertEqual(puntajes["V"], 1)
        self.assertEqual(puntajes["A"], 1)

        self.assertEqual(resultado.puntajes.count(), 4)
