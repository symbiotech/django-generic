import re

from django import template
from django.template.defaultfilters import stringfilter
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

@register.filter
@stringfilter
def unbreakable(string):
    return mark_safe(string.strip().replace(' ', '&nbsp;'))

HTML_COMMENTS = re.compile(r'<!--.*?-->', re.DOTALL)
@register.filter
def unescape(text):
    ENTITIES = {
        'amp': '&',
        'lt': '<',
        'gt': '>',
        'quot': '"',
        '#39': "'",
        'nbsp': ' ',
        'ndash': '-',
        'rsquo': "'",
        'rdquo': '"',
        'lsquo': "'",
        'ldquo': '"',
        'middot': '*',
        }
    text = HTML_COMMENTS.sub('', text)
    return re.sub(
        '&(%s);' % '|'.join(ENTITIES),
        lambda match: ENTITIES[match.group(1)], text)
