"""Wiki rendering helpers built on the shared core.markdown pipeline."""
import base64
import re

from django.urls import reverse
from django.utils.html import escape

from core.markdown import render_markdown

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
            b64 = base64.b64encode(diagram.svg.encode()).decode()
            body = (
                f'<img src="data:image/svg+xml;base64,{b64}" '
                f'alt="{escape(diagram.title)}" loading="lazy">'
            )
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
