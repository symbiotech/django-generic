from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Shortcut for syncdb / migrate / collectstatic'
    def handle(self, *args, **options):
        call_command('syncdb')
        if 'south' in settings.INSTALLED_APPS:
            call_command('migrate')
        if 'django.contrib.staticfiles' in settings.INSTALLED_APPS:
            call_command('collectstatic')
        if 'django.contrib.sites' in settings.INSTALLED_APPS:
            call_command('set_site_name_and_domain')
