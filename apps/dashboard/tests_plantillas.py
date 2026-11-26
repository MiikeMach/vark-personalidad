"""Pruebas rápidas (sin navegador) de las plantillas y archivos estáticos del frontend."""

import re

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


def estaticos_referenciados(html):
    """Rutas de /static/ que carga una página (sin el ?v=)."""
    return sorted({ruta for ruta in re.findall(r'(?:src|href)="/static/([^"?#]+)', html)})


class PaginaPublicaPlantillaTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse("home")).content.decode()

    def test_tiene_las_tres_secciones_y_el_menu(self):
        for seccion in ("page-inicio", "page-instrumentos", "page-guia"):
            self.assertIn(f'id="{seccion}"', self.html)
        for ruta in ('data-route="inicio"', 'data-route="instrumentos"', 'data-route="guia"',
                     'data-scroll="guideVideo"', 'data-scroll="contacto"'):
            self.assertIn(ruta, self.html)

    def test_formulario_de_evaluacion_con_grupo_estudiante_y_cuestionario(self):
        for campo in ('id="groupSelect"', 'id="studentSelect"', 'id="questionnaireSelect"',
                      'id="questionnairePreview"', "csrfmiddlewaretoken"):
            self.assertIn(campo, self.html)

    def test_resultado_ofrece_ficha_pdf_descarga_y_nueva_evaluacion(self):
        for boton in ('id="viewFicha"', 'id="downloadPdf"', 'id="newAssessment"', 'id="assessmentScores"'):
            self.assertIn(boton, self.html)

    def test_guia_con_video_y_formulario_de_contacto(self):
        self.assertIn('id="introVideo"', self.html)
        self.assertIn("dashboard/video/brujula-intro.mp4", self.html)
        self.assertIn("VIDEO DE INTRODUCCIÓN<", self.html)
        self.assertIn('id="videoPlaceholder"', self.html)
        formulario = re.search(r'<form class="contact-form".*?</form>', self.html, re.S).group(0)
        for campo in ('name="nombre"', 'name="correo"', 'type="email"', 'name="asunto"', 'name="mensaje"'):
            self.assertIn(campo, formulario)
        # El formulario se envía a la API de contacto; ya no abre el programa de correo.
        self.assertNotIn("mailto:", self.html)

    def test_es_responsivo(self):
        self.assertIn('name="viewport" content="width=device-width, initial-scale=1"', self.html)
        self.assertIn('id="menuToggle"', self.html)

    def test_archivos_estaticos_existen(self):
        rutas = estaticos_referenciados(self.html)
        for esperado in ("dashboard/styles.css", "dashboard/app.js", "dashboard/ficha.js",
                         "dashboard/vendor/jspdf.umd.min.js"):
            self.assertIn(esperado, rutas)
        for ruta in rutas:
            if ruta.endswith(".mp4"):
                continue  # El video se agrega aparte; la página muestra un aviso mientras no exista.
            with self.subTest(ruta=ruta):
                self.assertIsNotNone(finders.find(ruta), f"No existe el archivo estático {ruta}")

    def test_jspdf_se_carga_antes_que_la_ficha_y_la_app(self):
        posiciones = [self.html.index(nombre) for nombre in ("jspdf.umd.min.js", "dashboard/ficha.js", "dashboard/app.js")]
        self.assertEqual(posiciones, sorted(posiciones))


class PanelPlantillasTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("admin_t", password="x")

    def test_tablero_carga_ficha_pdf_y_filtros_de_alcance(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("admin:index")).content.decode()
        for elemento in ('id="groupFilter"', 'id="studentFilter"', 'id="scopeLabel"', 'id="reportButton"',
                         'id="showAllResults"', 'id="varkChart"', 'id="personalityChart"'):
            self.assertIn(elemento, html)
        rutas = estaticos_referenciados(html)
        for esperado in ("dashboard/vendor/jspdf.umd.min.js", "dashboard/ficha.js", "admin/js/brujuela-results.js"):
            self.assertIn(esperado, rutas)
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertIsNotNone(finders.find(ruta), f"No existe el archivo estático {ruta}")

    def test_login_rediseñado(self):
        html = self.client.get(reverse("admin:login")).content.decode()
        self.assertIn("bru-login-card", html)
        self.assertIn("Entrar al panel", html)
        self.assertIn(reverse("home"), html)

    def test_cerrar_sesion_muestra_despedida_y_redirige_al_inicio(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("admin:logout"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "registration/logged_out.html")
        html = respuesta.content.decode()
        self.assertIn("Sesión cerrada", html)
        self.assertIn('href="/#inicio"', html)
        self.assertIn('const destino = "/#inicio"', html)
        self.assertIn('id="logoutStay"', html)
        self.assertNotIn('class="breadcrumbs"', html)
        # La sesión quedó cerrada.
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)
