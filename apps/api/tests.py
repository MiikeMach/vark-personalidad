"""Pruebas de integración HTTP de guardado y finalización.

Convenciones:
- Cada clase es independiente y crea en setUpTestData solo lo que necesita.
- Los tests de auth usan self.client.post("/api/auth/login/", ...) porque el
  login es el objeto de la prueba; el resto usa force_login para ser rápido.
- RequireStaffTests verifica 401 (sin sesión), 403 (no staff) y que staff
  pase el decorador (404 por id inexistente, nunca 401/403).
- ContactoAPITests usa locmem.EmailBackend solo en esa clase, sin tocar
  settings.py ni .env, para inspeccionar mail.outbox.
- PdfAPITests comprueba cabecera %PDF-, Content-Type y nombre de archivo;
  no extrae texto (sin dependencias nuevas).
"""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.assessments.models import Evaluacion, Respuesta
from apps.questionnaires.models import Cuestionario, Pregunta, Opcion
from apps.results.models import Resultado
from apps.students.models import Grupo, Estudiante


# =====================================================================
# Flujo existente (se mantiene intacto, incluido el test de /calcular/)
# =====================================================================

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


class EvaluacionEstudianteAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo = Grupo.objects.create(clave="PUBLICO", nombre="Grupo público")
        cls.estudiante = Estudiante.objects.create(
            matricula="PUB-1", nombres="Ana", apellidos="Prueba", grupo=grupo
        )
        cls.otro = Estudiante.objects.create(
            matricula="PUB-2", nombres="Luis", apellidos="Prueba", grupo=grupo
        )
        cls.cuestionario = Cuestionario.objects.create(titulo="VARK", tipo="VARK")
        cls.pregunta = Pregunta.objects.create(cuestionario=cls.cuestionario, texto="P", orden=1)
        cls.opcion = Opcion.objects.create(pregunta=cls.pregunta, texto="V", dimension="V", orden=1)

    def iniciar(self, estudiante):
        return self.client.post(
            "/api/evaluaciones/iniciar/",
            data=json.dumps({"estudiante": estudiante.pk, "cuestionario": self.cuestionario.pk}),
            content_type="application/json",
        )

    def responder(self, evaluacion):
        return self.client.post(
            f"/api/evaluaciones/{evaluacion.pk}/responder/",
            data=json.dumps({
                "respuestas": [{"pregunta": self.pregunta.pk, "opciones": [self.opcion.pk]}],
                "calcular": True,
            }),
            content_type="application/json",
        )

    def test_estudiante_sin_cuenta_guarda_su_evaluacion(self):
        inicio = self.iniciar(self.estudiante)
        self.assertEqual(inicio.status_code, 201)
        self.assertEqual(self.iniciar(self.estudiante).json()["evaluacion"]["id"], inicio.json()["evaluacion"]["id"])
        evaluacion = Evaluacion.objects.get(pk=inicio.json()["evaluacion"]["id"])
        respuesta = self.responder(evaluacion)
        self.assertEqual(respuesta.status_code, 200)
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.FINALIZADA)
        self.assertEqual(Resultado.objects.get(evaluacion=evaluacion).puntajes.get(dimension="V").puntaje, 1)

    def test_otra_sesion_no_puede_responder_ni_reutilizar_evaluacion(self):
        inicio = self.iniciar(self.estudiante)
        evaluacion = Evaluacion.objects.get(pk=inicio.json()["evaluacion"]["id"])
        otro_cliente = Client()
        respuesta = otro_cliente.post(
            f"/api/evaluaciones/{evaluacion.pk}/responder/",
            data=json.dumps({"respuestas": [{"pregunta": self.pregunta.pk, "opciones": [self.opcion.pk]}]}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Respuesta.objects.filter(evaluacion=evaluacion).exists())
        self.assertFalse(Resultado.objects.filter(evaluacion=evaluacion).exists())
        nuevo = otro_cliente.post(
            "/api/evaluaciones/iniciar/",
            data=json.dumps({"estudiante": self.estudiante.pk, "cuestionario": self.cuestionario.pk}),
            content_type="application/json",
        )
        self.assertEqual(nuevo.status_code, 201)
        self.assertNotEqual(nuevo.json()["evaluacion"]["id"], evaluacion.pk)

    def test_estudiante_inactivo_no_puede_iniciar_ni_guardar(self):
        inicio = self.iniciar(self.estudiante)
        evaluacion = Evaluacion.objects.get(pk=inicio.json()["evaluacion"]["id"])
        self.estudiante.activo = False
        self.estudiante.save(update_fields=["activo"])
        self.assertEqual(self.iniciar(self.estudiante).status_code, 403)
        self.assertEqual(self.responder(evaluacion).status_code, 403)

    def test_autenticacion_y_escritura_requieren_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/")
        login = {"username": "alumno", "password": "clave-de-prueba"}
        self.assertEqual(client.post("/api/auth/login/", json.dumps(login), content_type="application/json").status_code, 403)
        token = client.cookies["csrftoken"].value
        data = json.dumps({"estudiante": self.estudiante.pk, "cuestionario": self.cuestionario.pk})
        self.assertEqual(client.post("/api/evaluaciones/iniciar/", data, content_type="application/json").status_code, 403)
        inicio = client.post("/api/evaluaciones/iniciar/", data, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(inicio.status_code, 201)
        url = f"/api/evaluaciones/{inicio.json()['evaluacion']['id']}/responder/"
        answers = json.dumps({"respuestas": [{"pregunta": self.pregunta.pk, "opciones": [self.opcion.pk]}], "calcular": True})
        self.assertEqual(client.post(url, answers, content_type="application/json").status_code, 403)
        self.assertEqual(client.post(url, answers, content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_personalidad_sin_cuenta_guarda_y_calcula(self):
        cuestionario = Cuestionario.objects.create(titulo="Personalidad", tipo="PERSONALIDAD")
        pregunta = Pregunta.objects.create(cuestionario=cuestionario, texto="P", orden=1)
        opcion_e = Opcion.objects.create(pregunta=pregunta, texto="E", dimension="E", orden=1)
        opcion_i = Opcion.objects.create(pregunta=pregunta, texto="I", dimension="I", orden=2)
        inicio = self.client.post(
            "/api/evaluaciones/iniciar/",
            data=json.dumps({"estudiante": self.otro.pk, "cuestionario": cuestionario.pk}),
            content_type="application/json",
        )
        self.assertEqual(inicio.status_code, 201)
        evaluacion_id = inicio.json()["evaluacion"]["id"]
        respuesta = self.client.post(
            f"/api/evaluaciones/{evaluacion_id}/responder/",
            data=json.dumps({"respuestas": [{"pregunta": pregunta.pk, "selecciones": [
                {"opcion": opcion_e.pk, "puntos": 7}, {"opcion": opcion_i.pk, "puntos": 3},
            ]}], "calcular": True}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(Resultado.objects.get(evaluacion_id=evaluacion_id).puntajes.get(dimension="E").puntaje, 7)


# =====================================================================
# Autenticación por API
# =====================================================================

class AuthAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.activo = get_user_model().objects.create_user(
            username="auth_activo", password="clave-auth-2026", is_staff=True,
        )
        cls.inactivo = get_user_model().objects.create_user(
            username="auth_inactivo", password="clave-auth-2026", is_active=False,
        )

    def test_me_sin_sesion_401(self):
        respuesta = self.client.get("/api/auth/me/")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json(), {"user": None})

    def test_login_ok_200_y_me_200(self):
        respuesta = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "auth_activo", "password": "clave-auth-2026"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        payload = respuesta.json()
        self.assertEqual(payload["user"]["username"], "auth_activo")
        self.assertTrue(payload["user"]["is_staff"])

        respuesta = self.client.get("/api/auth/me/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["user"]["username"], "auth_activo")

    def test_login_mal_401(self):
        respuesta = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "auth_activo", "password": "incorrecta"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json(), {"detail": "Credenciales inválidas."})

    def test_login_usuario_inactivo_401(self):
        respuesta = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "auth_inactivo", "password": "clave-auth-2026"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json(), {"detail": "Credenciales inválidas."})

    def test_logout_200_y_me_401(self):
        self.client.force_login(self.activo)
        respuesta = self.client.post("/api/auth/logout/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"detail": "Sesión cerrada."})

        respuesta = self.client.get("/api/auth/me/")
        self.assertEqual(respuesta.status_code, 401)


# =====================================================================
# Control de acceso sobre /responder/ y /calcular/
# =====================================================================

class RequireStaffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="rs_staff", password="clave-rs-2026", is_staff=True,
        )
        cls.no_staff = get_user_model().objects.create_user(
            username="rs_nostaff", password="clave-rs-2026", is_staff=False,
        )

    def _post_responder(self, pk=999999):
        return self.client.post(
            f"/api/evaluaciones/{pk}/responder/",
            data=json.dumps({"respuestas": []}),
            content_type="application/json",
        )

    def _post_calcular(self, pk=999999):
        return self.client.post(
            f"/api/evaluaciones/{pk}/calcular/",
            data=json.dumps({}),
            content_type="application/json",
        )

    def test_responder_evaluacion_inexistente_404(self):
        self.assertEqual(self._post_responder().status_code, 404)

    def test_responder_no_staff_evaluacion_inexistente_404(self):
        self.client.force_login(self.no_staff)
        self.assertEqual(self._post_responder().status_code, 404)

    def test_calcular_sin_sesion_401(self):
        self.assertEqual(self._post_calcular().status_code, 401)

    def test_calcular_no_staff_403(self):
        self.client.force_login(self.no_staff)
        self.assertEqual(self._post_calcular().status_code, 403)

    def test_calcular_staff_pasa_y_da_404_si_no_existe(self):
        self.client.force_login(self.staff)
        respuesta = self._post_calcular()
        # require_staff deja pasar; get_object_or_404 responde 404.
        self.assertEqual(respuesta.status_code, 404)


# =====================================================================
# Cuestionario completo
# =====================================================================

class CuestionarioCompletoAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cuestionario = Cuestionario.objects.create(
            titulo="Completo API", tipo=Cuestionario.Tipo.VARK,
        )
        cls.pregunta = Pregunta.objects.create(
            cuestionario=cls.cuestionario, texto="P1", orden=1,
        )
        Opcion.objects.create(pregunta=cls.pregunta, texto="V", dimension="V", orden=1)
        Opcion.objects.create(pregunta=cls.pregunta, texto="A", dimension="A", orden=2)

    def test_completo_200_con_preguntas_y_opciones(self):
        respuesta = self.client.get(f"/api/cuestionarios/{self.cuestionario.pk}/completo/")
        self.assertEqual(respuesta.status_code, 200)
        payload = respuesta.json()
        self.assertEqual(payload["id"], self.cuestionario.pk)
        self.assertEqual(len(payload["preguntas"]), 1)
        self.assertEqual(len(payload["preguntas"][0]["opciones"]), 2)
        self.assertEqual(
            [o["dimension"] for o in payload["preguntas"][0]["opciones"]],
            ["V", "A"],
        )

    def test_completo_404_si_no_existe(self):
        respuesta = self.client.get("/api/cuestionarios/999999/completo/")
        self.assertEqual(respuesta.status_code, 404)


# =====================================================================
# Agregados
# =====================================================================

class AgregadosAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo = Grupo.objects.create(clave="AGR", nombre="Grupo agregados")
        cls.estudiante = Estudiante.objects.create(
            matricula="AGR-001", nombres="Ana", apellidos="Agregados", grupo=cls.grupo,
        )
        cls.cuestionario = Cuestionario.objects.create(
            titulo="VARK agregados", tipo=Cuestionario.Tipo.VARK,
        )
        evaluacion = Evaluacion.objects.create(
            estudiante=cls.estudiante, cuestionario=cls.cuestionario,
        )
        pregunta = Pregunta.objects.create(
            cuestionario=cls.cuestionario, texto="P1", orden=1,
        )
        opcion_v = Opcion.objects.create(pregunta=pregunta, texto="V", dimension="V", orden=1)
        opcion_a = Opcion.objects.create(pregunta=pregunta, texto="A", dimension="A", orden=2)
        respuesta = Respuesta.objects.create(evaluacion=evaluacion, pregunta=pregunta)
        from apps.assessments.models import SeleccionRespuesta
        SeleccionRespuesta.objects.create(respuesta=respuesta, opcion=opcion_v)
        SeleccionRespuesta.objects.create(respuesta=respuesta, opcion=opcion_a)

        from apps.results.services import guardar_resultado
        # guardar_resultado exige estado EN_PROGRESO (no valida respuestas aquí).
        guardar_resultado(evaluacion.pk)

    def test_total_vark_200_estructura(self):
        respuesta = self.client.get("/api/resultados/agregados/?alcance=total&tipo=VARK")
        self.assertEqual(respuesta.status_code, 200)
        payload = respuesta.json()
        self.assertEqual(payload["alcance"], "total")
        self.assertEqual(payload["tipo"], "VARK")
        self.assertGreaterEqual(payload["n_resultados"], 1)
        self.assertEqual(
            [d["dimension"] for d in payload["dimensiones"]],
            ["V", "A", "R", "K"],
        )
        self.assertIn("distribucion_dominante", payload)

    def test_grupal_vark_200(self):
        respuesta = self.client.get(
            f"/api/resultados/agregados/?alcance=grupal&grupo={self.grupo.pk}&tipo=VARK"
        )
        self.assertEqual(respuesta.status_code, 200)
        payload = respuesta.json()
        self.assertEqual(payload["alcance"], "grupal")
        self.assertGreaterEqual(payload["n_resultados"], 1)

    def test_alcance_invalido_400(self):
        respuesta = self.client.get("/api/resultados/agregados/?alcance=foo&tipo=VARK")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("alcance", respuesta.json()["detail"])

    def test_tipo_invalido_400(self):
        respuesta = self.client.get("/api/resultados/agregados/?alcance=total&tipo=XYZ")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("tipo", respuesta.json()["detail"])

    def test_individual_sin_estudiante_400(self):
        respuesta = self.client.get("/api/resultados/agregados/?alcance=individual&tipo=VARK")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("estudiante", respuesta.json()["detail"])


# =====================================================================
# Búsqueda
# =====================================================================

class BuscarAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo = Grupo.objects.create(clave="BQ", nombre="Grupo búsqueda")
        cls.estudiante = Estudiante.objects.create(
            matricula="BQ-001", nombres="Beto", apellidos="Búsqueda", grupo=cls.grupo,
        )

    def test_q_valido_200_devuelve_estudiantes_y_grupos(self):
        respuesta = self.client.get("/api/buscar/?q=BQ")
        self.assertEqual(respuesta.status_code, 200)
        payload = respuesta.json()
        self.assertEqual(payload["q"], "BQ")
        self.assertEqual(len(payload["estudiantes"]), 1)
        self.assertEqual(payload["estudiantes"][0]["matricula"], "BQ-001")
        self.assertEqual(len(payload["grupos"]), 1)
        self.assertEqual(payload["grupos"][0]["clave"], "BQ")

    def test_q_corto_400(self):
        respuesta = self.client.get("/api/buscar/?q=B")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("q", respuesta.json()["detail"])

    def test_q_ausente_400(self):
        respuesta = self.client.get("/api/buscar/")
        self.assertEqual(respuesta.status_code, 400)


# =====================================================================
# PDF (cabecera, Content-Type, Content-Disposition, bytes)
# =====================================================================

class PdfAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo = Grupo.objects.create(clave="PDF", nombre="Grupo PDF")
        cls.estudiante = Estudiante.objects.create(
            matricula="PDF-001", nombres="Pía", apellidos="PDF", grupo=cls.grupo,
        )
        cls.cuestionario = Cuestionario.objects.create(
            titulo="VARK PDF", tipo=Cuestionario.Tipo.VARK,
        )
        cls.evaluacion = Evaluacion.objects.create(
            estudiante=cls.estudiante, cuestionario=cls.cuestionario,
        )
        pregunta = Pregunta.objects.create(
            cuestionario=cls.cuestionario, texto="P1", orden=1,
        )
        opcion_v = Opcion.objects.create(pregunta=pregunta, texto="V", dimension="V", orden=1)
        respuesta = Respuesta.objects.create(evaluacion=cls.evaluacion, pregunta=pregunta)
        from apps.assessments.models import SeleccionRespuesta
        SeleccionRespuesta.objects.create(respuesta=respuesta, opcion=opcion_v)

        from apps.results.services import guardar_resultado
        cls.resultado = guardar_resultado(cls.evaluacion.pk)

    def _es_pdf(self, contenido):
        return contenido[:5] == b"%PDF-"

    def test_pdf_individual_200_pdf_bytes(self):
        respuesta = self.client.get(f"/api/resultados/{self.resultado.pk}/pdf/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        disposicion = respuesta["Content-Disposition"]
        self.assertIn(f"ficha_resultado_{self.resultado.pk}.pdf", disposicion)
        self.assertGreater(len(respuesta.content), 0)
        self.assertTrue(self._es_pdf(respuesta.content))

    def test_pdf_multiple_200_pdf_bytes(self):
        respuesta = self.client.get("/api/resultados/pdf/?alcance=total&tipo=VARK")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        disposicion = respuesta["Content-Disposition"]
        self.assertIn("ficha_total_vark.pdf", disposicion)
        self.assertGreater(len(respuesta.content), 0)
        self.assertTrue(self._es_pdf(respuesta.content))


# =====================================================================
# Contacto (locmem.EmailBackend solo en esta clase)
# =====================================================================

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ContactoAPITests(TestCase):
    def setUp(self):
        mail.outbox = []

    def _post(self, payload):
        return self.client.post(
            "/api/contacto/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_valido_201_y_envia_correo(self):
        respuesta = self._post({
            "nombre": "Prueba Verif",
            "correo": "prueba@example.test",
            "asunto": "Asunto de prueba",
            "mensaje": "Mensaje de prueba con longitud suficiente.",
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(respuesta.json(), {"detail": "Mensaje enviado correctamente."})
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn("[Contacto VARK] Asunto de prueba", correo.subject)
        self.assertIn("Prueba Verif", correo.body)
        self.assertIn("prueba@example.test", correo.body)

    def test_invalido_400_con_errores_por_campo(self):
        respuesta = self._post({
            "nombre": "",
            "correo": "no-es-correo",
            "asunto": "",
            "mensaje": "corto",
        })
        self.assertEqual(respuesta.status_code, 400)
        detalle = respuesta.json()["detail"]
        for campo in ("nombre", "correo", "asunto", "mensaje"):
            self.assertIn(campo, detalle)
        self.assertEqual(len(mail.outbox), 0)

    def test_fallo_send_mail_500(self):
        with patch("apps.api.views.send_mail", side_effect=Exception("boom")):
            respuesta = self._post({
                "nombre": "Prueba Verif",
                "correo": "prueba@example.test",
                "asunto": "Asunto",
                "mensaje": "Mensaje con longitud suficiente.",
            })
        self.assertEqual(respuesta.status_code, 500)
        self.assertIn("No se pudo enviar", respuesta.json()["detail"])
        self.assertEqual(len(mail.outbox), 0)