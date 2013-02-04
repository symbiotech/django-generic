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




class HousekeepingMixin(models.Model):
    """Abstract mixin class to collect creation and update timestamps."""
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
