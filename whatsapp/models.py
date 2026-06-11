from django.conf import settings
from django.db import models


class WhatsAppMessage(models.Model):
    PENDING = 'PENDING'
    SENT = 'SENT'
    FAILED = 'FAILED'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (SENT, 'Sent'),
        (FAILED, 'Failed'),
    ]

    MANUAL = 'MANUAL'
    ISSUE_ASSIGNED = 'ISSUE_ASSIGNED'
    MENTION = 'MENTION'
    SPRINT_STARTED = 'SPRINT_STARTED'
    SPRINT_COMPLETED = 'SPRINT_COMPLETED'
    PASSWORD_RESET = 'PASSWORD_RESET'
    TYPE_CHOICES = [
        (MANUAL, 'Manual'),
        (ISSUE_ASSIGNED, 'Issue assigned'),
        (MENTION, '@Mention'),
        (SPRINT_STARTED, 'Sprint started'),
        (SPRINT_COMPLETED, 'Sprint completed'),
        (PASSWORD_RESET, 'Password reset'),
    ]

    phone_number = models.CharField(max_length=30)
    message = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='whatsapp_messages',
    )
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=MANUAL)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.phone_number:
            from accounts.utils import normalize_phone
            self.phone_number = normalize_phone(self.phone_number)
        super().save(*args, **kwargs)

    def __str__(self):
        who = self.user.display_name if self.user else self.phone_number
        return f'{who} — {self.get_status_display()} ({self.created_at:%Y-%m-%d})'


class WhatsAppDevice(WhatsAppMessage):
    """Proxy model whose sole purpose is a 'Connection' link in the admin sidebar."""
    class Meta:
        proxy = True
        verbose_name = 'Connection'
        verbose_name_plural = 'Connection'
