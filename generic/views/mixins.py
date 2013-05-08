import json
import django.views.generic
from django import http
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .exceptions import PermissionDenied, RedirectInstead

class Authenticated(django.views.generic.View):
    """ Base for views which require an authenticated user """
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(Authenticated, self).dispatch(*args, **kwargs)


class View(django.views.generic.View):
    result_text = 'OK'
    ajax_catch_redirects = False
    default_context_data = {}

    def __init__(self, *args, **kwargs):
        super(View, self).__init__(*args, **kwargs)
        self.context_data = dict(self.default_context_data)

    def finalize_response(self, response):
        """ Hook for any last-minute response tweaking; e.g. JSON for AJAX """
        if self.request.is_ajax() and response.status_code == 302:
            if self.ajax_catch_redirects:
                return http.HttpResponse(
                    json.dumps(
                        {
                            'redirect': response['location'],
                            'result': self.result_text,
                        }
                    ),
                    mimetype="application/json"
                )
        return response

    def dispatch(self, request, *args, **kwargs):
        """ Allow translation of custom exceptions into HTTP responses. """
        try:
            response = super(View, self).dispatch(request, *args, **kwargs)
        except PermissionDenied:
            response = http.HttpResponseForbidden('Permission denied')
        except RedirectInstead as redirect_exception:
            response = redirect(redirect_exception.message)
        return self.finalize_response(response)

    def get_context_data(self, **kwargs):
        context = super(View, self).get_context_data(**kwargs)
        context['use_multipart_form'] = self.requires_multipart_form()
        context.update(self.context_data)
        return context

    def requires_multipart_form(self):
        return hasattr(self, 'form') and self.form.is_multipart()


class InlineFormSetView(View):
    """ Validates and saves both self.form and self.formsets """
    formset_classes = ()
    formsets = {}

    def requires_multipart_form(self):
        return (
            any([formset.is_multipart() for formset in self.formsets.values()])
            or super(InlineFormSetView, self).requires_multipart_form()
        )

    def get_formset_kwargs(self, formset_class):
        return {
            'data': self.request.POST or None,
            'files': self.request.FILES or None,
            'instance': getattr(self, 'object', None),
        }

    def get_formset(self, formset_class):
        return formset_class(**self.get_formset_kwargs(formset_class))

    def get_form(self, form_class):
        self.formsets = {}
        for formset_class in self.formset_classes:
            key = formset_class.model._meta.module_name
            self.formsets[key] = self.get_formset(formset_class)
        self.context_data['formsets'] = self.formsets
        return super(InlineFormSetView, self).get_form(form_class)

    def save_formsets(self):
        for formset in self.formsets.values():
            formset.save()

    def form_valid(self, form):
        form = self.get_form(self.get_form_class())
        for formset in self.formsets.values():
            formset.instance = form.save(commit=False)
            if not formset.is_valid():
                return self.form_invalid(form)
        # OK, all valid
        response = super(InlineFormSetView, self).form_valid(form)
        self.save_formsets()
        return response
