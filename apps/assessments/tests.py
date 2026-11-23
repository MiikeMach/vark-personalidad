
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.assessments.models import Evaluacion
from apps.assessments.services import validar_selecciones
from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from apps.students.models import Estudiante, Grupo


class ValidarSeleccionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo = Grupo.objects.create(
            clave="TEST-01",
            nombre="Grupo de pruebas",
        )

        estudiante = Estudiante.objects.create(
            matricula="TEST-001",
            nombres="Alumno",
            apellidos="Prueba",
            grupo=grupo,
        )

        cls.vark = Cuestionario.objects.create(
            titulo="VARK de prueba",
            tipo=Cuestionario.Tipo.VARK,
        )

        cls.personalidad = Cuestionario.objects.create(
            titulo="Personalidad de prueba",
            tipo=Cuestionario.Tipo.PERSONALIDAD,
        )

        cls.pregunta_vark = Pregunta.objects.create(
            cuestionario=cls.vark,
            texto="Pregunta VARK",
            orden=1,
        )

        cls.otra_pregunta = Pregunta.objects.create(
            cuestionario=cls.vark,
            texto="Otra pregunta",
            orden=2,
        )

        cls.opcion_v = Opcion.objects.create(
            pregunta=cls.pregunta_vark,
            texto="Visual",
            dimension="V",
            orden=1,
        )

        cls.opcion_a = Opcion.objects.create(
            pregunta=cls.pregunta_vark,
            texto="Auditivo",
            dimension="A",
            orden=2,
        )

        cls.opcion_ajena = Opcion.objects.create(
            pregunta=cls.otra_pregunta,
            texto="Otra opción",
            dimension="K",
            orden=1,
        )

        cls.evaluacion_vark = Evaluacion.objects.create(
            estudiante=estudiante,
            cuestionario=cls.vark,
        )

        cls.pregunta_personalidad = Pregunta.objects.create(
            cuestionario=cls.personalidad,
            texto="Pregunta personalidad",
            orden=1,
        )

        cls.opcion_e = Opcion.objects.create(
            pregunta=cls.pregunta_personalidad,
            texto="Extroversión",
            dimension="E",
            orden=1,
        )

        cls.opcion_i = Opcion.objects.create(
            pregunta=cls.pregunta_personalidad,
            texto="Introversión",
            dimension="I",
            orden=2,
        )

        cls.evaluacion_personalidad = Evaluacion.objects.create(
            estudiante=estudiante,
            cuestionario=cls.personalidad,
        )

    def test_vark_permite_varias_opciones(self):
        opciones = validar_selecciones(
            self.evaluacion_vark,
            self.pregunta_vark.pk,
            [self.opcion_v.pk, self.opcion_a.pk],
        )
        self.assertEqual(len(opciones), 2)

    def test_vark_permite_omitir_pregunta(self):
        opciones = validar_selecciones(
            self.evaluacion_vark,
            self.pregunta_vark.pk,
            [],
        )
        self.assertEqual(opciones, [])

    def test_rechaza_opcion_de_otra_pregunta(self):
        with self.assertRaises(ValidationError):
            validar_selecciones(
                self.evaluacion_vark,
                self.pregunta_vark.pk,
                [self.opcion_ajena.pk],
            )

    def test_rechaza_opciones_duplicadas(self):
        with self.assertRaises(ValidationError):
            validar_selecciones(
                self.evaluacion_vark,
                self.pregunta_vark.pk,
                [self.opcion_v.pk, self.opcion_v.pk],
            )

    def test_personalidad_rechaza_varias_opciones(self):
        with self.assertRaises(ValidationError):
            validar_selecciones(
                self.evaluacion_personalidad,
                self.pregunta_personalidad.pk,
                [self.opcion_e.pk, self.opcion_i.pk],
            )

    def test_rechaza_pregunta_de_otro_cuestionario(self):
        with self.assertRaises(ValidationError):
            validar_selecciones(
                self.evaluacion_vark,
                self.pregunta_personalidad.pk,
                [self.opcion_e.pk],
            )
