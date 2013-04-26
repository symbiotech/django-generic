from django import forms
from django import http
from django.conf import settings
from django.contrib import admin
from django.conf.urls import patterns, url
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404, redirect

try:
    import json
except ImportError:
    from django.utils import simplejson as json

from .widgets import ForeignKeyCookedIdWidget, ManyToManyCookedIdWidget

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
        if target_model_admin:
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


class ReturnURLAdminMixin(admin.ModelAdmin):
    def response_add(self, request, obj, post_url_continue=None):
        referrer = request.GET.get('_return_url')
        if referrer and not '_continue' in request.POST:
            return http.HttpResponseRedirect(referrer)
        else:
            return super(ReturnURLAdminMixin, self).response_add(
                request, obj, post_url_continue=post_url_continue)

    def response_change(self, request, obj):
        referrer = request.GET.get('_return_url')
        if (referrer and
            not '_continue' in request.REQUEST and
            not '_popup' in request.REQUEST
        ):
            return http.HttpResponseRedirect(referrer)
        else:
            return super(ReturnURLAdminMixin, self).response_change(
                request, obj)


class BatchUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        from django.forms.forms import BoundField
        super(BatchUpdateForm, self).__init__(*args, **kwargs)
        for field_name in self.fields.keys():
            self.fields[field_name].update_checkbox = BoundField(
                self,
                forms.BooleanField(required=False),
                'updating-'+field_name
            )

    def clean(self):
        cleaned_data = super(BatchUpdateForm, self).clean()
        self.fields_to_update = []
        for field_name, field in self.fields.iteritems():
            if field.update_checkbox.value():
                self.fields_to_update.append(field_name)
        if not self.fields_to_update:
            raise ValidationError(
                ["You haven't selected any fields to update"])
        return cleaned_data

    def apply(self, request, queryset):
        update_params = {}
        updated = 0
        for field_name in self.fields_to_update:
            field = queryset.model._meta.get_field(field_name)
            if isinstance(field, models.ManyToManyField):
                for obj in queryset.all():
                    getattr(obj, field_name).clear()
                    # TODO: consider removing only those no longer present
                    for related_obj in self.cleaned_data[field_name]:
                        getattr(obj, field_name).add(related_obj)
                    updated += 1
            else:
                update_params[field_name] = self.cleaned_data[field_name]
        if update_params:
            updated = queryset.update(**update_params)
        return updated


class BatchUpdateAdmin(admin.ModelAdmin):
    batch_update_fields = ()

    def _get_url_name(self, view_name, include_namespace=True):
        return '%s%s_%s_%s' % (
            'admin:' if include_namespace else '',
            self.model._meta.app_label,
            self.model._meta.module_name,
            view_name,
        )

    def batch_update(self, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        return http.HttpResponseRedirect(
            '%s?ids=%s' % (
                reverse(
                    self._get_url_name('batchupdate'),
                    current_app=self.admin_site.name,
                ),
                ','.join(selected),
            )
        )

    def get_batch_update_form_class(self, request):
        return self.get_form(
            request,
            obj=None,
            form=BatchUpdateForm,
            fields=self.batch_update_fields,
        )

    def batch_update_view(self, request):
        template_paths = map(
            lambda path: path % {
                'app_label': self.model._meta.app_label,
                'module_name': self.model._meta.module_name,
            }, (
                'admin/%(app_label)s/%(module_name)s/batch_update.html',
                'admin/%(app_label)s/batch_update.html',
                'admin/batch_update.html',
                'admin/generic/batch_update.html',
            )
        )
        ids = request.REQUEST.get('ids', '').split(',')
        form_class = self.get_batch_update_form_class(request)
        form = form_class(request.POST or None)
        if form.is_valid():
            queryset = self.queryset(request).filter(pk__in=ids)
            updated = form.apply(request, queryset)
            self.message_user(
                request,
                u'Updated fields (%s) for %d %s' % (
                    ', '.join(form.fields_to_update),
                    updated,
                    unicode(
                        self.model._meta.verbose_name if len(ids) == 1 else
                        self.model._meta.verbose_name_plural
                    ),
                )
            )
            return self.response_post_save_change(request, None)

        return TemplateResponse(
            request,
            template_paths, {
                'form': form,
                'model_meta': self.model._meta,
                'has_change_permission': self.has_change_permission(request),
                'count': len(ids),
                'media': self.media,
            },
            current_app=self.admin_site.name,
        )

    def get_urls(self):
        return patterns(
            '',
            url(r'^batch-update/$',
                self.admin_site.admin_view(self.batch_update_view),
                name=self._get_url_name(
                    'batchupdate', include_namespace=False),
            ),
        ) + super(BatchUpdateAdmin, self).get_urls()

    def get_actions(self, request):
        actions = super(BatchUpdateAdmin, self).get_actions(request)
        if self.batch_update_fields:
            self._validate_batch_update_fields()
            if not 'batch_update' in actions:
                actions['batch_update'] = self.get_action('batch_update')
        else:
            if 'batch_update' in actions:
                del actions['batch_update']
        return actions

    def _validate_batch_update_fields(self):
        for field in self.batch_update_fields:
            field = self.model._meta.get_field(field)


from ..models.delible import Delible
class DelibleAdmin(admin.ModelAdmin):
    """ Admin with "undelete" functionality for Delible objects """
    change_form_template = 'admin/delible_change_form.html'

    def delete_model(self, request, obj):
        if isinstance(obj, Delible):
            obj.delete(request=request)
        else:
            obj.delete()

    def undelete(self, request, pk):
        permission = '%s.delete_%s' % (
            self.model._meta.app_label, self.model._meta.module_name)
        if not request.user.has_perm(permission):
            return http.HttpResponseForbidden()
        else:
            obj = get_object_or_404(self.model, pk=pk)
            try:
                obj.undelete()
            except AttributeError:
                self.message_user(request, 'Error; cannot undelete.')
            else:
                self.message_user(request, u"%s undeleted!" % obj)
            return redirect(
                'admin:%s_%s_change' % (
                    obj._meta.app_label, obj._meta.module_name), obj.pk)

    def get_urls(self):
        urls = super(DelibleAdmin, self).get_urls()
        if issubclass(self.model, Delible):
            urls = patterns(
                '', url(
                    r'^(?P<pk>.+)/undelete/$',
                    self.admin_site.admin_view(self.undelete),
                    name='%s_%s_undelete' % (
                        self.model._meta.app_label,
                        self.model._meta.module_name))
                ) + urls
        return urls
