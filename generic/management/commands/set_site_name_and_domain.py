from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Set Site name and domain from settings.SITE_NAME/DOMAIN'
    def handle(self, *args, **options):
        if Site.objects.count() > 1:
            raise CommandError("Must have only one Site.\n")
        Site.objects.get_or_create(
            defaults={
                'domain':settings.SITE_DOMAIN,
                'name':settings.SITE_NAME})
        self.stdout.write(
            u'Site details set:\n   {0.name} / {0.domain}\n'.format(
                Site.objects.all()[0]))
