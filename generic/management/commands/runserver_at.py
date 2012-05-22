from django.conf import settings
from django.core.management.commands.runserver import Command as Runserver

class Command(Runserver):
    help = 'Shortcut for runserver which uses settings.SITE_DOMAIN'
    def handle(self, addrport='', *args, **options):
        addrport = addrport or settings.SITE_DOMAIN
        super(Command, self).handle(addrport, *args, **options)
