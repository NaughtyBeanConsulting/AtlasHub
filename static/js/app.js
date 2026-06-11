/* AtlasHub front-end glue: Alpine components + htmx hooks.
   Load order in base.html: htmx → app.js → alpine (registrations below run
   on alpine:init, before Alpine scans the DOM). */
'use strict';

// ── Theme (light / dark / system) ────────────────────────────────────────────
// base.html applies the saved theme pre-paint; this keeps it in sync when the
// user switches or the OS preference changes.
function applyTheme() {
  const t = localStorage.getItem('ah-theme') || 'system';
  const dark = t === 'dark'
    || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
}

window.setTheme = function (mode) {
  localStorage.setItem('ah-theme', mode);
  applyTheme();
};

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);

document.addEventListener('alpine:init', () => {
  // Theme picker state (profile menu).
  Alpine.data('themePicker', () => ({
    mode: localStorage.getItem('ah-theme') || 'system',
    set(mode) {
      this.mode = mode;
      window.setTheme(mode);
    },
  }));

  // Generic dropdown / popover.
  Alpine.data('dropdown', () => ({
    open: false,
    toggle() { this.open = !this.open; },
    close() { this.open = false; },
  }));

  // Auto-dismissing toast (Django messages).
  Alpine.data('toast', (timeout = 6000) => ({
    show: true,
    init() { setTimeout(() => { this.show = false; }, timeout); },
  }));

  // Markdown editor: mention autocomplete + toolbar actions + preview tab.
  Alpine.data('mdEditor', (mentionUrl) => ({
    tab: 'write',
    results: [],
    show: false,
    onInput() {
      const ta = this.$refs.ta;
      const upto = ta.value.slice(0, ta.selectionStart);
      const match = upto.match(/@([\w.\-]*)$/);
      if (!match) { this.show = false; return; }
      fetch(`${mentionUrl}?q=${encodeURIComponent(match[1])}`)
        .then((r) => r.json())
        .then((data) => {
          this.results = data.results;
          this.show = this.results.length > 0;
        })
        .catch(() => { this.show = false; });
    },
    pick(item) {
      const ta = this.$refs.ta;
      const pos = ta.selectionStart;
      const before = ta.value.slice(0, pos).replace(/@[\w.\-]*$/, `@[${item.name}](u:${item.id}) `);
      ta.value = before + ta.value.slice(pos);
      this.show = false;
      ta.focus();
      ta.selectionStart = before.length;
      ta.selectionEnd = before.length;
    },
    wrap(prefix, suffix = prefix) {
      const ta = this.$refs.ta;
      const { selectionStart: s, selectionEnd: e, value: v } = ta;
      const selected = v.slice(s, e) || 'text';
      ta.value = v.slice(0, s) + prefix + selected + suffix + v.slice(e);
      ta.focus();
      ta.selectionStart = s + prefix.length;
      ta.selectionEnd = s + prefix.length + selected.length;
    },
    block(text) {
      const ta = this.$refs.ta;
      const pos = ta.selectionEnd;
      const before = ta.value.slice(0, pos);
      const glue = before === '' || before.endsWith('\n\n') ? '' : (before.endsWith('\n') ? '\n' : '\n\n');
      ta.value = before + glue + text + '\n' + ta.value.slice(pos);
      ta.focus();
      ta.selectionStart = ta.selectionEnd = (before + glue + text).length;
    },
    async insertDiagram(url, pageId) {
      const params = new URLSearchParams({ page: pageId, title: 'Untitled diagram' });
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body: params,
      });
      if (!resp.ok) return;
      const data = await resp.json();
      this.tab = 'write';
      this.block(data.fence);
    },
  }));

  // @mention autocomplete for textareas (x-ref="ta" inside the component).
  Alpine.data('mentionBox', (url) => ({
    results: [],
    show: false,
    onInput() {
      const ta = this.$refs.ta;
      const upto = ta.value.slice(0, ta.selectionStart);
      const match = upto.match(/@([\w.\-]*)$/);
      if (!match) { this.show = false; return; }
      fetch(`${url}?q=${encodeURIComponent(match[1])}`)
        .then((r) => r.json())
        .then((data) => {
          this.results = data.results;
          this.show = this.results.length > 0;
        })
        .catch(() => { this.show = false; });
    },
    pick(item) {
      const ta = this.$refs.ta;
      const pos = ta.selectionStart;
      const before = ta.value.slice(0, pos).replace(/@[\w.\-]*$/, `@[${item.name}](u:${item.id}) `);
      ta.value = before + ta.value.slice(pos);
      this.show = false;
      ta.focus();
      ta.selectionStart = before.length;
      ta.selectionEnd = before.length;
    },
  }));
});

function csrfToken() {
  try {
    return JSON.parse(document.body.getAttribute('hx-headers'))['X-CSRFToken'] || '';
  } catch (e) {
    return '';
  }
}

function postForm(url, params) {
  return fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken() },
    body: params,
  }).then((r) => {
    if (!r.ok) window.location.reload();
  });
}

// Backlog: drag to reorder within an epic group, or across groups to change epic.
function initBacklogLists(root) {
  if (!window.Sortable) return;
  root.querySelectorAll('.js-backlog-list').forEach((el) => {
    if (el._sortable) return;
    el._sortable = new Sortable(el, {
      group: 'backlog',
      handle: '.js-grip',
      animation: 150,
      ghostClass: 'opacity-40',
      onEnd(evt) {
        const list = evt.to;
        const params = new URLSearchParams();
        params.append('moved', evt.item.dataset.id);
        params.append('epic', list.dataset.epic || '');
        list.querySelectorAll('.js-backlog-row').forEach((row) => params.append('ids', row.dataset.id));
        postForm(list.dataset.url, params);
      },
    });
  });
}

// Backlog: sprint-planning panels — same drag group as the backlog lists so
// issues can be dragged between the backlog and (planned/active) sprints.
function initSprintLists(root) {
  if (!window.Sortable) return;
  root.querySelectorAll('.js-sprint-list').forEach((el) => {
    if (el._sortable) return;
    el._sortable = new Sortable(el, {
      group: 'backlog',
      handle: '.js-grip',
      animation: 150,
      ghostClass: 'opacity-40',
      onEnd(evt) {
        const list = evt.to;
        const params = new URLSearchParams();
        params.append('moved', evt.item.dataset.id);
        if (list.dataset.sprint) {
          params.append('sprint', list.dataset.sprint);
        } else {
          params.append('epic', list.dataset.epic || '');
        }
        list.querySelectorAll('.js-backlog-row').forEach((row) => params.append('ids', row.dataset.id));
        postForm(list.dataset.url, params);
      },
    });
  });
}

// Board: drag cards between status columns.
function initBoardLists(root) {
  if (!window.Sortable) return;
  root.querySelectorAll('.js-board-list').forEach((el) => {
    if (el._sortable) return;
    el._sortable = new Sortable(el, {
      group: 'board',
      animation: 150,
      ghostClass: 'opacity-40',
      onEnd(evt) {
        const list = evt.to;
        const params = new URLSearchParams();
        params.append('moved', evt.item.dataset.id);
        params.append('status', list.dataset.status);
        list.querySelectorAll('.js-board-card').forEach((card) => params.append('ids', card.dataset.id));
        postForm(list.dataset.url, params);
      },
    });
  });
}

// Wiki sidebar tree: drag to reorder among siblings (re-parenting uses Move).
function initTreeLists(root) {
  if (!window.Sortable) return;
  root.querySelectorAll('.js-tree-list').forEach((el) => {
    if (el._sortable) return;
    el._sortable = new Sortable(el, {
      group: 'tree-' + (el.dataset.parent || 'root'),
      handle: '.js-tree-grip',
      animation: 150,
      ghostClass: 'opacity-40',
      onEnd(evt) {
        const list = evt.to;
        const params = new URLSearchParams();
        params.append('parent', list.dataset.parent || '');
        list.querySelectorAll(':scope > li[data-id]').forEach((li) => params.append('ids', li.dataset.id));
        postForm(list.dataset.url, params);
      },
    });
  });
}

// htmx.onLoad fires on initial load and after every swap.
if (window.htmx) {
  htmx.onLoad((root) => {
    initBacklogLists(root);
    initSprintLists(root);
    initBoardLists(root);
    initTreeLists(root);
  });
}

// Mermaid: render fenced diagrams on initial page load.
document.addEventListener('DOMContentLoaded', () => {
  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral' });
    window.mermaid.run();
  }
});

// Re-render mermaid diagrams inside content swapped in by htmx (wiki pages).
document.addEventListener('htmx:afterSwap', (evt) => {
  if (window.mermaid) {
    const nodes = evt.detail.elt.querySelectorAll('.mermaid');
    if (nodes.length) window.mermaid.run({ nodes });
  }
});
