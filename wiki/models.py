from django.conf import settings
from django.db import models
from django.utils.text import slugify

from core.models import Space

# Slugs that would shadow wiki URL routes.
RESERVED_SLUGS = {'create', 'reorder', 'preview', 'diagrams'}


def unique_slug(space, title, exclude_pk=None):
    base = slugify(title)[:80] or 'page'
    if base in RESERVED_SLUGS:
        base = f'{base}-page'
    slug = base
    n = 2
    qs = Page.objects.filter(space=space)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        slug = f'{base}-{n}'
        n += 1
    return slug


class Page(models.Model):
    """A wiki page in an arbitrarily nested tree (parent self-FK)."""

    # Who may VIEW the page. Restrictions inherit down the tree: a page is at
    # least as restricted as every ancestor. (Editing always needs member+.)
    VIEW_VIEWER = 'viewer'
    VIEW_MEMBER = 'member'
    VIEW_ADMIN = 'admin'
    VIEW_CHOICES = [
        (VIEW_VIEWER, 'Everyone in the space'),
        (VIEW_MEMBER, 'Members and admins'),
        (VIEW_ADMIN, 'Admins only'),
    ]

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='pages')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children',
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=90)
    body_md = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    view_role = models.CharField(max_length=10, choices=VIEW_CHOICES, default=VIEW_VIEWER)
    # Draft pages are only visible to people who could edit them (member+).
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_pages',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='updated_pages',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        unique_together = ['space', 'slug']

    def __str__(self):
        return f'{self.title} ({self.space.key})'

    def ancestors(self):
        """Root-first ancestor chain for breadcrumbs (cycle-safe)."""
        chain, node, seen = [], self.parent, {self.pk}
        while node and node.pk not in seen:
            chain.append(node)
            seen.add(node.pk)
            node = node.parent
        return list(reversed(chain))

    def descendant_pks(self):
        """All descendant ids (used by the move-cycle guard)."""
        pks, frontier = set(), [self.pk]
        while frontier:
            children = list(
                Page.objects.filter(parent_id__in=frontier).values_list('pk', flat=True)
            )
            children = [pk for pk in children if pk not in pks]
            pks.update(children)
            frontier = children
        return pks

    def effective_view_role(self):
        """The strictest view_role along this page's ancestor chain."""
        from core.models import SpaceMembership
        rank = SpaceMembership.ROLE_RANK
        strictest = self.view_role
        for ancestor in self.ancestors():
            if rank[ancestor.view_role] > rank[strictest]:
                strictest = ancestor.view_role
        return strictest

    @property
    def is_restricted(self):
        return self.effective_view_role() != self.VIEW_VIEWER


class PageVersion(models.Model):
    """Snapshot of a page taken on every save — cheap text-only history."""

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='versions')
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    body_md = models.TextField(blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='page_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-number']
        unique_together = ['page', 'number']

    def __str__(self):
        return f'{self.page.title} v{self.number}'


class Diagram(models.Model):
    """A draw.io diagram embedded in a page via a ```drawio:<id>``` fence.
    `xml` is the editable source; `svg` is the export captured at save time so
    viewing never needs the embed iframe."""

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='diagrams')
    title = models.CharField(max_length=200, default='Untitled diagram')
    xml = models.TextField(blank=True)
    svg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.title} (page: {self.page.title})'

    @property
    def fence(self):
        return f'```drawio:{self.pk}\n```'


class PageComment(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='page_comments',
    )
    body_md = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment on {self.page.title} by {self.author}'
