"""Background queue flusher — runs in a daemon thread inside the web process.

Each tick sends up to 10 PENDING WhatsAppMessage rows via the Node worker.
Rows are taken with select_for_update(skip_locked=True) so multiple gunicorn
workers can run the scheduler without double-sending (ClockInSop's version is
single-worker-safe only — this is the hardened variant).
"""
import logging
import threading

logger = logging.getLogger('whatsapp')

TICK_SECONDS = 10
BATCH_SIZE = 10
MAX_RETRIES = 3


class QueueScheduler:
    _instance = None
    _class_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._thread = None
                    obj._stop_event = threading.Event()
                    cls._instance = obj
        return cls._instance

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name='whatsapp-scheduler',
        )
        self._thread.start()
        logger.info('WhatsApp queue scheduler started (tick %ds)', TICK_SECONDS)

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                _flush_queue()
            except Exception as exc:
                logger.warning('Queue flush error: %s', exc)
            self._stop_event.wait(timeout=TICK_SECONDS)


def _flush_queue():
    from django.db import transaction
    from django.utils import timezone

    from .client import service
    from .models import WhatsAppMessage

    for _ in range(BATCH_SIZE):
        with transaction.atomic():
            msg = (
                WhatsAppMessage.objects
                .select_for_update(skip_locked=True)
                .filter(status=WhatsAppMessage.PENDING)
                .order_by('created_at')
                .first()
            )
            if msg is None:
                return
            ok = service.send(msg.phone_number, msg.message)
            if ok:
                msg.status = WhatsAppMessage.SENT
                msg.sent_at = timezone.now()
                msg.error_message = ''
            else:
                msg.retry_count += 1
                if msg.retry_count >= MAX_RETRIES:
                    msg.status = WhatsAppMessage.FAILED
                    msg.error_message = service.info.get('error') or 'Send failed.'
            msg.save(update_fields=['status', 'sent_at', 'retry_count', 'error_message'])


# Module-level singleton — imported by apps.py
scheduler = QueueScheduler()
