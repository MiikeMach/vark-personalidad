from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.assessments.models import Evaluacion
from apps.assessments.services import validar_selecciones
from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from apps.students.models import Estudiante, Grupo
from django.test import SimpleTestCase
from apps.assessments.services import validar_evaluacion_editable
from apps.assessments.models import Respuesta, SeleccionRespuesta
from apps.assessments.services import guardar_respuesta
from apps.assessments.services import validar_distribucion_personalidad
from apps.assessments.services import validar_par_personalidad
from apps.assessments.services import guardar_respuesta_personalidad

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
    def test_guardar_respuesta_con_varias_opciones(self):
        respuesta = guardar_respuesta(
            self.evaluacion_vark.pk,
            self.pregunta_vark.pk,
            [self.opcion_v.pk, self.opcion_a.pk],
        )

        self.assertEqual(
            Respuesta.objects.filter(
                evaluacion=self.evaluacion_vark,
                pregunta=self.pregunta_vark,
            ).count(),
            1,
        )
        self.assertEqual(respuesta.selecciones.count(), 2)

    def test_guardar_respuesta_rechaza_personalidad(self):
        with self.assertRaises(ValidationError):
            guardar_respuesta(
                self.evaluacion_personalidad.pk,
                self.pregunta_personalidad.pk,
                [self.opcion_e.pk, self.opcion_i.pk],
            )

        self.assertFalse(
            Respuesta.objects.filter(
                evaluacion=self.evaluacion_personalidad,
                pregunta=self.pregunta_personalidad,
            ).exists()
        )


    def test_actualizar_respuesta_reemplaza_selecciones(self):
        guardar_respuesta(
            self.evaluacion_vark.pk,
            self.pregunta_vark.pk,
            [self.opcion_v.pk],
        )

        respuesta = guardar_respuesta(
            self.evaluacion_vark.pk,
            self.pregunta_vark.pk,
            [self.opcion_a.pk],
        )

        self.assertEqual(respuesta.selecciones.count(), 1)
        self.assertTrue(
            respuesta.selecciones.filter(
                opcion=self.opcion_a
            ).exists()
        )

    def test_guardar_pregunta_omitida(self):
        respuesta = guardar_respuesta(
            self.evaluacion_vark.pk,
            self.pregunta_vark.pk,
            [],
        )

        self.assertEqual(respuesta.selecciones.count(), 0)

    def test_no_modificar_evaluacion_finalizada(self):
        self.evaluacion_vark.estado = Evaluacion.Estado.FINALIZADA
        self.evaluacion_vark.save(update_fields=["estado"])

        with self.assertRaises(ValidationError):
            guardar_respuesta(
                self.evaluacion_vark.pk,
                self.pregunta_vark.pk,
                [self.opcion_v.pk],
            )

        self.assertFalse(
            Respuesta.objects.filter(
                evaluacion=self.evaluacion_vark
            ).exists()
        )

class ValidarEvaluacionEditableTests(SimpleTestCase):

    def test_permite_evaluacion_en_progreso(self):
        evaluacion = Evaluacion(
            estado=Evaluacion.Estado.EN_PROGRESO
        )

        validar_evaluacion_editable(evaluacion)

    def test_rechaza_evaluacion_finalizada(self):
        evaluacion = Evaluacion(
            estado=Evaluacion.Estado.FINALIZADA
        )

        with self.assertRaises(ValidationError):
            validar_evaluacion_editable(evaluacion)
class ValidarDistribucionPersonalidadTests(SimpleTestCase):

    def test_acepta_distribucion_7_3(self):
        self.assertTrue(
            validar_distribucion_personalidad(7, 3)
        )

    def test_acepta_distribucion_10_0(self):
        self.assertTrue(
            validar_distribucion_personalidad(10, 0)
        )

    def test_rechaza_distribucion_5_5(self):
        with self.assertRaises(ValidationError):
            validar_distribucion_personalidad(5, 5)

    def test_rechaza_suma_diferente_de_10(self):
        with self.assertRaises(ValidationError):
            validar_distribucion_personalidad(6, 2)

    def test_rechaza_puntos_fuera_de_rango(self):
        with self.assertRaises(ValidationError):
            validar_distribucion_personalidad(11, -1)

    def test_rechaza_valores_no_enteros(self):
        with self.assertRaises(ValidationError):
            validar_distribucion_personalidad(7.5, 2.5)

    def test_rechaza_valores_booleanos(self):
        with self.assertRaises(ValidationError):
            validar_distribucion_personalidad(True, 9)

class ValidarParPersonalidadTests(SimpleTestCase):

    def test_acepta_par_extroversion_introversion(self):
        self.assertTrue(validar_par_personalidad("E", "I"))

    def test_acepta_par_sensacion_intuicion(self):
        self.assertTrue(validar_par_personalidad("S", "N"))

    def test_acepta_par_pensamiento_sentimiento(self):
        self.assertTrue(validar_par_personalidad("T", "F"))

    def test_acepta_par_juicio_percepcion(self):
        self.assertTrue(validar_par_personalidad("J", "P"))

    def test_acepta_par_en_orden_inverso(self):
        self.assertTrue(validar_par_personalidad("I", "E"))

    def test_rechaza_dimensiones_de_pares_diferentes(self):
        with self.assertRaises(ValidationError):
            validar_par_personalidad("E", "S")

    def test_rechaza_dimensiones_repetidas(self):
        with self.assertRaises(ValidationError):
            validar_par_personalidad("E", "E")

    def test_rechaza_dimensiones_vark(self):
        with self.assertRaises(ValidationError):
            validar_par_personalidad("V", "A")

class GuardarRespuestaPersonalidadTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        grupo = Grupo.objects.create(
            clave="PERS-TEST",
            nombre="Grupo Personalidad",
        )

        estudiante = Estudiante.objects.create(
            matricula="PERS-001",
            nombres="Alumno",
            apellidos="Personalidad",
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

        cls.pregunta = Pregunta.objects.create(
            cuestionario=cls.cuestionario,
            texto="Pregunta de personalidad",
            orden=1,
        )

        cls.opcion_e = Opcion.objects.create(
            pregunta=cls.pregunta,
            texto="Extroversión",
            dimension="E",
            orden=1,
        )

        cls.opcion_i = Opcion.objects.create(
            pregunta=cls.pregunta,
            texto="Introversión",
            dimension="I",
            orden=2,
        )

        cls.opcion_s = Opcion.objects.create(
            pregunta=cls.pregunta,
            texto="Sensación",
            dimension="S",
            orden=3,
        )

    def test_guarda_distribucion_7_3(self):
        respuesta = guardar_respuesta_personalidad(
            self.evaluacion.pk,
            self.pregunta.pk,
            self.opcion_e.pk, 7,
            self.opcion_i.pk, 3,
        )

        self.assertEqual(respuesta.selecciones.count(), 2)

        puntos = {
            seleccion.opcion.dimension: seleccion.puntos
            for seleccion in respuesta.selecciones.select_related("opcion")
        }

        self.assertEqual(puntos, {"E": 7, "I": 3})

    def test_actualiza_distribucion_sin_duplicar(self):
        guardar_respuesta_personalidad(
            self.evaluacion.pk,
            self.pregunta.pk,
            self.opcion_e.pk, 7,
            self.opcion_i.pk, 3,
        )

        respuesta = guardar_respuesta_personalidad(
            self.evaluacion.pk,
            self.pregunta.pk,
            self.opcion_e.pk, 8,
            self.opcion_i.pk, 2,
        )

        self.assertEqual(respuesta.selecciones.count(), 2)

        puntos = {
            seleccion.opcion.dimension: seleccion.puntos
            for seleccion in respuesta.selecciones.select_related("opcion")
        }

        self.assertEqual(puntos, {"E": 8, "I": 2})

    def test_distribucion_invalida_no_modifica_respuesta(self):
        guardar_respuesta_personalidad(
            self.evaluacion.pk,
            self.pregunta.pk,
            self.opcion_e.pk, 7,
            self.opcion_i.pk, 3,
        )

        with self.assertRaises(ValidationError):
            guardar_respuesta_personalidad(
                self.evaluacion.pk,
                self.pregunta.pk,
                self.opcion_e.pk, 5,
                self.opcion_i.pk, 5,
            )

        respuesta = Respuesta.objects.get(
            evaluacion=self.evaluacion,
            pregunta=self.pregunta,
        )

        puntos = {
            seleccion.opcion.dimension: seleccion.puntos
            for seleccion in respuesta.selecciones.select_related("opcion")
        }

        self.assertEqual(puntos, {"E": 7, "I": 3})

    def test_rechaza_dimensiones_de_pares_distintos(self):
        with self.assertRaises(ValidationError):
            guardar_respuesta_personalidad(
                self.evaluacion.pk,
                self.pregunta.pk,
                self.opcion_e.pk, 7,
                self.opcion_s.pk, 3,
            )

        self.assertFalse(
            Respuesta.objects.filter(
                evaluacion=self.evaluacion
            ).exists()
        )

    def test_no_modifica_evaluacion_finalizada(self):
        self.evaluacion.estado = Evaluacion.Estado.FINALIZADA
        self.evaluacion.save(update_fields=["estado"])

        with self.assertRaises(ValidationError):
            guardar_respuesta_personalidad(
                self.evaluacion.pk,
                self.pregunta.pk,
                self.opcion_e.pk, 7,
                self.opcion_i.pk, 3,
            )

        self.assertFalse(
            Respuesta.objects.filter(
                evaluacion=self.evaluacion
            ).exists()
        )