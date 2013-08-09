from django import forms
from django.contrib import admin

class OWRTInlineForm(forms.ModelForm):
    """
    Meta.order_with_respect_to is handy in some cases, and adds a `_order`
    field with `editable=False`. This form overrides the immutable nature of
    that field so that drag-and-drop javascript can use it.
    """
    _order = forms.IntegerField(label='Order')

    def __init__(self, *args, **kwargs):
        super(OWRTInlineForm, self).__init__(*args, **kwargs)
        self.fields['_order'].initial = self.instance._order

    def save(self, commit=True):
        self.instance._order = self.cleaned_data.get(
            '_order', self.instance._order)
        return super(OWRTInlineForm, self).save(commit=commit)


class OWRTInline(admin.TabularInline):
    form = OWRTInlineForm

class OWRTStackedInline(admin.StackedInline):
    form = OWRTInlineForm
