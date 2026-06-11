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

// Re-render mermaid diagrams inside content swapped in by htmx (wiki pages).
document.addEventListener('htmx:afterSwap', (evt) => {
  if (window.mermaid) {
    const nodes = evt.detail.elt.querySelectorAll('.mermaid');
    if (nodes.length) window.mermaid.run({ nodes });
  }
});
