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

| Variable                 | Default                    | Purpose                 |
| ------------------------ | -------------------------- | ----------------------- |
| `NEWSAGENT_DATABASE_URL` | `sqlite:///./newsagent.db` | SQLAlchemy database URL |

There is no runnable app yet — the API server, frontend, and pipeline are tracked as
[open issues](https://github.com/MONS-Designers/news-agent/issues).

## Development

```bash
pytest          # run tests
mypy            # type-check src/newsagent
```

Backend, frontend, and pipeline are kept as separate layers, with the API as the only contract
between backend and frontend.

## Status

Early scaffolding — see open issues for current progress.
