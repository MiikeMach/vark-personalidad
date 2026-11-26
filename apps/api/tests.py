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
from django.test import TestCase, override_settings, Client

from apps.assessments.models import Evaluacion, Respuesta
from apps.questionnaires.models import Cuestionario, Pregunta, Opcion
from apps.results.models import Resultado
from apps.students.models import Grupo, Estudiante


# =====================================================================
# Flujo existente (se mantiene intacto)
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

    def test_login_sin_csrf_falla_con_enforce(self):
        client = Client(enforce_csrf_checks=True)
        resp = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "auth_activo", "password": "clave-auth-2026"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_obtener_csrf_y_luego_login_ok(self):
        client = Client(enforce_csrf_checks=True)
        
        resp = client.get("/api/auth/csrf/")
        self.assertEqual(resp.status_code, 200)
        csrf_token = client.cookies.get("csrftoken").value
        
        resp = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "auth_activo", "password": "clave-auth-2026"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(resp.status_code, 200)


# =====================================================================
# require_staff
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

    def test_responder_sin_sesion_401(self):
        self.assertEqual(self._post_responder().status_code, 401)

    def test_responder_no_staff_403(self):
        self.client.force_login(self.no_staff)
        self.assertEqual(self._post_responder().status_code, 403)

    def test_calcular_sin_sesion_401(self):
        self.assertEqual(self._post_calcular().status_code, 401)

    def test_calcular_no_staff_403(self):
        self.client.force_login(self.no_staff)
        self.assertEqual(self._post_calcular().status_code, 403)

    def test_calcular_staff_pasa_y_da_404_si_no_existe(self):
        self.client.force_login(self.staff)
        respuesta = self._post_calcular()
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
# Agregados (Actualizado para privacidad)
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
        
        # Estudiante 1 y su evaluación
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
        guardar_resultado(evaluacion.pk)

        # Estudiante 2 y su evaluación (Añadido para pasar la regla de privacidad)
        cls.estudiante2 = Estudiante.objects.create(
            matricula="AGR-002", nombres="Luis", apellidos="Agregados", grupo=cls.grupo,
        )
        evaluacion2 = Evaluacion.objects.create(
            estudiante=cls.estudiante2, cuestionario=cls.cuestionario,
        )
        respuesta2 = Respuesta.objects.create(evaluacion=evaluacion2, pregunta=pregunta)
        SeleccionRespuesta.objects.create(respuesta=respuesta2, opcion=opcion_v)
        guardar_resultado(evaluacion2.pk)

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff_agr", password="x", is_staff=True
        )
        self.client.force_login(self.staff)

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
        # Al tener 2 estudiantes en el grupo, ahora debe dar 200
        respuesta = self.client.get(
            f"/api/resultados/agregados/?alcance=grupal&grupo={self.grupo.pk}&tipo=VARK"
        )
        self.assertEqual(respuesta.status_code, 200)
        payload = respuesta.json()
        self.assertEqual(payload["alcance"], "grupal")
        self.assertGreaterEqual(payload["n_resultados"], 1)

    def test_grupal_privacidad_minimo_dos_estudiantes(self):
        # Creamos un grupo nuevo con un solo estudiante
        grupo_p = Grupo.objects.create(clave="PRI", nombre="Privado")
        estudiante_p = Estudiante.objects.create(
            matricula="PRI-001", nombres="Solo", apellidos="Uno", grupo=grupo_p,
        )
        Evaluacion.objects.create(estudiante=estudiante_p, cuestionario=self.cuestionario)
        
        respuesta = self.client.get(
            f"/api/resultados/agregados/?alcance=grupal&grupo={grupo_p.pk}&tipo=VARK"
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("suficientes estudiantes", respuesta.json()["detail"])

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
        cls.staff = get_user_model().objects.create_user(
            username="staff_bq", password="x", is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.staff)

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
# PDF
# =====================================================================

class PdfAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="staff_pdf", password="x", is_staff=True
        )
        cls.grupo = Grupo.objects.create(clave="PDF", nombre="Grupo PDF")
        cls.estudiante = Estudiante.objects.create(
            matricula="PDF-001", nombres="Pía", apellidos="PDF", grupo=cls.grupo,
        )
        
        # Datos para VARK
        cls.cuestionario_vark = Cuestionario.objects.create(
            titulo="VARK PDF", tipo=Cuestionario.Tipo.VARK,
        )
        cls.evaluacion_vark = Evaluacion.objects.create(
            estudiante=cls.estudiante, cuestionario=cls.cuestionario_vark,
        )
        pregunta_v = Pregunta.objects.create(cuestionario=cls.cuestionario_vark, texto="P1", orden=1)
        opcion_v = Opcion.objects.create(pregunta=pregunta_v, texto="V", dimension="V", orden=1)
        resp_v = Respuesta.objects.create(evaluacion=cls.evaluacion_vark, pregunta=pregunta_v)
        from apps.assessments.models import SeleccionRespuesta
        SeleccionRespuesta.objects.create(respuesta=resp_v, opcion=opcion_v)
        from apps.results.services import guardar_resultado
        cls.resultado_vark = guardar_resultado(cls.evaluacion_vark.pk)

        # Datos para Personalidad
        cls.cuestionario_pers = Cuestionario.objects.create(
            titulo="Pers PDF", tipo=Cuestionario.Tipo.PERSONALIDAD,
        )
        cls.evaluacion_pers = Evaluacion.objects.create(
            estudiante=cls.estudiante, cuestionario=cls.cuestionario_pers,
        )
        pregunta_p = Pregunta.objects.create(cuestionario=cls.cuestionario_pers, texto="P1", orden=1)
        op_e = Opcion.objects.create(pregunta=pregunta_p, texto="E", dimension="E", orden=1)
        op_i = Opcion.objects.create(pregunta=pregunta_p, texto="I", dimension="I", orden=2)
        resp_p = Respuesta.objects.create(evaluacion=cls.evaluacion_pers, pregunta=pregunta_p)
        SeleccionRespuesta.objects.create(respuesta=resp_p, opcion=op_e, puntos=7)
        SeleccionRespuesta.objects.create(respuesta=resp_p, opcion=op_i, puntos=3)
        cls.resultado_pers = guardar_resultado(cls.evaluacion_pers.pk)

    def setUp(self):
        self.client.force_login(self.staff)

    def _es_pdf(self, contenido):
        return contenido[:5] == b"%PDF-"

    def test_pdf_individual_200_pdf_bytes(self):
        respuesta = self.client.get(f"/api/resultados/{self.resultado_vark.pk}/pdf/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn(f"ficha_resultado_{self.resultado_vark.pk}.pdf", respuesta["Content-Disposition"])
        self.assertTrue(self._es_pdf(respuesta.content))

    def test_pdf_multiple_total_vark(self):
        respuesta = self.client.get("/api/resultados/pdf/?alcance=total&tipo=VARK")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("ficha_total_vark.pdf", respuesta["Content-Disposition"])
        self.assertTrue(self._es_pdf(respuesta.content))

    def test_pdf_multiple_grupal_vark(self):
        respuesta = self.client.get(f"/api/resultados/pdf/?alcance=grupal&grupo={self.grupo.pk}&tipo=VARK")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(f"ficha_grupal_vark_grupo{self.grupo.pk}.pdf", respuesta["Content-Disposition"])
        self.assertTrue(self._es_pdf(respuesta.content))

    def test_pdf_multiple_individual_vark(self):
        respuesta = self.client.get(f"/api/resultados/pdf/?alcance=individual&estudiante={self.estudiante.pk}&tipo=VARK")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("ficha_individual_vark.pdf", respuesta["Content-Disposition"])
        self.assertTrue(self._es_pdf(respuesta.content))

    def test_pdf_multiple_total_personalidad(self):
        respuesta = self.client.get("/api/resultados/pdf/?alcance=total&tipo=PERSONALIDAD")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("ficha_total_personalidad.pdf", respuesta["Content-Disposition"])
        self.assertTrue(self._es_pdf(respuesta.content))


# =====================================================================
# Contacto
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

    def test_mensaje_muy_corto_400(self):
        respuesta = self._post({
            "nombre": "Test",
            "correo": "test@example.com",
            "asunto": "Hola",
            "mensaje": "Corto",
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("mensaje", respuesta.json()["detail"])
        self.assertIn("Mínimo 10 caracteres.", respuesta.json()["detail"]["mensaje"])

    def test_mensaje_muy_largo_400(self):
        respuesta = self._post({
            "nombre": "Test",
            "correo": "test@example.com",
            "asunto": "Hola",
            "mensaje": "A" * 5001,
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("mensaje", respuesta.json()["detail"])
        self.assertIn("Máximo 5000 caracteres.", respuesta.json()["detail"]["mensaje"])

    def test_nombre_muy_largo_400(self):
        respuesta = self._post({
            "nombre": "A" * 101,
            "correo": "test@example.com",
            "asunto": "Hola",
            "mensaje": "Este es un mensaje de prueba válido.",
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("nombre", respuesta.json()["detail"])


# =====================================================================
# Contratos y manejo de errores
# =====================================================================

class ManejoErroresAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="staff_err", password="x", is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def test_json_invalido_400(self):
        resp = self.client.post(
            "/api/evaluaciones/iniciar/",
            data="{esto no es json",
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("JSON inválido", resp.json()["detail"])

    def test_json_raiz_lista_400(self):
        resp = self.client.post(
            "/api/evaluaciones/iniciar/",
            data=json.dumps([1, 2, 3]),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("debe ser un objeto", resp.json()["detail"])

    def test_iniciar_tipos_incorrectos_400(self):
        resp = self.client.post(
            "/api/evaluaciones/iniciar/",
            data=json.dumps({"estudiante": "1", "cuestionario": 2}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("numéricos", resp.json()["detail"])

    def test_responder_items_invalidos_400(self):
        resp = self.client.post(
            "/api/evaluaciones/1/responder/",
            data=json.dumps({"respuestas": "no-es-una-lista"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("debe ser una lista", resp.json()["detail"])

    def test_contacto_raiz_lista_400(self):
        resp = self.client.post(
            "/api/contacto/",
            data=json.dumps([{"nombre": "test"}]),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("debe ser un objeto", resp.json()["detail"])