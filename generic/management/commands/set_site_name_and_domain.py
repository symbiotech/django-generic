from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Set Site name and domain from settings.SITE_NAME/DOMAIN'
    def handle(self, *args, **options):
        try:
            site = Site.objects.get()
        except Site.DoesNotExist:
            site = Site.objects.create(
                domain=settings.SITE_DOMAIN,
                name=settings.SITE_NAME)
        except Site.MultipleObjectsReturned:
            raise CommandError("Must have only one Site.\n")
        else:
            site.domain = settings.SITE_DOMAIN
            site.name = settings.SITE_NAME
            site.save()

        self.stdout.write(
            u'Site details set:\n   {0.name} / {0.domain}\n'.format(site))
