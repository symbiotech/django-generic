from django.core.management.base import AppCommand
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.contrib.auth.management import _get_all_permissions

class Command(AppCommand):
    help = 'Creates permissions for proxy models; see Django #11154.'

    def handle_app(self, app, **options):
        app_name = app.__name__.split('.')[-2] # app is the models module
        for ctype in ContentType.objects.filter(
            app_label=app_name, permission__isnull=True
        ):
            for codename, name in _get_all_permissions(
                ctype.model_class()._meta
            ):
                p, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type__pk=ctype.id,
                    defaults={'name': name, 'content_type': ctype})
                if created:
                    if options.get('verbosity', 1) >= 1:
                        self.stdout.write("Created: %s\n" % (p,))
