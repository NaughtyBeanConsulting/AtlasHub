from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Space

from .models import Status

DEFAULT_STATUSES = [
    ('To Do', Status.CATEGORY_TODO),
    ('In Progress', Status.CATEGORY_IN_PROGRESS),
    ('In Review', Status.CATEGORY_IN_PROGRESS),
    ('Done', Status.CATEGORY_DONE),
]


@receiver(post_save, sender=Space)
def seed_statuses(sender, instance, created, **kwargs):
    """New software spaces get the default Jira-style workflow columns."""
    if created and instance.space_type == Space.TYPE_SOFTWARE:
        Status.objects.bulk_create([
            Status(space=instance, name=name, category=category, order=i)
            for i, (name, category) in enumerate(DEFAULT_STATUSES)
        ])
