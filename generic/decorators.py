from functools import wraps
from django.conf import settings
from django.http import HttpResponse
from django.utils import simplejson

def cache_result_in_instance(method):
    """
    Caches the results of a method into its object instance using the passed
    args as cache key (not the Django cache framework)
    """
    @wraps(method)
    def wrapped_method(self, *args, **kwargs):
        force_reload = kwargs.pop('force_reload', False)
        if kwargs and settings.DEBUG:
            raise RuntimeError(
                "@cache_result_in_instance cannot currently handle methods "
                "with keyword arguments")
        cache_attribute_name = '_%s_cache' % method.__name__
        if not hasattr(self, cache_attribute_name):
            setattr(self, cache_attribute_name, {})
        cache = getattr(self, cache_attribute_name)
        try:
            key = hash(args)
        except TypeError: # unhashable
            return method(self, *args) # forget trying to cache...
        else:
            if not key in cache or force_reload:
                cache[key] = method(self, *args)
            return cache[key]
    return wrapped_method


def json_view(view):
    """
    Convenience decorator for views which return JSON data.

    Allows a view to return data (e.g. a dict) and have it serialized into
    an HTTPResponse with the appropriate mimetype.
    """
    @wraps(view)
    def wrapped_view(request, *args, **kwargs):
        response_data = view(request, *args, **kwargs)
        if isinstance(response_data, HttpResponse):
            if settings.DEBUG:
                raise RuntimeError(
                    'json_view-wrapped method is returning an HttpResponse!')
            else:
                return response_data
        try:
            json = simplejson.dumps(response_data)
        except TypeError:
            json = simplejson.dumps(
                {'result': False, 'reason': 'Error encoding JSON response'})
        return HttpResponse(json, mimetype='application/json')
    return wrapped_view
