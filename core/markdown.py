"""Shared markdown rendering pipeline.

Used for issue descriptions, comments and wiki pages so previews, mentions
and mermaid behave identically everywhere:

    raw markdown
      → mention tokens  @[Name](u:<id>)  become styled chips
      → python-markdown (fenced code, tables, sane lists, nl2br)
      → nh3 sanitisation (allow-list)
      → ```mermaid fences become <pre class="mermaid"> for mermaid.js
"""
import re

import markdown as md
import nh3

MENTION_RE = re.compile(r'@\[([^\]\n]{1,80})\]\(u:(\d+)\)')
_MERMAID_RE = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.DOTALL,
)

ALLOWED_TAGS = {
    'a', 'p', 'br', 'hr', 'strong', 'em', 'del', 'blockquote',
    'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'span', 'img',
}
ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title'},
    'img': {'src', 'alt', 'title'},
    'span': {'class'},
    'code': {'class'},
    'pre': {'class'},
    'th': {'align'},
    'td': {'align'},
}


def render_markdown(text):
    """Markdown → safe HTML string (mark_safe is the caller's job)."""
    if not text:
        return ''
    source = MENTION_RE.sub(r'<span class="mention">@\1</span>', text)
    html = md.markdown(
        source,
        extensions=['fenced_code', 'tables', 'sane_lists', 'nl2br'],
    )
    html = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={'http', 'https', 'mailto'},
        link_rel='noopener noreferrer',
    )
    return _MERMAID_RE.sub(r'<pre class="mermaid">\1</pre>', html)


def extract_mention_ids(text):
    """User pks mentioned in raw markdown (for notification triggers)."""
    if not text:
        return []
    return [int(pk) for _, pk in MENTION_RE.findall(text)]
