from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode

from .admin_actions import DashboardAdminMixin


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

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        usuario = form.cleaned_data.get("usuario")
        if usuario is not None and request.user.has_perm("auth.change_user"):
            usuario.groups.add(form.instance)


admin.site.unregister(Group)
admin.site.register(Group, RolAdmin)


class UsuarioAdmin(DashboardAdminMixin, UserAdmin):
    list_filter = ("is_staff", "is_active", "groups")


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), UsuarioAdmin)
