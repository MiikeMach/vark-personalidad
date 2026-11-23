
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.assessments.models import Evaluacion
from apps.assessments.services import guardar_respuesta
from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from apps.scoring.services import calcular_puntajes_vark
from apps.students.models import Estudiante, Grupo


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
