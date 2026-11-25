"""Pruebas de integración HTTP de guardado y finalización."""
import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.students.models import Grupo, Estudiante
from apps.questionnaires.models import Cuestionario, Pregunta, Opcion
from apps.assessments.models import Evaluacion, Respuesta
from apps.results.models import Resultado


class FlujoEvaluacionAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            username="admin_api_test", password="password-ficticio", is_staff=True,
        )
        grupo = Grupo.objects.create(clave="API-T", nombre="API pruebas")
        cls.estudiante = Estudiante.objects.create(
            matricula="API-001", nombres="Alumno", apellidos="Prueba", grupo=grupo,
        )
        cls.vark = Cuestionario.objects.create(titulo="VARK API", tipo=Cuestionario.Tipo.VARK)
        cls.personalidad = Cuestionario.objects.create(
            titulo="Personalidad API", tipo=Cuestionario.Tipo.PERSONALIDAD,
        )
        cls.pregunta_v = Pregunta.objects.create(cuestionario=cls.vark, texto="V", orden=1)
        cls.opcion_v = Opcion.objects.create(pregunta=cls.pregunta_v, texto="Visual", dimension="V", orden=1)
        cls.opcion_a = Opcion.objects.create(pregunta=cls.pregunta_v, texto="Auditivo", dimension="A", orden=2)
        cls.pregunta_p = Pregunta.objects.create(cuestionario=cls.personalidad, texto="P", orden=1)
        cls.opcion_e = Opcion.objects.create(pregunta=cls.pregunta_p, texto="E", dimension="E", orden=1)
        cls.opcion_i = Opcion.objects.create(pregunta=cls.pregunta_p, texto="I", dimension="I", orden=2)

    def setUp(self):
        self.client.force_login(self.admin)

    def nuevo(self, cuestionario):
        return Evaluacion.objects.create(estudiante=self.estudiante, cuestionario=cuestionario)

    def enviar(self, evaluacion, respuestas, calcular=True):
        return self.client.post(
            f"/api/evaluaciones/{evaluacion.pk}/responder/",
            data=json.dumps({"respuestas": respuestas, "calcular": calcular}),
            content_type="application/json",
        )

    def test_vark_guarda_y_finaliza(self):
        evaluacion = self.nuevo(self.vark)
        respuesta = self.enviar(evaluacion, [{"pregunta": self.pregunta_v.pk,
            "opciones": [self.opcion_v.pk, self.opcion_a.pk]}])
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.FINALIZADA)
        puntajes = dict(Resultado.objects.get(evaluacion=evaluacion).puntajes.values_list("dimension", "puntaje"))
        self.assertEqual(puntajes["V"], 1)
        self.assertEqual(puntajes["A"], 1)

    def test_personalidad_guarda_puntos_y_finaliza(self):
        evaluacion = self.nuevo(self.personalidad)
        respuesta = self.enviar(evaluacion, [{"pregunta": self.pregunta_p.pk,
            "selecciones": [{"opcion": self.opcion_e.pk, "puntos": 7},
                            {"opcion": self.opcion_i.pk, "puntos": 3}]}])
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.FINALIZADA)
        seleccionadas = list(Respuesta.objects.get(evaluacion=evaluacion).selecciones.values_list("puntos", flat=True))
        self.assertEqual(sorted(seleccionadas), [3, 7])

    def test_personalidad_invalida_no_guarda(self):
        evaluacion = self.nuevo(self.personalidad)
        respuesta = self.enviar(evaluacion, [{"pregunta": self.pregunta_p.pk,
            "selecciones": [{"opcion": self.opcion_e.pk, "puntos": 5},
                            {"opcion": self.opcion_i.pk, "puntos": 5}]}])
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Respuesta.objects.filter(evaluacion=evaluacion).exists())
        self.assertFalse(Resultado.objects.filter(evaluacion=evaluacion).exists())

    def test_resultado_finalizado_no_se_recalcula(self):
        evaluacion = self.nuevo(self.vark)
        self.assertEqual(self.enviar(evaluacion, [{"pregunta": self.pregunta_v.pk,
            "opciones": [self.opcion_v.pk]}]).status_code, 200)
        respuesta = self.client.post(f"/api/evaluaciones/{evaluacion.pk}/calcular/",
            data=json.dumps({}), content_type="application/json")
        self.assertEqual(respuesta.status_code, 400)

    def test_calcular_endpoint_devuelve_resultado(self):
        evaluacion = self.nuevo(self.vark)
        from apps.assessments.services import guardar_respuesta
        guardar_respuesta(
            evaluacion.pk,
            self.pregunta_v.pk,
            [self.opcion_v.pk, self.opcion_a.pk],
        )

        respuesta = self.client.post(
            f"/api/evaluaciones/{evaluacion.pk}/calcular/",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        payload = respuesta.json()
        self.assertIn("evaluacion", payload)
        self.assertIn("resultado", payload)
        self.assertIn("puntajes", payload["resultado"])
        self.assertEqual(payload["evaluacion"]["estado"], Evaluacion.Estado.FINALIZADA)
        puntajes = {p["dimension"]: p["puntaje"] for p in payload["resultado"]["puntajes"]}
        self.assertEqual(puntajes["V"], 1)
        self.assertEqual(puntajes["A"], 1)

    def test_usuario_sin_permisos_no_modifica(self):
        usuario = get_user_model().objects.create_user(username="usuario_api_test", password="x")
        self.client.force_login(usuario)
        evaluacion = self.nuevo(self.vark)
        respuesta = self.enviar(evaluacion, [{"pregunta": self.pregunta_v.pk,
            "opciones": [self.opcion_v.pk]}])
        self.assertEqual(respuesta.status_code, 403)