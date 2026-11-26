"""Pruebas funcionales del frontend con un navegador real (Playwright).

Cubren el sitio público (elegir cuestionario, contestar, guardar y ver el
resultado) y el tablero de resultados del panel (estadísticas, gráfica,
búsqueda y ficha imprimible).

Requisitos: ``pip install -r requirements-dev.txt``. No hace falta descargar
navegadores: se usa Microsoft Edge o Google Chrome instalados en el equipo
(variable ``E2E_BROWSER_CHANNEL`` para elegir; por defecto ``msedge``).
Si Playwright no está instalado, estas pruebas se omiten.
"""

import os
import re
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.test import tag

from apps.assessments.models import Evaluacion, Respuesta, SeleccionRespuesta
from apps.assessments.services import guardar_respuesta, guardar_respuesta_personalidad
from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from apps.results.models import Resultado
from apps.results.services import finalizar_evaluacion
from apps.students.models import Estudiante, Grupo

try:
    from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright
except ImportError:  # pragma: no cover - depende del entorno
    # Se definen igualmente para que otros módulos (tests_frontend_e2e) puedan
    # importarlos sin fallar; las clases quedan omitidas por skipIf.
    sync_playwright = None
    expect = None
    PlaywrightError = Exception

TIEMPO = 10_000  # ms


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

def crear_cuestionario_vark(titulo="Estilos de aprendizaje", activo=True):
    cuestionario = Cuestionario.objects.create(titulo=titulo, tipo="VARK", activo=activo)
    textos = {"V": "Con imágenes", "A": "Escuchando", "R": "Leyendo", "K": "Practicando"}
    for orden, pregunta_texto in enumerate(("¿Cómo prefieres aprender?", "¿Cómo repasas?"), start=1):
        pregunta = Pregunta.objects.create(cuestionario=cuestionario, texto=pregunta_texto, orden=orden)
        for indice, (dimension, texto) in enumerate(textos.items(), start=1):
            Opcion.objects.create(pregunta=pregunta, texto=f"{texto} ({orden})", dimension=dimension, orden=indice)
    return cuestionario


def crear_cuestionario_personalidad(titulo="Preferencias personales"):
    cuestionario = Cuestionario.objects.create(titulo=titulo, tipo="PERSONALIDAD")
    pares = (("E", "I", "Convivir en grupo", "Pensar a solas"),
             ("S", "N", "Datos concretos", "Ideas posibles"),
             ("T", "F", "Lógica", "Valores"),
             ("J", "P", "Planear", "Improvisar"))
    for orden, (uno, dos, texto_uno, texto_dos) in enumerate(pares, start=1):
        pregunta = Pregunta.objects.create(cuestionario=cuestionario, texto=f"Prefieres… ({orden})", orden=orden)
        Opcion.objects.create(pregunta=pregunta, texto=texto_uno, dimension=uno, orden=1)
        Opcion.objects.create(pregunta=pregunta, texto=texto_dos, dimension=dos, orden=2)
    return cuestionario


def completar_vark(estudiante, cuestionario, dimensiones_por_pregunta):
    """Guarda y finaliza una evaluación VARK sin pasar por el navegador."""
    evaluacion = Evaluacion.objects.create(estudiante=estudiante, cuestionario=cuestionario)
    for pregunta, dimensiones in zip(cuestionario.preguntas.order_by("orden"), dimensiones_por_pregunta):
        opciones = list(pregunta.opciones.filter(dimension__in=dimensiones).values_list("id", flat=True))
        guardar_respuesta(evaluacion.pk, pregunta.pk, opciones)
    return finalizar_evaluacion(evaluacion.pk)


def completar_personalidad(estudiante, cuestionario, puntos_primera_opcion=7):
    evaluacion = Evaluacion.objects.create(estudiante=estudiante, cuestionario=cuestionario)
    for pregunta in cuestionario.preguntas.order_by("orden"):
        uno, dos = pregunta.opciones.order_by("orden")
        guardar_respuesta_personalidad(
            evaluacion.pk, pregunta.pk, uno.pk, puntos_primera_opcion, dos.pk, 10 - puntos_primera_opcion
        )
    return finalizar_evaluacion(evaluacion.pk)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@tag("e2e")
@unittest.skipIf(sync_playwright is None, "Playwright no está instalado (pip install -r requirements-dev.txt).")
class NavegadorTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        # Playwright usa un bucle de eventos; Django lo permite explícitamente en pruebas.
        os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        canal = os.environ.get("E2E_BROWSER_CHANNEL", "msedge")
        try:
            cls.browser = cls.playwright.chromium.launch(channel=canal)
        except PlaywrightError:
            try:
                cls.browser = cls.playwright.chromium.launch(channel="chrome")
            except PlaywrightError:
                cls.playwright.stop()
                super().tearDownClass()
                raise unittest.SkipTest("No se encontró Edge ni Chrome para las pruebas de navegador.")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        self.context = self.browser.new_context(locale="es-MX", viewport={"width": 1280, "height": 900})
        self.context.set_default_timeout(TIEMPO)
        # Sin diálogo de impresión ni visor de PDF: el visor del navegador sin interfaz lo cierra.
        self.context.add_init_script("window.print = () => {}; window.__BRUJULA_SIN_VISOR_PDF__ = true;")
        self.page = self.context.new_page()
        self.errores_js = []
        self.page.on("pageerror", lambda error: self.errores_js.append(str(error)))

    def tearDown(self):
        self.context.close()

    def assertSinErroresJS(self):
        self.assertEqual(self.errores_js, [], "La página lanzó errores de JavaScript.")

    @staticmethod
    def texto_del_pdf(ruta):
        """Texto de un PDF hecho con jsPDF (sin compresión, fuentes estándar en latin-1)."""
        with open(ruta, "rb") as archivo:
            datos = archivo.read()
        assert datos.startswith(b"%PDF"), "El archivo descargado no es un PDF."
        cadenas = re.findall(r"\(((?:\\.|[^\\)])*)\) Tj", datos.decode("latin-1"))
        return " | ".join(re.sub(r"\\(.)", r"\1", cadena) for cadena in cadenas)

    def descargar_ficha_de_la_vista_previa(self):
        """Con la vista previa abierta, descarga el PDF y devuelve (nombre, texto)."""
        modal = self.page.locator(".bru-pdf-modal")
        expect(modal).to_be_visible()
        self.assertTrue(modal.locator("iframe").get_attribute("data-pdf-url").startswith("blob:"))
        with self.page.expect_download() as descarga:
            modal.get_by_role("button", name="Descargar PDF").click()
        return descarga.value.suggested_filename, self.texto_del_pdf(descarga.value.path())

    def assertSinDesbordeHorizontal(self, donde=""):
        """La página no debe desplazarse a lo ancho (diseño responsivo)."""
        ancho = self.page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        self.assertLessEqual(ancho[0], ancho[1] + 1, f"Desborde horizontal en {donde or self.page.url}: {ancho}")

    def iniciar_sesion(self, usuario):
        """Comparte con el navegador una sesión iniciada con el cliente de pruebas de Django."""
        self.client.force_login(usuario)
        self.context.add_cookies([{
            "name": "sessionid",
            "value": self.client.cookies["sessionid"].value,
            "url": self.live_server_url,
        }])


# ---------------------------------------------------------------------------
# Sitio público: cuestionarios, guardado de respuestas y resultados
# ---------------------------------------------------------------------------

class EvaluacionPublicaE2ETests(NavegadorTestCase):
    def setUp(self):
        super().setUp()
        self.grupo = Grupo.objects.create(clave="3A", nombre="Tercero A")
        self.estudiante = Estudiante.objects.create(
            matricula="A-001", nombres="Lucía", apellidos="Ramos", grupo=self.grupo
        )

    def abrir_instrumentos(self):
        self.page.goto(f"{self.live_server_url}/#instrumentos")
        expect(self.page.locator("#connectionStatus")).to_have_text("Sistema conectado")

    def elegir(self, tipo, cuestionario):
        self.page.click(f'.assessment-choice[data-choice="{tipo}"]')
        self.page.select_option("#studentSelect", str(self.estudiante.pk))
        self.page.select_option("#questionnaireSelect", str(cuestionario.pk))
        self.page.click('#assessmentSetup button[type="submit"]')

    def test_lista_solo_estudiantes_y_cuestionarios_activos_por_tipo(self):
        Estudiante.objects.create(matricula="A-002", nombres="Inactivo", apellidos="X", grupo=self.grupo, activo=False)
        vark = crear_cuestionario_vark()
        crear_cuestionario_vark(titulo="Cuestionario archivado", activo=False)
        personalidad = crear_cuestionario_personalidad()
        self.abrir_instrumentos()

        estudiantes = self.page.locator("#studentSelect option").all_inner_texts()
        self.assertIn("Lucía Ramos · A-001", estudiantes)
        self.assertFalse(any("Inactivo" in texto for texto in estudiantes))

        cuestionarios = self.page.locator("#questionnaireSelect option").all_inner_texts()
        self.assertIn(vark.titulo, cuestionarios)
        self.assertNotIn("Cuestionario archivado", cuestionarios)
        self.assertNotIn(personalidad.titulo, cuestionarios)

        self.page.click('.assessment-choice[data-choice="PERSONALIDAD"]')
        expect(self.page.locator("#assessmentTitle")).to_contain_text("Personalidad")
        cuestionarios = self.page.locator("#questionnaireSelect option").all_inner_texts()
        self.assertIn(personalidad.titulo, cuestionarios)
        self.assertNotIn(vark.titulo, cuestionarios)
        self.assertSinErroresJS()

    def test_comenzar_sin_elegir_no_envia_el_formulario(self):
        crear_cuestionario_vark()
        self.abrir_instrumentos()
        self.page.click('#assessmentSetup button[type="submit"]')
        # Los campos son obligatorios: el navegador bloquea el envío y marca el primero.
        self.assertTrue(self.page.eval_on_selector("#studentSelect", "el => el.validity.valueMissing"))
        expect(self.page.locator("#questionMount")).to_be_hidden()
        self.assertFalse(Evaluacion.objects.exists())

    def test_vark_completo_guarda_respuestas_y_muestra_resultado(self):
        cuestionario = crear_cuestionario_vark()
        self.abrir_instrumentos()
        self.elegir("VARK", cuestionario)

        mount = self.page.locator("#questionMount")
        expect(mount).to_contain_text("Pregunta 1 de 2")
        expect(mount.locator(".progress-fill")).to_have_attribute("style", "width:50%")

        # No deja avanzar sin respuesta.
        mount.locator('[data-action="next"]').click()
        expect(self.page.locator("#globalNotice")).to_contain_text("Selecciona al menos una respuesta")

        mount.get_by_label("Con imágenes (1)").check()
        mount.get_by_label("Escuchando (1)").check()
        mount.locator('[data-action="next"]').click()
        expect(mount).to_contain_text("Pregunta 2 de 2")
        expect(mount.locator('[data-action="next"]')).to_have_text("Finalizar")

        # Al volver, conserva lo elegido.
        mount.locator('[data-action="previous"]').click()
        expect(mount.get_by_label("Con imágenes (1)")).to_be_checked()
        expect(mount.get_by_label("Escuchando (1)")).to_be_checked()
        mount.locator('[data-action="next"]').click()

        mount.get_by_label("Con imágenes (2)").check()
        mount.locator('[data-action="next"]').click()

        expect(self.page.locator("#globalNotice")).to_have_text("Tu evaluación quedó registrada.")
        resultado_ui = self.page.locator("#assessmentResult")
        expect(resultado_ui).to_be_visible()
        expect(self.page.locator("#assessmentInterpretation")).to_contain_text("Preferencia más alta: Visual")
        expect(self.page.locator("#resultHighlight")).to_have_text("Visual")
        expect(self.page.locator("#assessmentResultMeta")).to_contain_text("Lucía Ramos")
        valores = {
            fila.get_attribute("data-dimension"): fila.locator(".score-value").inner_text()
            for fila in self.page.locator("#assessmentScores li").all()
        }
        self.assertEqual(valores, {"V": "2", "A": "1", "R": "0", "K": "0"})
        expect(self.page.locator('#assessmentScores li[data-dimension="V"]')).to_have_class("score-row is-top")
        expect(mount).to_be_hidden()
        # «Nueva evaluación» devuelve el formulario listo para otra persona.
        self.page.click("#newAssessment")
        expect(self.page.locator("#assessmentSetup")).to_be_visible()
        expect(resultado_ui).to_be_hidden()

        # Lo guardado en la base de datos coincide con lo contestado.
        evaluacion = Evaluacion.objects.get()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.FINALIZADA)
        self.assertIsNotNone(evaluacion.finalizada_en)
        self.assertEqual(Respuesta.objects.filter(evaluacion=evaluacion).count(), 2)
        self.assertEqual(
            sorted(SeleccionRespuesta.objects.filter(respuesta__evaluacion=evaluacion)
                   .values_list("opcion__dimension", flat=True)),
            ["A", "V", "V"],
        )
        resultado = Resultado.objects.get(evaluacion=evaluacion)
        self.assertEqual((resultado.preguntas_contestadas, resultado.preguntas_omitidas), (2, 0))
        self.assertEqual(
            dict(resultado.puntajes.values_list("dimension", "puntaje")),
            {"V": 2, "A": 1, "R": 0, "K": 0},
        )
        self.assertSinErroresJS()

    def test_personalidad_completa_guarda_puntos_y_muestra_perfil(self):
        cuestionario = crear_cuestionario_personalidad()
        self.abrir_instrumentos()
        self.elegir("PERSONALIDAD", cuestionario)

        mount = self.page.locator("#questionMount")
        expect(mount).to_contain_text("Pregunta 1 de 4")
        # No se ofrece el reparto 5 y 5.
        self.assertNotIn("5", mount.locator("#personalityPoints option").all_inner_texts())

        mount.locator('[data-action="next"]').click()
        expect(self.page.locator("#globalNotice")).to_contain_text("Selecciona una distribución de puntos")

        puntos = ["7", "2", "8", "6"]  # E, N (2 vs 8), T, J
        for indice, valor in enumerate(puntos, start=1):
            expect(mount).to_contain_text(f"Pregunta {indice} de 4")
            mount.locator("#personalityPoints").select_option(valor)
            expect(mount.locator("#personalityOtherPoints")).to_contain_text(f": {10 - int(valor)}.")
            mount.locator('[data-action="next"]').click()

        expect(self.page.locator("#globalNotice")).to_have_text("Tu evaluación quedó registrada.")
        expect(self.page.locator("#resultHighlight")).to_have_text("ENTJ")
        expect(self.page.locator("#assessmentInterpretation")).to_contain_text("Tendencia observada: ENTJ")
        expect(self.page.locator("#assessmentScores li")).to_have_count(4)
        expect(self.page.locator('#assessmentScores li[data-axis="SN"] .axis-pole.is-win')).to_contain_text("Intuición")

        evaluacion = Evaluacion.objects.get()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.FINALIZADA)
        selecciones = SeleccionRespuesta.objects.filter(respuesta__evaluacion=evaluacion)
        self.assertEqual(selecciones.count(), 8)
        for respuesta in Respuesta.objects.filter(evaluacion=evaluacion):
            self.assertEqual(sum(respuesta.selecciones.values_list("puntos", flat=True)), 10)
        resultado = Resultado.objects.get(evaluacion=evaluacion)
        self.assertEqual(resultado.interpretacion, "ENTJ")
        self.assertEqual(
            dict(resultado.puntajes.values_list("dimension", "puntaje")),
            {"E": 7, "I": 3, "S": 2, "N": 8, "T": 8, "F": 2, "J": 6, "P": 4},
        )
        self.assertSinErroresJS()

    def test_vark_permite_omitir_preguntas(self):
        cuestionario = crear_cuestionario_vark()
        self.abrir_instrumentos()
        self.elegir("VARK", cuestionario)
        mount = self.page.locator("#questionMount")
        mount.get_by_role("button", name="Omitir").click()
        expect(mount).to_contain_text("Pregunta 2 de 2")
        expect(mount.locator(".skipped-help")).to_contain_text("1 pregunta omitida")
        # Al regresar, la omitida sigue sin respuesta y puede contestarse si se quiere.
        mount.locator('[data-action="previous"]').click()
        expect(mount.get_by_label("Con imágenes (1)")).not_to_be_checked()
        mount.get_by_role("button", name="Omitir").click()
        mount.get_by_label("Leyendo (2)").check()
        mount.locator('[data-action="next"]').click()

        expect(self.page.locator("#assessmentResult")).to_be_visible()
        expect(self.page.locator("#assessmentResultMeta")).to_contain_text("1 pregunta omitida")
        expect(self.page.locator("#resultHighlight")).to_have_text("Lectura/Escritura")
        resultado = Resultado.objects.get()
        self.assertEqual((resultado.preguntas_contestadas, resultado.preguntas_omitidas), (1, 1))
        self.assertEqual(dict(resultado.puntajes.values_list("dimension", "puntaje")), {"V": 0, "A": 0, "R": 1, "K": 0})
        self.assertSinErroresJS()

    def test_vark_no_permite_omitir_todas(self):
        cuestionario = crear_cuestionario_vark()
        self.abrir_instrumentos()
        self.elegir("VARK", cuestionario)
        mount = self.page.locator("#questionMount")
        mount.get_by_role("button", name="Omitir").click()
        mount.get_by_role("button", name="Omitir").click()
        expect(self.page.locator("#globalNotice")).to_contain_text("Contesta al menos una pregunta")
        expect(mount).to_be_visible()
        self.assertFalse(Resultado.objects.exists())

    def test_personalidad_no_ofrece_omitir(self):
        cuestionario = crear_cuestionario_personalidad()
        self.abrir_instrumentos()
        self.elegir("PERSONALIDAD", cuestionario)
        expect(self.page.locator('#questionMount [data-action="skip"]')).to_have_count(0)

    def contestar_vark(self, cuestionario):
        self.abrir_instrumentos()
        self.elegir("VARK", cuestionario)
        mount = self.page.locator("#questionMount")
        mount.get_by_label("Con imágenes (1)").check()
        mount.locator('[data-action="next"]').click()
        mount.get_by_label("Escuchando (2)").check()
        mount.locator('[data-action="next"]').click()
        expect(self.page.locator("#assessmentResult")).to_be_visible()
        return Resultado.objects.get()

    def test_al_terminar_se_descarga_la_ficha_en_pdf(self):
        resultado = self.contestar_vark(crear_cuestionario_vark())
        with self.page.expect_download() as descarga:
            self.page.click("#downloadPdf")
        self.assertEqual(descarga.value.suggested_filename, "Ficha Lucía Ramos A-001.pdf")
        texto = self.texto_del_pdf(descarga.value.path())
        for esperado in ("Ficha de resultado", "Lucía Ramos", "A-001", "Tercero A (3A)",
                         "Finalizada", "2 contestadas · 0 omitidas", "Visual y Auditivo",
                         f"Folio de evaluación #{resultado.evaluacion_id}"):
            self.assertIn(esperado, texto)
        self.assertSinErroresJS()

    def test_al_terminar_se_ve_la_ficha_en_pdf_y_se_puede_descargar(self):
        self.contestar_vark(crear_cuestionario_vark())
        self.page.click("#viewFicha")
        nombre, texto = self.descargar_ficha_de_la_vista_previa()
        self.assertEqual(nombre, "Ficha Lucía Ramos A-001.pdf")
        expect(self.page.locator(".bru-pdf-modal")).to_contain_text(nombre)
        self.assertIn("PUNTAJES POR DIMENSIÓN", texto)
        self.assertIn("50%", texto)  # Visual y Auditivo: 1 de 2 selecciones cada una.
        self.page.keyboard.press("Escape")
        expect(self.page.locator(".bru-pdf-modal")).to_be_hidden()
        self.assertSinErroresJS()

    def test_muestra_vista_previa_y_contadores_de_cuestionarios(self):
        cuestionario = crear_cuestionario_vark()
        Cuestionario.objects.create(titulo="Borrador sin preguntas", tipo="VARK")
        self.abrir_instrumentos()
        expect(self.page.locator('.choice-count[data-count="VARK"]')).to_have_text("1 cuestionario disponible")
        expect(self.page.locator('.choice-count[data-count="PERSONALIDAD"]')).to_have_text("Aún no hay cuestionarios")
        # El que no tiene preguntas aparece, pero no se puede elegir.
        borrador = self.page.locator("#questionnaireSelect option", has_text="Borrador sin preguntas")
        expect(borrador).to_be_disabled()
        self.page.select_option("#questionnaireSelect", str(cuestionario.pk))
        vista = self.page.locator("#questionnairePreview")
        expect(vista).to_be_visible()
        expect(vista).to_contain_text(cuestionario.titulo)
        expect(self.page.locator("#previewCount")).to_have_text("2 preguntas")
        self.assertSinErroresJS()

    def test_un_cuestionario_recien_creado_aparece_al_volver_a_instrumentos(self):
        crear_cuestionario_vark()
        self.abrir_instrumentos()
        self.page.click('.sidebar .nav-link[data-route="inicio"]')
        nuevo = crear_cuestionario_vark(titulo="VARK recién creado")
        self.page.click('.sidebar .nav-link[data-route="instrumentos"]')
        expect(self.page.locator("#questionnaireSelect option", has_text=nuevo.titulo)).to_have_count(1)
        expect(self.page.locator('.card-count[data-count="VARK"]')).to_have_text("2 cuestionarios disponibles")

    def test_cuestionario_sin_opciones_avisa_y_no_muestra_preguntas(self):
        cuestionario = Cuestionario.objects.create(titulo="Incompleto", tipo="VARK")
        Pregunta.objects.create(cuestionario=cuestionario, texto="Sin opciones", orden=1)
        self.abrir_instrumentos()
        self.elegir("VARK", cuestionario)
        expect(self.page.locator("#globalNotice")).to_contain_text("no tienen opciones configuradas")
        expect(self.page.locator("#questionMount")).to_be_hidden()

    def test_navegacion_entre_secciones(self):
        self.page.goto(self.live_server_url)
        expect(self.page.locator("#pageName")).to_have_text("INICIO")
        for ruta in ("instrumentos", "guia", "inicio"):
            self.page.click(f'.sidebar .nav-link[data-route="{ruta}"]:not([data-scroll])')
            expect(self.page.locator(f"#page-{ruta}")).to_have_class("page-section current")
        self.assertSinErroresJS()

    def test_grupo_filtra_estudiantes_para_aplicar_al_grupo(self):
        otro = Grupo.objects.create(clave="3B", nombre="Tercero B")
        Estudiante.objects.create(matricula="B-001", nombres="Mario", apellidos="Soto", grupo=otro)
        cuestionario = crear_cuestionario_vark()
        self.abrir_instrumentos()
        self.page.select_option("#groupSelect", str(otro.pk))
        self.assertEqual(self.page.locator("#studentSelect option").all_inner_texts(),
                         ["Selecciona una opción", "Mario Soto · B-001"])
        self.page.select_option("#groupSelect", str(self.grupo.pk))
        self.page.select_option("#studentSelect", str(self.estudiante.pk))
        self.page.select_option("#questionnaireSelect", str(cuestionario.pk))
        self.page.click('#assessmentSetup button[type="submit"]')
        mount = self.page.locator("#questionMount")
        mount.get_by_label("Con imágenes (1)").check()
        mount.locator('[data-action="next"]').click()
        mount.get_by_label("Leyendo (2)").check()
        mount.locator('[data-action="next"]').click()
        # Al iniciar otra evaluación se conserva el grupo para seguir con el resto.
        self.page.click("#newAssessment")
        expect(self.page.locator("#groupSelect")).to_have_value(str(self.grupo.pk))
        self.assertSinErroresJS()

    def test_formulario_de_contacto_valida_y_prepara_el_correo(self):
        self.page.goto(self.live_server_url)
        self.page.click('.sidebar .nav-link[data-scroll="contacto"]')
        formulario = self.page.locator("#contactForm")
        expect(formulario).to_be_visible()
        formulario.get_by_role("button", name="Enviar mensaje").click()
        expect(self.page.locator("#contactError")).to_contain_text("tu nombre")
        expect(self.page.locator("#contactName")).to_have_attribute("aria-invalid", "true")

        self.page.fill("#contactName", "Lucía Ramos")
        self.page.fill("#contactEmail", "lucia@escuela.example")
        self.page.select_option("#contactTopic", "Problema de acceso")
        self.page.fill("#contactMessage", "No encuentro mi nombre en la lista.")
        formulario.get_by_role("button", name="Enviar mensaje").click()
        expect(self.page.locator("#globalNotice")).to_contain_text("Tu mensaje se envió correctamente")
        expect(self.page.locator("#contactError")).to_be_hidden()
        expect(self.page.locator("#contactName")).to_have_value("")  # El formulario queda limpio.

        # El correo se envió a la dirección de contacto configurada con los datos del formulario.
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [settings.CONTACT_EMAIL])
        self.assertIn("Problema de acceso", correo.subject)
        self.assertIn("Lucía Ramos", correo.body)
        self.assertIn("lucia@escuela.example", correo.body)
        self.assertIn("No encuentro mi nombre en la lista.", correo.body)
        self.assertSinErroresJS()

    def test_contacto_muestra_error_si_el_envio_falla(self):
        self.page.route("**/api/contacto/", lambda route: route.fulfill(
            status=500, content_type="application/json",
            body='{"detail": "No se pudo enviar el mensaje. Intenta más tarde."}'))
        self.page.goto(f"{self.live_server_url}/#guia")
        self.page.fill("#contactName", "Lucía Ramos")
        self.page.fill("#contactEmail", "lucia@escuela.example")
        self.page.select_option("#contactTopic", "Otro")
        self.page.fill("#contactMessage", "Mensaje de prueba suficientemente largo.")
        self.page.get_by_role("button", name="Enviar mensaje").click()
        expect(self.page.locator("#contactError")).to_contain_text("No se pudo enviar el mensaje")
        # Lo escrito se conserva para reintentar.
        expect(self.page.locator("#contactName")).to_have_value("Lucía Ramos")
        expect(self.page.get_by_role("button", name="Enviar mensaje")).to_be_enabled()
        self.assertEqual(len(mail.outbox), 0)

    def test_seccion_de_video_en_la_guia(self):
        self.page.goto(self.live_server_url)
        self.page.click('.sidebar .nav-link[data-scroll="guideVideo"]')
        expect(self.page.locator("#page-guia")).to_have_class("page-section current")
        expect(self.page.locator("#guideVideo")).to_contain_text("¿Qué es Brújula y para qué sirve?")
        # Sin el archivo de video se muestra el aviso en lugar de un reproductor vacío.
        video = os.path.join(os.path.dirname(__file__), "static", "dashboard", "video", "brujula-intro.mp4")
        if not os.path.exists(video):
            expect(self.page.locator("#videoPlaceholder")).to_be_visible()
        else:
            expect(self.page.locator("#introVideo")).to_be_visible()


# ---------------------------------------------------------------------------
# Panel: tablero de resultados y gráficas
# ---------------------------------------------------------------------------

class TableroResultadosE2ETests(NavegadorTestCase):
    def setUp(self):
        super().setUp()
        self.grupo_a = Grupo.objects.create(clave="3A", nombre="Tercero A")
        self.grupo_b = Grupo.objects.create(clave="3B", nombre="Tercero B")
        self.lucia = Estudiante.objects.create(matricula="A-001", nombres="Lucía", apellidos="Ramos", grupo=self.grupo_a)
        self.mario = Estudiante.objects.create(matricula="A-002", nombres="Mario", apellidos="Soto", grupo=self.grupo_a)
        Estudiante.objects.create(matricula="B-001", nombres="Sin", apellidos="Resultados", grupo=self.grupo_b)
        self.vark = crear_cuestionario_vark()
        completar_vark(self.lucia, self.vark, [["V", "A"], ["V"]])   # V2 A1
        completar_vark(self.mario, self.vark, [["K"], ["V", "K"]])   # V1 K2
        self.iniciar_sesion(get_user_model().objects.create_superuser(username="admin_e2e", password="x"))

    def abrir_tablero(self):
        self.page.goto(f"{self.live_server_url}/admin/")
        expect(self.page.locator("#resultsNotice")).to_be_hidden()

    def barras(self):
        grupos = self.page.locator("#varkChart .bru-results-bar-group")
        return {
            grupo.locator("small").inner_text(): int(grupo.locator("span").inner_text())
            for grupo in grupos.all()
        }

    def test_estadisticas_y_grafica_vark_con_totales_correctos(self):
        self.abrir_tablero()
        expect(self.page.locator("#statEvaluations")).to_have_text("2")
        expect(self.page.locator("#statStudents")).to_have_text("3")
        expect(self.page.locator("#statResults")).to_have_text("2")
        self.assertEqual(self.barras(), {"Visual": 3, "Auditivo": 1, "Lectura/Escritura": 0, "Kinestésico": 2})
        # La barra mayor ocupa el 100 % y la gráfica se describe para lectores de pantalla.
        visual = self.page.locator("#varkChart .bru-results-bar-group", has_text="Visual").locator(".bru-results-bar")
        self.assertIn("--height:100%", visual.get_attribute("style"))
        self.assertIn("Visual 3", self.page.locator("#varkChart").get_attribute("aria-label"))
        expect(self.page.locator("#recentResults")).to_contain_text("Lucía Ramos")
        expect(self.page.locator("#recentResults")).to_contain_text("Mario Soto")
        self.assertSinErroresJS()

    def test_filtro_por_grupo_actualiza_estadisticas_y_grafica(self):
        self.abrir_tablero()
        self.page.select_option("#groupFilter", str(self.grupo_b.pk))
        expect(self.page.locator("#statResults")).to_have_text("0")
        expect(self.page.locator("#statStudents")).to_have_text("1")
        expect(self.page.locator("#varkChart")).to_contain_text("Los datos aparecerán cuando haya evaluaciones completadas")
        self.page.select_option("#groupFilter", str(self.grupo_a.pk))
        expect(self.page.locator("#scopeLabel")).to_have_text("Grupo: Tercero A (3A)")
        expect(self.page.locator("#statResults")).to_have_text("2")
        self.assertEqual(self.barras()["Visual"], 3)

    def test_busqueda_y_ficha_imprimible(self):
        self.abrir_tablero()
        self.page.fill("#resultSearch", "ramos")
        self.page.press("#resultSearch", "Enter")
        filas = self.page.locator("#searchResults tr")
        expect(filas).to_have_count(1)
        expect(filas.first).to_contain_text("Lucía Ramos")
        expect(filas.first).to_contain_text("A-001")

        filas.first.get_by_role("button", name="Ver PDF").click()
        nombre, texto = self.descargar_ficha_de_la_vista_previa()
        self.assertEqual(nombre, "Ficha Lucía Ramos A-001.pdf")
        for esperado in ("Ficha de resultado", "Lucía Ramos", "A-001", "Tercero A (3A)", "Estilos de aprendizaje",
                         "Finalizada", "2 contestadas · 0 omitidas", "Preferencia más alta: Visual"):
            self.assertIn(esperado, texto)
        # Visual 2 de 3 selecciones = 67 %.
        self.assertRegex(texto, r"Visual \| 2 \| 67%")
        self.page.get_by_role("button", name="Cerrar").click()
        expect(self.page.locator(".bru-pdf-modal")).to_be_hidden()

        self.page.fill("#resultSearch", "nadie-se-llama-asi")
        self.page.click("#searchButton")
        expect(self.page.locator("#searchResults")).to_contain_text("No se encontraron resultados")
        self.assertSinErroresJS()

    def test_vista_individual_por_alumno(self):
        self.abrir_tablero()
        self.page.select_option("#groupFilter", str(self.grupo_a.pk))
        # Solo se ofrecen los alumnos del grupo elegido.
        self.assertEqual(self.page.locator("#studentFilter option").all_inner_texts(),
                         ["Todos los alumnos", "Lucía Ramos · A-001", "Mario Soto · A-002"])
        self.page.select_option("#studentFilter", str(self.mario.pk))
        expect(self.page.locator("#scopeLabel")).to_have_text("Alumno: Mario Soto (A-002)")
        expect(self.page.locator("#statResults")).to_have_text("1")
        expect(self.page.locator("#statStudents")).to_have_text("1")
        self.assertEqual(self.barras(), {"Visual": 1, "Auditivo": 0, "Lectura/Escritura": 0, "Kinestésico": 2})
        self.assertSinErroresJS()

    def test_ver_todos_lista_el_alcance_sin_escribir(self):
        self.abrir_tablero()
        expect(self.page.locator("#searchResults")).to_contain_text("Ver todos")
        self.page.click("#showAllResults")
        expect(self.page.locator("#searchResults tr")).to_have_count(2)
        self.page.select_option("#groupFilter", str(self.grupo_b.pk))
        expect(self.page.locator("#searchResults")).to_contain_text("No hay resultados en este alcance")
        self.page.select_option("#groupFilter", "")
        self.page.select_option("#studentFilter", str(self.lucia.pk))
        expect(self.page.locator("#searchResults tr")).to_have_count(1)
        expect(self.page.locator("#searchResults")).to_contain_text("Lucía Ramos")

    def test_reporte_pdf_total_y_por_grupo(self):
        self.abrir_tablero()
        self.page.click("#reportButton")
        nombre, texto = self.descargar_ficha_de_la_vista_previa()
        self.assertEqual(nombre, "Reporte de resultados - Total.pdf")
        for esperado in ("REPORTE DE RESULTADOS", "Ficha técnica", "Total", "2 (2 VARK · 0 personalidad)",
                         "Detalle de resultados".upper(), "Lucía Ramos", "Mario Soto", "Preferencia del conjunto: Visual",
                         "Página 1 de 3"):
            self.assertIn(esperado, texto)
        # Tras el resumen se incluye la ficha individual de cada resultado.
        self.assertEqual(texto.count("Ficha de resultado"), 2)
        self.page.keyboard.press("Escape")

        self.page.select_option("#groupFilter", str(self.grupo_b.pk))
        self.page.click("#reportButton")
        nombre, texto = self.descargar_ficha_de_la_vista_previa()
        self.assertEqual(nombre, "Reporte de resultados - Grupo Tercero B (3B).pdf")
        self.assertIn("No hay resultados registrados para este alcance.", texto)
        self.assertSinErroresJS()

    def test_actualizar_muestra_resultados_nuevos(self):
        self.abrir_tablero()
        expect(self.page.locator("#statResults")).to_have_text("2")
        completar_vark(self.lucia, crear_cuestionario_vark(titulo="Otro VARK"), [["R"], ["R"]])
        self.page.click("#refreshResults")
        expect(self.page.locator("#statResults")).to_have_text("3")
        self.assertEqual(self.barras()["Lectura/Escritura"], 2)

    def test_grafica_de_personalidad(self):
        self.abrir_tablero()
        chart = self.page.locator("#personalityChart")
        expect(chart).to_contain_text("Los datos aparecerán cuando haya evaluaciones completadas")

        completar_personalidad(self.mario, crear_cuestionario_personalidad(), puntos_primera_opcion=7)
        self.page.click("#refreshResults")
        expect(self.page.locator("#statResults")).to_have_text("3")
        barras = {
            grupo.locator("small").inner_text(): int(grupo.locator("span").inner_text())
            for grupo in chart.locator(".bru-results-bar-group").all()
        }
        self.assertEqual(barras, {
            "Extroversión": 7, "Introversión": 3, "Sensación": 7, "Intuición": 3,
            "Pensamiento": 7, "Sentimiento": 3, "Juicio": 7, "Percepción": 3,
        })
        self.assertIn("Extroversión 7", chart.get_attribute("aria-label"))
        # La gráfica VARK no se mezcla con personalidad.
        self.assertEqual(self.barras()["Visual"], 3)

        # Ficha de personalidad: un renglón por eje con los dos polos.
        self.page.fill("#resultSearch", "preferencias personales")
        self.page.press("#resultSearch", "Enter")
        self.page.locator("#searchResults").get_by_role("button", name="Ver PDF").click()
        _, texto = self.descargar_ficha_de_la_vista_previa()
        self.assertIn("ESTJ", texto)
        for eje in ("ENERGÍA", "INFORMACIÓN", "DECISIONES", "ESTILO DE VIDA"):
            self.assertIn(eje, texto)
        self.assertIn("Extroversión  7", texto)
        self.assertIn("3  Introversión", texto)
        self.assertSinErroresJS()

    def test_tabla_muestra_estado_real_e_interpretacion_vark(self):
        self.abrir_tablero()
        self.page.fill("#resultSearch", "ramos")
        self.page.press("#resultSearch", "Enter")
        fila = self.page.locator("#searchResults tr").first
        expect(fila).to_contain_text("Finalizada")
        expect(fila).to_contain_text("Preferencia más alta: Visual")
        fila.get_by_role("button", name="Ver PDF").click()
        _, texto = self.descargar_ficha_de_la_vista_previa()
        self.assertIn("Preferencia más alta: Visual", texto)
        self.page.keyboard.press("Escape")

        # Empate entre dimensiones: se nombran ambas.
        self.page.fill("#resultSearch", "soto")  # Mario: V1 K2 → Kinestésico
        self.page.press("#resultSearch", "Enter")
        expect(self.page.locator("#searchResults tr").first).to_contain_text("Preferencia más alta: Kinestésico")


# ---------------------------------------------------------------------------
# Panel: inicio de sesión con las cuentas de cada rol
# ---------------------------------------------------------------------------

class InicioSesionPorRolE2ETests(NavegadorTestCase):
    CLAVE = "ClaveDePrueba-2026!"

    def setUp(self):
        super().setUp()
        from django.core.management import call_command
        from io import StringIO
        call_command("crear_cuentas_roles", password=self.CLAVE, stdout=StringIO())

    def entrar(self, rol):
        self.page.goto(f"{self.live_server_url}/admin/login/")
        self.page.fill("#id_username", f"demo.{rol}")
        self.page.fill("#id_password", self.CLAVE)
        self.page.locator('#login-form [type="submit"]').click()

    def test_roles_con_panel_entran_y_ven_sus_secciones(self):
        esperado = {
            "administrador": ("Usuarios", True),
            "coordinador": ("Estudiantes", False),
            "docente": ("Resultados", False),
            "consultor": ("Resultados", False),
        }
        for rol, (seccion, ve_usuarios) in esperado.items():
            with self.subTest(rol=rol):
                self.context.clear_cookies()
                self.entrar(rol)
                expect(self.page.locator("#bru-results-title")).to_be_visible()
                expect(self.page.locator(".bru-app-grid")).to_contain_text(seccion)
                usuarios = self.page.locator('.bru-app-grid a[href="/admin/auth/user/"]')
                if ve_usuarios:
                    expect(usuarios.first).to_be_visible()
                else:
                    expect(usuarios).to_have_count(0)
        self.assertSinErroresJS()

    def test_estudiante_no_puede_entrar_al_panel(self):
        self.entrar("estudiante")
        expect(self.page.locator(".errornote")).to_be_visible()
        self.assertIn("/admin/login/", self.page.url)


# ---------------------------------------------------------------------------
# Panel: constructor de cuestionarios
# ---------------------------------------------------------------------------

class ConstructorCuestionariosE2ETests(NavegadorTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(get_user_model().objects.create_superuser(username="admin_e2e", password="x"))
        self.page.on("dialog", lambda dialog: dialog.accept())

    def abrir_constructor(self):
        self.page.goto(f"{self.live_server_url}/admin/questionnaires/cuestionario/add/")
        expect(self.page.locator("#bru-questionnaire-builder")).to_be_visible()

    def test_ejemplo_y_vista_previa(self):
        self.abrir_constructor()
        self.page.click('[data-builder-action="example"]')
        expect(self.page.locator("[data-builder-status]")).to_contain_text("Ejemplo ficticio cargado")
        self.page.click('[data-builder-action="preview"]')
        vista = self.page.locator("[data-builder-preview]")
        expect(vista).to_be_visible()
        # La vista previa se ve como el formulario del estudiante y se puede contestar.
        expect(vista.locator(".bru-preview-header h3")).to_have_text("DEMO - Preferencias de aprendizaje")
        expect(vista.locator(".bru-preview-question")).to_have_count(2)
        opcion = vista.locator(".bru-preview-option").first
        opcion.click()
        expect(opcion.locator("input")).to_be_checked()
        expect(vista.get_by_role("button", name="Finalizar")).to_be_disabled()
        self.assertFalse(Cuestionario.objects.exists())
        self.assertSinErroresJS()

    def test_pregunta_arriba_opciones_abajo_y_botones(self):
        self.abrir_constructor()
        pregunta = self.page.locator(".bru-builder-question").first
        # Orden visual: texto de la pregunta, opciones, «Agregar opción».
        self.page.fill("[data-question-text]", "¿Cómo estudias?")
        expect(pregunta.locator(".bru-builder-option")).to_have_count(2)
        expect(pregunta.locator("[data-option-text]").first).to_have_attribute("placeholder", "Opción 1")
        pregunta.get_by_role("button", name="Agregar opción").click()
        expect(pregunta.locator(".bru-builder-option")).to_have_count(3)
        expect(pregunta.locator("[data-question-count]")).to_have_text("3 opciones")
        # Solo hay un botón para agregar preguntas, al final.
        agregar = self.page.locator('[data-builder-action="add-question"]')
        expect(agregar).to_have_count(1)
        agregar.click()
        expect(self.page.locator(".bru-builder-question")).to_have_count(2)
        expect(self.page.locator("[data-builder-summary]")).to_have_text("2 preguntas · 5 opciones")

    def test_personalidad_limita_a_dos_opciones_y_vista_previa_de_puntos(self):
        self.abrir_constructor()
        self.page.select_option('[data-builder-field="type"]', "PERSONALIDAD")
        pregunta = self.page.locator(".bru-builder-question").first
        expect(pregunta.get_by_role("button", name="Agregar opción")).to_be_hidden()
        # Solo se ofrecen dimensiones de personalidad.
        visibles = pregunta.locator("[data-option-dimension]").first.locator("optgroup:not([hidden]) option")
        self.assertEqual(visibles.all_inner_texts()[0], "Extroversión")
        self.page.click('[data-builder-action="example"]')
        self.page.click('[data-builder-action="preview"]')
        vista = self.page.locator("[data-builder-preview]")
        puntos = vista.locator(".bru-preview-points select").first
        self.assertNotIn("5", puntos.locator("option").all_inner_texts())
        puntos.select_option("7")
        expect(vista.locator(".bru-preview-points").first).to_contain_text(": 3.")

    def test_validaciones_del_borrador(self):
        self.abrir_constructor()
        self.page.click('[data-builder-action="preview"]')
        expect(self.page.locator("[data-builder-status]")).to_have_text("Escribe un título para el cuestionario.")
        self.page.fill('[data-builder-field="title"]', "Mi cuestionario")
        self.page.click('[data-builder-action="preview"]')
        expect(self.page.locator("[data-builder-status]")).to_have_text("Escribe el texto de la pregunta 1.")
        self.page.fill("[data-question-text]", "¿Qué prefieres?")
        opciones = self.page.locator(".bru-builder-option")
        for indice in range(2):
            opciones.nth(indice).locator("[data-option-text]").fill(f"Opción {indice + 1}")
        opciones.nth(0).locator("[data-option-dimension]").select_option("V")
        opciones.nth(1).locator("[data-option-dimension]").select_option("E")
        self.page.click('[data-builder-action="preview"]')
        expect(self.page.locator("[data-builder-status]")).to_contain_text("no corresponde al tipo elegido")

    # --- Editar cuestionario: tarjetas de preguntas con sus opciones ---------------------

    def abrir_edicion(self, cuestionario):
        self.page.goto(f"{self.live_server_url}/admin/questionnaires/cuestionario/{cuestionario.pk}/change/")
        expect(self.page.locator("#preguntas-group .bru-card-option").first).to_be_visible()

    def tarjeta(self, indice):
        return self.page.locator("#preguntas-group tbody tr.form-row:not(.empty-form)").nth(indice)

    def guardar_y_seguir(self):
        self.page.locator('input[name="_continue"]').click()
        self.page.wait_for_load_state()
        expect(self.page.locator(".messagelist .success").first).to_be_visible()

    def test_tarjetas_muestran_pregunta_y_sus_opciones(self):
        cuestionario = crear_cuestionario_vark()
        self.abrir_edicion(cuestionario)
        primera = self.tarjeta(0)
        expect(primera.locator("td.field-texto textarea")).to_have_value("¿Cómo prefieres aprender?")
        textos = [campo.input_value() for campo in primera.locator(".bru-card-option input").all()]
        self.assertEqual(textos, ["Con imágenes (1)", "Escuchando (1)", "Leyendo (1)", "Practicando (1)"])
        expect(primera.locator(".bru-card-count")).to_have_text("4 opciones")
        # Botón «Eliminar pregunta» en lugar de la casilla.
        expect(primera.locator('td.delete input[type="checkbox"]')).to_be_hidden()
        expect(primera.get_by_role("button", name="Eliminar pregunta")).to_be_visible()
        expect(self.page.locator("#preguntas-group .add-row a")).to_have_text("Agregar pregunta")
        self.assertSinErroresJS()

    def test_editar_agregar_y_quitar_opciones_se_guarda(self):
        cuestionario = crear_cuestionario_vark()
        pregunta = cuestionario.preguntas.get(orden=1)
        self.abrir_edicion(cuestionario)
        primera = self.tarjeta(0)
        opciones = primera.locator(".bru-card-option")
        opciones.nth(0).locator("input").fill("Con mapas y esquemas")
        opciones.nth(3).locator(".bru-card-option-remove").click()
        primera.get_by_role("button", name="Agregar opción").click()
        nueva = primera.locator(".bru-card-option").last
        nueva.locator("input").fill("Con videos")
        nueva.locator("select").select_option("V")
        self.guardar_y_seguir()

        self.assertEqual(
            list(pregunta.opciones.order_by("orden").values_list("texto", "dimension")),
            [("Con mapas y esquemas", "V"), ("Escuchando (1)", "A"), ("Leyendo (1)", "R"), ("Con videos", "V")],
        )
        # La otra pregunta no cambió.
        self.assertEqual(cuestionario.preguntas.get(orden=2).opciones.count(), 4)
        self.assertSinErroresJS()

    def test_eliminar_pregunta_con_boton(self):
        cuestionario = crear_cuestionario_vark()
        self.abrir_edicion(cuestionario)
        segunda = self.tarjeta(1)
        segunda.get_by_role("button", name="Eliminar pregunta").click()
        expect(segunda).to_have_class(re.compile("is-deleted"))
        expect(segunda.get_by_role("button", name="Deshacer")).to_be_visible()
        self.guardar_y_seguir()
        self.assertEqual(list(cuestionario.preguntas.values_list("orden", flat=True)), [1])

    def test_pregunta_nueva_con_sus_opciones(self):
        cuestionario = crear_cuestionario_vark()
        self.abrir_edicion(cuestionario)
        self.page.locator("#preguntas-group .add-row a").click()
        nueva = self.tarjeta(2)
        expect(nueva.locator("td.field-orden input")).to_have_value("3")
        nueva.locator("td.field-texto textarea").fill("¿Cómo tomas apuntes?")
        opciones = nueva.locator(".bru-card-option")
        expect(opciones).to_have_count(2)
        opciones.nth(0).locator("input").fill("Con dibujos")
        opciones.nth(0).locator("select").select_option("V")
        opciones.nth(1).locator("input").fill("Grabando la clase")
        opciones.nth(1).locator("select").select_option("A")
        self.guardar_y_seguir()

        pregunta = cuestionario.preguntas.get(orden=3)
        self.assertEqual(pregunta.texto, "¿Cómo tomas apuntes?")
        self.assertEqual(list(pregunta.opciones.values_list("dimension", flat=True)), ["V", "A"])
        self.assertEqual(cuestionario.preguntas.count(), 3)  # Sin duplicados.
        self.assertSinErroresJS()

    def test_valida_antes_de_guardar(self):
        cuestionario = crear_cuestionario_personalidad()
        self.abrir_edicion(cuestionario)
        primera = self.tarjeta(0)
        # Personalidad: solo dos opciones, sin botón para agregar más.
        expect(primera.get_by_role("button", name="Agregar opción")).to_be_hidden()
        primera.locator(".bru-card-option").nth(1).locator("select").select_option("E")
        self.page.locator('input[name="_continue"]').click()
        expect(primera.locator(".bru-card-note")).to_contain_text("polos opuestos")
        self.assertEqual(
            list(cuestionario.preguntas.get(orden=1).opciones.values_list("dimension", flat=True)), ["E", "I"]
        )

    @unittest.expectedFailure
    def test_FALLA_el_constructor_no_permite_guardar(self):
        """El constructor solo genera una vista previa y oculta el formulario original con su botón Guardar."""
        self.abrir_constructor()
        self.page.click('[data-builder-action="example"]')
        self.page.click('[data-builder-action="preview"]')
        guardar = self.page.locator('input[name="_save"], button[name="_save"]')
        expect(guardar).to_be_visible(timeout=2_000)
        guardar.click()
        self.assertTrue(Cuestionario.objects.exists())
