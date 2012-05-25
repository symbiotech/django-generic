import re

from django import template
from django.core.urlresolvers import reverse
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from .. import models

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


def _get_admin_url(obj, view='change', admin_site_name='admin'):
    return reverse(
        '%(namespace)s:%(app)s_%(model)s_%(view)s' % {
            'namespace': admin_site_name,
            'app': obj._meta.app_label,
            'model': obj._meta.module_name,
            'view': view}, args=(obj.pk,))

@register.simple_tag
def admin_url(obj, view='change', admin_site_name='admin'):
    return _get_admin_url(obj, view, admin_site_name)
