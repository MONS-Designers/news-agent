# NewsAgent

An automated news digest agent: fetches articles from admin-curated RSS sources, filters for
relevance per topic, summarizes and translates to Hebrew, and delivers a weekly digest by email.

## MVP scope

- Weekly email digest only, for 2 dogfood users (seeded, not self-registered)
- Admin source approval and user topic preferences via a small web UI
- Public signup and WhatsApp delivery are explicitly out of scope for MVP

## Architecture

- **Backend** — FastAPI + SQLAlchemy, Postgres (Neon)
- **Frontend** — Vue, three surfaces: admin source approval, admin taxonomy queue, and the user
  profile picker + topic preferences
- **Auth** — Google OAuth (admin email allowlist / matched seeded user email), no separate
  login/password system
- **Pipeline** — scheduled process (fetch → filter → summarize/translate → build digest → send),
  separate from the API and reading/writing the DB directly

### Schedule (decided 2026-08-07)

The digest is **weekly**, but the pipeline is not: the collection stages run daily so nothing
scrolls off an RSS feed unseen, and only the last two stages run weekly.

| Stage(s)                             | Cadence | Why                                                       |
| ------------------------------------ | ------- | --------------------------------------------------------- |
| `fetch`, `filter`, `summarize`       | daily   | RSS feeds hold only the latest ~20–50 items and roll the rest off |
| `build-digests`, `send-digests`      | weekly  | one email per user per week                               |

That means two scheduled jobs, not one — see `news-agent-infra` for the cron definitions.
Ranking is tuned to match: `digest_max_articles=7` and `recency_half_life_hours=84` (half a
week), so an article from Monday still competes with one from Sunday.

## Getting started

Requires Python 3.12+.

```bash
# create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# install dependencies + the package in editable mode
pip install -r requirements-dev.txt
pip install -e .

# point NEWSAGENT_DATABASE_URL (in .env) at your Postgres DB, then create the schema
alembic upgrade head
```

Configuration is read from environment variables (or a local `.env` file, not committed) with the
`NEWSAGENT_` prefix. `NEWSAGENT_DATABASE_URL` has no usable default and must be set; the rest work
out of the box for local dev:

| Variable                      | Default                    | Purpose                                            |
| ----------------------------- | -------------------------- | -------------------------------------------------- |
| `NEWSAGENT_DATABASE_URL`      | _(none — required)_        | SQLAlchemy database URL (Postgres, e.g. a Neon branch) |
| `NEWSAGENT_LOG_DESTINATION`   | `stderr`                   | Where log records go: `stderr`, `stdout`, or `file` |
| `NEWSAGENT_LOG_LEVEL`         | `WARNING`                  | Root log level (`DEBUG`, `INFO`, `WARNING`, ...)   |
| `NEWSAGENT_LOG_FILE`          | _(unset)_                  | Log file path — required when destination is `file` |

Logging is wired at every entrypoint — the CLI, the API process, and `newsagent.llm.demo` — so
the same settings apply however you run it. With `file`, the parent directory is created if
missing, and the API's own uvicorn startup/error/access lines are captured alongside
`newsagent.*` records. `httpx`/`httpcore` stay at WARNING so `DEBUG` shows application records
rather than transport traces.

`NEWSAGENT_LOG_LEVEL` is the single source of truth for verbosity and takes precedence over
uvicorn's own `--log-level`. `--no-access-log` is still honored — it says "don't produce these
records", not "how verbose". Note the default level is `WARNING`, so a deployment that wants
uvicorn's startup and request lines must set `NEWSAGENT_LOG_LEVEL=INFO`.

To capture a pipeline run for debugging (PowerShell):

```powershell
$env:NEWSAGENT_LOG_DESTINATION="file"; $env:NEWSAGENT_LOG_FILE="./logs/newsagent.log"; $env:NEWSAGENT_LOG_LEVEL="DEBUG"; python -m newsagent.cli summarize
```

The equivalent in bash:

```bash
NEWSAGENT_LOG_DESTINATION=file NEWSAGENT_LOG_FILE=./logs/newsagent.log NEWSAGENT_LOG_LEVEL=DEBUG python -m newsagent.cli summarize
```

## Running locally

### Backend API

From the project root (with Python venv active):

```bash
uvicorn newsagent.api.main:app --reload
```

- Interactive API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- `/auth/*` (Google OAuth), `/admin/*` (source approval + taxonomy queue), `/me/*` (profile and
  topic preferences) and `/t/*` (digest open tracking) are all implemented.

### Frontend

From `frontend/` directory:

```bash
npm install         # one time, or after updating package.json
npm run dev         # start dev server
```

- Frontend: http://127.0.0.1:5173/
- The dev server proxies `/api/*` to http://localhost:8000 (the backend) by default.
- Four routes: `/` (landing page), `/admin` (source approval), `/admin/taxonomy` (pending
  Field/Role curation queue) and `/preferences` (guided profile picker + topic subscriptions).

Run both servers in separate terminals to test end-to-end.

### Pipeline

The pipeline stages are built and run from the CLI, independently of the API:

```bash
python -m newsagent.cli fetch          # pull new articles from approved RSS sources
python -m newsagent.cli filter         # score each article's relevance to its topic
python -m newsagent.cli summarize      # summarize + translate to Hebrew
python -m newsagent.cli build-digests  # rank and select each user's articles
python -m newsagent.cli send-digests   # render and send
```

The first three run daily and the last two weekly — see [Schedule](#schedule-decided-2026-08-07).
`newsagent.cli --help` lists the seeding and user-management commands too. Remaining gaps are
tracked as [open issues](https://github.com/MONS-Designers/news-agent/issues) — most notably
there is no real email sender yet (`NEWSAGENT_EMAIL_SENDER` only accepts `console`).

## Development

```bash
pytest          # run tests
mypy            # type-check src/newsagent
```

Backend, frontend, and pipeline are kept as separate layers, with the API as the only contract
between backend and frontend.

## Status

All product logic is built — the full pipeline, both admin surfaces, and the user profile picker.
What stands between here and a live MVP is delivery and operations, not features:

- **No real email sender.** `newsagent.mail` only ships the `console` adapter, so no digest can
  actually be delivered. The `EmailSender` interface is in place; a real adapter is one class.
- **No scheduler, hosting target, or secrets management** — tracked in `news-agent-infra`
  (issues [#15](https://github.com/MONS-Designers/news-agent/issues/15),
  [#17](https://github.com/MONS-Designers/news-agent/issues/17),
  [#18](https://github.com/MONS-Designers/news-agent/issues/18)).
- **Never run end to end** against real users
  ([#23](https://github.com/MONS-Designers/news-agent/issues/23)).

See open issues for the rest.
