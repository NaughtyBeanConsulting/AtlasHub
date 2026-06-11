from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

# Preset space colours (ADS accents) offered in the create form.
SPACE_COLORS = [
    '#0052CC', '#6554C0', '#00875A', '#FF8B00',
    '#DE350B', '#00A3BF', '#5243AA', '#172B4D',
]

key_validator = RegexValidator(
    r'^[A-Z][A-Z0-9]{1,9}$',
    'Keys are 2–10 characters, uppercase letters/digits, starting with a letter (e.g. CLIC).',
)


class Space(models.Model):
    """A container with a short KEY and members — a Jira project space
    (software) or a Confluence wiki space (wiki). One model on purpose:
    membership, roles, the picker and the create flow are shared."""

    TYPE_SOFTWARE = 'software'
    TYPE_WIKI = 'wiki'
    TYPE_CHOICES = [
        (TYPE_SOFTWARE, 'Jira project'),
        (TYPE_WIKI, 'Confluence space'),
    ]

    name = models.CharField(max_length=120)
    key = models.CharField(max_length=10, unique=True, validators=[key_validator])
    space_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default=SPACE_COLORS[0])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='created_spaces',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Per-space sequence behind issue keys (software spaces only).
    issue_counter = models.PositiveIntegerField(default=0)

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='SpaceMembership', related_name='spaces',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.key})'

    def role_for(self, user):
        """The user's role in this space, or None. Superusers act as admins."""
        if not user.is_authenticated:
            return None
        if user.is_superuser:
            return SpaceMembership.ROLE_ADMIN
        membership = self.memberships.filter(user=user).first()
        return membership.role if membership else None


class SpaceMembership(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_VIEWER = 'viewer'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
        (ROLE_VIEWER, 'Viewer'),
    ]
    # Rank for "at least this role" checks.
    ROLE_RANK = {ROLE_VIEWER: 0, ROLE_MEMBER: 1, ROLE_ADMIN: 2}

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='space_memberships',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['space', 'user']
        ordering = ['space', 'user__first_name']

    def __str__(self):
        return f'{self.user.display_name} — {self.get_role_display()} of {self.space.key}'
