import re

from django import template
from django.core.urlresolvers import reverse
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from urlparse import urlparse

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
    """
    Renders a link to an object.
    """
    return mark_safe('<a href="%s">%s</a>' % (obj.get_absolute_url(), obj))

@register.filter
@stringfilter
def unbreakable(string):
    """
    Replaces spaces with non-breaking spaces
    and hyphens with non-breaking hyphens.
    """
    return mark_safe(string.strip().replace(' ', '&nbsp;').replace('-', '&#8209;'))

HTML_COMMENTS = re.compile(r'<!--.*?-->', re.DOTALL)
@register.filter
def unescape(text):
    """
    Renders plain versions of HTML text - useful for supplying HTML into
    plain text contexts.
    """
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

@register.simple_tag
def domain_only(full_url):
    """
    Return only the domain in a url.
    """
    parsed = urlparse(full_url)
    return parsed.netloc.lstrip("www.")


"""
split_list
==========
Split list into n sublists, eg. to enable the display of some results in
several columns in HTML. Based on http://djangosnippets.org/snippets/889/

    {% split_list people as my_list 3 %}
    {% for l in my_list %}
        <ul>
            {%for p in l %}
                <li>{{ p }}</li>
            {% endfor %}
        </ul>
    {% endfor %}

"""

@register.tag(name='split_list')
def split_list(parser, token):
    """Parse template tag: {% split_list list as new_list 2 %}"""
    bits = token.contents.split()
    if len(bits) != 5:
        raise TemplateSyntaxError, "split_list list as new_list 2"
    if bits[2] != 'as':
        raise TemplateSyntaxError, "second argument to the split_list tag must be 'as'"
    return SplitListNode(bits[1], bits[4], bits[3])

class SplitListNode(Node):
    def __init__(self, list, cols, new_list):
        self.list, self.cols, self.new_list = list, cols, new_list

    def split_seq(self, list, cols=2):
        start = 0
        for i in xrange(cols):
            stop = start + len(list[i::cols])
            yield list[start:stop]
            start = stop

    def render(self, context):
        context[self.new_list] = self.split_seq(context.get(self.list, []), int(self.cols))
        return ''


"""
captureas
=========
Renders the contents of a block, and stores the rendered result in a new variable.
Taken from http://www.djangosnippets.org/snippets/545/.

    {% captureas person_name %}{% complex_logic %}{% endcaptureas %}
    {% include "person.html" with name=person_name %}

Django's {% filter %} tag covers many of the same use cases.

"""
@register.tag(name='captureas')
def do_capture_as(parser, token):
    try:
        tag_name, args = token.contents.split(None, 1)
    except ValueError:
        raise template.TemplateSyntaxError("'captureas' node requires a variable name.")
    nodelist = parser.parse(('endcaptureas',))
    parser.delete_first_token()
    return CaptureasNode(nodelist, args)

class CaptureasNode(template.Node):
    def __init__(self, nodelist, varname):
        self.nodelist = nodelist
        self.varname = varname

    def render(self, context):
        output = self.nodelist.render(context)
        context[self.varname] = output
        return ''

"""
update_GET allows you to substitute parameters into the current request's
GET parameters. This is useful for updating search filters without losing
the current set.

{% load update_GET %}

<a href="?{% update_GET attr1 += value1 attr2 -= value2 attr3 = value3 %}">foo</a>
This adds value1 to (the list of values in) attr1,
removes value2 from (the list of values in) attr2,
sets attr3 to value3.

And returns a urlencoded GET string.

Allowed values are:
    strings, in quotes
    vars that resolve to strings
    lists of strings
    None (without quotes)

If a attribute is set to None or an empty list, the GET parameter is removed.
If an attribute's value is an empty string, or [""] or None, the value remains, but has a "" value.
If you try to =- a value from a list that doesn't contain that value, nothing happens.
If you try to =- a value from a list where the value appears more than once, only the first value is removed.
"""
from django.template.defaultfilters import fix_ampersands
from django.http import QueryDict

@register.tag(name='update_GET')
def do_update_GET(parser, token):
    try:
        args = token.split_contents()[1:]
        triples = list(_chunks(args, 3))
        if triples and len(triples[-1]) != 3:
            raise template.TemplateSyntaxError, "%r tag requires arguments in groups of three (op, attr, value)." % token.contents.split()[0]
        ops = set([t[1] for t in triples])
        if not ops <= set(['+=', '-=', '=']):
            raise template.TemplateSyntaxError, "The only allowed operators are '+=', '-=' and '='. You have used %s" % ", ".join(ops)

    except ValueError:
        return UpdateGetNode()

    return UpdateGetNode(triples)

def _chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


class UpdateGetNode(template.Node):
    def __init__(self, triples=[]):
        self.triples = [(template.Variable(attr), op, template.Variable(val)) for attr, op, val in triples]

    def render(self, context):
        try:
            GET = context.get('request').GET.copy()
        except AttributeError:
            GET = QueryDict("", mutable=True)

        for attr, op, val in self.triples:
            actual_attr = attr.resolve(context)

            try:
                actual_val = val.resolve(context)
            except:
                if val.var == "None":
                    actual_val = None
                else:
                    actual_val = val.var

            if actual_attr:
                if op == "=":
                    if actual_val is None or actual_val == []:
                        if GET.has_key(actual_attr):
                            del GET[actual_attr]
                    elif hasattr(actual_val, '__iter__'):
                        GET.setlist(actual_attr, actual_val)
                    else:
                        GET[actual_attr] = unicode(actual_val)
                elif op == "+=":
                    if actual_val is None or actual_val == []:
                        if GET.has_key(actual_attr):
                            del GET[actual_attr]
                    elif hasattr(actual_val, '__iter__'):
                        GET.setlist(actual_attr, GET.getlist(actual_attr) + list(actual_val))
                    else:
                        GET.appendlist(actual_attr, unicode(actual_val))
                elif op == "-=":
                    li = GET.getlist(actual_attr)
                    if hasattr(actual_val, '__iter__'):
                        for v in list(actual_val):
                            if v in li:
                                li.remove(v)
                        GET.setlist(actual_attr, li)
                    else:
                        actual_val = unicode(actual_val)
                        if actual_val in li:
                            li.remove(actual_val)
                        GET.setlist(actual_attr, li)

        return fix_ampersands(GET.urlencode())