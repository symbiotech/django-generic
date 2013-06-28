from django import http
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from ..widgets import ForeignKeyCookedIdWidget, ManyToManyCookedIdWidget

try:
    from django.conf.urls import patterns, url
except ImportError:
    from django.conf.urls.defaults import patterns, url

try:
    import json
except ImportError:
    from django.utils import simplejson as json

class CookedIdAdmin(admin.ModelAdmin):
    """
    Support for CookedIdWidgets (vs. RawIdWidgets) in admin.

    See:
    - `generic.admin.widgets.ManyToManyCookedIdWidget`, and
    - `generic.admin.widgets.ForeignKeyCookedIdWidget`

    Simply list fields in self.cooked_id_widgets instead of self.raw_id_widgets

    Override self.cook() to customise cooked object representations.
    """
    cooked_id_fields = ()

    def cook(self, obj, request, field_name):
        """
        Override this to customise the "cooked" representation of objects
        """
        return unicode(obj)

    def cook_ids(self, request, field_name, raw_ids):
        # TODO: extend to support non-integer/non-`id` PKs
        if not field_name in self.cooked_id_fields:
            raise http.Http404
        try:
            ids = map(int, raw_ids.split(','))
        except ValueError:
            if raw_ids == '':
                ids = []
            else:
                raise http.Http404
        target_model_admin = self.admin_site._registry.get(
            self.model._meta.get_field(field_name).rel.to)
        response_data = {}
        if (
                target_model_admin and
                target_model_admin.has_change_permission(request)
        ):
            for obj in target_model_admin.queryset(request).filter(id__in=ids):
                response_data[obj.pk] = self.cook(
                    obj, request=request, field_name=field_name)
        else:
            pass # graceful-ish.
        return http.HttpResponse(
            json.dumps(response_data), mimetype='application/json')

    def get_urls(self):
        return patterns(
            '',
            url(r'^cook-ids/(?P<field_name>\w+)/(?P<raw_ids>.*)/$',
                self.admin_site.admin_view(self.cook_ids))
        ) + super(CookedIdAdmin, self).get_urls()

    def assert_cooked_target_admin(self, db_field):
        if db_field.rel.to in self.admin_site._registry:
            return True
        else:
            if settings.DEBUG:
                raise ImproperlyConfigured(
                    "%s.cooked_id_fields contains '%r', but %r "
                    "is not registed in the same admin site." % (
                        self.__class__.__name__,
                        db_field.name,
                        db_field.rel.to,
                    )
                )
            else:
                pass # fail silently

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        if db_field.name in self.cooked_id_fields:
            if self.assert_cooked_target_admin(db_field):
                kwargs['widget'] = ManyToManyCookedIdWidget(
                    db_field.rel, self.admin_site)
        return super(CookedIdAdmin, self).formfield_for_manytomany(
            db_field, request=request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name in self.cooked_id_fields:
            if self.assert_cooked_target_admin(db_field):
                kwargs['widget'] = ForeignKeyCookedIdWidget(
                    db_field.rel, self.admin_site)
        return super(CookedIdAdmin, self).formfield_for_foreignkey(
            db_field, request=request, **kwargs)
