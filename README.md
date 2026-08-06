# NewsAgent

An automated news digest agent: fetches articles from admin-curated RSS sources, filters for
relevance per topic, summarizes and translates to Hebrew, and delivers a daily digest by email.

## MVP scope

- Email digest only, for 2 dogfood users (seeded, not self-registered)
- Admin source approval and user topic preferences via a small web UI
- Public signup and WhatsApp delivery are explicitly out of scope for MVP

## Architecture

- **Backend** — FastAPI + SQLAlchemy, SQLite for MVP
- **Frontend** — Vue, two surfaces: admin source approval and user preferences
- **Auth** — Google OAuth (admin email allowlist / matched seeded user email), no separate
  login/password system
- **Pipeline** — scheduled process (fetch → filter → summarize/translate → build digest → send),
  separate from the API and reading/writing the DB directly

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

# create the SQLite database (newsagent.db) from the migrations
alembic upgrade head
```

Configuration is read from environment variables (or a local `.env` file, not committed) with the
`NEWSAGENT_` prefix. Defaults work out of the box for local dev:

| Variable                      | Default                    | Purpose                                            |
| ----------------------------- | -------------------------- | -------------------------------------------------- |
| `NEWSAGENT_DATABASE_URL`      | `sqlite:///./newsagent.db` | SQLAlchemy database URL                            |
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
- The `/admin/*` and `/me/*` endpoints are stubs; real logic lands with the admin panel and
  preferences page issues.

### Frontend

From `frontend/` directory:

```bash
npm install         # one time, or after updating package.json
npm run dev         # start dev server
```

- Frontend: http://127.0.0.1:5173/
- The dev server proxies `/api/*` to http://localhost:8000 (the backend) by default.
- Two routes: `/admin` (source approval) and `/preferences` (topic subscriptions) — both currently
  call the backend stub endpoints.

Run both servers in separate terminals to test end-to-end. The digest pipeline is not built yet —
tracked as [open issues](https://github.com/MONS-Designers/news-agent/issues).

## Development

```bash
pytest          # run tests
mypy            # type-check src/newsagent
```

Backend, frontend, and pipeline are kept as separate layers, with the API as the only contract
between backend and frontend.

## Status

Early scaffolding — see open issues for current progress.
