from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Set Site name and domain from settings.SITE_NAME/DOMAIN'
    def handle(self, *args, **options):
        if Site.objects.count() != 1:
            raise CommandError("Error: Must have only one Site.\n")
        Site.objects.update(
            domain=settings.SITE_DOMAIN, name=settings.SITE_NAME)
        self.stdout.write(
            u'Site details set:\n   %(name)s / %(domain)s\n' % (
                Site.objects.all()[0].__dict__))
