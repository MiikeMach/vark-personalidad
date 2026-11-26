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
from django.core.exceptions import ValidationError
from apps.results.services import validar_respuestas_para_finalizar
from apps.results.services import finalizar_evaluacion
from unittest.mock import patch
from apps.results.services import finalizar_evaluacion

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

    def test_guarda_perfil_entj(self):
        evaluacion = self.crear_evaluacion(self.personalidad)

        distribuciones = [
            ("E", "I", 7, 3),
            ("S", "N", 2, 8),
            ("T", "F", 6, 4),
            ("J", "P", 9, 1),
        ]

        for orden, (primera, segunda, puntos_1, puntos_2) in enumerate(
            distribuciones,
            start=1,
        ):
            pregunta, opciones = self.crear_pregunta(
                self.personalidad,
                orden,
                [primera, segunda],
            )

            self.seleccionar(
                evaluacion,
                pregunta,
                opciones[primera],
                puntos=puntos_1,
            )

            self.seleccionar(
                evaluacion,
                pregunta,
                opciones[segunda],
                puntos=puntos_2,
            )

        resultado = guardar_resultado(evaluacion.pk)

        self.assertEqual(resultado.interpretacion, "ENTJ")
        self.assertEqual(resultado.preguntas_contestadas, 4)
        self.assertEqual(resultado.preguntas_omitidas, 0)
        self.assertEqual(resultado.puntajes.count(), 8)

    def test_guarda_perfil_no_determinado_por_empate(self):
        evaluacion = self.crear_evaluacion(self.personalidad)

        distribuciones = [
            ("E", "I", 7, 3),
            ("E", "I", 3, 7),
            ("S", "N", 2, 8),
            ("T", "F", 6, 4),
            ("J", "P", 9, 1),
        ]

        for orden, (primera, segunda, puntos_1, puntos_2) in enumerate(
            distribuciones,
            start=1,
        ):
            pregunta, opciones = self.crear_pregunta(
                self.personalidad,
                orden,
                [primera, segunda],
            )

            self.seleccionar(
                evaluacion,
                pregunta,
                opciones[primera],
                puntos=puntos_1,
            )

            self.seleccionar(
                evaluacion,
                pregunta,
                opciones[segunda],
                puntos=puntos_2,
            )

        resultado = guardar_resultado(evaluacion.pk)

        self.assertEqual(
            resultado.interpretacion,
            "Perfil no determinado",
        )
        self.assertEqual(resultado.preguntas_contestadas, 5)

    def test_guarda_perfil_no_determinado_si_faltan_dimensiones(self):
        evaluacion = self.crear_evaluacion(self.personalidad)

        pregunta, opciones = self.crear_pregunta(
            self.personalidad,
            1,
            ["E", "I"],
        )

        self.seleccionar(
            evaluacion,
            pregunta,
            opciones["E"],
            puntos=7,
        )

        self.seleccionar(
            evaluacion,
            pregunta,
            opciones["I"],
            puntos=3,
        )

        resultado = guardar_resultado(evaluacion.pk)

        self.assertEqual(
            resultado.interpretacion,
            "Perfil no determinado",
        )
        self.assertEqual(resultado.puntajes.count(), 8)


class ValidarRespuestasParaFinalizarTests(GuardarResultadoTests):

    def test_error_al_guardar_revierte_finalizacion(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta, opciones = self.crear_pregunta(
            self.vark, 1, ["V", "A"]
        )

        self.seleccionar(
            evaluacion,
            pregunta,
            opciones["V"],
        )

        def guardar_y_fallar(evaluacion_id):
            resultado = guardar_resultado(evaluacion_id)

            raise RuntimeError(
                "Fallo simulado después de guardar resultados."
            )

        with patch(
            "apps.results.services.guardar_resultado",
            side_effect=guardar_y_fallar,
        ):
            with self.assertRaises(RuntimeError):
                finalizar_evaluacion(evaluacion.pk)

        evaluacion.refresh_from_db()

        self.assertEqual(
            evaluacion.estado,
            Evaluacion.Estado.EN_PROGRESO,
        )
        self.assertIsNone(evaluacion.finalizada_en)

        self.assertFalse(
            Resultado.objects.filter(
                evaluacion=evaluacion
            ).exists()
        )


    def test_vark_permite_preguntas_omitidas(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta, opciones = self.crear_pregunta(
            self.vark, 1, ["V", "A"]
        )

        self.crear_pregunta(
            self.vark, 2, ["R", "K"]
        )

        self.seleccionar(
            evaluacion, pregunta, opciones["V"]
        )

        self.assertTrue(
            validar_respuestas_para_finalizar(evaluacion)
        )

    def test_personalidad_completa_es_valida(self):
        evaluacion = self.crear_evaluacion(
            self.personalidad
        )

        pregunta, opciones = self.crear_pregunta(
            self.personalidad, 1, ["E", "I"]
        )

        self.seleccionar(
            evaluacion,
            pregunta,
            opciones["E"],
            puntos=7,
        )

        self.seleccionar(
            evaluacion,
            pregunta,
            opciones["I"],
            puntos=3,
        )

        self.assertTrue(
            validar_respuestas_para_finalizar(evaluacion)
        )

    def test_personalidad_rechaza_preguntas_sin_responder(self):
        evaluacion = self.crear_evaluacion(
            self.personalidad
        )

        self.crear_pregunta(
            self.personalidad, 1, ["E", "I"]
        )

        with self.assertRaises(ValidationError):
            validar_respuestas_para_finalizar(evaluacion)

    def test_personalidad_rechaza_distribucion_invalida(self):
        evaluacion = self.crear_evaluacion(
            self.personalidad
        )

        pregunta, opciones = self.crear_pregunta(
            self.personalidad, 1, ["E", "I"]
        )

        self.seleccionar(
            evaluacion,
            pregunta,
            opciones["E"],
            puntos=5,
        )

        self.seleccionar(
            evaluacion,
            pregunta,
            opciones["I"],
            puntos=5,
        )

        with self.assertRaises(ValidationError):
            validar_respuestas_para_finalizar(evaluacion)

    def test_rechaza_opcion_de_otra_pregunta(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta_1, _ = self.crear_pregunta(
            self.vark, 1, ["V"]
        )

        _, opciones_2 = self.crear_pregunta(
            self.vark, 2, ["A"]
        )

        self.seleccionar(
            evaluacion,
            pregunta_1,
            opciones_2["A"],
        )

        with self.assertRaises(ValidationError):
            validar_respuestas_para_finalizar(evaluacion)

    def test_finaliza_evaluacion_vark(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta, opciones = self.crear_pregunta(
            self.vark, 1, ["V", "A"]
        )

        self.crear_pregunta(
            self.vark, 2, ["R", "K"]
        )

        self.seleccionar(
            evaluacion, pregunta, opciones["V"]
        )

        resultado = finalizar_evaluacion(evaluacion.pk)

        evaluacion.refresh_from_db()

        self.assertEqual(
            evaluacion.estado,
            Evaluacion.Estado.FINALIZADA,
        )
        self.assertIsNotNone(evaluacion.finalizada_en)

        self.assertEqual(resultado.preguntas_contestadas, 1)
        self.assertEqual(resultado.preguntas_omitidas, 1)
        self.assertEqual(resultado.puntajes.count(), 4)

    def test_finaliza_personalidad_y_guarda_perfil(self):
        evaluacion = self.crear_evaluacion(
            self.personalidad
        )

        distribuciones = [
            ("E", "I", 7, 3),
            ("S", "N", 2, 8),
            ("T", "F", 6, 4),
            ("J", "P", 9, 1),
        ]

        for orden, (primera, segunda, puntos_1, puntos_2) in enumerate(
            distribuciones,
            start=1,
        ):
            pregunta, opciones = self.crear_pregunta(
                self.personalidad,
                orden,
                [primera, segunda],
            )

            self.seleccionar(
                evaluacion,
                pregunta,
                opciones[primera],
                puntos=puntos_1,
            )

            self.seleccionar(
                evaluacion,
                pregunta,
                opciones[segunda],
                puntos=puntos_2,
            )

        resultado = finalizar_evaluacion(evaluacion.pk)

        evaluacion.refresh_from_db()

        self.assertEqual(
            evaluacion.estado,
            Evaluacion.Estado.FINALIZADA,
        )
        self.assertIsNotNone(evaluacion.finalizada_en)
        self.assertEqual(resultado.interpretacion, "ENTJ")
        self.assertEqual(resultado.preguntas_contestadas, 4)
        self.assertEqual(resultado.puntajes.count(), 8)

    def test_no_finaliza_personalidad_invalida(self):
        evaluacion = self.crear_evaluacion(
            self.personalidad
        )

        pregunta, opciones = self.crear_pregunta(
            self.personalidad, 1, ["E", "I"]
        )

        self.seleccionar(
            evaluacion, pregunta, opciones["E"], puntos=5
        )
        self.seleccionar(
            evaluacion, pregunta, opciones["I"], puntos=5
        )

        with self.assertRaises(ValidationError):
            finalizar_evaluacion(evaluacion.pk)

        evaluacion.refresh_from_db()

        self.assertEqual(
            evaluacion.estado,
            Evaluacion.Estado.EN_PROGRESO,
        )
        self.assertIsNone(evaluacion.finalizada_en)

        self.assertFalse(
            Resultado.objects.filter(
                evaluacion=evaluacion
            ).exists()
        )

    def test_rechaza_finalizar_dos_veces(self):
        evaluacion = self.crear_evaluacion(self.vark)

        pregunta, opciones = self.crear_pregunta(
            self.vark, 1, ["V", "A"]
        )

        self.seleccionar(
            evaluacion, pregunta, opciones["V"]
        )

        primer_resultado = finalizar_evaluacion(
            evaluacion.pk
        )

        evaluacion.refresh_from_db()
        primera_fecha = evaluacion.finalizada_en

        with self.assertRaises(ValidationError):
            finalizar_evaluacion(evaluacion.pk)

        evaluacion.refresh_from_db()

        self.assertEqual(
            evaluacion.finalizada_en,
            primera_fecha,
        )

        self.assertEqual(
            Resultado.objects.filter(
                evaluacion=evaluacion
            ).count(),
            1,
        )
        self.assertEqual(
            primer_resultado.evaluacion_id,
            evaluacion.pk,
        )
