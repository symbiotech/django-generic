from django.db import models

from ..mixins import Inheritable

class Relatable(models.Model, Inheritable):
    """
    NON-abstract model mixin that encapsulates a many-to-many field to itself.
    """
    related_items = models.ManyToManyField('Relatable', blank=True,
                       symmetrical=True, help_text="contents related to this")    
