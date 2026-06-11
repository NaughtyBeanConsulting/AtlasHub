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
| WhatsApp | Node ≥18 sidecar running whatsapp-web.js, controlled over HTTP |

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

## WhatsApp worker

```bash
cd whatsapp-node-worker
npm install
node index.js                   # reads the repo-root .env
```

Then visit **/whatsapp/link/** (staff user) and scan the QR with
WhatsApp → Settings → Linked devices. Messages queue in the DB and a
background scheduler flushes them every ~10 s; if the worker is down the
queue simply waits and password resets fall back to email.

- On macOS, if puppeteer's bundled Chromium fails to launch, point the worker
  at desktop Chrome: `CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" node index.js`
  (or set `CHROME_PATH` in `.env`).
- `whatsapp_session/` holds WhatsApp auth tokens. It is gitignored — never
  commit it.
- The control API binds to `127.0.0.1` and is protected by
  `WHATSAPP_WORKER_TOKEN` (set the same value for Django and the worker).

## Environment variables

All configuration lives in the repo-root `.env` (loaded with python-dotenv,
shared by Django and the worker). See [.env.example](.env.example) for the
full annotated list: `SECRET_KEY, DEBUG, ALLOWED_HOSTS, SITE_URL, DB_*`,
optional `EMAIL_*` (reset fallback), `WHATSAPP_WORKER_URL/TOKEN, COUNTRY_CODE`
(Django) and `WHATSAPP_WORKER_PORT/TOKEN, WHATSAPP_SESSION_PATH, CHROME_PATH`
(worker).

## Production notes

- `DEBUG=False` serves static files through whitenoise
  (`manage.py collectstatic` first); run Django under gunicorn.
- Install [atlashub-whatsapp-worker.service](atlashub-whatsapp-worker.service)
  (adjust paths) so systemd keeps the worker alive:
  `systemctl enable --now atlashub-whatsapp-worker`.
- The queue scheduler runs inside the web process and is safe under multiple
  gunicorn workers (`SELECT … FOR UPDATE SKIP LOCKED`).
- `SITE_URL` must be the public base URL — it is embedded in WhatsApp/email
  links.

## Project layout

```
app/        settings, root urls, wsgi/asgi
accounts/   custom User, auth flows, notification preferences
core/       Space + membership/roles, markdown pipeline, search, seed_demo
projects/   Atlas: issues, sprints, board, backlog, timeline, activity
wiki/       Hub: page tree, versions, draw.io diagrams, comments
whatsapp/   queue model, worker HTTP client, scheduler, ops UI
whatsapp-node-worker/   the only Node component (whatsapp-web.js sidecar)
```
