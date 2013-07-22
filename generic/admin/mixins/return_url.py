from django import http
from django.contrib import admin

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
