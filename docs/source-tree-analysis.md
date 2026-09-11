# news-agent - Source Tree Analysis

**Date:** 2026-09-10

## Overview

One repository, three parts that ship and run independently: a FastAPI backend, a Vue
single-page app, and an operator command-line interface that also drives the content
pipeline. Backend and CLI share the same installed Python package, `newsagent`, under
`src/`; the frontend is a self-contained npm project under `frontend/`.

The separation is enforced by import direction rather than by folders alone. The
`services/` layer holds domain logic with no FastAPI imports, so both the CLI and the API
call the same functions. The API layer adds routing, schemas and guards on top. The
frontend knows nothing about the backend beyond the JSON contract.

## Multi-Part Structure

- **backend** (`src/newsagent`): the HTTP API, the domain services, the data models and
  the LLM, mail and suggestion adapters.
- **web** (`frontend`): the Vue 3 single-page app, three admin and reader surfaces.
- **cli** (`src/newsagent/cli.py`, `src/newsagent/pipeline`, `src/newsagent/scheduler.py`):
  operator commands and the six pipeline stages, run as processes separate from the API.

## Complete Directory Structure

```text
news-agent/
├── src/
│   └── newsagent/                      # The installed Python package (editable, pip install -e .)
│       ├── api/                        # PART: backend. FastAPI layer only.
│       │   ├── main.py                 # ENTRY POINT. create_app(), middleware, health routes
│       │   ├── auth.py                 # Identity dataclass, session read/write, route guards
│       │   ├── deps.py                 # get_db() request-scoped session dependency
│       │   ├── routers/                # One module per URL prefix
│       │   │   ├── auth.py             # /auth - Google OAuth, dev-login, logout
│       │   │   ├── admin.py            # /admin/sources - source approval
│       │   │   ├── admin_taxonomy.py   # /admin/taxonomy - Field/Role curation queue
│       │   │   ├── admin_engagement.py # /admin/engagement - opens and clicks report
│       │   │   ├── me.py               # /me - profile, preferences, feedback, suggestions
│       │   │   └── tracking.py         # /t and /c - public pixel and click redirect
│       │   └── schemas/                # Pydantic request/response models, one per concern
│       ├── models/                     # SQLAlchemy 2.0 declarative models, one per table
│       ├── services/                   # DOMAIN LAYER. No FastAPI imports - shared by API and CLI
│       │   ├── identity.py             # Admin/User creation, the capacity-gated cap
│       │   ├── profile.py              # Profile save transaction + async suggestion task
│       │   ├── taxonomy.py             # Field/Role lookup, seeding, the "Other" review queue
│       │   ├── preferences.py          # Topic subscriptions
│       │   ├── sources.py              # Topics and sources, plus the curated default list
│       │   ├── cadence.py              # Turns a reader's frequency into "due today?"
│       │   ├── scheduler_lease.py      # One conditional UPDATE = mutual exclusion
│       │   ├── engagement.py           # The admin engagement report
│       │   ├── feedback.py             # One write path for all three feedback entry points
│       │   ├── subscription.py         # Delivery opt-out
│       │   ├── waitlist.py             # Capacity-full capture
│       │   ├── telemetry.py            # SOLE WRITER for OutboundRun/OutboundCall
│       │   ├── log_entries.py          # The only module that turns a log record into a row
│       │   └── device_detection.py     # User-Agent to mobile/tablet/desktop/bot/unknown
│       ├── pipeline/                   # PART: cli. The six stages, in dependency order.
│       │   ├── fetcher.py              # 1. Poll approved RSS sources, dedupe by URL
│       │   ├── relevance.py            # 2. Score each article against its topic
│       │   ├── extract.py              # 3. Fetch the page, pull the article body
│       │   ├── summarize.py            # 4. Summarize + translate to Hebrew
│       │   ├── ranking.py              #    Scoring and top-N selection, used by digest.py
│       │   ├── digest.py               # 5. Build each reader's digest
│       │   ├── render.py               #    Hebrew RTL email HTML from a built digest
│       │   └── send.py                 # 6. Render and deliver, mark sent_at
│       ├── llm/                        # Swappable LLM adapters behind LLMProvider
│       │   ├── base.py                 # ABC, template-method retry policy
│       │   ├── factory.py              # NEWSAGENT_LLM_PROVIDER -> class
│       │   ├── types.py                # ArticleInput, RelevanceScore, SummaryResult, ...
│       │   ├── external.py             # The real HTTP provider
│       │   ├── mock.py, demo.py        # Local development stand-ins
│       │   └── errors.py
│       ├── suggestions/                # Sibling adapter family for profile suggestions
│       │   ├── base.py, factory.py, types.py, errors.py
│       │   ├── popularity.py           # Default - no LLM call
│       │   └── llm.py                  # Uses the separately configured local LLM
│       ├── mail/                       # Swappable email adapters behind EmailSender
│       │   ├── base.py, factory.py
│       │   ├── console.py              # Prints, optionally writes HTML to an outbox dir
│       │   └── smtp.py                 # Real delivery, no vendor SDK
│       ├── telemetry/                  # Measure and attribute; never writes to the DB itself
│       │   ├── context.py              # Two contextvars: open_run() and attribute_call()
│       │   ├── sink.py                 # Joins measurement + attribution, calls the writer
│       │   ├── pricing.py              # lookup_rate() and refresh_from_openrouter()
│       │   └── types.py                # CallMeasurement, CallAttribution
│       ├── templates/
│       │   ├── digest.html.j2          # The Hebrew RTL email template
│       │   └── assets/logo-mark.b64    # Inlined logo, base64
│       ├── cli.py                      # ENTRY POINT. argparse operator CLI, 15 subcommands
│       ├── scheduler.py                # ENTRY POINT. The long-lived delivery loop
│       ├── config.py                   # Settings - the ONLY way config is read
│       ├── db.py                       # engine + SessionLocal, built at import time
│       ├── logging_setup.py            # Wires the DB-backed log handler
│       ├── branding.py                 # Product name, logo data URI, digest noun
│       ├── http_llm_client.py          # Shared HTTP transport for both LLM adapter families
│       └── llm_json.py                 # Tolerant JSON parsing of model output
│
├── frontend/                           # PART: web. Self-contained npm project.
│   ├── src/
│   │   ├── main.ts                     # ENTRY POINT. createApp, router, style.css
│   │   ├── App.vue                     # Shell: header, nav, FeedbackWidget gate
│   │   ├── router/index.ts             # 5 routes + the requiresAdmin/requiresAuth guard
│   │   ├── api/client.ts               # THE ONLY module that talks to the backend
│   │   ├── auth.ts                     # Shared `me` ref - single owner of "who is signed in"
│   │   ├── profile-draft.ts            # Draft persistence for the picker wizard
│   │   ├── branding.ts
│   │   ├── style.css                   # Tailwind v4 @theme tokens - the design system
│   │   ├── views/                      # One per route
│   │   │   ├── HomeView.vue            # Landing + first-run state + profile picker host
│   │   │   ├── PreferencesView.vue     # Profile picker + topic grid
│   │   │   ├── AdminView.vue           # Source approval
│   │   │   ├── TaxonomyQueueView.vue   # Field/Role curation queue
│   │   │   └── EngagementView.vue      # Opens and clicks report
│   │   ├── components/
│   │   │   ├── profile-picker/         # The three-step guided wizard
│   │   │   ├── FeedbackWidget.vue
│   │   │   ├── HybridDepthBackground.vue
│   │   │   └── HybridSpinner.vue
│   │   ├── assets/                     # logo-mark.svg, google-g.svg, google-wordmark.svg
│   │   └── __tests__/                  # Vitest specs, colocated per folder
│   ├── e2e/                            # Playwright specs + global-setup + fixtures
│   ├── vite.config.ts                  # Vite + vitest + the /api dev proxy
│   ├── playwright.config.ts
│   └── package.json
│
├── alembic/
│   ├── env.py
│   └── versions/                       # 33 revisions, one linear chain
├── tests/                              # 64 pytest modules, mirroring src/newsagent
│   ├── conftest.py                     # TWO autouse fixtures - read this before writing a test
│   ├── api/routers/, llm/, mail/, models/, pipeline/, services/, suggestions/, telemetry/
│   └── test_cli.py, test_scheduler.py, test_config.py, ...
├── scripts/e2e_setup.py                # Seeds the isolated Playwright backend
├── docs/                               # This documentation set
├── _bmad-output/                       # BMad planning and implementation artifacts
│   ├── project-context.md              # Stack rules and DB-safety rules for AI agents
│   ├── planning-artifacts/             # Epics, PRDs, architecture, UX designs
│   ├── implementation-artifacts/       # Per-story specs and deferred-work.md
│   └── specs/, brainstorming/
├── .github/workflows/
│   ├── ci.yml                          # lint + pytest, type-check + vitest, then Playwright
│   └── trigger-deploy.yml              # repository_dispatch into news-agent-infra
├── Dockerfile.backend                  # Two stages; ships the API and the scheduler
├── Dockerfile.frontend                 # Two stages; ships nginx + dist
├── nginx.frontend.conf.template        # SPA fallback + runtime /api reverse proxy
├── pyproject.toml                      # setuptools, mypy, ruff, pytest config
├── requirements.txt                    # Exact pins
├── requirements-dev.txt
├── alembic.ini
├── README.md
└── CLAUDE.md                           # Cross-repo context and locked product decisions
```

## Critical Directories

### `src/newsagent/api/`

**Purpose:** the HTTP layer, and nothing else. Routing, request and response schemas,
session handling, route guards.

**Contains:** `main.py` (the app factory), `auth.py` (identity and guards), `deps.py` (the
session dependency), plus `routers/` and `schemas/`.

**Entry point:** `newsagent.api.main:app`, served by uvicorn.

**Integration:** the only part of the backend the frontend can reach. Everything below it
is reachable from the CLI too.

### `src/newsagent/services/`

**Purpose:** the domain layer. Kept free of FastAPI imports on purpose, so the CLI and any
future API endpoint reuse the same logic.

**Contains:** fifteen modules, each owning one concern. `telemetry.py` and `log_entries.py`
are singled out in their own docstrings as the *sole* writers for their tables, so a future
change to storage shape has one call site to change.

### `src/newsagent/pipeline/`

**Purpose:** the six content stages. Each is a plain function taking a `Session` and
returning a report dataclass. None of them import from `api/`.

**Entry points:** invoked from `cli.py` subcommands, and the last two also from
`scheduler.py`.

**Integration:** reads and writes the same database the API does, in a separate process.

### `src/newsagent/models/`

**Purpose:** one module per table, all inheriting `Base` from `base.py`. Re-exported
through `__init__.py`, which is what the rest of the codebase imports from.

### `frontend/src/api/client.ts`

**Purpose:** the single module that knows the backend exists. Every view and component
imports its typed functions rather than calling `fetch` directly.

**Integration:** this file is the whole client side of the API contract. Its
`API_BASE` resolution is the piece most easily broken by a deployment change; see
`integration-architecture.md`.

### `frontend/src/components/profile-picker/`

**Purpose:** the three-step guided wizard that turns Field, Role, Experience and Interests
into suggested Topics. The largest cluster of UI logic in the app.

### `tests/`

**Purpose:** 64 pytest modules mirroring the package layout.

**Trap:** `conftest.py` declares two `autouse` fixtures that reset `settings` to the code
defaults and redirect telemetry and logging to in-memory SQLite. A new test that touches
the database must bring its own in-memory engine. Do not assume the autouse fixtures cover
you.

## Part-Specific Trees

### backend

```text
src/newsagent/
├── api/         routers/, schemas/, main.py, auth.py, deps.py
├── models/      20 table modules + base.py
├── services/    15 domain modules
├── llm/         base, factory, types, errors, external, mock, demo
├── suggestions/ base, factory, types, errors, popularity, llm
├── mail/        base, factory, console, smtp
├── telemetry/   context, sink, pricing, types
├── config.py, db.py, logging_setup.py, branding.py
└── http_llm_client.py, llm_json.py
```

### web

```text
frontend/
├── src/
│   ├── main.ts, App.vue, style.css
│   ├── router/, api/, assets/
│   ├── auth.ts, branding.ts, profile-draft.ts
│   ├── views/       5 route components
│   └── components/  3 shared + profile-picker/ (5 components)
├── e2e/             3 Playwright specs + fixtures + global-setup
└── vite.config.ts, playwright.config.ts, tsconfig.json
```

### cli

```text
src/newsagent/
├── cli.py           argparse, 15 subcommands, one SessionLocal for the whole run
├── scheduler.py     the long-lived delivery loop
└── pipeline/        fetcher, relevance, extract, summarize, ranking, digest, render, send
```

## Integration Points

### web to backend

- **Location:** `frontend/src/api/client.ts`
- **Type:** REST over JSON, with a signed session cookie
- **Details:** every request goes through one private `request<T>()` helper, prefixed with
  `API_BASE`, which resolves to `import.meta.env.VITE_API_BASE` and falls back to the
  relative path `/api`. In development, Vite's proxy rewrites that to the backend. In
  production, nginx does the same at runtime.

### cli to backend domain

- **Location:** `src/newsagent/cli.py` imports
- **Type:** direct in-process function calls
- **Details:** the CLI opens one `SessionLocal()` for the whole run and calls
  `services.*` and `pipeline.*` functions directly. It never issues an HTTP request to the
  API. Both processes talk to the same database.

### scheduler to pipeline

- **Location:** `src/newsagent/scheduler.py`
- **Type:** direct in-process function calls, on a loop
- **Details:** each tick runs two passes, unwelcomed readers and cadence-due readers. Both
  are bounded by a query that usually returns nobody, so an idle tick costs two selects and
  no LLM call.

## Entry Points

### backend

- **Entry point:** `newsagent.api.main:app`
- **Bootstrap:** `create_app()` configures logging, warns loudly if development login is
  enabled, installs `SessionMiddleware` then `CORSMiddleware`, includes the six routers,
  and registers the two health routes. The module-level `app = create_app()` means import
  alone builds the application.

### web

- **Entry point:** `frontend/src/main.ts`
- **Bootstrap:** imports `style.css`, creates the app from `App.vue`, installs the router,
  mounts to `#app` in `index.html`.

### cli

- **Entry points:** `python -m newsagent.cli <command>` and `python -m newsagent.scheduler`
- **Bootstrap:** `cli.main()` configures logging, builds the argparse tree, opens one
  session, and dispatches on `args.command`. The scheduler installs signal handlers so a
  container stop ends the loop cleanly.

## File Organization Patterns

- **One concern per module.** Models, services, routers and schemas are all split one file
  per table, domain, prefix or concern, rather than grouped into large modules.
- **Adapters are a family of four files.** `base.py` holds the abstract contract,
  `factory.py` maps a config string to a class, `types.py` holds the frozen dataclasses that
  cross the boundary, and `errors.py` holds the typed error. `llm/`, `suggestions/` and
  `mail/` all follow it. `llm/` and `suggestions/` deliberately do not import each other.
- **Stages return report dataclasses.** Every pipeline stage returns a small frozen-ish
  dataclass of counters, which the CLI prints and the scheduler aggregates.
- **Tests mirror the package.** `tests/services/test_x.py` covers `services/x.py`.
- **Frontend tests are colocated.** Each folder has its own `__tests__/` subfolder.

## Key File Types

### SQLAlchemy models

- **Pattern:** `src/newsagent/models/*.py`
- **Purpose:** one declarative class per table, re-exported from `__init__.py`
- **Examples:** `article.py`, `digest_link.py`, `outbound_call.py`

### Domain services

- **Pattern:** `src/newsagent/services/*.py`
- **Purpose:** business logic callable from both the API and the CLI
- **Examples:** `profile.py` (503 lines, the largest), `taxonomy.py` (467 lines)

### Pipeline stages

- **Pattern:** `src/newsagent/pipeline/*.py`
- **Purpose:** one stage per module, each a function over a `Session`
- **Examples:** `fetcher.py`, `summarize.py`, `send.py`

### Vue single-file components

- **Pattern:** `frontend/src/**/*.vue`
- **Purpose:** `<script setup lang="ts">` composition API, Tailwind utility classes
- **Examples:** `HomeView.vue` (503 lines), `AboutYouStep.vue` (332 lines)

### Alembic revisions

- **Pattern:** `alembic/versions/<hash>_<slug>.py`
- **Purpose:** one linear chain of 33 schema changes
- **Examples:** `7de791f6b76c_initial_schema.py`, `b7e4a1c9d3f2_user_given_family_name.py`

## Asset Locations

- **Frontend SVG**: `frontend/src/assets/` - the logo mark and the two Google sign-in marks.
- **Email assets**: `src/newsagent/templates/assets/logo-mark.b64` - base64, inlined into the
  digest so the email needs no external image host.
- **Documentation images**: `docs/assets/v1-fixes/`.
- No large binary asset directories exist; `frontend/public/` and `frontend/dist/` are build
  concerns, and `build/` is a stale setuptools artifact directory.

## Configuration Files

- **`pyproject.toml`**: setuptools packaging, plus the mypy, ruff and pytest configuration.
  The ruff `select` list is pinned deliberately and must not be widened.
- **`requirements.txt` / `requirements-dev.txt`**: exact backend pins.
- **`alembic.ini`**: migration configuration.
- **`frontend/package.json`**: caret-ranged frontend dependencies and the npm scripts.
- **`frontend/vite.config.ts`**: Vite plugins, the `@` alias, the dev-server `/api` proxy,
  and the vitest block that excludes `e2e/`.
- **`frontend/tsconfig.json`**: strict mode with `noUnusedLocals` and `noUnusedParameters`.
- **`nginx.frontend.conf.template`**: substituted at container start from `BACKEND_HOST`.
- **`.env`** and **`.env.prod`**: both gitignored, both dangerous. See the development guide.

## Notes for Development

- **Backend pins are exact, frontend pins use caret ranges.** That inconsistency is a known
  fact, not a task. Do not align it as a side effect of another change.
- **`db.py` builds the engine at import time** from `settings.database_url`. Any code that
  opens its own `SessionLocal()` talks to whatever `.env` resolved to.
- **Config is read only through `newsagent.config.Settings`.** Never `os.environ` directly.
- **The frontend reaches the backend only through the relative `/api` prefix.** Baking an
  absolute backend hostname anywhere freezes one environment into the image, and has already
  broken OAuth login once after a deploy.
- **`build/`, `frontend/dist/`, `frontend/test-results/`, `newsagent.db` and the various
  cache directories** are generated. `marketing/` is currently empty.

---

_Generated using BMAD Method `document-project` workflow_
