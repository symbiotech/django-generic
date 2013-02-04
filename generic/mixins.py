from django.contrib.contenttypes.models import ContentType
from django.db import models



class Inheritable(object):
    def get_leaf_object(self):
        """Returns the model instance object as instance of the outermost leaf class,
        by searching through its related descriptors to find the right model."""
        for obj in self._meta.get_all_related_objects():
            if obj.model != self.__class__ and obj.field.rel.parent_link:
                try:
                    return getattr(self, obj.get_accessor_name()).get_leaf_object()
                except obj.model.DoesNotExist:
                    pass
        return self



class Relatable(models.Model, Inheritable):
    """
    NON-abstract model mixin that encapsulates a many-to-many field to itself.
    """
    content_type = models.ForeignKey(ContentType, blank=True, null=True)
    related_items = models.ManyToManyField('RelatableContent', blank=True,
                       symmetrical=True, help_text="contents related to this")