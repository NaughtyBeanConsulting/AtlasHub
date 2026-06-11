/* AtlasHub front-end glue: Alpine components + htmx hooks.
   Load order in base.html: htmx → app.js → alpine (registrations below run
   on alpine:init, before Alpine scans the DOM). */
'use strict';

document.addEventListener('alpine:init', () => {
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

// htmx.onLoad fires on initial load and after every swap.
if (window.htmx) {
  htmx.onLoad((root) => {
    initBacklogLists(root);
    initSprintLists(root);
    initBoardLists(root);
  });
}

// Re-render mermaid diagrams inside content swapped in by htmx (wiki pages).
document.addEventListener('htmx:afterSwap', (evt) => {
  if (window.mermaid) {
    const nodes = evt.detail.elt.querySelectorAll('.mermaid');
    if (nodes.length) window.mermaid.run({ nodes });
  }
});
