from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from apps.assessments.models import Evaluacion, Respuesta, SeleccionRespuesta
from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from apps.students.models import Estudiante, Grupo


class RolesAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin_test", password="test-password"
        )
        self.usuario = get_user_model().objects.create_user(
            username="docente_test", first_name="Ana", last_name="López"
        )
        self.client.force_login(self.admin)

    def test_crear_rol_y_asignar_usuario_sin_quitar_otros_roles(self):
        otro_rol = Group.objects.create(name="Otro")
        self.usuario.groups.add(otro_rol)
        permiso = Permission.objects.get(content_type__app_label="students", codename="view_estudiante")

        response = self.client.post(reverse("admin:auth_group_add"), {
            "name": "Docente",
            "permissions": [permiso.pk],
            "usuario": self.usuario.pk,
            "_save": "Guardar",
        })

        self.assertEqual(response.status_code, 302)
        rol = Group.objects.get(name="Docente")
        self.assertTrue(self.usuario.groups.filter(pk=rol.pk).exists())
        self.assertTrue(self.usuario.groups.filter(pk=otro_rol.pk).exists())
        self.assertEqual(list(rol.permissions.all()), [permiso])

    def test_asignar_usuario_a_rol_existente_sin_cambiar_permisos(self):
        rol = Group.objects.create(name="Personalizado")
        permiso = Permission.objects.get(content_type__app_label="students", codename="view_estudiante")
        rol.permissions.add(permiso)

        response = self.client.post(reverse("admin:auth_group_change", args=[rol.pk]), {
            "name": rol.name,
            "permissions": [permiso.pk],
            "usuario": self.usuario.pk,
            "_save": "Guardar",
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.usuario.groups.filter(pk=rol.pk).exists())
        self.assertEqual(list(rol.permissions.all()), [permiso])

    def test_sin_permiso_de_usuario_no_puede_asignar_rol(self):
        gestor = get_user_model().objects.create_user(
            username="gestor_test", password="test-password", is_staff=True
        )
        gestor.user_permissions.add(Permission.objects.get(codename="change_group"))
        self.client.force_login(gestor)
        rol = Group.objects.create(name="Personalizado")
        url = reverse("admin:auth_group_change", args=[rol.pk])

        response = self.client.get(url)
        self.assertNotContains(response, 'name="usuario"')
        response = self.client.post(url, {
            "name": rol.name,
            "usuario": self.usuario.pk,
            "_save": "Guardar",
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.usuario.groups.filter(pk=rol.pk).exists())

    def test_usuario_invalido_no_se_asigna(self):
        response = self.client.post(reverse("admin:auth_group_add"), {
            "name": "Docente",
            "usuario": 999999,
            "_save": "Guardar",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Group.objects.filter(name="Docente").exists())

    def test_error_al_editar_no_cambia_permisos_ni_asigna_usuario(self):
        rol = Group.objects.create(name="Consulta")
        Group.objects.create(name="Nombre duplicado")
        permiso = Permission.objects.get(content_type__app_label="students", codename="view_estudiante")
        otro_permiso = Permission.objects.get(content_type__app_label="students", codename="change_estudiante")
        rol.permissions.add(permiso)

        response = self.client.post(reverse("admin:auth_group_change", args=[rol.pk]), {
            "name": "Nombre duplicado",
            "permissions": [otro_permiso.pk],
            "usuario": self.usuario.pk,
            "_save": "Guardar",
        })

        self.assertEqual(response.status_code, 200)
        rol.refresh_from_db()
        self.assertEqual(rol.name, "Consulta")
        self.assertEqual(list(rol.permissions.all()), [permiso])
        self.assertFalse(self.usuario.groups.filter(pk=rol.pk).exists())
        self.assertContains(response, 'id="bru-role-permission-list"')

    def test_lista_muestra_eliminar_por_fila_y_confirmacion(self):
        rol = Group.objects.create(name="Docente")
        url = reverse("admin:auth_group_changelist")
        delete_url = reverse("admin:auth_group_delete", args=[rol.pk])

        response = self.client.get(url, {"q": "Docente"})

        self.assertContains(response, 'class="bru-row-delete"')
        self.assertContains(response, delete_url)
        self.assertContains(response, "_changelist_filters=")
        self.assertNotContains(response, 'name="action"')
        self.assertNotContains(response, 'name="_selected_action"')
        response = self.client.get(delete_url)
        self.assertContains(response, "Docente")
        self.assertTrue(Group.objects.filter(pk=rol.pk).exists())
        response = self.client.post(delete_url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Group.objects.filter(pk=rol.pk).exists())

    def test_listas_de_usuarios_y_grupos_escolares_tienen_acciones_por_fila(self):
        from apps.students.models import Grupo

        grupo = Grupo.objects.create(clave="TEST", nombre="Grupo de prueba")
        for list_url, delete_url in (
            (reverse("admin:auth_user_changelist"), reverse("admin:auth_user_delete", args=[self.usuario.pk])),
            (reverse("admin:students_grupo_changelist"), reverse("admin:students_grupo_delete", args=[grupo.pk])),
        ):
            with self.subTest(url=list_url):
                response = self.client.get(list_url)
                self.assertContains(response, delete_url)
                self.assertNotContains(response, 'name="action"')

    def test_sin_permiso_no_muestra_ni_permite_eliminar(self):
        rol = Group.objects.create(name="Consulta")
        gestor = get_user_model().objects.create_user(
            username="consulta", password="test-password", is_staff=True
        )
        gestor.user_permissions.add(Permission.objects.get(codename="view_group"))
        self.client.force_login(gestor)

        response = self.client.get(reverse("admin:auth_group_changelist"))
        self.assertNotContains(response, 'class="bru-row-delete"')
        response = self.client.post(reverse("admin:auth_group_delete", args=[rol.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Group.objects.filter(pk=rol.pk).exists())

    def test_popup_no_muestra_acciones_por_fila(self):
        Group.objects.create(name="Consulta")
        response = self.client.get(reverse("admin:auth_group_changelist"), {"_popup": "1"})
        self.assertNotContains(response, 'class="bru-row-delete"')
        self.assertNotContains(response, 'class="bru-row-view"')

    def test_ver_usuarios_muestra_solo_los_integrantes_del_rol(self):
        rol = Group.objects.create(name="Docente")
        self.usuario.groups.add(rol)
        url = reverse("admin:auth_user_changelist") + f"?groups__id__exact={rol.pk}"

        response = self.client.get(reverse("admin:auth_group_changelist"))
        self.assertContains(response, f'href="{url}"')
        self.assertContains(response, 'aria-label="Ver usuarios del rol Docente"')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cl"].result_list), [self.usuario])

        vacio = Group.objects.create(name="Sin integrantes")
        response = self.client.get(reverse("admin:auth_user_changelist"), {
            "groups__id__exact": vacio.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["cl"].result_list.exists())

    def test_ver_usuarios_requiere_permiso_de_consulta_de_usuarios(self):
        Group.objects.create(name="Consulta")
        gestor = get_user_model().objects.create_user(
            username="gestor_roles", password="test-password", is_staff=True
        )
        gestor.user_permissions.add(Permission.objects.get(codename="view_group"))
        self.client.force_login(gestor)

        response = self.client.get(reverse("admin:auth_group_changelist"))
        self.assertNotContains(response, 'class="bru-row-view"')
        self.assertEqual(self.client.get(reverse("admin:auth_user_changelist")).status_code, 403)

        gestor.user_permissions.add(Permission.objects.get(codename="view_user"))
        response = self.client.get(reverse("admin:auth_group_changelist"))
        self.assertContains(response, 'class="bru-row-view"')


class CambioContrasenaAdminTests(TestCase):
    def test_formulario_y_errores_sin_selector_de_tema(self):
        usuario = get_user_model().objects.create_superuser(
            username="admin_clave", password="clave-anterior-de-prueba"
        )
        self.client.force_login(usuario)
        url = reverse("admin:password_change")

        response = self.client.get(url)
        self.assertContains(response, 'name="old_password"')
        self.assertContains(response, 'name="new_password1"')
        self.assertNotContains(response, 'class="theme-toggle"')

        response = self.client.post(url, {
            "old_password": "clave-incorrecta",
            "new_password1": "nueva-clave-de-prueba",
            "new_password2": "nueva-clave-de-prueba",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("old_password"))
        self.assertNotContains(response, 'class="theme-toggle"')
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("clave-anterior-de-prueba"))

    def test_confirmacion_sin_selector_de_tema(self):
        self.client.force_login(get_user_model().objects.create_superuser(
            username="admin_confirmacion", password="clave-de-prueba"
        ))
        response = self.client.get(reverse("admin:password_change_done"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="theme-toggle"')


class TableroResultadosTests(TestCase):
    def test_tablero_no_aparece_en_inicio(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'id="page-resultados"')
        self.assertNotContains(response, 'data-route="resultados"')

    def test_tablero_admin_requiere_permiso_de_resultados(self):
        usuario = get_user_model().objects.create_user(
            username="staff_tablero", password="test-password", is_staff=True
        )
        self.client.force_login(usuario)
        url = reverse("admin:index")
        self.assertNotContains(self.client.get(url), 'id="bru-results-title"')

        usuario.user_permissions.add(Permission.objects.get(
            content_type__app_label="results", codename="view_resultado"
        ))
        self.assertContains(self.client.get(url), 'id="bru-results-title"')


class FiltrosAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser(
            username="admin_filtros", password="test-password"
        ))

    def test_listas_sin_filtros_de_fecha(self):
        listas = (
            "admin:students_grupo_changelist",
            "admin:students_estudiante_changelist",
            "admin:questionnaires_cuestionario_changelist",
            "admin:assessments_evaluacion_changelist",
            "admin:results_resultado_changelist",
            "admin:auth_user_changelist",
        )
        for nombre in listas:
            with self.subTest(lista=nombre):
                response = self.client.get(reverse(nombre))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'type="date"')
                self.assertFalse(any(
                    getattr(spec, "field_path", None) in {
                        "creado_en", "iniciada_en", "finalizada_en",
                        "calculado_en", "date_joined", "last_login",
                    }
                    for spec in response.context["cl"].filter_specs
                ))

    def test_lista_usuarios_conserva_filtros_de_gestion_sin_superusuario(self):
        Group.objects.create(name="Docente")
        response = self.client.get(reverse("admin:auth_user_changelist"))

        self.assertEqual(response.status_code, 200)
        filtros = {spec.field_path for spec in response.context["cl"].filter_specs}
        self.assertEqual(filtros, {"is_staff", "is_active", "groups"})

    def test_recuentos_siempre_visibles_y_sin_selector(self):
        Grupo.objects.create(clave="ACTIVO-1", nombre="Activo 1", activo=True)
        Grupo.objects.create(clave="ACTIVO-2", nombre="Activo 2", activo=True)
        Grupo.objects.create(clave="INACTIVO", nombre="Inactivo", activo=False)
        url = reverse("admin:students_grupo_changelist")

        for params in ({}, {"activo__exact": "1"}, {"_facets": "False"}):
            with self.subTest(params=params):
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, 200)
                changelist = response.context["cl"]
                self.assertTrue(changelist.add_facets)
                self.assertFalse(changelist.is_facets_optional)
                self.assertNotContains(response, "Mostrar recuentos")
                self.assertNotContains(response, "Ocultar recuentos")
                filtro = next(spec for spec in changelist.filter_specs if getattr(spec, "field_path", None) == "activo")
                opciones = list(filtro.choices(changelist))
                self.assertTrue(any(str(choice["display"]).endswith("(2)") for choice in opciones))
                self.assertTrue(any(str(choice["display"]).endswith("(1)") for choice in opciones))


class InterfazFrontendTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin_interfaz", password="clave-de-prueba"
        )

    def test_panel_muestra_enlaces_a_los_apartados_de_gestion(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:index"))

        for texto, url in (
            ("Usuarios y acceso", reverse("admin:auth_user_changelist")),
            ("Roles y permisos", reverse("admin:auth_group_changelist")),
            ("Estudiantes", reverse("admin:students_estudiante_changelist")),
            ("Cuestionarios", reverse("admin:questionnaires_cuestionario_changelist")),
            ("Opciones seleccionadas", reverse("admin:assessments_seleccionrespuesta_changelist")),
            ("Resultados", reverse("admin:results_resultado_changelist")),
        ):
            with self.subTest(apartado=texto):
                self.assertContains(response, texto)
                self.assertContains(response, f'href="{url}"')

    def test_panel_solo_muestra_apartados_permitidos(self):
        usuario = get_user_model().objects.create_user(
            username="consulta_estudiantes", password="clave-de-prueba", is_staff=True
        )
        usuario.user_permissions.add(Permission.objects.get(
            content_type__app_label="students", codename="view_estudiante"
        ))
        self.client.force_login(usuario)
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, reverse("admin:students_estudiante_changelist"))
        self.assertNotContains(response, reverse("admin:students_estudiante_add"))
        self.assertNotContains(response, reverse("admin:auth_user_changelist"))
        self.assertNotContains(response, reverse("admin:results_resultado_changelist"))

    def test_inicio_ofrece_formulario_de_evaluacion_y_acceso(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'id="assessmentSetup"')
        self.assertContains(response, 'id="studentSelect"')
        self.assertContains(response, 'id="questionnaireSelect"')
        self.assertContains(response, 'data-choice="VARK"')
        self.assertContains(response, 'data-choice="PERSONALIDAD"')
        self.assertContains(response, 'href="/admin/login/?next=/"')

    def test_constructor_ofrece_vista_previa_sin_descarga(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:questionnaires_cuestionario_add"))

        self.assertContains(response, 'id="bru-questionnaire-builder"')
        self.assertContains(response, 'data-builder-action="preview"')
        self.assertNotContains(response, "Descargar borrador JSON")
        self.assertContains(response, "brujuela-questionnaire-builder.js")

    def test_opciones_seleccionadas_muestran_detalles_de_la_respuesta(self):
        grupo = Grupo.objects.create(clave="TEST", nombre="Grupo de prueba")
        estudiante = Estudiante.objects.create(
            matricula="TEST-1", nombres="Ana", apellidos="Prueba", grupo=grupo
        )
        cuestionario = Cuestionario.objects.create(titulo="Cuestionario de prueba", tipo="VARK")
        pregunta = Pregunta.objects.create(cuestionario=cuestionario, texto="Pregunta de prueba", orden=1)
        opcion = Opcion.objects.create(pregunta=pregunta, texto="Opción de prueba", dimension="V", orden=1)
        evaluacion = Evaluacion.objects.create(estudiante=estudiante, cuestionario=cuestionario)
        respuesta = Respuesta.objects.create(evaluacion=evaluacion, pregunta=pregunta)
        SeleccionRespuesta.objects.create(respuesta=respuesta, opcion=opcion)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin:assessments_seleccionrespuesta_changelist"))

        for texto in ("Ana", "Cuestionario de prueba", "Pregunta de prueba", "Opción de prueba", "Visual"):
            with self.subTest(texto=texto):
                self.assertContains(response, texto)
