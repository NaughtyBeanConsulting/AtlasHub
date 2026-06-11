# AtlasHub — build a Jira + Confluence clone (plan first, then implement)

You are in /Users/shaundeponte/github/AtlasHub, a greenfield repo (only .env, .gitignore,
LICENSE, README.md). Before writing any application code, do the research below and present
a comprehensive implementation plan for my approval. Only build after I approve the plan.

## Mission
Build **AtlasHub**: a self-hosted clone of Atlassian Jira (Scrum, for software engineering
teams) and Confluence (wiki), as one Django monolith with two front-end components that
share authentication, navigation, and a common Atlassian-style design language — plus a
custom WhatsApp Web integration for notifications and password resets.

## Tech stack (fixed — do not substitute)
- **Backend:** Django (latest stable), one project, cleanly separated apps
  (suggested: `accounts`, `projects` (jira), `wiki` (confluence), `whatsapp`, `core`).
- **Database:** PostgreSQL. Credentials are already in `.env` (`SECRET_KEY`, `DEBUG`,
  `ALLOWED_HOSTS`, `SITE_URL`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`).
  Load them with **python-dotenv**. Never hardcode or commit secret values.
- **Frontend:** server-rendered Django templates + **HTMX** for partial updates,
  **Alpine.js** for client-side state, **Tailwind CSS** for styling.
  No React/Vue, no DRF, no SPA.
- **Admin:** Django admin styled with **django-unfold** (https://unfoldadmin.com) is the
  back-office for configuring users, permissions, projects/spaces. The custom front end is
  for day-to-day interaction with the Jira and Confluence components.
- **WhatsApp:** a sidecar **Node (≥18) worker running whatsapp-web.js** — the only Node
  runtime component in the system; it is a background service Django talks to over HTTP,
  not part of the web frontend.
- **Environment:** create a virtualenv with `python3 -m venv venv`; pin everything in
  `requirements.txt` (and the worker's deps in its own `package.json`).
- Small focused JS libraries are allowed where the stack needs them (e.g. SortableJS for
  drag-and-drop, mermaid.js, the draw.io embed iframe) — justify each one in the plan,
  and state how Tailwind will be built (standalone CLI vs django-tailwind; avoid a CDN
  setup for production).

## Research before you plan
1. Inspect the repo and the `.env` variable names (do not echo values).
2. I am signed into Jira — use the Atlassian MCP/integration to study my **clickcollect**
   space (project key **CLIC**) and mirror how I work: issue types and hierarchy, workflow
   statuses and board columns, how sprints are set up, how acceptance criteria are written,
   priorities, story points, labels. Pull 2–3 representative issues to model the ticket
   card and detail layout on.
3. Study the existing WhatsApp integration in **/Users/shaundeponte/github/ClockInSop**
   and mirror its architecture — read at minimum:
   - `whatsapp-node-worker/index.js` and `package.json` (the worker)
   - `whatsapp/client.py`, `models.py`, `scheduler.py`, `views.py`, `urls.py` (Django side)
   - `whatsapp-worker.service` (production systemd unit)
4. Check django-unfold's docs for the correct setup with a custom user model.

## Functional requirements

### Authentication — custom, email-based
- Custom user model: **email + password**, no username field anywhere (model, forms,
  admin, auth backend). `USERNAME_FIELD = "email"`. Include an optional **phone number**
  field (E.164-normalisable) for WhatsApp delivery.
- This decision must land **before the first migration** (Django's custom-user gotcha).
- Front-end signup, login, logout, password change/reset flows styled to match the app.
- **Password reset is delivered over WhatsApp** when the user has a linked phone number,
  with email as the fallback channel.
- Users, groups, and permissions are administered through the unfold-styled admin.

### Shared platform
- **Spaces are creatable from the front end** for both components: Jira project spaces
  (with a short key like CLIC that prefixes issue keys) and Confluence wiki spaces.
  Decide in the plan whether these are one model or two parallel ones, and how membership/
  roles work (e.g. admin / member / viewer per space).
- Atlassian-style global top nav (product switcher between "Jira" and "Confluence" views,
  space picker, search, profile menu) and a left sidebar per space.

### Jira component (Scrum for software engineering)
- **Issue hierarchy:** Epic → Story / Task / Bug → Sub-task. Stories carry **acceptance
  criteria** (checklist-style, individually checkable). Issues get auto-incrementing keys
  per space (CLIC-1, CLIC-2, …).
- **Issue fields:** summary, description (rich text), type, status, priority, story points,
  assignee, reporter, epic link, sprint, labels, created/updated. Comments and an activity
  history on every issue.
- **Backlog view:** ordered list of unscheduled issues, grouped by epic, drag-to-reorder,
  drag issues into a sprint; inline create.
- **Sprints:** create → **start** (name, goal, start/end dates) → **complete** (incomplete
  issues roll back to backlog or into the next sprint). Only one active sprint per board
  to start with.
- **Board (Kanban-style):** columns mapped to workflow statuses, drag-and-drop cards
  between columns (HTMX-persisted). Cards must resemble Jira's: issue key, type icon,
  priority icon, story points badge, assignee avatar, epic tag.
- **Ticket detail:** clicking a card opens a Jira-like detail (modal or side panel) with
  all fields, acceptance criteria, comments, and activity — editable in place via HTMX.
- **Timeline view:** sprints and epics laid out across time (a lightweight Gantt-style
  view: epics as bars spanning their issues' sprint dates, current sprint highlighted).
- Nice-to-have (scope it in the plan, cut if needed): burndown chart, basic search/filters.

### Confluence component (wiki)
- Spaces contain a **page tree with arbitrarily nested subpages**; sidebar tree navigation,
  breadcrumbs, drag to re-parent (or a simple "move" action).
- Rich page editor — pick and justify one approach in the plan (e.g. Markdown editor vs a
  CDN-loadable WYSIWYG like TipTap) given the Alpine/HTMX constraint.
- **Native draw.io integration:** embed the draw.io editor (embed.diagrams.net postMessage
  protocol), store the diagram XML with the page, render a preview in the page, and allow
  re-editing in place.
- **Mermaid support:** fenced ```mermaid blocks render as diagrams when viewing a page.
- Nice-to-have: page version history, page search.

### WhatsApp integration (mirror ClockInSop's architecture)
- **Node worker** (`whatsapp-node-worker/`): whatsapp-web.js with `LocalAuth` (session
  persisted to a gitignored `whatsapp_session/` directory — it contains auth tokens, it
  must never be committed), headless puppeteer Chrome, and an Express HTTP control API
  protected by a shared bearer token. Endpoints as in ClockInSop:
  `GET /health`, `GET /status` (includes pairing QR as base64), `POST /send`
  ({phone, message}), `POST /restart`, `POST /disconnect` (logout + fresh QR).
  Phone normalisation with a configurable `COUNTRY_CODE` (default 27, South Africa).
- **Django `whatsapp` app:** a thin stdlib-only HTTP client wrapping the worker API
  (like ClockInSop's `client.py`); a `WhatsAppMessage` queue model (phone, message, FK to
  user, message_type, PENDING/SENT/FAILED status, retry_count, error_message, sent_at);
  a background scheduler that flushes the pending queue in batches via the worker —
  callers `enqueue()` rather than send inline so web requests never block on WhatsApp.
- **Pairing & ops UI:** a connection dashboard (front end or unfold admin) showing worker
  status, the QR code for linking a device (HTMX polling until CONNECTED), restart/
  disconnect actions, the message queue with statuses, and a manual send for testing.
- **Notification triggers for AtlasHub** (each enqueues a message; decide the exact set
  in the plan): issue assigned to you, @mention in an issue or wiki comment, sprint
  started/completed, password reset code/link. Per-user notification preferences
  (opt-in/out per trigger) on the profile.
- **Config:** extend `.env` with `WHATSAPP_WORKER_URL`, `WHATSAPP_WORKER_TOKEN`,
  `COUNTRY_CODE` (Django side) and `WHATSAPP_WORKER_PORT`, `WHATSAPP_WORKER_TOKEN`,
  `WHATSAPP_SESSION_PATH`, optional `CHROME_PATH` (worker side). Document how to run the
  worker in dev (node alongside runserver) and ship a systemd unit like ClockInSop's
  `whatsapp-worker.service` for production. The system must degrade gracefully when the
  worker is down (queue accumulates, UI shows DISCONNECTED, email fallback for resets).

### Look and feel
- Visually close to current Jira/Confluence: Atlassian color palette (their blues,
  neutrals), typography, spacing, card and board styling, modals, sidebar patterns —
  recreated with Tailwind (define the palette as Tailwind theme tokens, don't inline
  hex values everywhere).

## What the plan must contain
1. Architecture overview and Django app breakdown, including the Django ↔ Node worker
   boundary and how both processes run in dev and prod.
2. Full data model (entities, fields, relationships — an ERD in mermaid is welcome),
   including how issue keys, sprint state, page trees, diagram storage, and the WhatsApp
   message queue work.
3. URL map and the HTMX interaction patterns (what's a full page, what's a partial,
   how drag-and-drop persists, how the QR pairing poll works).
4. Template/component structure and the Tailwind build setup.
5. Auth flow details — including the WhatsApp password-reset flow and its email fallback —
   and the permission/role model (front end + admin).
6. Decisions with trade-offs where I've left room (editor choice, one Space model vs two,
   timeline rendering approach, scheduler mechanism for the message queue).
7. Phased milestones, each ending in something runnable I can verify (e.g. Phase 1:
   venv + settings + custom auth + unfold admin; Phase 2: spaces + issues + backlog;
   Phase 3: sprints + board; Phase 4: ticket detail + timeline; Phase 5: wiki + draw.io
   + mermaid; Phase 6: WhatsApp worker + queue + notifications + WhatsApp password reset;
   Phase 7: polish/seed data).
8. Risks and open questions for me before you start.

## Build conventions (once approved)
- Seed a demo space with epics, stories (with acceptance criteria), a started sprint, and
  a few wiki pages so every view renders with realistic data; include a management command
  for it and instructions to create a superuser.
- Run migrations and the dev server at each phase boundary and verify the checkpoint
  before moving on. Commit at each phase boundary with a clear message.
- Ensure `whatsapp_session/`, `venv/`, and `node_modules/` are gitignored before the
  first commit that could touch them.
