"""Wiki rendering helpers built on the shared core.markdown pipeline."""
import base64
import re

from django.urls import reverse
from django.utils.html import escape

from core.markdown import render_markdown
from core.models import SpaceMembership


def required_view_ranks(space):
    """Map of page id → minimum role rank needed to view it, taking inherited
    restrictions (max along the ancestor chain) and draft status (member+)
    into account. One query per space — used by trees, search, dashboards."""
    rank = SpaceMembership.ROLE_RANK
    member_rank = rank[SpaceMembership.ROLE_MEMBER]
    pages = {
        p['id']: p for p in
        space.pages.values('id', 'parent_id', 'view_role', 'is_published')
    }
    needed = {}

    def resolve(pid, seen):
        if pid in needed:
            return needed[pid]
        page = pages[pid]
        need = rank[page['view_role']]
        parent_id = page['parent_id']
        if parent_id in pages and parent_id not in seen:
            seen.add(pid)
            need = max(need, resolve(parent_id, seen))
        if not page['is_published']:
            need = max(need, member_rank)
        needed[pid] = need
        return need

    for pid in pages:
        resolve(pid, {pid})
    return needed


def visible_page_ids(space, role):
    """Ids of the pages a member with `role` may see in this space."""
    user_rank = SpaceMembership.ROLE_RANK[role]
    return {pid for pid, need in required_view_ranks(space).items() if user_rank >= need}


def filter_pages_for_user(user, pages, limit=None):
    """Apply page-level security (restrictions + drafts) to pages that may
    span several spaces. `pages` should be select_related('space')."""
    ranks, needs = {}, {}
    out = []
    for page in pages:
        space = page.space
        if space.pk not in ranks:
            role = space.role_for(user)
            ranks[space.pk] = SpaceMembership.ROLE_RANK[role] if role else -1
            needs[space.pk] = required_view_ranks(space)
        if ranks[space.pk] >= needs[space.pk].get(page.pk, 99):
            out.append(page)
            if limit and len(out) >= limit:
                break
    return out

# ```drawio:<id>``` fences are swapped for a token BEFORE markdown runs
# (python-markdown won't treat "drawio:<id>" as a fence language), and the
# token — a span nh3's allow-list keeps — is replaced with the embed AFTER
# sanitisation. Only diagrams belonging to the page resolve, so a hand-typed
# token can't leak anything.
_DRAWIO_FENCE_MD = re.compile(r'```drawio:(\d+)[^\n]*\n[\s\S]*?```')
_DRAWIO_TOKEN_HTML = re.compile(r'<span class="drawio-token">(\d+)</span>')


def render_page_html(page, can_edit=False):
    """Render a page's markdown, swapping ```drawio:<id>``` fences for the
    stored SVG export (as a data URI <img>, so untrusted SVG never executes)
    plus an edit affordance."""
    source = _DRAWIO_FENCE_MD.sub(
        lambda m: f'<span class="drawio-token">{m.group(1)}</span>',
        page.body_md or '',
    )
    html = render_markdown(source)
    diagrams = {d.pk: d for d in page.diagrams.all()}

    def replace(match):
        diagram = diagrams.get(int(match.group(1)))
        if diagram is None:
            return '<span class="drawio-missing">⚠ Diagram not found.</span>'
        edit_url = reverse('wiki:diagram_edit', args=[page.space.key, diagram.pk])
        if diagram.svg:
            # Newer saves store the export as a data URI (SVG, or PNG when
            # draw.io's SVG exporter fails); older rows hold raw SVG text.
            if diagram.svg.startswith('data:image'):
                src = diagram.svg
            else:
                b64 = base64.b64encode(diagram.svg.encode()).decode()
                src = f'data:image/svg+xml;base64,{b64}'
            body = f'<img src="{src}" alt="{escape(diagram.title)}" loading="lazy">'
            action = 'Edit diagram'
        else:
            body = (
                f'<span class="drawio-placeholder">“{escape(diagram.title)}” '
                'hasn\'t been drawn yet.</span>'
            )
            action = 'Draw diagram'
        link = (
            f'<a href="{edit_url}" class="drawio-edit">{action}</a>'
            if can_edit else ''
        )
        return (
            f'<span class="drawio-embed" data-diagram="{diagram.pk}">{body}{link}</span>'
        )

    return _DRAWIO_TOKEN_HTML.sub(replace, html)
