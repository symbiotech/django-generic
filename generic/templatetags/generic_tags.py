from django import template
from django.utils.safestring import mark_safe
register = template.Library()

@register.inclusion_tag('_field.html')
def field(field, *args, **kwargs):
    return {
        'field': field,
        'show_label': kwargs.get('show_label', True),
        'label_override': kwargs.get('label_override', None),
        }

@register.filter
def linkify(obj):
    return mark_safe('<a href="%s">%s</a>' % (obj.get_absolute_url(), obj))
