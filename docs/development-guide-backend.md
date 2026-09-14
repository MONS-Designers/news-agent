# Development Guide - backend

**Date:** 2026-09-10
**Part:** `backend` (`src/newsagent`)

## Prerequisites

- Python 3.12 or newer
- A PostgreSQL database. The project uses Neon; any Postgres reachable by connection string
  works.

## Setup

From the repository root:

```bash
python -m venv .venv
```

Activate it. On Windows:

```bash
.venv\Scripts\activate
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies and the package in editable mode:

```bash
pip install -r requirements-dev.txt
```

```bash
pip install -e .
```

Point `NEWSAGENT_DATABASE_URL` at your database in a local `.env`, then create the schema:

```bash
alembic upgrade head
```

## Configuration

Every setting is read through `newsagent.config.Settings`, which uses the `NEWSAGENT_`
prefix and reads `.env`. **Never read `os.environ` directly.**

`NEWSAGENT_DATABASE_URL` has no usable default and must be set. The rest work out of the box
for local development.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEWSAGENT_DATABASE_URL` | none, required | SQLAlchemy URL, for example a Neon branch |
| `NEWSAGENT_LOG_LEVEL` | `WARNING` | Root log level |
| `NEWSAGENT_LLM_PROVIDER` | `mock` | `mock` or `external` |
| `NEWSAGENT_SUGGESTION_PROVIDER` | `popularity` | `popularity` or `llm` |
| `NEWSAGENT_EMAIL_SENDER` | `console` | `console` or `smtp` |
| `NEWSAGENT_EMAIL_OUTBOX_DIR` | empty | When set, the console sender also writes each email's HTML there |
| `NEWSAGENT_MAX_USERS` | `10` | Self-registration hard cap |
| `NEWSAGENT_DEV_AUTH_EMAIL` | empty | Local only. When set, registers `GET /auth/dev-login` |
| `NEWSAGENT_FRONTEND_URL` | `http://127.0.0.1:5173` | Where the API redirects after login |
| `NEWSAGENT_BACKEND_BASE_URL` | `http://127.0.0.1:8000` | Used to build the tracking pixel URL |
| `NEWSAGENT_SESSION_SECRET` | empty | Signs the session cookie; override for anything non-local |
| `NEWSAGENT_SESSION_COOKIE_DOMAIN` | empty | Host-only by default; set to a parent domain only for split-subdomain deploys |
| `NEWSAGENT_GOOGLE_CLIENT_ID` / `_SECRET` | empty | Google OAuth |

The two LLM endpoint families are read **without** the prefix: `EXTERNAL_LLM_BASE_URL`,
`EXTERNAL_LLM_AUTH_TOKEN` and `EXTERNAL_LLM_MODEL` for the article pipeline, and
`LOCAL_LLM_BASE_URL`, `LOCAL_LLM_AUTH_TOKEN` and `LOCAL_LLM_MODEL` for profile suggestions.
They are deliberately independent.

## Environment safety

Read this before running anything locally: a local run can send real email and spend real
money. The rules are in
[Project Context: Secrets and the environment](../_bmad-output/project-context.md#secrets-and-the-environment).

## Running locally

Start the API with reload:

```bash
uvicorn newsagent.api.main:app --reload
```

- Interactive API documentation: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

To sign in without Google, set `NEWSAGENT_DEV_AUTH_EMAIL` and visit `/auth/dev-login`. The
optional `?email=` parameter lets one environment move between several seeded accounts, an
admin, a fresh reader and a returning one, without editing configuration between them. The
API prints a warning on every boot while this is enabled.

Bootstrap the first accounts from the command line:

```bash
python -m newsagent.cli add-admin you@example.com
```

```bash
python -m newsagent.cli add-user you@example.com --name "Full Name"
```

## Common tasks

Run the tests:

```bash
pytest
```

Type-check the package:

```bash
mypy
```

Lint:

```bash
ruff check .
```

Create a migration after changing a model:

```bash
alembic revision --autogenerate -m "short description"
```

Then read the generated file before applying it. Column changes use `op.batch_alter_table`
even though production is Postgres; see [Project Context for AI Agents](../_bmad-output/project-context.md) before
simplifying it.

Capture a verbose pipeline run for debugging, in PowerShell:

```bash
$env:NEWSAGENT_LOG_LEVEL="DEBUG"; python -m newsagent.cli summarize
```

The same in bash:

```bash
NEWSAGENT_LOG_LEVEL=DEBUG python -m newsagent.cli summarize
```

## Where logs go

**Every log record becomes a `log_entries` row in the same database. There is no stderr,
stdout or file destination.** Each row carries the application version read from installed
package metadata, and, for records emitted during a `filter` or `summarize` run, the id of
that run's `outbound_runs` row.

`NEWSAGENT_LOG_LEVEL` is the single source of truth for verbosity and takes precedence over
uvicorn's own `--log-level`. The `--no-access-log` flag is still honored, because it says
"do not produce these records" rather than "how verbose". The default is `WARNING`, so a
deployment that wants uvicorn's startup and request lines must set `INFO`. The `httpx` and
`httpcore` loggers stay at `WARNING` so `DEBUG` shows application records rather than
transport traces.

A write failure inside the log handler falls back to `logging.Handler.handleError()`, which
prints to stderr, rather than raising into application code.

## Testing notes

`tests/conftest.py` declares two `autouse` fixtures: one resets `settings` to the `Settings`
class defaults, the other redirects telemetry and logging to in-memory SQLite. What they do not
cover, and the traps around threads and type checking, are in
[Project Context: Testing](../_bmad-output/project-context.md#testing).

## Conventions to respect

The conventions an agent must follow, including the comment policy, are kept in
[Project Context for AI Agents](../_bmad-output/project-context.md), the single source for them.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request. The backend job installs the
pinned requirements plus the editable package, then runs `ruff check .` followed by `pytest`.
A separate job type-checks and tests the frontend, and a third runs Playwright once both have
passed.

---

_Generated using BMAD Method `document-project` workflow_
