"""
HTTP client that talks to whatsapp-node-worker (index.js).
Stdlib-only — Django never imports anything Node-side.
"""
import json
import logging
import os
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger('whatsapp.client')

_WORKER_URL = os.environ.get('WHATSAPP_WORKER_URL', 'http://127.0.0.1:8030').rstrip('/')
_WORKER_TOKEN = os.environ.get('WHATSAPP_WORKER_TOKEN', '')

_UNAVAILABLE = {
    'status': 'DISCONNECTED',
    'qr_base64': None,
    'error': 'WhatsApp worker is not running.',
}


def _headers():
    h = {'Content-Type': 'application/json'}
    if _WORKER_TOKEN:
        h['Authorization'] = f'Bearer {_WORKER_TOKEN}'
    return h


def _get(path):
    try:
        req = Request(f'{_WORKER_URL}{path}', headers=_headers())
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning('WhatsApp worker GET %s failed: %s', path, exc)
        return None


def _post(path, body=None):
    try:
        data = json.dumps(body or {}).encode()
        req = Request(f'{_WORKER_URL}{path}', data=data, headers=_headers(), method='POST')
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning('WhatsApp worker POST %s failed: %s', path, exc)
        return None


class WhatsAppClient:
    """Delegates all WhatsApp operations to the Node worker process."""

    @property
    def info(self):
        return _get('/status') or _UNAVAILABLE

    @property
    def is_connected(self):
        return self.info.get('status') == 'CONNECTED'

    def restart(self):
        if not getattr(settings, 'WHATSAPP_MANAGES_SESSION', True):
            logger.info('Ignoring restart — WhatsApp session is managed by the shared worker owner.')
            return
        _post('/restart')

    def disconnect(self):
        """Log out, clear session, reinitialise with fresh QR."""
        if not getattr(settings, 'WHATSAPP_MANAGES_SESSION', True):
            logger.info('Ignoring disconnect — WhatsApp session is managed by the shared worker owner.')
            return
        _post('/disconnect')

    def send(self, phone, message):
        """Send a message immediately. Returns True on success."""
        result = _post('/send', {'phone': phone, 'message': message})
        return bool(result and result.get('ok'))

    def enqueue(self, phone, message, user=None, msg_type='MANUAL'):
        """Write a pending message to the DB — the scheduler will send it.
        Callers never block a web request on WhatsApp."""
        from .models import WhatsAppMessage
        return WhatsAppMessage.objects.create(
            phone_number=phone,
            message=message,
            user=user,
            message_type=msg_type,
        )


service = WhatsAppClient()
