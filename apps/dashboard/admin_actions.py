from django.contrib import admin
from django.contrib.admin.utils import quote
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.urls import reverse
from django.utils.html import format_html


class DashboardAdminMixin:
    show_facets = admin.ShowFacets.ALWAYS

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        if not self.has_delete_permission(request) or "_popup" in request.GET:
            return fields

        @admin.display(description="Acciones")
        def eliminar(obj):
            if not self.has_delete_permission(request, obj):
                return "—"
            opts = self.model._meta
            url = reverse(
                f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_delete",
                args=(quote(obj.pk),),
            )
            url = add_preserved_filters(
                {"opts": opts, "preserved_filters": self.get_preserved_filters(request)},
                url,
            )
            return format_html(
                '<a class="bru-row-delete" href="{}" aria-label="Eliminar {}">Eliminar</a>',
                url,
                str(obj),
            )

        return (*fields, eliminar)
