# Architecture - backend

**Date:** 2026-09-10
**Part:** `backend`
**Root:** `src/newsagent`
**Project type:** backend service
**Architecture pattern:** layered service, with swappable adapters at every external edge

## Executive Summary

A FastAPI application serving 23 endpoints across six routers, backed by PostgreSQL through
SQLAlchemy 2.0. Its job is narrow: authenticate a reader through Google, let admins curate
sources and taxonomy, let readers set a profile and topic preferences, and record digest
opens and clicks. It does not fetch, summarize or send anything. That work lives in the CLI
and scheduler processes, which share this part's domain layer and database but run
separately.

Three architectural commitments shape the code:

1. **The domain layer imports no web framework.** `services/` is callable from an HTTP
   handler and from a cron job identically.
2. **Every external dependency sits behind an abstract adapter** selected by one
   configuration string. The LLM provider, the suggestion source and the email sender all
   follow the same four-file shape.
3. **Configuration is read in exactly one place.** `newsagent.config.Settings` is the only
   reader of the environment; `os.environ` is never touched directly.

## Technology Stack

| Category | Technology | Version | Justification |
| --- | --- | --- | --- |
| Language | Python | >= 3.12 | Modern typing syntax used throughout |
| Web framework | FastAPI | 0.139.2 | Pydantic-native request and response validation, generated OpenAPI |
| ASGI server | uvicorn | 0.51.0 | Standard FastAPI pairing |
| ORM | SQLAlchemy | 2.0.51 | 2.0 declarative style only |
| Driver | psycopg | 3.3.4 | PostgreSQL |
| Migrations | Alembic | 1.18.5 | 33 revisions, one linear chain |
| Auth | Authlib | 1.7.2 | Google OpenID Connect discovery and token exchange |
| Session | itsdangerous | 2.2.0 | Signs the Starlette session cookie |
| Settings | pydantic-settings | 2.14.2 | Typed settings from environment and `.env` |
| Templating | Jinja2 | 3.1.6 | Digest email HTML |
| HTTP client | httpx | 0.28.1 | LLM transport and page fetching |
| Feeds | feedparser | 6.0.12 | RSS parsing |
| Extraction | trafilatura | 2.2.0 | Article body from a page |
| Tests | pytest | 9.1.1 | 64 modules |
| Types | mypy | 2.3.0 | Checks `packages = ["newsagent"]` only |
| Lint | ruff | 0.15.22 | Rule set pinned to `E4`, `E7`, `E9`, `F` |

Every backend dependency is pinned exactly. Bumping one is an approved change, never a side
effect of other work.

## Architecture Pattern

Four layers, with a strict import direction. Nothing below reaches upward.

```text
   api/routers/  ──uses──►  api/schemas/     HTTP layer: routing, validation, guards
        │
        ▼
   services/                                 Domain layer: no FastAPI imports
        │
        ├──────────────► llm/  suggestions/  mail/     Adapter layer
        ▼
   models/  +  db.py                         Persistence layer
```

`api/deps.py` supplies the request-scoped session, and `api/auth.py` supplies the three
guards. Everything a route needs beyond that comes from `services/`.

### Why the domain layer stays framework-free

`services/identity.py` states the reason in its own docstring: the same admin-creation
logic is needed by the operator CLI, which has no HTTP request to hang a dependency off,
and by any future API endpoint. Keeping FastAPI out of `services/` is what makes both
possible without a second implementation.

The one place the boundary is crossed deliberately is `api/routers/me.py`'s profile update,
which schedules a FastAPI `BackgroundTask` calling into `services/profile.py`. It hands the
task `db.get_bind()`, the engine, rather than the session, because the request-scoped
session is already closed by the time the task runs.

### The adapter pattern, three times

`llm/`, `suggestions/` and `mail/` each contain the same four files:

- **`base.py`** - an abstract base class defining the contract in domain language. `llm` and
  `suggestions` both use the template-method pattern: the public methods own the uniform
  retry behavior every adapter must share, and subclasses implement only the raw operation.
- **`factory.py`** - a dictionary mapping a configuration string to a class, and a
  `get_*()` function that raises a `ValueError` naming the known values when the string is
  unrecognized.
- **`types.py`** - frozen dataclasses that cross the boundary.
- **`errors.py`** - the one typed error the contract raises.

`llm/` and `suggestions/` are siblings that deliberately do not import each other, and are
configured by two independent settings, `NEWSAGENT_LLM_PROVIDER` and
`NEWSAGENT_SUGGESTION_PROVIDER`. The article pipeline and the profile-suggestion feature can
therefore point at different models without one change affecting the other. They share only
the low-level transport, `http_llm_client.py`.

The contract objects speak domain language, never LLM language. `ArticleInput` carries a
title and clean plain text; media and HTML handling is the pipeline's job, upstream of any
provider. A provider may return a `Refusal` instead of a result, which is a first-class
outcome rather than an error.

Purity is stated as a contract property: the same input may legally return the same output.
That is what makes a caching adapter a valid implementation.

## Data Architecture

Twenty tables. See [data-models-backend.md](./data-models-backend.md) for the full schema.
The shaping conventions:

- Status columns are plain strings with no database enum, with allowed values as
  module-level constants beside the model.
- "Has this happened, and when" is a nullable timestamp, never a boolean.
- The pipeline's state machines live on `articles`, as three independent
  status-plus-attempt-counter pairs, so a deterministically failing article reaches a
  terminal state and stops being retried and billed for.
- Telemetry has a strict two-level shape: one `outbound_runs` row per stage invocation, one
  `outbound_calls` row per HTTP attempt. Totals are never denormalized onto the run; they are
  always a sum over the children.

`db.py` is four lines and builds `engine` and `SessionLocal` at import time.
`pool_pre_ping=True` is load-bearing on Neon, where an idle connection closed by the server
otherwise surfaces as an SSL error on the next request.

## API Design

See [api-contracts-backend.md](./api-contracts-backend.md) for every endpoint.

Structural notes:

- **Six routers**, each with a URL prefix and a tag. The three admin routers all declare
  `dependencies=[Depends(require_admin)]` at router level rather than per route, so the
  guard cannot be forgotten when a route is added.
- **Guards compose.** `require_admin` and `require_user` both depend on `require_identity`,
  so the 401-versus-403 distinction is made once.
- **Schemas are split one file per concern** and re-exported from
  `api/schemas/__init__.py` with an explicit `__all__`.
- **Handlers translate service exceptions into HTTP status codes** and do nothing else.
  `TopicCapExceededError` and `ValueError` become 400; a missing row becomes 404.

### Authentication

Session-cookie based, with Google as the only identity provider. There is no password
system, no local account creation, and no token refresh.

`resolve_identity` in `api/auth.py` is the single mapping from a verified Google email to
this system's rows, and the only place a `User` row is created from a request that was
unauthenticated until that moment. It is reached only after Google's callback has verified
the email. Its rules:

- An existing `User` signs in, and its row is never mutated, even when Google's claims have
  since changed.
- A brand-new email creates a row when there is room under `NEWSAGENT_MAX_USERS`.
- An `Admin` with no `User` row goes through the same capacity-gated creation as anyone
  else. An admin who wants their own digest counts against the same cap, with no exemption.
  What never changes is that an admin always signs in; when the cap is full they simply keep
  a null `user_id`.
- Returning `None` means the email has no admin row **and** the cap is full. The caller then
  captures the address to the waitlist rather than signing anyone in.

The cap is enforced atomically at the database level by
`services/identity.register_user_if_capacity`, not by an application-level count check that
two concurrent requests could both pass.

### Development login

`GET /auth/dev-login` exists only when `NEWSAGENT_DEV_AUTH_EMAIL` is set, and the route is
registered inside an `if` at import time. In every other environment the path does not
exist, rather than existing and 404-ing on a flag, so a stray value cannot re-enable it by
accident. It performs a real sign-in producing exactly the session the Google callback
produces, so nothing downstream behaves differently under it and no code on the
authenticated request path can skip a check. The API logs a warning on every boot when it is
enabled, because the failure mode is nobody noticing.

## Observability

Logging is not conventional here, and the difference matters.

**Every log record becomes a `log_entries` row. There is no file or stream destination at
all.** `logging_setup.configure_logging()` installs a database-backed handler; the level
comes from `NEWSAGENT_LOG_LEVEL`, defaulting to `WARNING`. Each row carries the application
version read from installed package metadata, and, for records emitted during a filter or
summarize run, the id of that run's `outbound_runs` row.

`NEWSAGENT_LOG_LEVEL` is the single source of truth for verbosity and takes precedence over
uvicorn's own `--log-level`. A deployment that wants uvicorn's startup and request lines must
set it to `INFO`. `httpx` and `httpcore` are held at `WARNING` so `DEBUG` shows application
records rather than transport traces.

A write failure inside the handler falls back to `logging.Handler.handleError()`, which
prints to stderr, rather than raising into application code. There is no other destination
left to fall back to.

### Outbound-call telemetry

A three-role split, each role in its own module, described in the architecture spine as
AD-11 through AD-16:

- **The measurer** is the transport, which produces a domain-free `CallMeasurement`: no
  purpose, no article, no run.
- **The attributor** is `telemetry/context.py`, holding two `contextvars`. `open_run()`
  opens once per stage invocation; `attribute_call()` nests inside it per call. Attribution
  travels only through these variables, never as a parameter threaded through `llm/`,
  `suggestions/` or the HTTP client.
- **The writer** is `services/telemetry.py`, the sole module that touches `OutboundRun` and
  `OutboundCall`. `telemetry/sink.py` joins the two halves and calls it, opening its own
  short-lived session for every write and swallowing and logging any exception, so a
  telemetry failure can never break the work being measured.

Because attribution is ambient rather than passed, a call made with no open run is still
recorded, as `purpose='UNATTRIBUTED'`, rather than being silently dropped or attached to a
fabricated run.

Pricing is looked up per call and **copied onto the call row**, rather than referenced by
foreign key, so a later refresh can never change a historical call's recorded cost.
`model_prices` is append-only for the same reason.

**Trap:** `contextvars` do not propagate into `ThreadPoolExecutor` workers. Every stage that
parallelizes calls copies the context explicitly.

## Configuration

`newsagent.config.Settings` uses the `NEWSAGENT_` prefix and reads a `.env` file, with
`extra="ignore"`. Roughly forty settings, grouped as: database, provider selection, pipeline
tuning and concurrency, ranking weights, authentication and OAuth, email delivery, logging,
and the two LLM endpoint families.

The two LLM families use `Field(alias=...)` to read **unprefixed** environment variables:
`EXTERNAL_LLM_BASE_URL` and friends for the article pipeline, `LOCAL_LLM_BASE_URL` and
friends for suggestions. Everything else takes the `NEWSAGENT_` prefix.

Ranking weights are three settings summing to 1.0, with a nested pair splitting the interest
term. `recency_half_life_hours` defaults to 84, half a week, tuned to the weekly send
cadence so a Monday article still competes with a Sunday one.

## Testing Strategy

64 pytest modules under `tests/`, mirroring the package layout: `api/routers/`, `services/`,
`pipeline/`, `llm/`, `suggestions/`, `mail/`, `telemetry/`, `models/`, plus top-level
modules for the CLI, the scheduler, configuration, logging and the JSON parser.

**`tests/conftest.py` has two `autouse` fixtures.** One resets `settings` to the `Settings`
class defaults so a developer's `.env` cannot leak into a test run. The other redirects
telemetry and logging to in-memory SQLite. A new test that touches the database must bring
its own in-memory engine; do not assume the autouse fixtures cover you.

**mypy checks `packages = ["newsagent"]` only.** `tests/` and the frontend are outside it.
A type error in a test would not have been caught.

**ruff's rule set is pinned to `E4`, `E7`, `E9`, `F`,** deliberately narrower than ruff's own
default. Version 0.16.0 widened that default, adding `B`, `I`, `UP` and `RUF`, which turned
an unrelated linter release into red CI on untouched files. Do not modernize it.

## Development Workflow

See [development-guide-backend.md](./development-guide-backend.md).

## Deployment Architecture

See [deployment-guide.md](./deployment-guide.md). In short: a two-stage `Dockerfile.backend`
producing one image that carries both the API and the scheduler, run as two containers with
different commands. Infrastructure, secrets and the schedule live in the sibling repository
`news-agent-infra`.

## Known Constraints and Gaps

- **Never run end to end against real users**, tracked as issue 23.
- **A silent empty digest** results when a reader subscribes to a topic with zero
  admin-approved sources, tracked as issue 48.
- **The send window is open by design.** `pipeline/send.py` sends before committing
  `sent_at`; a process killed between the two re-sends. SMTP and the database share no
  transaction, so the window cannot be closed, only pointed at at-most-once delivery
  instead. See `_bmad-output/implementation-artifacts/deferred-work.md`.
- **Terraform's production frontend and backend URLs use the App Service raw hostname**
  rather than the mapped custom domain, and `NEWSAGENT_SESSION_COOKIE_DOMAIN` does not
  appear in the Terraform configuration at all. Both are flagged to the infrastructure
  owner and unfixed.

---

_Generated using BMAD Method `document-project` workflow_
