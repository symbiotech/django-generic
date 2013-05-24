""" Loosely modelled off http://djangosnippets.org/snippets/85/ """

from django import http
from django.conf import settings

class SSLRedirect:
    def process_view(self, request, view_func, view_args, view_kwargs):
        secure_default = getattr(settings, 'SSL_DEFAULT', False)
        secure = view_kwargs.pop('SSL', secure_default)
        if not secure == request.is_secure():
            if getattr(settings, 'SSL_REDIRECTS_ACTIVE', False):
                return self._redirect(request, secure)

    def _redirect(self, request, secure):
        protocol = 'https' if secure else 'http'
        newurl = "%s://%s%s" % (
            protocol,
            request.get_host(),
            request.get_full_path()
        )
        if settings.DEBUG and request.method == 'POST':
            raise RuntimeError, (
                "Django can't perform a SSL redirect while maintaining POST "
                "data. Please structure your views so that redirects only "
                "occur during GETs."
            )
        if getattr(settings, 'SSL_REDIRECTS_PERMANENT', True):
            return http.HttpResponsePermanentRedirect(newurl)
        else:
            return http.HttpResponseRedirect(newurl)
