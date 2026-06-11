"""Small helpers shared by the projects views."""
from .models import Activity


def record_activity(issue, actor, field, old='', new=''):
    """Append one history line to an issue. Display values, not pks."""
    return Activity.objects.create(
        issue=issue, actor=actor, field=field,
        old_value=str(old or ''), new_value=str(new or ''),
    )
