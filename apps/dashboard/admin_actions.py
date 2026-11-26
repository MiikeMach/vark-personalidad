from django.contrib import admin
from django.contrib.admin.utils import quote
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.urls import reverse
from django.utils.html import format_html, format_html_join


def insignia(texto, tono=""):
    """Etiqueta de estado con el estilo del panel (tono: ok, off, warn o vacío)."""
    clase = f"bru-badge is-{tono}" if tono else "bru-badge"
    return format_html('<span class="{}">{}</span>', clase, texto)


class DashboardAdminMixin:
    show_facets = admin.ShowFacets.ALWAYS

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def _url_de_fila(self, request, accion, obj):
        opts = self.model._meta
        url = reverse(
            f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_{accion}",
            args=(quote(obj.pk),),
        )
        return add_preserved_filters(
            {"opts": opts, "preserved_filters": self.get_preserved_filters(request)},
            url,
        )

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        if "_popup" in request.GET:
            return fields
        puede_ver = self.has_view_or_change_permission(request)
        puede_eliminar = self.has_delete_permission(request)
        if not puede_ver and not puede_eliminar:
            return fields

        @admin.display(description="Acciones")
        def acciones(obj):
            enlaces = []
            if self.has_change_permission(request, obj):
                enlaces.append(("bru-row-edit", self._url_de_fila(request, "change", obj), "Editar", obj))
            elif self.has_view_permission(request, obj):
                enlaces.append(("bru-row-edit", self._url_de_fila(request, "change", obj), "Ver", obj))
            if self.has_delete_permission(request, obj):
                enlaces.append(("bru-row-delete", self._url_de_fila(request, "delete", obj), "Eliminar", obj))
            if not enlaces:
                return "—"
            return format_html(
                '<span class="bru-row-actions">{}</span>',
                format_html_join(
                    "", '<a class="{}" href="{}" aria-label="{} {}">{}</a>',
                    ((clase, url, texto, str(o), texto) for clase, url, texto, o in enlaces),
                ),
            )

        return (*fields, acciones)
