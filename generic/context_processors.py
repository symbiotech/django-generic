from django.conf import settings

def generic(request=None):
    return settings.TEMPLATE_CONSTANTS
