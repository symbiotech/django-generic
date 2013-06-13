import logging

from django import forms
from django import http
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.filters import SimpleListFilter
from django.conf.urls import patterns, url
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import loading
from django.template import defaultfilters
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ungettext_lazy, ugettext_lazy as _

try:
    import json
except ImportError:
    from django.utils import simplejson as json

from ..utils import unicode_csv
from .widgets import ForeignKeyCookedIdWidget, ManyToManyCookedIdWidget

logger = logging.getLogger(__name__)

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
                [_("You haven't selected any fields to update")])
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
        queryset = self.queryset(request).filter(pk__in=ids)
        form_class = self.get_batch_update_form_class(request)
        form = form_class(request.POST or None)
        if form.is_valid():
            updated = form.apply(request, queryset)
            self.message_user(
                request,
                ungettext_lazy(
                    u'Updated fields (%(field_list)s) '
                    u'for %(count)d %(verbose_name)s',
                    u'Updated fields (%(field_list)s) '
                    u'for %(count)d %(verbose_name_plural)s',
                    updated,
                ) % {
                    'field_list': u', '.join(
                        [
                            self.model._meta.get_field(name).verbose_name
                            for name in form.fields_to_update
                        ]
                    ),
                    'count': updated,
                    'verbose_name': self.model._meta.verbose_name,
                    'verbose_name_plural': self.model._meta.verbose_name_plural
                }
            )
            return self.response_post_save_change(request, None)

        return TemplateResponse(
            request,
            template_paths, {
                'form': form,
                'model_meta': self.model._meta,
                'has_change_permission': self.has_change_permission(request),
                'count': len(queryset),
                'media': self.media + helpers.AdminForm(
                    form, list(self.get_fieldsets(request)),
                    self.get_prepopulated_fields(request),
                    self.get_readonly_fields(request),
                    model_admin=self
                ).media,
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


class ThumbnailAdminMixin(admin.ModelAdmin):
    """
    Shortcut for displaying a thumbnail in a changelist.

    Requires easy-thumbnails.

    Specify ImageField name in `thumbnail_field`, and optionally override
    `thumbnail_options` for customisation such as sizing, cropping, etc.
    Plays nicely with list_display_links if you want a clickable thumbnail.
    """

    thumbnail_field = None
    thumbnail_options = {'size': (100,100)}

    def thumbnail(self, obj):
        if not self.thumbnail_field:
            logger.warning('ThumbnailAdminMixin.thumbnail_field unspecified')
            return ''

        try:
            field_value = getattr(obj, self.thumbnail_field)
        except AttributeError:
            logger.error('ThumbnailAdminMixin.thumbnail_field getattr failed')
            return ''

        if field_value:
            from easy_thumbnails.files import get_thumbnailer
            thumbnailer = get_thumbnailer(field_value)
            thumbnail = thumbnailer.get_thumbnail(self.thumbnail_options)
            return '<img class="thumbnail" src="{0}" />'.format(thumbnail.url)
        else:
            return ''
    thumbnail.allow_tags = True


class CSVExportAdmin(admin.ModelAdmin):
    def _get_url_name(self, view_name, include_namespace=True):
        return '%s%s_%s_%s' % (
            'admin:' if include_namespace else '',
            self.model._meta.app_label,
            self.model._meta.module_name,
            view_name,
        )

    def csv_export(self, request, queryset):
        response = http.HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename={0}'.format(
            self.csv_export_filename(request)
        )
        writer = unicode_csv.Writer(response)
        fields = self.csv_export_fields(request)
        writer.writerow([title for title, key in fields])
        # TODO: detect absence of callables and use efficient .values query
        for obj in queryset:
            row = []
            for title, key in fields:
                if callable(key):
                    row.append(key(obj))
                else:
                    row.append(getattr(obj, key))
            writer.writerow(row)
        return response

    def get_actions(self, request):
        actions = super(CSVExportAdmin, self).get_actions(request)
        if self.csv_export_enabled(request):
            if not 'csv_export' in actions:
                actions['csv_export'] = self.get_action('csv_export')
        else:
            if 'csv_export' in actions:
                del actions['csv_export']
        return actions
    csv_export.short_description = _('Export selected items in CSV format')

    def csv_export_enabled(self, request):
        return bool(self.csv_export_fields(request))

    def csv_export_fields(self, request):
        """
        This returns a list of two-tuples describing the fields to export.
        The first element of each tuple is the label for the column.
        The second element is a field name or callable which will return the
        appropriate value for the field given a model instance.
        """
        fields = []
        for field in self.model._meta.fields:
            fields.append((field.verbose_name, field.name))
        return fields

    def csv_export_filename(self, request):
        return '{0}.csv'.format(
            defaultfilters.slugify(self.model._meta.verbose_name_plural)
        )


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


class ChangeLinkInline(admin.TabularInline):
    """
    Base class for inlines which link to change forms for further editing.

    Simple workaround for "deep" admin interfaces which would otherwise
    require "nested inlines". See https://code.djangoproject.com/ticket/9025

    Generally useful in conjunction with ChangeFormOnlyAdmin below.
    """

    readonly_fields = ('change_link',)

    def change_link(self, obj):
        if obj.id is None:
            return 'Not yet saved'
        return '<a href="%s">Click to edit</a>' % reverse(
            'admin:%s_%s_change' % (
                obj._meta.app_label,
                obj._meta.module_name,
            ),
            args=(obj.id,)
        )
    change_link.allow_tags = True
    change_link.short_description = 'Edit'


class ChangeFormOnlyAdmin(admin.ModelAdmin):
    """
    For models which don't require an independent change list.

    Generally used with ChangeLinkInline (above) where the inlines on the
    parent object basically act as the change-list.
    """
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return False
        return super(
            ChangeFormOnlyAdmin, self).has_change_permission(request, obj)

    # TODO: rewrite/redirect change_list links in breadcrumbs, etc

    def has_add_permission(self, request):
        return False

# TODO: reorganise these modules, they're getting too big.

def get_subclass_choices(parent_model):
    title_if_lower = lambda s: (s.title() if s == s.lower() else s)
    return sorted(
        map(
            lambda model: (
                model._meta.module_name,
                title_if_lower(model._meta.verbose_name),
            ),
            filter(
                lambda model: (
                    issubclass(model, parent_model) and
                    parent_model in model._meta.parents
                ),
                loading.get_models()
            )
        )
    )


class SubclassFilter(SimpleListFilter):
    title = _('Type')
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return get_subclass_choices(model_admin.model)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.complex_filter(
                {'%s__isnull' % self.value(): False})
        else:
            return queryset


class PolymorphicAdmin(admin.ModelAdmin):
    """
    For use with django-model-utils' InheritanceManager.
    """

    list_filter = (SubclassFilter,)
    subclass_parameter_name = '__subclass'
    subclass_label = _('Type')

    def add_view(self, request, form_url='', extra_context=None):
        if self.subclass_parameter_name in request.POST:
            return http.HttpResponseRedirect(
                '?%s=%s' % (
                    self.subclass_parameter_name,
                    request.POST.get(self.subclass_parameter_name),
                )
            )
        return super(PolymorphicAdmin, self).add_view(
            request, form_url=form_url, extra_context=extra_context)

    def get_fieldsets(self, request, obj=None):
        if not self.get_model(request, obj):
            # show subclass selection field only
            return (
                (None, {'fields': (self.subclass_parameter_name,)},),
            )
        return self.get_modeladmin(request, obj).get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        model_admin = self.get_modeladmin(request, obj)
        return model_admin.get_readonly_fields(request, obj)

    def get_inline_instances(self, request, obj=None):
        model_admin = self.get_modeladmin(request, obj)
        return model_admin.get_inline_instances(request, obj)

    def get_formsets(self, request, obj=None):
        if not self.get_model(request, obj):
            return () # hide inlines on add form until subclass selected
        model_admin = self.get_modeladmin(request, obj)
        return model_admin.get_formsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        model_admin = self.get_modeladmin(request, obj)
        form_class = model_admin.get_form(request, obj=obj, **kwargs)
        if not self.get_model(request, obj):
            return self._build_subclass_selection_form(form_class)
        else:
            return form_class

    def get_model(self, request, obj=None):
        return obj.__class__ if obj else (
            loading.get_model(
                self.opts.app_label,
                request.REQUEST.get(self.subclass_parameter_name, '')
            )
        )

    def get_modeladmin(self, request, obj=None):
        model = self.get_model(request, obj)
        if model and model != self.model:
            return self.admin_site._registry.get(
                model, # use registered admin if it exists...
                self.get_unregistered_admin_classes().get(
                    model, # or unregistered one if we know about it
                    self.__class__ # ...or build a generic one
                )(model, self.admin_site)
            )
        else:
            return super(PolymorphicAdmin, self)

    def get_unregistered_admin_classes(self):
        return {
            # override with Model: ModelAdmin mapping
        }

    def _build_subclass_selection_form(self, form_class):
        class SubclassSelectionForm(form_class):
            def __init__(form, *args, **kwargs):
                super(SubclassSelectionForm, form).__init__(*args, **kwargs)
                form.fields[self.subclass_parameter_name] = forms.ChoiceField(
                    choices=get_subclass_choices(self.model),
                    label=self.subclass_label,
                )
        return SubclassSelectionForm

    # TODO: disable bulk deletion action when heterogeneous classes selected
    # -- collector doesn't cope, and raises AttributeErrors

    def queryset(self, request):
        return self.model.objects.select_subclasses()
