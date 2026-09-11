# Deployment Guide

**Date:** 2026-09-10
**Scope:** what this repository owns. Infrastructure, secrets, the schedule and the Terraform
definitions live in the sibling repository `news-agent-infra`.

## Ownership split

| Concern | Owner |
| --- | --- |
| Dockerfiles, nginx template, application configuration surface | this repository |
| Continuous integration, and the deploy trigger | this repository |
| Container build and push, Azure resources, secrets, cron schedules | `news-agent-infra` |

Nothing in this repository logs into Azure, builds a container for deployment, or pushes to a
registry. `trigger-deploy.yml` only tells the infrastructure repository that a commit landed.

## Images

Two images ship, built from two Dockerfiles at the repository root. Both build from local
context; neither clones anything at build time.

### `Dockerfile.backend`

Two stages, and only the second ships.

**Stage `build`**, on `python:3.12-slim`:

- Requires a `VITE_API_BASE` build argument with **no default**, and fails loudly when it is
  missing. This stage builds the frontend purely to prove it still compiles; baking a
  placeholder would silently ship a frontend that cannot reach the API.
- Installs Node 20 from NodeSource, because Debian's packaged Node is too old for
  `@tailwindcss/oxide`.
- Runs `npm ci && npm run build` in `frontend/`. **That output never reaches the deploy
  stage.** The frontend ships as its own image.
- Installs the backend into `/opt/venv` so the deploy stage can copy it wholesale.

**Stage `deploy`**, on `python:3.12-slim`:

- Accepts a `GIT_SHA` build argument, defaulting to `unknown`, and sets it as an environment
  variable. `GET /health` returns it.
- Creates a system user `newsagent` with no login shell and runs as that user.
- Copies the virtual environment, plus `alembic/` and `alembic.ini`. No Node, no npm cache,
  no build toolchain.
- Exposes 8000, declares a `HEALTHCHECK` against `/health`, and runs:

```bash
uvicorn newsagent.api.main:app --host 0.0.0.0 --port 8000
```

**This same image also carries the delivery scheduler.** Run it as a second container from
the same image, overriding the command:

```bash
python -m newsagent.scheduler
```

The scheduler container needs the database URL and the mail settings, `NEWSAGENT_EMAIL_SENDER`
plus the SMTP values. The API container does not. Extra scheduler replicas are safe, since the
lease row lets only one deliver at a time, but they do no useful work, so one is enough.

### `Dockerfile.frontend`

Two stages, and only the second ships.

**Stage `build`**, on `node:20-slim`: copies the lockfile first, runs `npm ci`, copies the
rest, runs `npm run build`. Then writes a static `dist/version.json` containing the commit
SHA, the same shape as the backend's `/health` commit field, so a deploy or rollback can be
verified against what is actually running rather than against a green build. It is written
into `dist/` at this stage, where the process runs as root, so the single copy below picks it
up like any other build asset.

**Stage `serve`**, on `nginxinc/nginx-unprivileged:1.27-alpine`: copies `dist` into the web
root and `nginx.frontend.conf.template` into `/etc/nginx/templates/`. Listens on 8080 as a
non-root user, with a `HEALTHCHECK` against the root path.

**No `VITE_API_BASE` build argument is accepted, deliberately.** `client.ts` already falls
back to the relative `/api`, matching the dev-server proxy. Baking an absolute URL would
freeze one environment's backend hostname into the image and break the stage-to-production
promotion the image exists for.

## Runtime request routing

`nginx.frontend.conf.template` does two things.

**SPA fallback:**

```text
location / {
    try_files $uri $uri/ /index.html;
}
```

**API reverse proxy:**

```text
location /api/ {
    proxy_pass https://${BACKEND_HOST}/;
    proxy_set_header Host ${BACKEND_HOST};
    proxy_ssl_server_name on;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Three details matter:

- **The trailing slash on `proxy_pass` strips the `/api` prefix**, matching what Vite's
  dev-server proxy does with an explicit rewrite.
- **`Host` is overridden to the backend's own hostname.** Azure App Service routes on the
  `Host` header, not on TLS SNI alone, so forwarding the frontend's own `Host` would reach the
  wrong application or a 404.
- **`BACKEND_HOST` is substituted at container start**, by nginx's own bundled
  `20-envsubst-on-templates.sh`, which rewrites any `${VARNAME}` matching a set environment
  variable. Only `BACKEND_HOST` qualifies; the bare `$`-prefixed nginx runtime variables in
  the file match no container environment variable and are left untouched.

That is one environment variable per environment instead of one image per environment.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request, with three jobs.

| Job | Runtime | Steps |
| --- | --- | --- |
| `lint-and-test` | Python 3.12, pip cache | install pinned requirements plus the editable package, `ruff check .`, `pytest` |
| `frontend-test` | Node 22, npm cache | `npm ci`, `npm run type-check`, `npm run test` |
| `e2e-test` | both | needs the first two, installs both toolchains and Chromium with system dependencies, then `npm run test:e2e` |

## Deploy trigger

`.github/workflows/trigger-deploy.yml` fires on a push to `dev` or `main` only.

It maps the branch to an environment name, `dev` to `stage` and `main` to `prod`, then POSTs
a `repository_dispatch` event of type `deploy` to `MONS-Designers/news-agent-infra` carrying
that environment and the commit SHA. It requires only `contents: read` and uses a token stored
as `INFRA_DISPATCH_TOKEN`.

It performs no Docker build, no Azure login and no registry push.

## Verifying a deploy

Both environments track a **fixed, reused container tag**, so the tag alone proves nothing
about what is running. Two endpoints answer that question instead:

```bash
curl https://<backend-host>/health
```

Returns `{"status": "ok", "commit": "<sha>"}`.

```bash
curl https://<frontend-host>/version.json
```

Returns `{"commit": "<sha>"}`.

Also worth checking after a database or network change:

```bash
curl -i https://<backend-host>/health/db
```

Returns 503 with `{"status": "error"}` when `SELECT 1` fails.

## Schedule

Two scheduled jobs, not one, because the digest is weekly but the pipeline is not.

| Stages | Cadence | Why |
| --- | --- | --- |
| `fetch`, `filter`, `extract`, `summarize` | daily | RSS feeds hold only the latest twenty to fifty items and roll the rest off |
| `build-digests`, `send-digests` | weekly | one email per reader per week |

The cron definitions live in `news-agent-infra`. Note that the scheduler process is an
alternative to cron for the last two stages: it owns the send schedule in code and gates each
reader by their own chosen cadence.

`refresh-pricing` is also scheduled from the infrastructure side, and its exit codes are the
whole contract: 0 means updated, 2 means the pricing source was unavailable this run and
existing rates stay in effect, which is not a failure, and 1 means a real failure.

## Configuration in the deployed environments

**The real source of truth is Terraform**, in `news-agent-infra/terraform/main.tf`'s
`app_settings` blocks, with secrets injected through Azure Key Vault references of the form
`@Microsoft.KeyVault(SecretUri=...)`.

**The two GitHub Environments named `stage` and `prod` are currently orphaned.** They hold
secrets and variables, but the infrastructure repository's `deploy.yml` has no `environment:`
key and reads none of them. Setting a GitHub Environment secret does not change production
behavior unless that workflow is changed to consume it, which is not currently planned.

### Known discrepancies, flagged and unfixed

These were found while investigating a production login failure on 2026-09-06 and are the
infrastructure owner's to fix:

- Terraform's production `NEWSAGENT_FRONTEND_URL` and `NEWSAGENT_BACKEND_BASE_URL` use the App
  Service's raw `default_hostname` rather than the mapped custom domain.
- `NEWSAGENT_SESSION_COOKIE_DOMAIN` does not appear in the Terraform configuration at all. It
  is needed as a parent domain on production, per the split-subdomain cookie logic in
  `config.py`, because the frontend and backend sit on different subdomains of the same parent.
- **Open question:** does the custom domain actually serve HTTPS? The redirect URI registered
  with Google must match the computed scheme exactly. If the frontend URL is computed as
  `http://` while Google has `https://` registered, or the reverse, the OAuth callback breaks.

### Resolved on 2026-09-06

- Production was pointed at the wrong Neon branch, the test one, and was corrected directly in
  Azure and Terraform.
- `db.py`'s engine lacked `pool_pre_ping`, so requests after Neon closed an idle connection
  failed with `SSL connection has been closed unexpectedly`. Fixed in commit `b124d3e`.

## Before assuming a deployment shape

Anything that touches the API base URL, the cookie domain or the CORS origins should be
checked against the real deployed topology, or made configurable rather than assumed.
`client.ts`'s `API_BASE` was a hardcoded relative path from the original scaffold commit and
silently broke OAuth login once the frontend and backend were deployed on split subdomains.
Nobody's job was to check that assumption before it shipped. A two-line message to the
infrastructure owner is cheaper than discovering the gap after a deploy.

The full write-up lives in `news-agent-infra` at
`_bmad-output/implementation-artifacts/retro-mvp-deploy-2026-08-16.md`.

---

_Generated using BMAD Method `document-project` workflow_
