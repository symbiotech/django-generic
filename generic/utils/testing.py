from __future__ import absolute_import

import hashlib
import logging

try:
    from django.contrib.auth import get_user_model
except ImportError:
    # Django < 1.5
    from django.contrib.auth.models import User
else:
    User = get_user_model()
from django.core.urlresolvers import reverse
from django.db import DEFAULT_DB_ALIAS, connections
import django.test
from django.test.testcases import _AssertNumQueriesContext

logger = logging.getLogger(__name__)

def get_hash(string, length=8):
    """ Shortcut for generating short hash strings """
    return hashlib.sha1(string).hexdigest()[:length]

def reloaded(obj):
    """ Reload an object from the database """
    return obj.__class__._default_manager.get(pk=obj.pk)


class TestCase(django.test.TestCase):
    """ TestCase with moderate superpowers """

    PASSWORDS = {}

    def _assertContains(self, super_method, response, text, **kwargs):
        """
        Logs content on failure and accepts case_sensitive kwarg.
        TODO: modify *copy* of content/text rather than actual...
        """
        case_sensitive = kwargs.pop('case_sensitive', True)
        if not case_sensitive:
            response.content = response.content.lower()
            text = text.lower()
        try:
            super_method(response, text, **kwargs)
        except AssertionError:
            logger.warning('Searched content: """%s"""' % response.content)
            raise

    def assertContains(self, *args, **kwargs):
        return self._assertContains(
            super(TestCase, self).assertContains, *args, **kwargs)

    def assertNotContains(self, *args, **kwargs):
        return self._assertContains(
            super(TestCase, self).assertNotContains, *args, **kwargs)

    def create_user(self, username, email=None, password=None, super=False):
        """ Shortcut for creating users """
        email = email or (u'%s@example.com' % get_hash(username))
        params = {
            'username': username,
            'email': email,
            'password': password or get_hash(email+'PASSWORD'),
        }
        method = (
            User._default_manager.create_superuser if super else
            User._default_manager.create_user
        )
        self.PASSWORDS[username] = params['password']
        return method(**params)

    def login(self, username):
        """ Shortcut for logging in which asserts success """
        self.assertTrue(
            self.client.login(
                username=username, password=self.PASSWORDS[username]))

    def _test_urls(self, url_attributes):
        """ Example helper for quick/dirty URL coverage """
        for url, attributes in url_attributes:
            response = self.client.get(url)
            try:
                if 'status_code' in attributes:
                    self.assertEqual(
                        response.status_code, attributes.pop('status_code'))
                if 'template' in attributes:
                    self.assertTemplateUsed(
                        response, attributes.pop('template'))
                if 'contains' in attributes:
                    self.assertContains(response, attributes.pop('contains'))
                if '~contains' in attributes:
                    self.assertNotContains(
                        response, attributes.pop('~contains'))
                if 'icontains' in attributes:
                    self.assertContains(
                        response,
                        attributes.pop('icontains'),
                        case_sensitive=False
                    )
                if '~icontains' in attributes:
                    self.assertNotContains(
                        response,
                        attributes.pop('~icontains'),
                        case_sensitive=False
                    )
                if 'context' in attributes:
                    for key, value in attributes.pop('context').iteritems():
                        if callable(value):
                            self.assertTrue(value(response.context[key]))
                        else:
                            self.assertEqual(response.context[key], value)
                if 'redirects' in attributes:
                    self.assertRedirects(response, attributes.pop('redirects'))
                if 'redirects_permanently' in attributes:
                    self.assertRedirects(
                        response,
                        attributes.pop('redirects_permanently'),
                        status_code=301,
                    )

                # that's all folks...
                self.assertFalse(
                    attributes, 'Untested attributes: %r' % attributes)
            except AssertionError:
                logger.warning('AssertionError while testing URL: %s' % url)
                raise

    def _test_admin(self, MODELS):
        """
        Shortcut for detecting broken admin change lists/forms.
        Beware query expense involved...
        """
        for model in MODELS:
            msg_prefix = 'While testing %r, ' % model

            changelist_url = reverse(
                'admin:%s_%s_changelist' % (
                    model._meta.app_label, model._meta.module_name
                )
            )
            response = self.client.get(changelist_url)
            self.assertTemplateUsed(
                response, 'admin/change_list.html', msg_prefix=msg_prefix)

            add_url = reverse(
                'admin:%s_%s_add' % (
                    model._meta.app_label,
                    model._meta.module_name
                )
            )
            response = self.client.get(add_url)
            self.assertTemplateUsed(
                response, 'admin/change_form.html', msg_prefix=msg_prefix)

            model_admin = response.context['adminform'].model_admin

            for instance in model_admin.queryset(response.request):
                change_url = reverse(
                    'admin:%s_%s_change' % (
                        model._meta.app_label,
                        model._meta.module_name,
                    ),
                    args=(instance.pk,)
                )
                response = self.client.get(change_url)
                self.assertTemplateUsed(
                    response, 'admin/change_form.html', msg_prefix=msg_prefix)

    def assertNumQueries(self, num, func=None, *args, **kwargs):
        """ Identical to TransactionTestCase, but with custom Context """
        using = kwargs.pop("using", DEFAULT_DB_ALIAS)
        conn = connections[using]

        context = _VerboseAssertNumQueriesContext(self, num, conn)
        if func is None:
            return context

        with context:
            func(*args, **kwargs)


class _VerboseAssertNumQueriesContext(_AssertNumQueriesContext):
    """
    Modified context manager which logs the unexpected queries.
    """

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            super(_VerboseAssertNumQueriesContext, self).__exit__(
                exc_type, exc_value, traceback)
        except AssertionError, e:
            queries = self.connection.queries[self.starting_queries:]
            logger.warning(
                '\n    '.join(
                    ['Unexpected queries (%s):' % e] +
                    map(unicode, queries)
                )
            )
            raise
