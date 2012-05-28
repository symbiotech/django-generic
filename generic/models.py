import datetime

from django.contrib.auth.models import User
from django.db import models

class DelibleManager(models.Manager):
    """
    Excludes "deleted" objects from standard query sets. Use with caution.
    """

    use_for_related_fields = True

    def get_query_set(self):
        return super(DelibleManager, self).get_query_set().filter(deleted=None)

    def deleted(self):
        return super(DelibleManager, self).get_query_set().exclude(
            deleted=None)

    def all_with_deleted(self):
        return super(DelibleManager, self).get_query_set()


class Delible(models.Model):
    """
    Able to be "deleted"/hidden using a flag. Deletion date/user are retained.
    """
    deleted = models.DateTimeField(null=True, editable=False)
    deleted_by = models.ForeignKey(
        User, null=True, related_name='+', editable=False)

    is_delible = True

    class Meta:
        abstract = True

    def is_deleted(self):
        return self.deleted is not None

    def delete(self, using=None, request=None):
        self.deleted = datetime.datetime.now()
        self.deleted_by = request.user
        self.save()

    def undelete(self):
        self.deleted = None
        self.deleted_by = None
        self.save()