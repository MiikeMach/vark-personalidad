
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.assessments.models import Evaluacion
from apps.assessments.services import guardar_respuesta
from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from apps.scoring.services import calcular_puntajes_vark
from apps.students.models import Estudiante, Grupo
from apps.scoring.services import generar_perfil_personalidad
from django.test import SimpleTestCase

class CalcularPuntajesVarkTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        grupo = Grupo.objects.create(
            clave="VARK-TEST",
            nombre="Grupo VARK",
        )

        estudiante = Estudiante.objects.create(
            matricula="VARK-001",
            nombres="Alumno",
            apellidos="Prueba",
            grupo=grupo,
        )

        cls.cuestionario = Cuestionario.objects.create(
            titulo="Cuestionario VARK de prueba",
            tipo=Cuestionario.Tipo.VARK,
        )

        cls.evaluacion = Evaluacion.objects.create(
            estudiante=estudiante,
            cuestionario=cls.cuestionario,
        )

        cls.pregunta1 = Pregunta.objects.create(
            cuestionario=cls.cuestionario,
            texto="Pregunta 1",
            orden=1,
        )

        cls.pregunta2 = Pregunta.objects.create(
            cuestionario=cls.cuestionario,
            texto="Pregunta 2",
            orden=2,
        )

        cls.opcion_v = Opcion.objects.create(
            pregunta=cls.pregunta1,
            texto="Visual",
            dimension="V",
            orden=1,
        )

        cls.opcion_a = Opcion.objects.create(
            pregunta=cls.pregunta1,
            texto="Auditivo",
            dimension="A",
            orden=2,
        )

        cls.opcion_r = Opcion.objects.create(
            pregunta=cls.pregunta2,
            texto="Lectura y escritura",
            dimension="R",
            orden=1,
        )

        cls.opcion_k = Opcion.objects.create(
            pregunta=cls.pregunta2,
            texto="Kinestésico",
            dimension="K",
            orden=2,
        )

    def test_evaluacion_sin_respuestas_devuelve_ceros(self):
        resultado = calcular_puntajes_vark(self.evaluacion)

        self.assertEqual(
            resultado,
            {"V": 0, "A": 0, "R": 0, "K": 0},
        )

    def test_calcula_cuatro_dimensiones(self):
        guardar_respuesta(
            self.evaluacion.pk,
            self.pregunta1.pk,
            [self.opcion_v.pk, self.opcion_a.pk],
        )

        guardar_respuesta(
            self.evaluacion.pk,
            self.pregunta2.pk,
            [self.opcion_r.pk, self.opcion_k.pk],
        )

        resultado = calcular_puntajes_vark(self.evaluacion)

        self.assertEqual(
            resultado,
            {"V": 1, "A": 1, "R": 1, "K": 1},
        )

    def test_pregunta_omitida_no_suma_puntos(self):
        guardar_respuesta(
            self.evaluacion.pk,
            self.pregunta1.pk,
            [self.opcion_v.pk],
        )

        guardar_respuesta(
            self.evaluacion.pk,
            self.pregunta2.pk,
            [],
        )

        resultado = calcular_puntajes_vark(self.evaluacion)

        self.assertEqual(
            resultado,
            {"V": 1, "A": 0, "R": 0, "K": 0},
        )

    def test_actualizacion_no_duplica_puntajes(self):
        guardar_respuesta(
            self.evaluacion.pk,
            self.pregunta1.pk,
            [self.opcion_v.pk],
        )

        guardar_respuesta(
            self.evaluacion.pk,
            self.pregunta1.pk,
            [self.opcion_a.pk],
        )

        resultado = calcular_puntajes_vark(self.evaluacion)

        self.assertEqual(
            resultado,
            {"V": 0, "A": 1, "R": 0, "K": 0},
        )

    def test_rechaza_cuestionario_de_personalidad(self):
        cuestionario = Cuestionario.objects.create(
            titulo="Personalidad de prueba",
            tipo=Cuestionario.Tipo.PERSONALIDAD,
        )

        evaluacion = Evaluacion.objects.create(
            estudiante=self.evaluacion.estudiante,
            cuestionario=cuestionario,
        )

        with self.assertRaises(ValidationError):
            calcular_puntajes_vark(evaluacion)


from apps.assessments.services import guardar_respuesta_personalidad
from apps.scoring.services import calcular_puntajes_personalidad

class CalcularPuntajesPersonalidadTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        grupo = Grupo.objects.create(
            clave="SCORE-PERS",
            nombre="Grupo de personalidad",
        )

        estudiante = Estudiante.objects.create(
            matricula="SCORE-PERS-001",
            nombres="Alumno",
            apellidos="Prueba",
            grupo=grupo,
        )

        cls.cuestionario = Cuestionario.objects.create(
            titulo="Personalidad de prueba",
            tipo=Cuestionario.Tipo.PERSONALIDAD,
        )

        cls.evaluacion = Evaluacion.objects.create(
            estudiante=estudiante,
            cuestionario=cls.cuestionario,
        )

        cls.preguntas = {}
        cls.opciones = {}

        for orden, (dimension_1, dimension_2) in enumerate(
            [("E", "I"), ("S", "N"), ("T", "F"), ("J", "P")],
            start=1,
        ):
            pregunta = Pregunta.objects.create(
                cuestionario=cls.cuestionario,
                texto=f"Pregunta {orden}",
                orden=orden,
            )

            opcion_1 = Opcion.objects.create(
                pregunta=pregunta,
                texto=f"Opción {dimension_1}",
                dimension=dimension_1,
                orden=1,
            )

            opcion_2 = Opcion.objects.create(
                pregunta=pregunta,
                texto=f"Opción {dimension_2}",
                dimension=dimension_2,
                orden=2,
            )

            cls.preguntas[dimension_1] = pregunta
            cls.opciones[dimension_1] = opcion_1
            cls.opciones[dimension_2] = opcion_2

    def guardar_par(self, primera, segunda, puntos_1, puntos_2):
        guardar_respuesta_personalidad(
            self.evaluacion.pk,
            self.preguntas[primera].pk,
            self.opciones[primera].pk,
            puntos_1,
            self.opciones[segunda].pk,
            puntos_2,
        )

    def test_sin_respuestas_devuelve_ceros(self):
        resultado = calcular_puntajes_personalidad(self.evaluacion)

        self.assertEqual(
            resultado,
            {
                "E": 0, "I": 0,
                "S": 0, "N": 0,
                "T": 0, "F": 0,
                "J": 0, "P": 0,
            },
        )

    def test_calcula_las_ocho_dimensiones(self):
        self.guardar_par("E", "I", 7, 3)
        self.guardar_par("S", "N", 2, 8)
        self.guardar_par("T", "F", 6, 4)
        self.guardar_par("J", "P", 9, 1)

        resultado = calcular_puntajes_personalidad(self.evaluacion)

        self.assertEqual(
            resultado,
            {
                "E": 7, "I": 3,
                "S": 2, "N": 8,
                "T": 6, "F": 4,
                "J": 9, "P": 1,
            },
        )

    def test_actualizar_respuesta_no_duplica_puntos(self):
        self.guardar_par("E", "I", 7, 3)
        self.guardar_par("E", "I", 8, 2)

        resultado = calcular_puntajes_personalidad(self.evaluacion)

        self.assertEqual(resultado["E"], 8)
        self.assertEqual(resultado["I"], 2)

    def test_rechaza_evaluacion_vark(self):
        cuestionario_vark = Cuestionario.objects.create(
            titulo="VARK de prueba",
            tipo=Cuestionario.Tipo.VARK,
        )

        evaluacion_vark = Evaluacion.objects.create(
            estudiante=self.evaluacion.estudiante,
            cuestionario=cuestionario_vark,
        )

        with self.assertRaises(ValidationError):
            calcular_puntajes_personalidad(evaluacion_vark)


class GenerarPerfilPersonalidadTests(SimpleTestCase):

    def test_genera_perfil_entj(self):
        puntajes = {
            "E": 7, "I": 3,
            "S": 2, "N": 8,
            "T": 6, "F": 4,
            "J": 9, "P": 1,
        }

        perfil = generar_perfil_personalidad(puntajes)

        self.assertEqual(perfil, "ENTJ")

    def test_genera_perfil_isfp(self):
        puntajes = {
            "E": 2, "I": 8,
            "S": 7, "N": 3,
            "T": 4, "F": 6,
            "J": 1, "P": 9,
        }

        perfil = generar_perfil_personalidad(puntajes)

        self.assertEqual(perfil, "ISFP")

    def test_empate_devuelve_none(self):
        puntajes = {
            "E": 5, "I": 5,
            "S": 2, "N": 8,
            "T": 6, "F": 4,
            "J": 9, "P": 1,
        }

        perfil = generar_perfil_personalidad(puntajes)

        self.assertIsNone(perfil)

    def test_datos_incompletos_devuelven_none(self):
        puntajes = {
            "E": 7,
            "I": 3,
        }

        perfil = generar_perfil_personalidad(puntajes)

        self.assertIsNone(perfil)

    def test_rechaza_puntuaciones_negativas(self):
        puntajes = {
            "E": -1, "I": 11,
            "S": 2, "N": 8,
            "T": 6, "F": 4,
            "J": 9, "P": 1,
        }

        with self.assertRaises(ValidationError):
            generar_perfil_personalidad(puntajes)

    def test_rechaza_valores_no_enteros(self):
        puntajes = {
            "E": "7", "I": 3,
            "S": 2, "N": 8,
            "T": 6, "F": 4,
            "J": 9, "P": 1,
        }

        with self.assertRaises(ValidationError):
            generar_perfil_personalidad(puntajes)
