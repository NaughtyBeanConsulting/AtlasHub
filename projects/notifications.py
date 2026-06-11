"""Notification trigger points for the projects app → WhatsApp queue.

All delivery rules (phone present, preference on, never self-notify) live in
whatsapp.notify.enqueue_for_user; these functions only build the messages.
"""
from django.urls import reverse

from core.markdown import extract_mention_ids


def notify_issue_assigned(issue, actor, old_assignee=None):
    from whatsapp.models import WhatsAppMessage
    from whatsapp.notify import absolute_url, enqueue_for_user

    if issue.assignee is None:
        return
    link = absolute_url(reverse('projects:browse', args=[issue.key]))
    text = (
        f'🔔 AtlasHub — {actor.display_name} assigned {issue.key} to you.\n'
        f'“{issue.summary}”\n{link}'
    )
    enqueue_for_user(
        issue.assignee, WhatsAppMessage.ISSUE_ASSIGNED, text,
        pref_field='notify_issue_assigned', actor=actor,
    )


def notify_mentions(issue, actor, body_md):
    from whatsapp.models import WhatsAppMessage
    from whatsapp.notify import absolute_url, enqueue_for_user

    ids = set(extract_mention_ids(body_md))
    if not ids:
        return
    link = absolute_url(reverse('projects:browse', args=[issue.key]))
    text = (
        f'💬 AtlasHub — {actor.display_name} mentioned you on {issue.key}.\n'
        f'“{issue.summary}”\n{link}'
    )
    for user in issue.space.members.filter(pk__in=ids, is_active=True):
        enqueue_for_user(user, WhatsAppMessage.MENTION, text,
                         pref_field='notify_mention', actor=actor)


def notify_sprint_event(sprint, actor, event):
    """event: 'started' | 'completed' — sent to the sprint's issue assignees."""
    from django.contrib.auth import get_user_model

    from whatsapp.models import WhatsAppMessage
    from whatsapp.notify import absolute_url, enqueue_for_user

    if event == 'started':
        msg_type, pref = WhatsAppMessage.SPRINT_STARTED, 'notify_sprint_started'
        link = absolute_url(reverse('projects:board', args=[sprint.space.key]))
        text = f'🏃 AtlasHub — sprint “{sprint.name}” started in {sprint.space.name}.'
        if sprint.goal:
            text += f'\nGoal: {sprint.goal}'
        if sprint.start_date and sprint.end_date:
            text += f'\n{sprint.start_date:%d %b} – {sprint.end_date:%d %b}'
    else:
        msg_type, pref = WhatsAppMessage.SPRINT_COMPLETED, 'notify_sprint_completed'
        link = absolute_url(reverse('projects:backlog', args=[sprint.space.key]))
        text = f'🏁 AtlasHub — sprint “{sprint.name}” completed in {sprint.space.name}.'
    text += f'\n{link}'

    assignee_ids = (
        sprint.issues.filter(assignee__isnull=False)
        .values_list('assignee_id', flat=True).distinct()
    )
    for user in get_user_model().objects.filter(pk__in=assignee_ids, is_active=True):
        enqueue_for_user(user, msg_type, text, pref_field=pref, actor=actor)
