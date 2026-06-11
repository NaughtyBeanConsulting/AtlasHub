"""Notification trigger points for the projects app.

Phase 6 wires these to the WhatsApp queue; until then they are safe no-ops so
views can call them unconditionally.
"""


def notify_issue_assigned(issue, actor, old_assignee=None):
    pass


def notify_mentions(issue, actor, body_md):
    pass


def notify_sprint_event(sprint, actor, event):
    """event: 'started' | 'completed' — sent to sprint issue assignees."""
    pass
