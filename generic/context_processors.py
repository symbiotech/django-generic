from django.conf import settings
from django.utils.translation import ugettext_lazy as _

def generic(request=None):
    """
    Add useful values to the context of every template
    """
    return dict(
        settings.TEMPLATE_CONSTANTS,
        SITE_NAME_TRANSLATED=_(settings.SITE_NAME))