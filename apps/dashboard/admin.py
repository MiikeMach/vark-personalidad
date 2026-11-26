from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode

from .admin_actions import DashboardAdminMixin, insignia
from .roles import (
    PLANTILLAS_ROL,
    acceso_al_panel,
    opciones_de_rol,
    plantillas_para_vista_previa,
    resolver_rol,
    roles_para_vista_previa,
    valor_de_rol,
)


class UsuarioRolChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        nombre = usuario.get_full_name().strip()
        return f"{nombre} ({usuario.get_username()})" if nombre else usuario.get_username()


class RolAdminForm(forms.ModelForm):
    usuario = UsuarioRolChoiceField(
        queryset=get_user_model().objects.order_by(get_user_model().USERNAME_FIELD),
        required=False,
        label="3. Asignar a un usuario (opcional)",
        empty_label="Selecciona un usuario (opcional)",
        help_text=(
            "El rol se añade al usuario al guardar; no elimina sus otros roles ni permisos. "
            "El acceso al panel se configura en la cuenta del usuario."
        ),
    )

    class Meta:
        model = Group
        fields = "__all__"


class RolAdmin(DashboardAdminMixin, GroupAdmin):
    form = RolAdminForm
    list_display = ("__str__", "ver_usuarios")

    def has_module_permission(self, request):
        # Los roles se asignan desde «Usuarios» con plantillas; no se muestran en el panel ni en el menú.
        return False

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        usuario_admin = self.admin_site.get_model_admin(get_user_model())
        if "_popup" in request.GET or not usuario_admin.has_view_or_change_permission(request):
            return tuple(field for field in fields if field != "ver_usuarios")
        return fields

    @admin.display(description="Usuarios")
    def ver_usuarios(self, rol):
        opts = get_user_model()._meta
        url = reverse(f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_changelist")
        query = urlencode({"groups__id__exact": rol.pk})
        return format_html(
            '<a class="bru-row-view" href="{}?{}" aria-label="Ver usuarios del rol {}">Ver</a>',
            url, query, rol,
        )

    def get_fields(self, request, obj=None):
        fields = ["name"]
        can_edit = self.has_change_permission(request, obj) if obj else self.has_add_permission(request)
        if can_edit and request.user.has_perm("auth.change_user"):
            fields.append("usuario")
        fields.append("permissions")
        return fields

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context["plantillas_rol"] = [
            {key: item[key] for key in ("key", "name", "description", "all", "permission_ids")}
            for item in plantillas_para_vista_previa()
        ]
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        usuario = form.cleaned_data.get("usuario")
        if usuario is not None and request.user.has_perm("auth.change_user"):
            usuario.groups.add(form.instance)


admin.site.unregister(Group)
admin.site.register(Group, RolAdmin)


class UsuarioFormMixin:
    """Campos comunes del alta y la edición: datos personales, usuario y rol."""

    puede_crear_roles = False
    usuario_actual_pk = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        etiquetas = {"first_name": "Nombre(s)", "last_name": "Apellidos", "email": "Correo electrónico"}
        for nombre, etiqueta in etiquetas.items():
            if nombre in self.fields:
                self.fields[nombre].label = etiqueta
                self.fields[nombre].required = True
        if "email" in self.fields:
            self.fields["email"].help_text = "Debe ser único; se usa para identificar y contactar a la persona."

        if "username" in self.fields:
            campo = self.fields["username"]
            campo.label = "Usuario"
            campo.validators.append(RegexValidator(
                regex=r"^[\w.@+ -]+\Z",
                message="Usa solo letras, números, espacios y los caracteres @, ., +, - y _.",
            ))
            campo.help_text = "Con este nombre iniciará sesión. Máximo 150 caracteres."
        if "is_active" in self.fields:
            self.fields["is_active"].label = "Cuenta activa"
            self.fields["is_active"].help_text = "Desmárcala para impedir que inicie sesión sin eliminar la cuenta."

        if "rol" in self.fields:
            opciones = opciones_de_rol(self.puede_crear_roles)
            if not opciones:
                self.fields.pop("rol")
            else:
                campo = self.fields["rol"]
                campo.choices = [("", "Selecciona un rol")] + opciones
                if self.instance.pk:
                    campo.initial = valor_de_rol(self.instance)
                    if self.instance.groups.count() > 1:
                        campo.help_text += " Tenía varios roles: al guardar se reemplazan por el elegido."

    # El formulario valida el nombre; el validador del modelo de Django no permite espacios.
    def _get_validation_exclusions(self):
        excluded = super()._get_validation_exclusions()
        excluded.add("username")
        return excluded

    def validate_unique(self):
        excluded = super()._get_validation_exclusions()
        try:
            self.instance.validate_unique(exclude=excluded)
        except ValidationError as error:
            self._update_errors(error)

    def clean_first_name(self):
        return " ".join(self.cleaned_data.get("first_name", "").split())

    def clean_last_name(self):
        return " ".join(self.cleaned_data.get("last_name", "").split())

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if email:
            duplicados = get_user_model().objects.filter(email__iexact=email)
            if self.instance.pk:
                duplicados = duplicados.exclude(pk=self.instance.pk)
            if duplicados.exists():
                raise ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        es_propia = self.instance.pk is not None and self.instance.pk == self.usuario_actual_pk
        if es_propia:
            # Evita que alguien se deje sin acceso al panel por error.
            if "is_active" in self.fields and not cleaned_data.get("is_active"):
                self.add_error("is_active", "No puedes desactivar tu propia cuenta.")
            rol = cleaned_data.get("rol")
            if rol and not acceso_al_panel(rol) and not self.instance.is_superuser:
                self.add_error("rol", "Este rol no tiene acceso al panel; no puedes asignártelo a ti.")
        return cleaned_data


def campo_rol():
    return forms.ChoiceField(
        label="Rol",
        choices=(),
        error_messages={"required": "Selecciona el rol de la cuenta."},
        help_text="Abajo verás los permisos que tendrá la cuenta con este rol.",
    )


class UsuarioAltaForm(UsuarioFormMixin, UserCreationForm):
    rol = campo_rol()


class UsuarioCambioForm(UsuarioFormMixin, UserChangeForm):
    rol = campo_rol()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "password" in self.fields:
            self.fields["password"].label = "Contraseña"
            self.fields["password"].widget.template_name = "admin/auth/user/password_summary.html"


class CambioContrasenaForm(AdminPasswordChangeForm):
    """Cambio de contraseña sin la opción de deshabilitar la autenticación por contraseña."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("usable_password", None)
        self.fields["password1"].required = True
        self.fields["password2"].required = True


class UsuarioAdmin(DashboardAdminMixin, UserAdmin):
    change_password_form = CambioContrasenaForm
    add_form = UsuarioAltaForm
    add_form_template = "admin/brujuela_user_add.html"
    form = UsuarioCambioForm
    list_display = ("username", "nombre_completo", "email", "roles", "acceso_panel", "estado")
    list_filter = ("is_staff", "is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("last_name", "first_name", "username")
    readonly_fields = ("roles",)
    _rol_fieldset = {
        "classes": ("bru-user-roles",),
        "description": (
            "La cuenta recibe los permisos del rol elegido. El acceso al panel "
            "administrativo depende del rol (Estudiante no entra al panel)."
        ),
    }
    add_fieldsets = (
        ("Información personal", {"fields": ("first_name", "last_name", "email")}),
        ("Datos de acceso", {"fields": ("username", "password1", "password2")}),
        ("Rol y permisos", {"fields": ("rol",), **_rol_fieldset}),
    )
    fieldsets = (
        ("Información personal", {"fields": ("first_name", "last_name", "email")}),
        ("Datos de acceso", {"fields": ("username", "password", "is_active")}),
        ("Rol y permisos", {"fields": ("rol",), **_rol_fieldset}),
    )

    @admin.display(description="Nombre completo", ordering="last_name")
    def nombre_completo(self, usuario):
        return usuario.get_full_name() or "—"

    @admin.display(description="Roles")
    def roles(self, usuario):
        nombres = [rol.name for rol in usuario.groups.all()]
        return ", ".join(nombres) if nombres else "Sin rol"

    @admin.display(description="Estado", ordering="is_active")
    def estado(self, usuario):
        return insignia("Activa", "ok") if usuario.is_active else insignia("Inactiva", "off")

    @admin.display(description="Panel", ordering="is_staff")
    def acceso_panel(self, usuario):
        return insignia("Sí", "ok") if usuario.is_staff else insignia("No")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("groups")

    def has_delete_permission(self, request, obj=None):
        # Evita que una persona elimine su propia cuenta y pierda el acceso.
        if obj is not None and obj.pk == request.user.pk:
            return False
        return super().has_delete_permission(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        return type(form_class.__name__, (form_class,), {
            "puede_crear_roles": request.user.has_perm("auth.add_group"),
            "usuario_actual_pk": request.user.pk,
        })

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        editable = self.has_change_permission(request, obj) if obj else self.has_add_permission(request)
        hay_roles = bool(opciones_de_rol(request.user.has_perm("auth.add_group")))
        resultado = []
        for nombre, datos in fieldsets:
            campos = datos["fields"]
            if "rol" in campos:
                if not editable:
                    campos = ("roles",)  # Solo lectura: muestra el rol actual.
                elif not hay_roles:
                    continue
            resultado.append((nombre, {**datos, "fields": campos}))
        return resultado

    def save_model(self, request, obj, form, change):
        valor = form.cleaned_data.get("rol")
        if valor:
            # El acceso al panel lo define el rol; un superusuario lo conserva siempre.
            obj.is_staff = acceso_al_panel(valor) or obj.is_superuser
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        valor = form.cleaned_data.get("rol")
        if valor:
            nombre = PLANTILLAS_ROL.get(valor, {}).get("name")
            if nombre and not Group.objects.filter(name=nombre).exists() and not request.user.has_perm("auth.add_group"):
                return
            rol, _ = resolver_rol(valor)
            form.instance.groups.set([rol])

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if "rol" in context["adminform"].form.fields:
            context["roles_preview"] = roles_para_vista_previa()
        return super().render_change_form(request, context, add, change, form_url, obj)


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), UsuarioAdmin)
