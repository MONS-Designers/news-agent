# Integration Architecture

**Date:** 2026-09-10
**Repository type:** multi-part monorepo, 3 parts

## Summary

The three parts meet in exactly two places: a JSON HTTP contract between the web app and
the backend, and the PostgreSQL database, which the API process and the pipeline process
both read and write directly. There is no message queue, no gRPC, no shared in-process
state, and the CLI never calls the API over HTTP.

```text
   browser
      │  HTTPS
      ▼
┌─────────────────────┐        /api/*  (prefix stripped)
│  web  (nginx + SPA) │ ───────────────────────────────┐
└─────────────────────┘                                │
                                                       ▼
                                          ┌────────────────────────┐
                                          │  backend (uvicorn)     │
                                          │  newsagent.api.main    │
                                          └───────────┬────────────┘
                                                      │ SQLAlchemy
                                                      ▼
                                          ┌────────────────────────┐
       ┌──────────────────────────────────│  PostgreSQL  (Neon)    │
       │           SQLAlchemy             └────────────────────────┘
       ▼                                              ▲
┌─────────────────────┐                               │
│  cli / scheduler    │───────────────────────────────┘
│  newsagent.cli      │
│  newsagent.scheduler│──────► RSS hosts, LLM provider, SMTP
└─────────────────────┘
```

## Integration point 1: web to backend

| Field | Value |
| --- | --- |
| From | `web` |
| To | `backend` |
| Type | REST over JSON |
| Location | `frontend/src/api/client.ts` |
| Auth | Signed session cookie, set by the backend |

### How the base URL resolves

`client.ts` opens with one line that decides everything:

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
```

The fallback to the relative path `/api` is the intended production behavior, and three
other files are built around it:

- **`frontend/vite.config.ts`** proxies `/api` to `http://127.0.0.1:8000` in development,
  rewriting the path to strip the prefix. `E2E_BACKEND_URL` overrides the target so the
  Playwright suite can point at its own isolated backend.
- **`nginx.frontend.conf.template`** does the same thing at runtime in production. The
  trailing slash on `proxy_pass https://${BACKEND_HOST}/;` performs the strip. `Host` is
  overridden to the backend's own hostname, because Azure App Service routes on the `Host`
  header rather than on TLS SNI alone; forwarding the frontend's own `Host` would hit the
  wrong app or a 404.
- **`Dockerfile.frontend`** deliberately accepts **no** `VITE_API_BASE` build argument.
  Baking an absolute URL would freeze one environment's backend hostname into the image and
  break the stage-to-production promotion the image exists for.

`BACKEND_HOST` is substituted into the nginx template at container start by nginx's own
bundled `20-envsubst-on-templates.sh`. Only that one variable is substituted; the bare
`$`-prefixed nginx runtime variables in the file match no container environment variable and
are left untouched.

**This is the single most fragile assumption in the system.** `API_BASE` was a hardcoded
relative path from the original frontend scaffold commit, and it silently broke OAuth login
once infrastructure deployed the frontend and backend on split subdomains. Any change that
touches how the frontend finds the backend warrants a message to the infrastructure repo
before assuming a deployment shape.

### The contract surface

Every call goes through one private helper in `client.ts`:

```ts
async function request<T>(path: string, init?: RequestInit): Promise<T>
```

It throws a typed `ApiError` carrying the HTTP status on any non-2xx response. `getMe()` is
the one caller that catches it, translating a 401 into `null` rather than an exception,
because "not signed in" is a normal state rather than a failure.

The exported functions map one to one onto backend routes. TypeScript interfaces in the same
file mirror the Pydantic response schemas field for field, in snake case, so a rename on
either side shows up as a type error rather than as a runtime `undefined`.

Two places deviate deliberately:

- **`listRoles`** maps the wire shape `{name, is_curated}` into the camel-cased
  `{name, isCurated}` used by the components, through a private `RoleOptionDto` interface.
- **`updateMyProfile`** builds its request body key by key, including only the keys the
  caller actually set. The interests step saves free text alone; sending undefined field and
  role keys would falsely resubmit "not provided" as an explicit part of the request.

### The session cookie

The backend signs the cookie with `itsdangerous` through Starlette's `SessionMiddleware`.
The `Domain` attribute comes from `NEWSAGENT_SESSION_COOKIE_DOMAIN`, which is empty by
default. Empty means a host-only cookie, correct for local development and single-domain
deploys. It must be set to a parent domain such as `.example.com` only when the frontend and
backend are split across subdomains, so the cookie the backend sets is sent on requests to
both.

CORS allows exactly one origin, `NEWSAGENT_FRONTEND_URL`, with credentials enabled. Under
the nginx-proxy topology the browser never issues a cross-origin request, so CORS is inert
there; it exists for the split-subdomain case.

### OAuth redirect chain

The full round trip crosses all three boundaries and is worth reading as one sequence:

1. The browser hits `GET /api/auth/login`; nginx or Vite strips the prefix and forwards to
   the backend's `/auth/login`.
2. The backend builds `redirect_uri` as `{NEWSAGENT_FRONTEND_URL}/api/auth/callback` and
   redirects to Google. It uses the configured frontend URL rather than
   `request.url_for("callback")`, because behind a proxy that overrides `Host`, `url_for`
   would resolve to the backend origin and send Google's redirect past the proxy.
3. Google redirects the browser back to the frontend origin at `/api/auth/callback`, which
   the proxy forwards to the backend's `/auth/callback`.
4. The backend resolves the identity, writes the session cookie, and issues a final redirect
   to a path inside the SPA.

**The registered redirect URI in the Google console must match the computed value exactly,
scheme included.** If the frontend URL is computed as `http://` while Google has `https://`
registered, or the reverse, the callback breaks.

## Integration point 2: cli and scheduler to the database

| Field | Value |
| --- | --- |
| From | `cli` |
| To | shared PostgreSQL |
| Type | Direct SQLAlchemy access, separate process |
| Location | `src/newsagent/db.py`, imported by both |

The CLI and the scheduler are not clients of the API. They import `services.*` and
`pipeline.*` directly and open their own session from the same `SessionLocal` the API uses.
This is what the domain layer's "no FastAPI imports" rule buys: the same code path serves an
HTTP request and a cron job.

`db.py` builds `engine` and `SessionLocal` **at import time** from `settings.database_url`.
Any module that opens its own session therefore talks to whatever the resolved configuration
pointed at. `pool_pre_ping=True` is set on the engine, which matters on Neon: an idle
connection closed by the server would otherwise surface as an
`SSL connection has been closed unexpectedly` error on the next request.

### Shared-state ownership

Because two processes write the same tables, ownership is explicit rather than implied:

| State | Owner | How the other side sees it |
| --- | --- | --- |
| `articles` lifecycle columns | pipeline stages | the API never writes them |
| `digests`, `digest_articles` | `pipeline/digest.py` | the API only reads, for the engagement report |
| `digests.sent_at` | `pipeline/send.py` | |
| `digests.opened_at`, `digest_links.clicked_at` | `api/routers/tracking.py` | the pipeline reads them for personalization |
| `users` profile and suggestion columns | `services/profile.py` | the pipeline reads them |
| `outbound_runs`, `outbound_calls` | `services/telemetry.py`, sole writer | |
| `log_entries` | `services/log_entries.py`, sole writer | |

### Concurrency control

Two mechanisms guard the parts of this that are not naturally idempotent:

- **`scheduler_lease`**, a single fixed row claimed by one conditional `UPDATE`. When two
  scheduler processes race, exactly one sees a row count of 1. It is time-based rather than
  a held lock, so a process killed without an orderly release does not block delivery
  forever.
- **`uq_pending_taxonomy_suggestions_open`**, a partial unique index that backstops the
  non-atomic select-then-insert in the taxonomy service.

Neither closes the send window: `pipeline/send.py` sends before committing `sent_at`, so a
process killed between the two re-sends an email the reader already received. SMTP and the
database share no transaction, so the window cannot be closed, only pointed the other way at
at-most-once delivery, which risks losing a digest instead. The current ordering
deliberately favours a rare duplicate over a silent loss.

## Integration point 3: outbound calls to third parties

All three leave from the CLI and scheduler processes, never from the API.

| Target | Where | Configuration |
| --- | --- | --- |
| RSS hosts | `pipeline/fetcher.py` via feedparser, `pipeline/extract.py` via httpx | `NEWSAGENT_EXTRACTION_*`, `NEWSAGENT_FETCH_CONCURRENCY` |
| LLM provider | `llm/external.py` through `http_llm_client.py` | `EXTERNAL_LLM_*`, unprefixed |
| LLM provider, suggestions | `suggestions/llm.py` through the same transport | `LOCAL_LLM_*`, unprefixed and deliberately separate |
| SMTP | `mail/smtp.py` | `NEWSAGENT_SMTP_*` |

The two LLM configuration families are independent on purpose, so the article pipeline and
the profile suggestion feature can point at different models or providers without one
change affecting the other.

Every outbound HTTP attempt is recorded as one `outbound_calls` row. Attribution travels
through two `contextvars` in `telemetry/context.py`, never as a parameter threaded through
the adapter code. That is what lets a call made outside any open run still be recorded, as
`purpose='UNATTRIBUTED'`, rather than being lost or fabricated into a synthetic run.

## Integration point 4: repository to infrastructure repository

| Field | Value |
| --- | --- |
| From | `news-agent` CI |
| To | `news-agent-infra` |
| Type | GitHub `repository_dispatch` |
| Location | `.github/workflows/trigger-deploy.yml` |

On a push to `dev` or `main`, the workflow maps the branch to an environment name, `dev` to
`stage` and `main` to `prod`, and POSTs a `deploy` dispatch event carrying that environment
and the commit SHA. It performs no Docker build, no Azure login and no registry push; the
real build and deploy pipeline lives in the infrastructure repository.

Two verification hooks travel with the deploy so a rollback can be checked against what is
actually running, rather than against static configuration. Both environments track a fixed,
reused container tag, so the tag alone proves nothing:

- The backend bakes `GIT_SHA` into the image and exposes it at `GET /health`.
- The frontend writes a static `dist/version.json` of the same shape at build time.

`refresh-pricing` has a documented exit-code contract with the infrastructure scheduler,
which is the whole interface: 0 means rates were updated, 2 means the pricing source was
unavailable this run and existing rates stay in effect, which is not a failure, and 1 means
a real failure such as the database write itself.

**Known configuration gaps, owned by the infrastructure repository.** The GitHub
Environments named `stage` and `prod` hold secrets and variables that `deploy.yml` never
reads. The real source of truth for what the deployed app runs with is Terraform's
`app_settings`, with secrets injected as Azure Key Vault references. Setting a GitHub
Environment secret does not change production behavior.

---

_Generated using BMAD Method `document-project` workflow_
