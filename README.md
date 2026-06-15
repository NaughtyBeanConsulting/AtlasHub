# AtlasHub

A self-hosted **Atlas + Hub clone** in one Django monolith: Scrum project
spaces (backlog → sprints → board → timeline) and wiki spaces (nested pages,
mermaid, native draw.io diagrams) sharing auth, navigation and an
Atlassian-style design language — plus a **WhatsApp Web sidecar** for
notifications and password resets.

| Stack | |
| --- | --- |
| Backend | Django 6 (Python ≥3.12), PostgreSQL (psycopg 3) |
| Frontend | Server-rendered templates + htmx + Alpine.js + Tailwind (standalone CLI — no Node in the CSS pipeline) |
| Admin | django-unfold |
| WhatsApp | Shared Node sidecar (whatsapp-web.js) — one worker under ClockInSop, used over HTTP |

## Features

- **Auth**: email-keyed custom user (no username anywhere), signup/login,
  profile with E.164-normalised phone, password reset **over WhatsApp** with
  email fallback, per-user notification preferences.
- **Atlas component**: spaces with short keys (CLIC-1, CLIC-2…), epics/stories/
  tasks/bugs/sub-tasks, acceptance-criteria checklists, backlog grouped by
  epic with drag-to-reorder and drag-into-sprint, sprint start/complete
  (rollover to backlog or next sprint), drag-and-drop board, inline-editable
  issue detail (side panel + `/browse/<KEY>`), comments with @mentions,
  activity history, CSS-grid timeline of epics × sprints.
- **Hub component**: arbitrarily nested page tree, markdown editor with
  toolbar + server-rendered preview, ```` ```mermaid ```` blocks, **draw.io**
  embedded editing (XML stored, SVG rendered inline), version history with
  restore, move with cycle guard, page comments.
- **WhatsApp**: queued (never inline) notifications for assignment, @mentions
  and sprint events; ops dashboard with QR pairing, restart/disconnect,
  manual send and live queue. Degrades gracefully when the worker is down.

## Quickstart (development)

```bash
git clone <repo> && cd AtlasHub
cp .env.example .env            # fill in SECRET_KEY + DB_* (Postgres must exist)
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./build_tailwind.sh             # downloads the Tailwind CLI once, builds CSS
./venv/bin/python manage.py migrate
./venv/bin/python manage.py createsuperuser   # email + password only
./venv/bin/python manage.py seed_demo         # optional demo data (see below)
./venv/bin/python manage.py runserver
```

Open http://127.0.0.1:8000 — `seed_demo` prints demo logins
(`demo@atlashub.local` / `atlashub-demo`); `--reset` recreates the demo data.
While editing templates run `./build_tailwind.sh --watch`.

## WhatsApp (shared worker)

AtlasHub does **not** run its own WhatsApp worker. It uses the single
`whatsapp-node-worker` that runs under **ClockInSop** (pm2) on the same host,
over a local token-authenticated HTTP API — one linked WhatsApp number shared by
every app on the box.

**What's independent vs shared:**

- **Independent** — AtlasHub's message **log and queue live in its own database**
  (`WhatsAppMessage`), flushed by its own scheduler. No other app can see
  AtlasHub's messages and vice-versa: the worker is send-only and stateless, so
  there's no cross-contamination of message history.
- **Shared** — the **connection status** and device pairing. Every app's status
  page reads the same `/status`, so they all reflect the one session. Pair the
  device (QR) **once, from ClockInSop**, and don't use "disconnect / clear
  session" from another app — it logs the shared number out for everyone.

Point `.env` at the worker (token must match what it was started with):

```
WHATSAPP_WORKER_URL=http://127.0.0.1:8025
WHATSAPP_WORKER_TOKEN=<same token the ClockInSop worker uses>
```

The worker binds `127.0.0.1`, so AtlasHub must run on the same server. Messages
queue in AtlasHub's DB and flush every ~10 s; if the worker is down the queue
waits and password resets fall back to email.

## Environment variables

All configuration lives in the repo-root `.env` (loaded with python-dotenv).
See [.env.example](.env.example) for the full annotated list: `SECRET_KEY,
DEBUG, ALLOWED_HOSTS, SITE_URL, DB_*`, optional `EMAIL_*` (reset fallback), and
`WHATSAPP_WORKER_URL/TOKEN, COUNTRY_CODE` — the WhatsApp vars just point at the
shared ClockInSop worker.

## Production notes

- Deploy order: `./build_tailwind.sh` (compiles `static/css/tailwind.css`) →
  `manage.py collectstatic` → run under gunicorn.
- With `DEBUG=False`, whitenoise serves static through
  `CompressedManifestStaticFilesStorage` — hashed filenames + pre-compressed
  `.gz` siblings, far-future cacheable. All JS/CSS is self-hosted (no CDN).
- Set `SITE_URL=https://your-host` to auto-enable the HTTPS hardening
  (SSL redirect, HSTS, secure session/CSRF cookies). `manage.py check --deploy`
  should then report no issues. Tunables: `SECURE_SSL_REDIRECT`,
  `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`,
  `LOG_LEVEL`, `DB_CONN_MAX_AGE` (see `.env.example`).
- WhatsApp is handled by the shared worker under ClockInSop (managed by pm2);
  AtlasHub runs no worker of its own — just set `WHATSAPP_WORKER_URL` and a
  matching `WHATSAPP_WORKER_TOKEN`, on the same host as the worker.
- The queue scheduler runs inside the web process and is safe under multiple
  gunicorn workers — rows are claimed with `select_for_update(skip_locked=True)`,
  so each message is sent exactly once.
- `SITE_URL` must be the public base URL — it is embedded in WhatsApp/email
  links.

## Project layout

```
app/        settings, root urls, wsgi/asgi
accounts/   custom User, auth flows, notification preferences
core/       Space + membership/roles, markdown pipeline, search, seed_demo
projects/   Atlas: issues, sprints, board, backlog, timeline, activity
wiki/       Hub: page tree, versions, draw.io diagrams, comments
whatsapp/   queue model, scheduler, ops UI, HTTP client → shared ClockInSop worker
```
