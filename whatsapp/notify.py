"""High-level notification helper: preference- and phone-aware enqueueing.

Everything goes through enqueue_for_user() so the rules live in one place:
no phone → skip; preference switched off → skip; never notify yourself.
Messages are queued (never sent inline) — the scheduler flushes them.
"""
import logging

from django.conf import settings

from .client import service

logger = logging.getLogger('whatsapp')


def absolute_url(path):
    return f'{settings.SITE_URL}{path}'


def enqueue_for_user(user, message_type, text, pref_field=None, actor=None):
    if user is None or not user.is_active:
        return None
    if actor is not None and user.pk == actor.pk:
        return None
    if not (user.phone or '').strip():
        return None
    if pref_field:
        from accounts.models import NotificationPreference
        prefs, _ = NotificationPreference.objects.get_or_create(user=user)
        if not getattr(prefs, pref_field, True):
            return None
    return service.enqueue(user.phone, text, user=user, msg_type=message_type)
