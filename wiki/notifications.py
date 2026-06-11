"""Wiki notification trigger points → WhatsApp queue."""
from django.urls import reverse

from core.markdown import extract_mention_ids


def notify_page_mentions(page, actor, body_md):
    from whatsapp.models import WhatsAppMessage
    from whatsapp.notify import absolute_url, enqueue_for_user

    ids = set(extract_mention_ids(body_md))
    if not ids:
        return
    link = absolute_url(reverse('wiki:page', args=[page.space.key, page.slug]))
    text = (
        f'💬 AtlasHub — {actor.display_name} mentioned you on '
        f'“{page.title}” in {page.space.name}.\n{link}'
    )
    for user in page.space.members.filter(pk__in=ids, is_active=True):
        enqueue_for_user(user, WhatsAppMessage.MENTION, text,
                         pref_field='notify_mention', actor=actor)
