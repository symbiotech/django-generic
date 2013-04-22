from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View

class Authenticated(View):
    """ Base for views which require an authenticated user """
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(Authenticated, self).dispatch(*args, **kwargs)
