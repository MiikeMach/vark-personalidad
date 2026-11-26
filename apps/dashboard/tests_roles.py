"""Pruebas de las cuentas por rol y de lo que cada rol puede hacer en el panel."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse

from apps.students.models import Estudiante, Grupo

CLAVE = "ClaveDePrueba-2026!"


def crear_cuentas(password=CLAVE):
    salida = StringIO()
    call_command("crear_cuentas_roles", password=password, stdout=salida)
    return salida.getvalue()


class ComandoCuentasRolesTests(TestCase):
    def test_crea_una_cuenta_por_rol_con_su_rol_y_acceso(self):
        salida = crear_cuentas()
        User = get_user_model()
        esperado = {
            "demo.administrador": ("Administrador", True),
            "demo.coordinador": ("Coordinador", True),
            "demo.docente": ("Docente", True),
            "demo.consultor": ("Consultor / Psicopedagogo", True),
            "demo.estudiante": ("Estudiante", False),
        }
        for username, (rol, staff) in esperado.items():
            with self.subTest(usuario=username):
                usuario = User.objects.get(username=username)
                self.assertEqual(list(usuario.groups.values_list("name", flat=True)), [rol])
                self.assertEqual(usuario.is_staff, staff)
                self.assertFalse(usuario.is_superuser)
                self.assertTrue(usuario.check_password(CLAVE))
                self.assertIn(username, salida)

    def test_es_repetible_y_cambia_la_contrasena(self):
        crear_cuentas()
        crear_cuentas("OtraClaveSegura-99")
        User = get_user_model()
        self.assertEqual(User.objects.filter(username__startswith="demo.").count(), 5)
        self.assertTrue(User.objects.get(username="demo.docente").check_password("OtraClaveSegura-99"))

    def test_sin_contrasena_genera_una_distinta_por_cuenta(self):
        salida = StringIO()
        call_command("crear_cuentas_roles", stdout=salida)
        User = get_user_model()
        hashes = set(User.objects.filter(username__startswith="demo.").values_list("password", flat=True))
        self.assertEqual(len(hashes), 5)

    def test_rechaza_contrasena_debil(self):
        with self.assertRaises(CommandError):
            crear_cuentas("123")
        self.assertFalse(get_user_model().objects.filter(username__startswith="demo.").exists())


def permisos_del_rol(nombre):
    from django.contrib.auth.models import Group

    return set(
        Group.objects.get(name=nombre).permissions.values_list("content_type__app_label", "codename")
    )


class SincronizacionRolesTests(TestCase):
    def test_cada_permiso_de_las_plantillas_existe(self):
        from apps.dashboard.roles import PLANTILLAS_ROL, permisos_de_plantilla

        for clave, plantilla in PLANTILLAS_ROL.items():
            if plantilla.get("all"):
                continue
            with self.subTest(rol=clave):
                encontrados = set(permisos_de_plantilla(clave).values_list("content_type__app_label", "codename"))
                self.assertEqual(encontrados, set(plantilla["permissions"]))

    def test_cada_rol_tiene_exactamente_los_permisos_de_su_plantilla(self):
        from django.contrib.auth.models import Permission

        from apps.dashboard.roles import PLANTILLAS_ROL

        crear_cuentas()
        todos = set(Permission.objects.values_list("content_type__app_label", "codename"))
        for clave, plantilla in PLANTILLAS_ROL.items():
            with self.subTest(rol=clave):
                esperado = todos if plantilla.get("all") else set(plantilla["permissions"])
                self.assertEqual(permisos_del_rol(plantilla["name"]), esperado)

    def test_corrige_un_rol_desfasado_y_el_acceso_de_sus_cuentas(self):
        from django.contrib.auth.models import Group, Permission

        crear_cuentas()
        docente = Group.objects.get(name="Docente")
        docente.permissions.remove(Permission.objects.get(codename="add_evaluacion"))
        docente.permissions.add(Permission.objects.get(codename="delete_estudiante"))
        administrador = Group.objects.get(name="Administrador")
        administrador.permissions.clear()
        User = get_user_model()
        User.objects.filter(username="demo.estudiante").update(is_staff=True)
        User.objects.filter(username="demo.consultor").update(is_staff=False)

        salida = StringIO()
        call_command("sincronizar_roles", stdout=salida)

        self.assertIn(("assessments", "add_evaluacion"), permisos_del_rol("Docente"))
        self.assertNotIn(("students", "delete_estudiante"), permisos_del_rol("Docente"))
        self.assertEqual(administrador.permissions.count(), Permission.objects.count())
        self.assertFalse(User.objects.get(username="demo.estudiante").is_staff)
        self.assertTrue(User.objects.get(username="demo.consultor").is_staff)
        self.assertIn("Roles sincronizados", salida.getvalue())

    def test_crea_los_roles_que_faltan(self):
        from django.contrib.auth.models import Group

        call_command("sincronizar_roles", stdout=StringIO())
        self.assertEqual(Group.objects.count(), 5)
        self.assertEqual(permisos_del_rol("Estudiante"), set())

    def test_al_migrar_se_reaplican_las_plantillas(self):
        from django.contrib.auth.models import Group, Permission

        crear_cuentas()
        consultor = Group.objects.get(name="Consultor / Psicopedagogo")
        consultor.permissions.add(Permission.objects.get(codename="delete_grupo"))
        call_command("migrate", verbosity=0)
        self.assertNotIn(("students", "delete_grupo"), permisos_del_rol("Consultor / Psicopedagogo"))

    def test_no_quita_el_acceso_a_un_superusuario(self):
        from django.contrib.auth.models import Group

        crear_cuentas()
        jefe = get_user_model().objects.create_superuser("jefe", "jefe@example.com", CLAVE)
        jefe.groups.set([Group.objects.get(name="Estudiante")])
        call_command("sincronizar_roles", stdout=StringIO())
        jefe.refresh_from_db()
        self.assertTrue(jefe.is_staff)


class ComandoDatosDemoTests(TestCase):
    def test_llena_todas_las_secciones_y_es_repetible(self):
        from apps.assessments.models import Evaluacion, Respuesta, SeleccionRespuesta
        from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
        from apps.results.models import PuntajeDimension, Resultado

        crear_cuentas()
        call_command("cargar_datos_demo", stdout=StringIO())
        modelos = (Grupo, Estudiante, Cuestionario, Pregunta, Opcion, Evaluacion,
                   Respuesta, SeleccionRespuesta, Resultado, PuntajeDimension)
        totales = {modelo: modelo.objects.count() for modelo in modelos}
        for modelo, total in totales.items():
            with self.subTest(modelo=modelo.__name__):
                self.assertGreater(total, 0)

        # Todos los campos con datos: correos, textos de cuestionario y ambos estados.
        self.assertFalse(Estudiante.objects.filter(correo="").exists())
        self.assertFalse(Cuestionario.objects.filter(descripcion="").exists())
        self.assertFalse(Cuestionario.objects.filter(instrucciones="").exists())
        self.assertTrue(Evaluacion.objects.filter(estado="FINALIZADA", finalizada_en__isnull=False).exists())
        self.assertTrue(Evaluacion.objects.filter(estado="EN_PROGRESO").exists())
        self.assertTrue(Resultado.objects.filter(evaluacion__cuestionario__tipo="PERSONALIDAD").exclude(interpretacion="").exists())
        self.assertTrue(Estudiante.objects.filter(usuario__username="demo.estudiante").exists())
        self.assertTrue(Grupo.objects.filter(activo=False).exists())

        call_command("cargar_datos_demo", stdout=StringIO())
        self.assertEqual({modelo: modelo.objects.count() for modelo in modelos}, totales)

        # El panel muestra los datos en todas sus listas.
        self.client.force_login(get_user_model().objects.create_superuser(username="admin_demo", password="x"))
        for nombre in ("students_grupo", "students_estudiante", "questionnaires_cuestionario",
                       "assessments_evaluacion", "results_resultado"):
            with self.subTest(lista=nombre):
                self.assertEqual(self.client.get(reverse(f"admin:{nombre}_changelist")).status_code, 200)


class PermisosPorRolTests(TestCase):
    """Comprueba en el panel lo que cada rol ve y puede hacer."""

    @classmethod
    def setUpTestData(cls):
        crear_cuentas()
        cls.grupo = Grupo.objects.create(clave="3A", nombre="Tercero A")
        cls.estudiante = Estudiante.objects.create(matricula="A-1", nombres="Ana", apellidos="Prueba", grupo=cls.grupo)

    def entrar(self, rol):
        self.assertTrue(self.client.login(username=f"demo.{rol}", password=CLAVE))

    def estado(self, url, metodo="get", datos=None):
        return getattr(self.client, metodo)(url, datos or {}).status_code

    def test_todas_las_cuentas_inician_sesion(self):
        for rol in ("administrador", "coordinador", "docente", "consultor", "estudiante"):
            with self.subTest(rol=rol):
                self.assertTrue(self.client.login(username=f"demo.{rol}", password=CLAVE))
                self.client.logout()

    def test_administrador_gestiona_usuarios_y_todo_el_panel(self):
        self.entrar("administrador")
        inicio = self.client.get(reverse("admin:index"))
        for url in (
            reverse("admin:auth_user_changelist"), reverse("admin:auth_user_add"),
            reverse("admin:students_estudiante_add"), reverse("admin:questionnaires_cuestionario_add"),
        ):
            with self.subTest(url=url):
                self.assertContains(inicio, f'href="{url}"')
                self.assertEqual(self.estado(url), 200)
        self.assertContains(inicio, 'id="bru-results-title"')
        self.assertEqual(self.estado(reverse("admin:students_estudiante_delete", args=[self.estudiante.pk])), 200)

    def test_coordinador_gestiona_estudiantes_pero_no_usuarios_ni_eliminar(self):
        self.entrar("coordinador")
        inicio = self.client.get(reverse("admin:index"))
        self.assertContains(inicio, reverse("admin:students_estudiante_add"))
        self.assertContains(inicio, 'id="bru-results-title"')
        self.assertNotContains(inicio, reverse("admin:auth_user_changelist"))
        self.assertEqual(self.estado(reverse("admin:students_estudiante_add")), 200)
        self.assertEqual(self.estado(reverse("admin:assessments_evaluacion_add")), 200)
        self.assertEqual(self.estado(reverse("admin:auth_user_changelist")), 403)
        self.assertEqual(self.estado(reverse("admin:students_estudiante_delete", args=[self.estudiante.pk])), 403)
        self.assertEqual(self.estado(reverse("admin:questionnaires_cuestionario_add")), 403)

    def test_docente_consulta_y_aplica_evaluaciones(self):
        self.entrar("docente")
        self.assertEqual(self.estado(reverse("admin:students_estudiante_changelist")), 200)
        self.assertEqual(self.estado(reverse("admin:results_resultado_changelist")), 200)
        self.assertEqual(self.estado(reverse("admin:assessments_evaluacion_add")), 200)
        self.assertEqual(self.estado(reverse("admin:students_estudiante_add")), 403)
        self.assertEqual(self.estado(reverse("admin:auth_user_changelist")), 403)
        # Solo puede ver la ficha del estudiante, no modificarla.
        url = reverse("admin:students_estudiante_change", args=[self.estudiante.pk])
        self.assertEqual(self.estado(url, "post", {"nombres": "Cambio"}), 403)

    def test_consultor_solo_consulta(self):
        self.entrar("consultor")
        inicio = self.client.get(reverse("admin:index"))
        self.assertContains(inicio, 'id="bru-results-title"')
        self.assertNotContains(inicio, 'class="addlink"')
        self.assertEqual(self.estado(reverse("admin:results_resultado_changelist")), 200)
        for url in (
            reverse("admin:assessments_evaluacion_add"), reverse("admin:students_estudiante_add"),
            reverse("admin:students_estudiante_delete", args=[self.estudiante.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.estado(url), 403)
        lista = self.client.get(reverse("admin:students_estudiante_changelist"))
        self.assertNotContains(lista, 'class="bru-row-delete"')
        self.assertContains(lista, ">Ver<")

    def test_estudiante_no_entra_al_panel(self):
        self.entrar("estudiante")
        respuesta = self.client.get(reverse("admin:index"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("admin:login"), respuesta["Location"])
        # Sí puede usar el sitio público.
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
