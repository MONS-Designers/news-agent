# NewsAgent

An automated news digest agent: fetches articles from admin-curated RSS sources, filters for
relevance per topic, summarizes and translates to Hebrew, and delivers a weekly digest by email.

## Scope (updated 2026-08-07 launch-readiness decision)

- Weekly email digest, delivered via a real email provider (SMTP)
- Self-registration via Google OAuth, hard-capped at a configurable max (10 at launch);
  overflow visitors are captured to a waitlist
- Admin curates RSS sources and the Field/Role taxonomy; users set preferences via a guided
  profile picker (Field/Role/Experience/Interests -> suggested Topics) or the classic Topic grid
- WhatsApp delivery is explicitly out of scope for this stage

## Architecture

- **Backend** - FastAPI + SQLAlchemy, Postgres (Neon)
- **Frontend** - Vue, three surfaces: admin source approval, admin taxonomy queue, and the user
  profile picker + topic preferences
- **Auth** - Google OAuth (admin email allowlist / matched seeded user email), no separate
  login/password system
- **Pipeline** - scheduled process (fetch → filter → extract → summarize/translate → build
  digest → send), separate from the API and reading/writing the DB directly

### Schedule (decided 2026-08-07)

The digest is **weekly**, but the pipeline is not: the collection stages run daily so nothing
scrolls off an RSS feed unseen, and only the last two stages run weekly.

| Stage(s)                             | Cadence | Why                                                       |
| ------------------------------------ | ------- | --------------------------------------------------------- |
| `fetch`, `filter`, `extract`, `summarize` | daily | RSS feeds hold only the latest ~20–50 items and roll the rest off |
| `build-digests`, `send-digests`      | weekly  | one email per user per week                               |

That means two scheduled jobs, not one - see `news-agent-infra` for the cron definitions.
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
| `NEWSAGENT_DATABASE_URL`      | _(none - required)_        | SQLAlchemy database URL (Postgres, e.g. a Neon branch) |
| `NEWSAGENT_LOG_LEVEL`         | `WARNING`                  | Root log level (`DEBUG`, `INFO`, `WARNING`, ...)   |

Every log record is written to the `log_entries` table in the same database - there is no
stderr/stdout/file destination choice. Each row carries the app version (read from installed
package metadata) and, for records emitted during a `filter`/`summarize` CLI run, the id of that
run's `pipeline_runs` row. Logging is wired at every entrypoint - the CLI, the API process, and
`newsagent.llm.demo` - so the same `NEWSAGENT_LOG_LEVEL` applies however you run it. The API's
own uvicorn startup/error/access lines are captured alongside `newsagent.*` records. `httpx`/
`httpcore` stay at WARNING so `DEBUG` shows application records rather than transport traces.

`NEWSAGENT_LOG_LEVEL` is the single source of truth for verbosity and takes precedence over
uvicorn's own `--log-level`. `--no-access-log` is still honored - it says "don't produce these
records", not "how verbose". Note the default level is `WARNING`, so a deployment that wants
uvicorn's startup and request lines must set `NEWSAGENT_LOG_LEVEL=INFO`.

To capture a pipeline run for debugging (PowerShell):

```powershell
$env:NEWSAGENT_LOG_LEVEL="DEBUG"; python -m newsagent.cli summarize
```

The equivalent in bash:

```bash
NEWSAGENT_LOG_LEVEL=DEBUG python -m newsagent.cli summarize
```

A DB write failure inside the log handler itself does not crash the app or raise into
application code - it falls back to `logging.Handler`'s default `handleError()` (prints to
stderr), since there is no other destination left to fall back to.

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
python -m newsagent.cli extract        # fetch + extract full article text (relevant articles only)
python -m newsagent.cli summarize      # summarize + translate to Hebrew
python -m newsagent.cli build-digests  # rank and select each user's articles
python -m newsagent.cli send-digests   # render and send
```

The first four run daily and the last two weekly - see [Schedule](#schedule-decided-2026-08-07).
`newsagent.cli --help` lists the seeding, user-management, and `usage-report` commands too.
See [Status](#status) for the current gap list.

## Development

```bash
pytest          # run tests
mypy            # type-check src/newsagent
```

Backend, frontend, and pipeline are kept as separate layers, with the API as the only contract
between backend and frontend.

## Status

The self-registration -> profile -> weekly-digest loop is built and shippable end to end,
including real SMTP delivery, full-text extraction, click/open tracking, and per-run LLM usage
accounting (the 2026-08-07 launch-readiness epics - see
`_bmad-output/planning-artifacts/epics-launch-readiness.md`). Known remaining gaps:

- **Never run end to end** against real users
  ([#23](https://github.com/MONS-Designers/news-agent/issues/23)).
- **Silent empty digest** if a user subscribes to a Topic with zero admin-approved Sources
  ([#48](https://github.com/MONS-Designers/news-agent/issues/48)).
- **Accessibility remediation incomplete** on the profile picker, despite being scoped as a
  baseline requirement ([#31](https://github.com/MONS-Designers/news-agent/issues/31)).
- **No scheduler, hosting target, or secrets management** - tracked in `news-agent-infra`
  (issues [#15](https://github.com/MONS-Designers/news-agent/issues/15),
  [#17](https://github.com/MONS-Designers/news-agent/issues/17),
  [#18](https://github.com/MONS-Designers/news-agent/issues/18)).
- Minor polish: digest email font/positioning
  ([#50](https://github.com/MONS-Designers/news-agent/issues/50)), missing lead-image fallback
  ([#49](https://github.com/MONS-Designers/news-agent/issues/49)), and test-coverage gaps
  ([#42](https://github.com/MONS-Designers/news-agent/issues/42),
  [#43](https://github.com/MONS-Designers/news-agent/issues/43)).

See open issues for the rest.
