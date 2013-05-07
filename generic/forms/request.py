from django import forms
from django.forms.models import BaseInlineFormSet

class RequestModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(RequestModelForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super(RequestModelForm, self).save(commit=False)
        if commit:
            if getattr(obj.save, 'accepts_request', False):
                obj.save(request=self.request)
            else:
                obj.save()
        return obj


class RequestInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(RequestInlineFormSet, self).__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        return super(RequestInlineFormSet, self)._construct_form(
            i, **dict(kwargs, request=self.request))
