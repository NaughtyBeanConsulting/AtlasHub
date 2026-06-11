from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from .utils import normalize_phone

# Atlassian-style avatar colours; a user's colour is a stable hash of their pk.
AVATAR_COLORS = [
    '#0052CC', '#6554C0', '#00875A', '#DE350B', '#FF8B00',
    '#00A3BF', '#5243AA', '#006644', '#BF2600', '#172B4D',
]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('An email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-keyed user — there is no username field anywhere in AtlasHub."""

    email = models.EmailField('email address', unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(
        max_length=30, blank=True,
        help_text='Optional. Used for WhatsApp notifications and password resets.',
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['first_name', 'last_name', 'email']

    def save(self, *args, **kwargs):
        if self.phone:
            self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name or self.email

    @property
    def display_name(self):
        return self.get_full_name() or self.email

    @property
    def initials(self):
        if self.first_name or self.last_name:
            return f'{self.first_name[:1]}{self.last_name[:1]}'.upper() or self.email[:2].upper()
        return self.email[:2].upper()

    @property
    def avatar_color(self):
        return AVATAR_COLORS[self.pk % len(AVATAR_COLORS)] if self.pk else AVATAR_COLORS[0]


class NotificationPreference(models.Model):
    """Per-user opt-in/out switches for WhatsApp notification triggers."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    notify_issue_assigned = models.BooleanField(
        'Issue assigned to me', default=True)
    notify_mention = models.BooleanField(
        'Someone @mentions me', default=True)
    notify_sprint_started = models.BooleanField(
        'Sprint started in my projects', default=True)
    notify_sprint_completed = models.BooleanField(
        'Sprint completed in my projects', default=True)

    class Meta:
        verbose_name = 'notification preference'

    def __str__(self):
        return f'Notification preferences — {self.user.display_name}'
