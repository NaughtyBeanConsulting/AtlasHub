from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from core.models import Space

# Colours an epic's tag can take (ADS accents, purple first as Atlas does).
EPIC_COLORS = [
    '#6554C0', '#00875A', '#0052CC', '#FF8B00',
    '#DE350B', '#00A3BF', '#403294', '#172B4D',
]


class Status(models.Model):
    """A workflow status = a board column. Per-space data, not schema, so any
    real Atlas workflow can be reproduced by editing rows (seeded on space
    creation with To Do / In Progress / In Review / Done)."""

    CATEGORY_TODO = 'todo'
    CATEGORY_IN_PROGRESS = 'in_progress'
    CATEGORY_DONE = 'done'
    CATEGORY_CHOICES = [
        (CATEGORY_TODO, 'To do'),
        (CATEGORY_IN_PROGRESS, 'In progress'),
        (CATEGORY_DONE, 'Done'),
    ]

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='statuses')
    name = models.CharField(max_length=60)
    category = models.CharField(max_length=12, choices=CATEGORY_CHOICES, default=CATEGORY_TODO)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ['space', 'name']
        verbose_name_plural = 'statuses'

    def __str__(self):
        return f'{self.name} ({self.space.key})'

    @property
    def lozenge_class(self):
        return {
            self.CATEGORY_TODO: 'lozenge-todo',
            self.CATEGORY_IN_PROGRESS: 'lozenge-inprogress',
            self.CATEGORY_DONE: 'lozenge-done',
        }[self.category]


class Label(models.Model):
    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='labels')
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ['name']
        unique_together = ['space', 'name']

    def __str__(self):
        return self.name


class Sprint(models.Model):
    STATE_PLANNED = 'planned'
    STATE_ACTIVE = 'active'
    STATE_COMPLETED = 'completed'
    STATE_CHOICES = [
        (STATE_PLANNED, 'Planned'),
        (STATE_ACTIVE, 'Active'),
        (STATE_COMPLETED, 'Completed'),
    ]

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='sprints')
    name = models.CharField(max_length=120)
    goal = models.TextField(blank=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_PLANNED)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    # Public holidays falling inside the sprint — everyone loses these days
    # in the capacity planner.
    public_holidays = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            # Only one sprint may be running per board/space.
            models.UniqueConstraint(
                fields=['space'], condition=Q(state='active'),
                name='one_active_sprint_per_space',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.space.key})'


class IssueManager(models.Manager):
    def active(self):
        return self.filter(archived=False)

    def create_issue(self, *, space, **fields):
        """Create an issue with a race-safe sequential key (CLIC-1, CLIC-2…):
        the Space row is locked while its counter increments."""
        with transaction.atomic():
            locked = Space.objects.select_for_update().get(pk=space.pk)
            locked.issue_counter += 1
            locked.save(update_fields=['issue_counter'])
            return self.create(
                space=locked,
                number=locked.issue_counter,
                key=f'{locked.key}-{locked.issue_counter}',
                **fields,
            )


class Issue(models.Model):
    TYPE_EPIC = 'epic'
    TYPE_STORY = 'story'
    TYPE_TASK = 'task'
    TYPE_BUG = 'bug'
    TYPE_SUBTASK = 'subtask'
    TYPE_CHOICES = [
        (TYPE_EPIC, 'Epic'),
        (TYPE_STORY, 'Story'),
        (TYPE_TASK, 'Task'),
        (TYPE_BUG, 'Bug'),
        (TYPE_SUBTASK, 'Sub-task'),
    ]
    # Types creatable in backlog/board flows (epics and subtasks have their own flows).
    STANDARD_TYPES = [TYPE_STORY, TYPE_TASK, TYPE_BUG]

    PRIORITY_CHOICES = [
        ('highest', 'Highest'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('lowest', 'Lowest'),
    ]

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='issues')
    number = models.PositiveIntegerField()
    key = models.CharField(max_length=20, unique=True)
    issue_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_STORY)
    summary = models.CharField(max_length=255)
    description_md = models.TextField(blank=True)
    # RESTRICT, not PROTECT: deleting a Status alone is blocked while issues
    # use it, but deleting the whole Space still cascades cleanly.
    status = models.ForeignKey(Status, on_delete=models.RESTRICT, related_name='issues')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    story_points = models.PositiveSmallIntegerField(null=True, blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_issues',
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reported_issues',
    )
    epic = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='epic_issues', limit_choices_to={'issue_type': TYPE_EPIC},
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='subtasks',
    )
    sprint = models.ForeignKey(
        Sprint, null=True, blank=True, on_delete=models.SET_NULL, related_name='issues',
    )
    labels = models.ManyToManyField(Label, blank=True, related_name='issues')
    # Hub pages documenting this issue (filtered by page-level security on display).
    linked_pages = models.ManyToManyField('wiki.Page', blank=True, related_name='linked_issues')
    # Archived issues are hidden everywhere (backlog, board, timeline, search,
    # reports) but kept for the record; admins can restore or hard-delete.
    archived = models.BooleanField(default=False)
    epic_color = models.CharField(max_length=7, default=EPIC_COLORS[0])
    # Display order. Contexts are disjoint: the backlog orders within an epic
    # group (sprint is null), the board orders within a status column.
    rank = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = IssueManager()

    class Meta:
        ordering = ['rank', 'id']
        unique_together = ['space', 'number']
        indexes = [
            models.Index(fields=['space', 'issue_type']),
            models.Index(fields=['space', 'sprint']),
        ]

    def __str__(self):
        return f'{self.key} {self.summary}'

    @property
    def is_done(self):
        return self.status.category == Status.CATEGORY_DONE


class AcceptanceCriterion(models.Model):
    """One checkable item of a story's acceptance-criteria checklist."""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='acceptance_criteria')
    text = models.CharField(max_length=500)
    is_done = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name_plural = 'acceptance criteria'

    def __str__(self):
        return self.text


class Comment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='issue_comments',
    )
    body_md = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment on {self.issue.key} by {self.author}'


class SprintCapacity(models.Model):
    """One member's row in a sprint's capacity planner.

    capacity = (base_points / working_days)
               × (working_days − public_holidays − leave_days)
               × role factor (team lead 0.8, tech lead 0.7)
    """

    ROLE_NONE = 'none'
    ROLE_TEAM_LEAD = 'team_lead'
    ROLE_TECH_LEAD = 'tech_lead'
    ROLE_CHOICES = [
        (ROLE_NONE, '—'),
        (ROLE_TEAM_LEAD, 'Team lead'),
        (ROLE_TECH_LEAD, 'Tech lead'),
    ]
    ROLE_FACTOR = {ROLE_NONE: 1.0, ROLE_TEAM_LEAD: 0.8, ROLE_TECH_LEAD: 0.7}

    sprint = models.ForeignKey(Sprint, on_delete=models.CASCADE, related_name='capacities')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sprint_capacities',
    )
    base_points = models.PositiveSmallIntegerField(
        default=10, help_text='Story points this person can take in a full sprint.',
    )
    leave_days = models.PositiveSmallIntegerField(default=0)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_NONE)

    class Meta:
        unique_together = ['sprint', 'user']
        verbose_name_plural = 'sprint capacities'

    def __str__(self):
        return f'{self.user.display_name} — {self.sprint.name}'


class RetroItem(models.Model):
    """A retrospective card for a completed sprint."""

    CATEGORY_WENT_WELL = 'went_well'
    CATEGORY_IMPROVE = 'improve'
    CATEGORY_ACTION = 'action'
    CATEGORY_CHOICES = [
        (CATEGORY_WENT_WELL, 'What went well'),
        (CATEGORY_IMPROVE, 'What could improve'),
        (CATEGORY_ACTION, 'Action items'),
    ]

    sprint = models.ForeignKey(Sprint, on_delete=models.CASCADE, related_name='retro_items')
    category = models.CharField(max_length=12, choices=CATEGORY_CHOICES)
    text = models.CharField(max_length=500)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='retro_items',
    )
    # Action items can be promoted to a backlog issue.
    linked_issue = models.ForeignKey(
        Issue, null=True, blank=True, on_delete=models.SET_NULL, related_name='retro_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.get_category_display()}] {self.text[:40]}'


class Activity(models.Model):
    """One line of an issue's history: 'created', or a field change with
    old/new display values. Written explicitly by record_activity()."""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='issue_activities',
    )
    field = models.CharField(max_length=40)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'activities'

    def __str__(self):
        return f'{self.issue.key}: {self.field}'
