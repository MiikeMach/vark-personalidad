from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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


class NombresDeUsuarioAdminTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser(
            username="admin_nombres", password="clave-de-prueba"
        )
        self.client.force_login(admin)

    def crear_usuario(self, username):
        return self.client.post(reverse("admin:auth_user_add"), {
            "first_name": "María",
            "last_name": "López",
            "email": "maria@example.test",
            "username": username,
            "password1": "UnaClaveSegura123!",
            "password2": "UnaClaveSegura123!",
            "rol": "docente",
            "_save": "Guardar",
        })

    def test_crear_usuario_con_espacios_y_acceder(self):
        response = self.crear_usuario("María López")
        self.assertEqual(response.status_code, 302)
        usuario = get_user_model().objects.get(username="María López")
        self.assertTrue(usuario.check_password("UnaClaveSegura123!"))
        self.client.logout()
        self.assertTrue(self.client.login(username="María López", password="UnaClaveSegura123!"))

    def test_rechaza_nombre_duplicado_y_caracteres_no_permitidos(self):
        get_user_model().objects.create_user(username="Ana López")
        for username in ("ana lópez", "Ana López!", "   ", "a" * 151):
            with self.subTest(username=username):
                response = self.crear_usuario(username)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors.get("username"))

    def test_editar_usuario_con_espacios_y_evitar_duplicados(self):
        usuario = get_user_model().objects.create_user(username="nombre_original")
        get_user_model().objects.create_user(username="Otro Usuario")
        url = reverse("admin:auth_user_change", args=[usuario.pk])
        datos = {
            "username": "Nombre Editado",
            "first_name": "Ana",
            "last_name": "Prueba",
            "email": "ana@example.test",
            "is_active": "on",
            "rol": "docente",
            "_save": "Guardar",
        }
        response = self.client.post(url, datos)
        self.assertEqual(response.status_code, 302)
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, "Nombre Editado")
        datos["username"] = "Otro Usuario"
        response = self.client.post(url, datos)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors.get("username"))
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, "Nombre Editado")


class AltaUsuarioAdminTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser(
            username="admin_alta", password="clave-de-prueba"
        )
        self.client.force_login(admin)
        self.permiso = Permission.objects.get(content_type__app_label="students", codename="view_estudiante")
        self.url = reverse("admin:auth_user_add")

    def datos(self):
        return {
            "username": "Ana Prueba",
            "password1": "UnaClaveSegura123!",
            "password2": "UnaClaveSegura123!",
            "first_name": "Ana",
            "last_name": "Prueba",
            "email": "ana@example.test",
            "rol": "docente",
            "_save": "Guardar",
        }

    def test_alta_muestra_datos_personales_acceso_y_lista_de_roles(self):
        response = self.client.get(self.url)
        contenido = response.content.decode()
        for campo in ("first_name", "last_name", "email", "username", "password1", "password2"):
            with self.subTest(campo=campo):
                self.assertIn(f'name="{campo}"', contenido)
        self.assertLess(contenido.index('name="first_name"'), contenido.index('name="username"'))
        self.assertLess(contenido.index('name="password2"'), contenido.index('name="rol"'))
        self.assertContains(response, '<select name="rol"')
        for clave in ("administrador", "coordinador", "docente", "consultor", "estudiante"):
            self.assertContains(response, f'<option value="{clave}"')
        for campo in ("usable_password", "groups", "is_staff", "is_superuser", "user_permissions", "date_joined_0"):
            with self.subTest(ausente=campo):
                self.assertNotContains(response, f'name="{campo}"')
        self.assertContains(response, 'id="bru-user-template-preview"')
        self.assertContains(response, "La fecha de creación se registra automáticamente")

    def test_alta_exige_datos_personales_y_rol(self):
        datos = self.datos()
        for campo in ("first_name", "last_name", "email", "rol"):
            datos.pop(campo)
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 200)
        errores = response.context["adminform"].form.errors
        for campo in ("first_name", "last_name", "email", "rol"):
            with self.subTest(campo=campo):
                self.assertIn(campo, errores)
        self.assertFalse(get_user_model().objects.filter(username=datos["username"]).exists())

    def test_alta_rechaza_correo_duplicado(self):
        get_user_model().objects.create_user(username="otra", email="ANA@example.test")
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["adminform"].form.errors)

    def test_plantilla_crea_el_rol_con_sus_permisos_y_da_acceso_al_panel(self):
        inicio = timezone.now()
        datos = self.datos()
        datos["is_staff"] = ""  # Se ignora: el acceso lo define el rol.
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 302)
        usuario = get_user_model().objects.get(username=datos["username"])
        self.assertEqual((usuario.first_name, usuario.last_name, usuario.email), ("Ana", "Prueba", "ana@example.test"))
        self.assertLessEqual(inicio, usuario.date_joined)
        rol = Group.objects.get(name="Docente")
        self.assertEqual(list(usuario.groups.all()), [rol])
        self.assertTrue(usuario.has_perm("assessments.add_evaluacion"))
        self.assertTrue(usuario.has_perm("results.view_resultado"))
        self.assertFalse(usuario.has_perm("students.delete_estudiante"))
        self.assertTrue(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.user_permissions.exists())

    def test_rol_estudiante_no_tiene_acceso_al_panel(self):
        datos = self.datos()
        datos["rol"] = "estudiante"
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 302)
        usuario = get_user_model().objects.get(username=datos["username"])
        self.assertFalse(usuario.is_staff)
        self.assertEqual(list(usuario.groups.values_list("name", flat=True)), ["Estudiante"])

    def test_plantilla_reutiliza_rol_existente_sin_cambiar_permisos(self):
        existente = Group.objects.create(name="Docente")
        existente.permissions.add(self.permiso)
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, 302)
        usuario = get_user_model().objects.get(username="Ana Prueba")
        self.assertEqual(list(usuario.groups.all()), [existente])
        self.assertEqual(list(existente.permissions.all()), [self.permiso])
        self.assertEqual(Group.objects.filter(name="Docente").count(), 1)

    def test_rol_personalizado_existente_aparece_en_la_lista(self):
        tutor = Group.objects.create(name="Tutor")
        tutor.permissions.add(self.permiso)
        response = self.client.get(self.url)
        self.assertContains(response, f'<option value="grupo-{tutor.pk}">Tutor</option>')
        datos = self.datos()
        datos["rol"] = f"grupo-{tutor.pk}"
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 302)
        usuario = get_user_model().objects.get(username=datos["username"])
        self.assertEqual(list(usuario.groups.all()), [tutor])
        self.assertTrue(usuario.has_perm("students.view_estudiante"))

    def test_alta_rechaza_rol_inexistente_sin_guardar_usuario(self):
        datos = self.datos()
        datos["rol"] = "inventado"
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors.get("rol"))
        self.assertFalse(get_user_model().objects.filter(username=datos["username"]).exists())

    def test_sin_permiso_para_crear_roles_solo_ofrece_roles_existentes(self):
        Group.objects.create(name="Docente")
        gestor = get_user_model().objects.create_user(
            username="gestor_plantillas", password="clave-de-prueba", is_staff=True
        )
        gestor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="auth", codename__in=["add_user", "change_user"]
        ))
        self.client.force_login(gestor)
        response = self.client.get(self.url)
        self.assertContains(response, '<option value="docente"')
        self.assertNotContains(response, '<option value="administrador"')
        datos = self.datos()
        datos["rol"] = "administrador"
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Group.objects.filter(name="Administrador").exists())


class FichaUsuarioAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin_ficha", password="clave-de-prueba"
        )
        self.usuario = get_user_model().objects.create_user(
            username="cuenta_prueba", password="clave-de-prueba", is_staff=True,
            first_name="Ana", last_name="Prueba", email="ana@example.test",
        )
        self.docente = Group.objects.create(name="Docente")
        self.coordinador = Group.objects.create(name="Coordinador")
        self.usuario.groups.add(self.docente)
        self.permiso = Permission.objects.get(content_type__app_label="students", codename="view_estudiante")
        self.usuario.user_permissions.add(self.permiso)
        self.client.force_login(self.admin)
        self.url = reverse("admin:auth_user_change", args=[self.usuario.pk])

    def datos(self):
        return {
            "first_name": "Ana",
            "last_name": "Prueba",
            "email": "ana@example.test",
            "username": self.usuario.username,
            "is_active": "on",
            "rol": "coordinador",
            "_save": "Guardar",
        }

    def test_ficha_muestra_solo_los_campos_necesarios(self):
        response = self.client.get(self.url)
        contenido = response.content.decode()
        for campo in ("first_name", "last_name", "email", "username", "is_active"):
            with self.subTest(campo=campo):
                self.assertIn(f'name="{campo}"', contenido)
        self.assertContains(response, '<select name="rol"')
        self.assertContains(response, '<option value="docente" selected>')
        self.assertContains(response, "Contraseña configurada")
        self.assertContains(response, 'id="bru-user-template-preview"')
        for ausente in (
            'name="groups"', 'name="is_staff"', 'name="is_superuser"', 'name="user_permissions"',
            'name="date_joined_0"', "Permisos avanzados", "Fechas de la cuenta", "Gestionar roles",
            "pbkdf2_sha256",
        ):
            with self.subTest(ausente=ausente):
                self.assertNotContains(response, ausente)

    def test_cambiar_rol_reemplaza_el_anterior_y_conserva_permisos_directos(self):
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(list(self.usuario.groups.all()), [self.coordinador])
        self.assertEqual(list(self.usuario.user_permissions.all()), [self.permiso])
        self.assertTrue(self.usuario.is_staff)
        self.assertFalse(self.usuario.is_superuser)

    def test_cambiar_a_estudiante_quita_acceso_al_panel(self):
        datos = self.datos()
        datos["rol"] = "estudiante"
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_staff)
        self.assertEqual(list(self.usuario.groups.values_list("name", flat=True)), ["Estudiante"])

    def test_desactivar_cuenta(self):
        datos = self.datos()
        datos.pop("is_active")
        self.assertEqual(self.client.post(self.url, datos).status_code, 302)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)

    def test_no_puede_quitarse_el_acceso_a_si_mismo(self):
        self.usuario.is_superuser = False
        url = reverse("admin:auth_user_change", args=[self.admin.pk])
        datos = {
            "first_name": "Admin", "last_name": "Ficha", "email": "admin@example.test",
            "username": self.admin.username, "rol": "administrador", "_save": "Guardar",
        }
        response = self.client.post(url, datos)
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_active", response.context["adminform"].form.errors)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_errores_no_cambian_los_datos(self):
        datos = self.datos()
        datos["username"] = ""
        datos["email"] = ""
        response = self.client.post(self.url, datos)
        self.assertEqual(response.status_code, 200)
        errores = response.context["adminform"].form.errors
        self.assertIn("username", errores)
        self.assertIn("email", errores)
        self.assertEqual(list(self.usuario.groups.all()), [self.docente])

    def test_lista_muestra_datos_roles_y_acciones(self):
        response = self.client.get(reverse("admin:auth_user_changelist"))
        for texto in ("Ana Prueba", "ana@example.test", "Docente", "Editar", "Eliminar"):
            with self.subTest(texto=texto):
                self.assertContains(response, texto)
        self.assertContains(response, f'href="{self.url}"')

    def test_no_permite_eliminar_la_cuenta_propia(self):
        delete_url = reverse("admin:auth_user_delete", args=[self.admin.pk])
        self.assertNotContains(self.client.get(reverse("admin:auth_user_changelist")), delete_url)
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
        self.assertTrue(get_user_model().objects.filter(pk=self.admin.pk).exists())

    def test_eliminar_otra_cuenta(self):
        delete_url = reverse("admin:auth_user_delete", args=[self.usuario.pk])
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        for texto in ("Ana Prueba", "ana@example.test", "Docente", "no se puede deshacer",
                      "Desactiva la cuenta", "Sí, eliminar cuenta", "Cancelar"):
            with self.subTest(texto=texto):
                self.assertContains(response, texto)
        self.assertNotContains(response, 'id="deleted-objects"')
        response = self.client.post(delete_url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(pk=self.usuario.pk).exists())

    def test_eliminar_cuenta_de_estudiante_conserva_su_registro(self):
        grupo = Grupo.objects.create(clave="G-1", nombre="Grupo 1")
        estudiante = Estudiante.objects.create(
            usuario=self.usuario, matricula="M-1", nombres="Ana", apellidos="Prueba", grupo=grupo
        )
        delete_url = reverse("admin:auth_user_delete", args=[self.usuario.pk])
        self.assertContains(self.client.get(delete_url), "se conserva, pero queda sin cuenta vinculada")
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 302)
        estudiante.refresh_from_db()
        self.assertIsNone(estudiante.usuario)

    def test_cambiar_contrasena_sin_opcion_de_deshabilitarla(self):
        url = reverse("admin:auth_user_password_change", args=[self.usuario.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="usable_password"')
        self.assertNotContains(response, 'name="unset-password"')
        response = self.client.post(url, {"password1": "", "password2": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("password1"))
        response = self.client.post(url, {"password1": "OtraClaveSegura456!", "password2": "OtraClaveSegura456!"})
        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("OtraClaveSegura456!"))

    def test_solo_lectura_no_permite_editar(self):
        consulta = get_user_model().objects.create_user(
            username="consulta_ficha", password="clave-de-prueba", is_staff=True
        )
        consulta.user_permissions.add(Permission.objects.get(content_type__app_label="auth", codename="view_user"))
        self.client.force_login(consulta)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="rol"')
        self.assertContains(response, "Docente")
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, 403)


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

    def test_roles_y_permisos_no_aparece_en_el_panel_ni_menu(self):
        self.client.force_login(self.admin)
        for url in (
            reverse("admin:index"),
            reverse("admin:app_list", kwargs={"app_label": "auth"}),
            reverse("admin:students_estudiante_changelist"),
            reverse("admin:auth_user_add"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="auth-user"')
                self.assertNotContains(response, 'id="auth-group"')
                self.assertNotContains(response, "Roles y permisos")
                self.assertNotContains(response, "Gestionar roles")
                self.assertNotContains(response, 'id="questionnaires-pregunta"')
                self.assertNotContains(response, 'id="questionnaires-opcion"')

    def test_inicio_ofrece_formulario_de_evaluacion_y_acceso(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'id="assessmentSetup"')
        self.assertContains(response, 'id="studentSelect"')
        self.assertContains(response, 'id="questionnaireSelect"')
        self.assertContains(response, 'data-choice="VARK"')
        self.assertContains(response, 'data-choice="PERSONALIDAD"')
        self.assertContains(response, 'href="/admin/"')
        self.assertNotContains(response, 'id="studentLogin"')

    def test_constructor_ofrece_vista_previa_sin_descarga(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:questionnaires_cuestionario_add"))

        self.assertContains(response, 'id="bru-questionnaire-builder"')
        self.assertContains(response, 'data-builder-action="preview"')
        self.assertNotContains(response, "Descargar borrador JSON")
        self.assertContains(response, "brujuela-questionnaire-builder.js")

    def test_todas_las_secciones_muestran_lista_ficha_y_eliminar_rediseñados(self):
        from apps.results.models import PuntajeDimension, Resultado

        grupo = Grupo.objects.create(clave="G-1", nombre="Grupo 1")
        estudiante = Estudiante.objects.create(matricula="M-1", nombres="Ana", apellidos="Prueba", grupo=grupo)
        cuestionario = Cuestionario.objects.create(titulo="Estilos", tipo="VARK")
        pregunta = Pregunta.objects.create(cuestionario=cuestionario, texto="¿Cómo aprendes?", orden=1)
        opcion = Opcion.objects.create(pregunta=pregunta, texto="Viendo", dimension="V", orden=1)
        evaluacion = Evaluacion.objects.create(estudiante=estudiante, cuestionario=cuestionario, estado="FINALIZADA")
        respuesta = Respuesta.objects.create(evaluacion=evaluacion, pregunta=pregunta)
        seleccion = SeleccionRespuesta.objects.create(respuesta=respuesta, opcion=opcion)
        resultado = Resultado.objects.create(evaluacion=evaluacion, preguntas_contestadas=1)
        puntaje = PuntajeDimension.objects.create(resultado=resultado, dimension="V", puntaje=3)
        self.client.force_login(self.admin)

        for nombre, obj in (
            ("students_grupo", grupo), ("students_estudiante", estudiante),
            ("questionnaires_cuestionario", cuestionario), ("questionnaires_pregunta", pregunta),
            ("questionnaires_opcion", opcion), ("assessments_evaluacion", evaluacion),
            ("assessments_respuesta", respuesta), ("assessments_seleccionrespuesta", seleccion),
            ("results_resultado", resultado), ("results_puntajedimension", puntaje),
        ):
            with self.subTest(seccion=nombre):
                lista = self.client.get(reverse(f"admin:{nombre}_changelist"))
                self.assertEqual(lista.status_code, 200)
                self.assertContains(lista, 'class="bru-row-edit"')
                self.assertContains(lista, 'class="bru-row-delete"')
                self.assertEqual(self.client.get(reverse(f"admin:{nombre}_change", args=[obj.pk])).status_code, 200)
                eliminar = self.client.get(reverse(f"admin:{nombre}_delete", args=[obj.pk]))
                self.assertEqual(eliminar.status_code, 200)
                contenido = eliminar.content.decode()
                # O se puede eliminar (con confirmación) o está en uso y se explica por qué.
                self.assertTrue(
                    ("no se puede deshacer" in contenido and "Sí, eliminar" in contenido)
                    or "No se puede eliminar este registro" in contenido
                )
                self.assertNotIn('id="deleted-objects"', contenido)

        # Columnas útiles en las listas.
        self.assertContains(self.client.get(reverse("admin:students_estudiante_changelist")), "Ana Prueba")
        self.assertContains(self.client.get(reverse("admin:results_resultado_changelist")), "Visual · 3")
        self.assertContains(self.client.get(reverse("admin:assessments_evaluacion_changelist")), "Ver resultado")
        # Un registro en uso no se puede eliminar y lo explica.
        protegido = self.client.get(reverse("admin:students_grupo_delete", args=[grupo.pk]))
        self.assertContains(protegido, "No se puede eliminar este registro")
        # Uno sin dependencias muestra la confirmación y se elimina.
        url = reverse("admin:results_puntajedimension_delete", args=[puntaje.pk])
        self.assertContains(self.client.get(url), "Sí, eliminar")
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        self.assertFalse(PuntajeDimension.objects.filter(pk=puntaje.pk).exists())

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
