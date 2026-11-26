"""Pruebas de navegador del resto del frontend.

Complementan ``tests_e2e.py`` (evaluación pública, tablero, constructor de cuestionarios):
diseño responsivo, inicio y cierre de sesión, recorrido de todas las pantallas del panel
sin errores de JavaScript, vista previa de permisos por rol, páginas de eliminar y la ficha
de personalidad desde el sitio público.
"""

from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import NoReverseMatch, reverse

from apps.dashboard.tests_e2e import (
    NavegadorTestCase,
    crear_cuestionario_personalidad,
    crear_cuestionario_vark,
    expect,
)
from apps.students.models import Estudiante, Grupo

CELULAR = {"width": 390, "height": 844}


# ---------------------------------------------------------------------------
# Sitio público: inicio, accesos y ficha de personalidad
# ---------------------------------------------------------------------------

class SitioPublicoE2ETests(NavegadorTestCase):
    def setUp(self):
        super().setUp()
        self.grupo = Grupo.objects.create(clave="3A", nombre="Tercero A")
        self.estudiante = Estudiante.objects.create(
            matricula="A-001", nombres="Lucía", apellidos="Ramos", grupo=self.grupo
        )

    def test_inicio_muestra_instrumentos_y_contadores(self):
        crear_cuestionario_vark()
        self.page.goto(self.live_server_url)
        expect(self.page.locator("#connectionStatus")).to_have_text("Sistema conectado")
        expect(self.page.locator("#home-heading")).to_contain_text("Aprende a tu")
        expect(self.page.locator('.card-count[data-count="VARK"]')).to_have_text("1 cuestionario disponible")
        expect(self.page.locator('.card-count[data-count="PERSONALIDAD"]')).to_have_text("Aún no hay cuestionarios")
        expect(self.page.locator('.card-count[data-count="PERSONALIDAD"]')).to_have_class("card-count is-empty")
        self.assertSinErroresJS()

    def test_comenzar_exploracion_abre_el_instrumento_elegido(self):
        crear_cuestionario_personalidad()
        self.page.goto(self.live_server_url)
        self.page.locator('.instrument-card a[data-focus="PERSONALIDAD"]').click()
        expect(self.page.locator("#page-instrumentos")).to_have_class("page-section current")
        expect(self.page.locator('.assessment-choice[data-choice="PERSONALIDAD"]')).to_have_attribute("aria-pressed", "true")
        expect(self.page.locator("#assessmentTitle")).to_contain_text("Personalidad")
        self.assertSinErroresJS()

    def test_hero_y_guia_llevan_a_sus_secciones(self):
        self.page.goto(self.live_server_url)
        self.page.locator(".hero-panel a[data-route='instrumentos']").click()
        expect(self.page.locator("#pageName")).to_have_text("INSTRUMENTOS")
        expect(self.page).to_have_url(f"{self.live_server_url}/#instrumentos")
        self.page.locator(".help-card a[data-route='guia']").click()
        expect(self.page.locator("#pageName")).to_have_text("GUÍA DE USO")
        # La dirección con #ruta abre directamente esa sección.
        self.page.goto(f"{self.live_server_url}/#guia")
        expect(self.page.locator("#page-guia")).to_have_class("page-section current")
        self.page.go_back()
        expect(self.page.locator("#pageName")).to_have_text("GUÍA DE USO")
        self.assertSinErroresJS()

    def test_ficha_de_personalidad_desde_el_sitio_publico(self):
        cuestionario = crear_cuestionario_personalidad()
        self.page.goto(f"{self.live_server_url}/#instrumentos")
        expect(self.page.locator("#connectionStatus")).to_have_text("Sistema conectado")
        self.page.click('.assessment-choice[data-choice="PERSONALIDAD"]')
        self.page.select_option("#studentSelect", str(self.estudiante.pk))
        self.page.select_option("#questionnaireSelect", str(cuestionario.pk))
        self.page.click('#assessmentSetup button[type="submit"]')
        mount = self.page.locator("#questionMount")
        # La barra de reparto refleja los puntos elegidos.
        mount.locator("#personalityPoints").select_option("8")
        expect(mount.locator(".split-a")).to_have_text("A · 8")
        expect(mount.locator(".split-b")).to_have_text("B · 2")
        for _ in range(4):
            if mount.locator("#personalityPoints").input_value() == "":
                mount.locator("#personalityPoints").select_option("7")
            mount.locator('[data-action="next"]').click()
        expect(self.page.locator("#resultHighlight")).to_have_text("ESTJ")

        self.page.click("#viewFicha")
        nombre, texto = self.descargar_ficha_de_la_vista_previa()
        self.assertEqual(nombre, "Ficha Lucía Ramos A-001.pdf")
        for esperado in ("Personalidad", "ENERGÍA", "INFORMACIÓN", "DECISIONES", "ESTILO DE VIDA",
                         "Tendencia observada: ESTJ", "Extroversión  8"):
            self.assertIn(esperado, texto)
        self.assertSinErroresJS()

    def test_sesion_iniciada_se_muestra_y_se_puede_cerrar(self):
        usuario = get_user_model().objects.create_user(
            "lucia", password="ClaveSegura-2026", first_name="Lucía", last_name="Ramos"
        )
        self.iniciar_sesion(usuario)
        self.page.goto(f"{self.live_server_url}/#instrumentos")
        expect(self.page.locator("#userName")).to_have_text("Lucía Ramos")
        expect(self.page.locator("#userAvatar")).to_have_text("L")
        expect(self.page.locator("#userRole")).to_have_text("Sesión activa")
        self.page.click("#logoutButton")
        # Al cerrar sesión regresa al inicio del sitio.
        expect(self.page).to_have_url(f"{self.live_server_url}/#inicio")
        expect(self.page.locator("#userName")).to_have_text("Tu espacio")
        expect(self.page.locator("#logoutButton")).to_be_hidden()
        self.assertSinErroresJS()

    def test_aviso_si_la_api_no_responde(self):
        self.page.route("**/api/estudiantes/", lambda route: route.fulfill(status=500, body="{}"))
        self.page.goto(self.live_server_url)
        expect(self.page.locator("#connectionStatus")).to_have_text("Conexión parcial")
        expect(self.page.locator("#globalNotice")).to_contain_text("No se pudieron cargar algunos datos")


# ---------------------------------------------------------------------------
# Diseño responsivo (celular)
# ---------------------------------------------------------------------------

class ResponsivoE2ETests(NavegadorTestCase):
    def setUp(self):
        super().setUp()
        self.context.close()
        self.context = self.browser.new_context(locale="es-MX", viewport=CELULAR, is_mobile=True, has_touch=True)
        self.context.set_default_timeout(10_000)
        self.context.add_init_script("window.print = () => {}; window.__BRUJULA_SIN_VISOR_PDF__ = true;")
        self.page = self.context.new_page()
        self.errores_js = []
        self.page.on("pageerror", lambda error: self.errores_js.append(str(error)))
        grupo = Grupo.objects.create(clave="3A", nombre="Tercero A")
        self.estudiante = Estudiante.objects.create(matricula="A-001", nombres="Lucía", apellidos="Ramos", grupo=grupo)

    def test_menu_lateral_se_abre_y_cierra_en_celular(self):
        self.page.goto(self.live_server_url)
        menu = self.page.locator("#menuToggle")
        expect(menu).to_be_visible()
        expect(menu).to_have_attribute("aria-expanded", "false")
        menu.click()
        expect(self.page.locator("#sidebar")).to_have_class("sidebar open")
        expect(menu).to_have_attribute("aria-expanded", "true")
        expect(self.page.locator("#mobileScrim")).to_have_class("mobile-scrim visible")
        # Al tocar fuera se cierra.
        self.page.locator("#mobileScrim").click(position={"x": 370, "y": 400})
        expect(self.page.locator("#sidebar")).to_have_class("sidebar")
        # Al elegir una sección también se cierra.
        menu.click()
        self.page.locator('.sidebar .nav-link[data-route="guia"]:not([data-scroll])').click()
        expect(self.page.locator("#pageName")).to_have_text("GUÍA DE USO")
        expect(self.page.locator("#sidebar")).to_have_class("sidebar")
        self.assertSinErroresJS()

    def test_secciones_publicas_sin_desborde_horizontal(self):
        crear_cuestionario_vark()
        for ruta in ("inicio", "instrumentos", "guia"):
            with self.subTest(ruta=ruta):
                self.page.goto(f"{self.live_server_url}/#{ruta}")
                expect(self.page.locator(f"#page-{ruta}")).to_have_class("page-section current")
                self.assertSinDesbordeHorizontal(ruta)
        self.assertSinErroresJS()

    def test_evaluacion_completa_en_celular(self):
        cuestionario = crear_cuestionario_vark()
        self.page.goto(f"{self.live_server_url}/#instrumentos")
        expect(self.page.locator("#connectionStatus")).to_have_text("Sistema conectado")
        self.page.select_option("#studentSelect", str(self.estudiante.pk))
        self.page.select_option("#questionnaireSelect", str(cuestionario.pk))
        self.page.click('#assessmentSetup button[type="submit"]')
        mount = self.page.locator("#questionMount")
        mount.get_by_label("Con imágenes (1)").check()
        self.assertSinDesbordeHorizontal("pregunta")
        mount.locator('[data-action="next"]').click()
        mount.get_by_label("Leyendo (2)").check()
        mount.locator('[data-action="next"]').click()
        expect(self.page.locator("#assessmentResult")).to_be_visible()
        self.assertSinDesbordeHorizontal("resultado")
        # Los botones del resultado quedan uno debajo de otro y visibles.
        for boton in ("#viewFicha", "#downloadPdf", "#newAssessment"):
            expect(self.page.locator(boton)).to_be_visible()
        self.assertSinErroresJS()

    def test_panel_de_gestion_en_celular(self):
        admin_user = get_user_model().objects.create_superuser("admin_movil", password="x")
        self.iniciar_sesion(admin_user)
        for url in (reverse("admin:index"), reverse("admin:students_estudiante_changelist"),
                    reverse("admin:students_estudiante_add"), reverse("admin:auth_user_add")):
            with self.subTest(url=url):
                self.page.goto(f"{self.live_server_url}{url}")
                expect(self.page.locator("#content")).to_be_visible()
                self.assertSinDesbordeHorizontal(url)
        self.assertSinErroresJS()

    def test_tablet_vertical_y_horizontal(self):
        crear_cuestionario_vark()
        admin_user = get_user_model().objects.create_superuser("admin_tablet", password="x")
        self.iniciar_sesion(admin_user)
        for nombre, tamaño in (("vertical", {"width": 820, "height": 1180}), ("horizontal", {"width": 1180, "height": 820})):
            self.page.set_viewport_size(tamaño)
            for url in ("/#inicio", "/#instrumentos", "/#guia", reverse("admin:index")):
                with self.subTest(tablet=nombre, url=url):
                    self.page.goto(f"{self.live_server_url}{url}")
                    self.page.wait_for_load_state("networkidle")
                    self.assertSinDesbordeHorizontal(f"tablet {nombre} {url}")
        # En el tablero, las gráficas se ven completas en tablet vertical.
        self.page.set_viewport_size({"width": 820, "height": 1180})
        self.page.goto(f"{self.live_server_url}{reverse('admin:index')}")
        expect(self.page.locator("#varkChart")).to_be_visible()
        expect(self.page.locator("#personalityChart")).to_be_visible()
        self.assertSinErroresJS()

    def test_inicio_de_sesion_y_cierre_en_celular(self):
        self.page.goto(f"{self.live_server_url}{reverse('admin:login')}")
        expect(self.page.locator(".bru-login-card")).to_be_visible()
        self.assertSinDesbordeHorizontal("login")


# ---------------------------------------------------------------------------
# Panel: sesión, permisos por rol, eliminar y recorrido completo sin errores
# ---------------------------------------------------------------------------

class PanelFrontendE2ETests(NavegadorTestCase):
    def setUp(self):
        super().setUp()
        self.clave = "ClaveSegura-2026"
        self.admin = get_user_model().objects.create_superuser("admin_e2e", password=self.clave)

    def entrar(self, usuario="admin_e2e", clave=None):
        self.page.goto(f"{self.live_server_url}{reverse('admin:login')}")
        self.page.fill("#id_username", usuario)
        self.page.fill("#id_password", clave or self.clave)
        self.page.click("#login-form button[type=submit]")

    def test_login_con_datos_incorrectos_muestra_error(self):
        self.entrar(clave="incorrecta")
        expect(self.page.locator(".errornote")).to_be_visible()
        expect(self.page.locator("#login-form")).to_be_visible()

    def test_cerrar_sesion_muestra_despedida_y_regresa_al_inicio(self):
        self.entrar()
        expect(self.page.locator(".bru-dashboard")).to_be_visible()
        self.page.locator("#logout-form button").click()
        tarjeta = self.page.locator(".bru-logout-card")
        expect(tarjeta).to_contain_text("Sesión cerrada")
        expect(self.page).to_have_title("Sesión cerrada · Brújula")
        expect(tarjeta.get_by_role("link", name="Ir al inicio")).to_have_attribute("href", "/#inicio")
        # Regresa solo al inicio del sitio público tras la cuenta regresiva.
        self.page.wait_for_url(f"{self.live_server_url}/#inicio", timeout=9_000)
        expect(self.page.locator("#pageName")).to_have_text("INICIO")
        # La sesión quedó cerrada: el panel vuelve a pedir datos.
        self.page.goto(f"{self.live_server_url}{reverse('admin:index')}")
        expect(self.page.locator("#login-form")).to_be_visible()
        self.assertSinErroresJS()

    def test_quedarme_en_la_pagina_cancela_la_redireccion(self):
        self.entrar()
        self.page.locator("#logout-form button").click()
        self.page.click("#logoutStay")
        expect(self.page.locator("#logoutTimer")).to_contain_text("Redirección cancelada")
        expect(self.page.locator("#logoutStay")).to_be_hidden()
        self.page.wait_for_timeout(6_500)
        self.assertIn("/admin/logout", self.page.url)
        self.page.get_by_role("link", name="Iniciar sesión de nuevo").click()
        expect(self.page.locator("#login-form")).to_be_visible()

    def test_vista_previa_de_permisos_al_elegir_rol(self):
        self.entrar()
        self.page.goto(f"{self.live_server_url}{reverse('admin:auth_user_add')}")
        vista = self.page.locator("#bru-user-template-preview")
        expect(vista).to_be_visible()
        expect(vista).to_contain_text("Elige un rol para ver sus permisos.")
        casos = {
            "docente": ("Docente:", "Podrá entrar al panel administrativo.", "12 permiso(s) del rol:", 12),
            "consultor": ("Consultor / Psicopedagogo:", "Podrá entrar al panel administrativo.", "11 permiso(s) del rol:", 11),
            "estudiante": ("Estudiante:", "No tendrá acceso al panel administrativo.", "no tiene permisos", 0),
            "administrador": ("Administrador:", "Podrá entrar al panel administrativo.", "todos los permisos", 0),
        }
        for rol, (nombre, acceso, estado, total) in casos.items():
            with self.subTest(rol=rol):
                self.page.select_option("#id_rol", rol)
                expect(vista).to_contain_text(nombre)
                expect(self.page.locator("#bru-user-template-access")).to_have_text(acceso)
                expect(self.page.locator("#bru-user-template-status")).to_contain_text(estado)
                expect(self.page.locator("#bru-user-template-permissions li")).to_have_count(total)
        self.assertSinErroresJS()

    def test_alta_de_usuario_desde_el_formulario(self):
        self.entrar()
        self.page.goto(f"{self.live_server_url}{reverse('admin:auth_user_add')}")
        self.page.fill("#id_first_name", "Diana")
        self.page.fill("#id_last_name", "Docente")
        self.page.fill("#id_email", "diana@escuela.example")
        self.page.fill("#id_username", "diana.docente")
        self.page.fill("#id_password1", "OtraClaveSegura-77")
        self.page.fill("#id_password2", "OtraClaveSegura-77")
        self.page.select_option("#id_rol", "docente")
        self.page.locator("input[name=_save]").click()
        expect(self.page.locator(".messagelist")).to_be_visible()
        usuario = get_user_model().objects.get(username="diana.docente")
        self.assertTrue(usuario.is_staff)
        self.assertEqual(list(usuario.groups.values_list("name", flat=True)), ["Docente"])
        self.assertSinErroresJS()

    def test_pagina_de_eliminar_rediseñada_y_cancelar(self):
        grupo = Grupo.objects.create(clave="9Z", nombre="Grupo temporal")
        self.entrar()
        self.page.goto(f"{self.live_server_url}{reverse('admin:students_grupo_delete', args=[grupo.pk])}")
        expect(self.page.locator(".bru-delete")).to_be_visible()
        expect(self.page.get_by_role("button", name="Sí, eliminar")).to_be_visible()
        self.page.get_by_role("link", name="Cancelar").click()
        self.assertTrue(Grupo.objects.filter(pk=grupo.pk).exists())
        self.page.goto(f"{self.live_server_url}{reverse('admin:students_grupo_delete', args=[grupo.pk])}")
        self.page.get_by_role("button", name="Sí, eliminar").click()
        expect(self.page.locator(".messagelist")).to_be_visible()
        self.assertFalse(Grupo.objects.filter(pk=grupo.pk).exists())
        self.assertSinErroresJS()

    def test_todas_las_pantallas_del_panel_sin_errores_de_javascript(self):
        call_command("cargar_datos_demo", stdout=StringIO())
        self.entrar()
        urls = [reverse("admin:index"), reverse("admin:password_change")]
        for modelo, modelo_admin in admin.site._registry.items():
            info = (modelo._meta.app_label, modelo._meta.model_name)
            for vista in ("changelist", "add"):
                try:
                    urls.append(reverse(f"admin:{info[0]}_{info[1]}_{vista}"))
                except NoReverseMatch:
                    pass
            objeto = modelo._default_manager.order_by("pk").first()
            if objeto is not None:
                urls.append(reverse(f"admin:{info[0]}_{info[1]}_change", args=[objeto.pk]))
                urls.append(reverse(f"admin:{info[0]}_{info[1]}_delete", args=[objeto.pk]))
        revisadas = 0
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.page.goto(f"{self.live_server_url}{url}")
                self.assertLess(respuesta.status, 500, url)
                if respuesta.status == 200:
                    expect(self.page.locator("#content")).to_be_visible()
                    revisadas += 1
        self.assertGreater(revisadas, 20)
        self.assertSinErroresJS()
