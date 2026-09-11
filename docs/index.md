# news-agent Documentation Index

**Type:** multi-part repository with 3 parts
**Primary Languages:** Python 3.12, TypeScript 5.6
**Architecture:** layered service with swappable adapters, a separate pipeline process, and a
thin single-page client
**Last Updated:** 2026-09-10

## Project Overview

NewsAgent is a news digest agent for Hebrew-speaking readers. It pulls articles from
admin-curated RSS sources in any language, scores each for relevance, extracts the body,
summarizes and translates into Hebrew, ranks each reader's candidates, and delivers a weekly
email digest. Hebrew is the output language only; the source language is irrelevant.

Fetching happens server-side on the reader's behalf. The client stays thin. The sibling
repository `news-agent-infra` owns the server, the schedules, secrets and cost control.

## Project Structure

This project consists of 3 parts:

### Backend API (`backend`)

- **Type:** backend service
- **Location:** `src/newsagent`
- **Tech Stack:** FastAPI 0.139.2, SQLAlchemy 2.0.51, Alembic, Authlib, PostgreSQL on Neon
- **Entry Point:** `newsagent.api.main:app`

### Vue SPA (`web`)

- **Type:** web single-page application
- **Location:** `frontend`
- **Tech Stack:** Vue 3.5, vue-router 4, TypeScript strict, Tailwind CSS 4, Vite 5
- **Entry Point:** `frontend/src/main.ts`

### Operator CLI and pipeline (`cli`)

- **Type:** command-line application
- **Location:** `src/newsagent/cli.py`, `src/newsagent/pipeline/`, `src/newsagent/scheduler.py`
- **Tech Stack:** argparse, feedparser, trafilatura, httpx, Jinja2, smtplib
- **Entry Points:** `python -m newsagent.cli`, `python -m newsagent.scheduler`

## Cross-Part Integration

Two integration points, and no message queue anywhere.

The web app talks to the backend over REST and JSON with a signed session cookie, through one
typed client module whose base URL resolves to the relative path `/api`. Vite's dev proxy and
nginx both strip that prefix before forwarding.

The command-line part and the scheduler are not clients of the API. They import the same
domain services directly and open their own session against the same database. That is the
payoff of keeping the domain layer free of web-framework imports.

Full detail, including the OAuth redirect chain and shared-state ownership, is in
[Integration Architecture](./integration-architecture.md).

## Quick Reference

### Backend API Quick Ref

- **Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL
- **Entry:** `uvicorn newsagent.api.main:app --reload`
- **Pattern:** four layers, strict import direction: routers, services, adapters, models
- **Surface:** 23 endpoints across 6 routers, 20 tables, 33 migrations

### Vue SPA Quick Ref

- **Stack:** Vue 3 Composition API, Tailwind 4, Vite
- **Entry:** `npm run dev` on port 5173
- **Pattern:** component-based, module-level reactive stores, no store library

### Operator CLI Quick Ref

- **Stack:** argparse plus the backend's own dependencies
- **Entry:** `python -m newsagent.cli <command>`
- **Pattern:** six stages over a shared database, state machines on the article row

## Generated Documentation

### Core Documentation

- [Project Overview](./project-overview.md) - executive summary and high-level architecture
- [Source Tree Analysis](./source-tree-analysis.md) - annotated directory structure

### Part-Specific Documentation

#### Backend API (`backend`)

- [Architecture](./architecture-backend.md) - layers, adapters, auth, telemetry, logging
- [API Contracts](./api-contracts-backend.md) - all 23 endpoints, schemas, error behavior
- [Data Models](./data-models-backend.md) - 20 tables, conventions, migration chain
- [Development Guide](./development-guide-backend.md) - setup, configuration, safety, testing

#### Vue SPA (`web`)

- [Architecture](./architecture-web.md) - routing, guards, state, API boundary, content rules
- [Component Inventory](./component-inventory-web.md) - design tokens, views, components
- [Development Guide](./development-guide-web.md) - setup, commands, conventions

#### Operator CLI and pipeline (`cli`)

- [Architecture](./architecture-cli.md) - the six stages, ranking, the scheduler, cadence
- [Development Guide](./development-guide-cli.md) - command reference, tuning, exit codes

### Integration

- [Integration Architecture](./integration-architecture.md) - how the parts communicate
- [Project Parts Metadata](./project-parts.json) - machine-readable structure

### Optional Documentation

- [Deployment Guide](./deployment-guide.md) - images, routing, CI, verification, known gaps

## Existing Documentation

- [README](../README.md) - scope, architecture summary, schedule, getting started, status
- [CLAUDE.md](../CLAUDE.md) - cross-repo context, locked product decisions, content policies
- [Project Context for AI Agents](../_bmad-output/project-context.md) - stack rules, comment
  policy, environment and database safety
- [User Management](./user-management.md) - operator notes on user accounts
- [V1 Manual Test Plan](./v1-manual-test-plan.md) - manual verification script
- [V1 Urgent Fixes](./v1-urgent-fixes-2026-08-24.md) - the 2026-08-24 fix log

## Getting Started

### Backend API Setup

**Prerequisites:** Python 3.12 or newer, a PostgreSQL database.

```bash
pip install -r requirements-dev.txt
```

```bash
pip install -e .
```

```bash
alembic upgrade head
```

```bash
uvicorn newsagent.api.main:app --reload
```

### Vue SPA Setup

**Prerequisites:** Node 20 or newer, and a running backend.

```bash
cd frontend && npm install
```

```bash
npm run dev
```

### Operator CLI Setup

**Prerequisites:** the same environment as the backend.

```bash
python -m newsagent.cli --help
```

## Read This Before Running Anything Locally

- **`.env` points at the TEST Neon branch. `.env.prod` holds the PRODUCTION database URL.**
  Both are gitignored. Never print, log or commit either, and never point a local run at
  `.env.prod`.
- **`.env` also carries real SMTP credentials and a real LLM token.** A careless local
  pipeline run sends real email and spends real money, even though its database is the test
  branch. Keep `NEWSAGENT_LLM_PROVIDER=mock` and `NEWSAGENT_EMAIL_SENDER=console`.
- **Configuration is read only through `newsagent.config.Settings`.** Never `os.environ`.
- **`tests/conftest.py` has two `autouse` fixtures** that reset settings and redirect
  telemetry and logging to in-memory SQLite. A new test touching the database must bring its
  own in-memory engine.

## For AI-Assisted Development

This documentation set was generated to let an agent understand and extend this codebase
without re-reading it from scratch.

### When Planning New Features

**UI-only features**
Reference `architecture-web.md` and `component-inventory-web.md`.

**API and backend features**
Reference `architecture-backend.md`, `api-contracts-backend.md` and `data-models-backend.md`.

**Pipeline, scheduling or cost features**
Reference `architecture-cli.md` and `development-guide-cli.md`.

**Full-stack features**
Reference all four architecture documents plus `integration-architecture.md`.

**Deployment changes**
Reference `deployment-guide.md`, and check with `news-agent-infra` before assuming a
deployment topology.

### Conventions That Are Not Negotiable

- Never widen the ruff rule set. It is pinned to `E4`, `E7`, `E9`, `F` deliberately.
- SQLAlchemy 2.0 style only. Migrations keep `op.batch_alter_table`.
- Tailwind is version 4. Tokens go in `@theme` in `style.css`; no config file, no scoped CSS.
- Never hardcode a backend hostname in the frontend.
- Backend pins are exact and deliberate. Bumping one is an approved change, never a side
  effect.
- No user-facing Hebrew string may assume the reader's gender.
- The digest ships no images of women, currently satisfied by shipping no images at all.

---

_Documentation generated by BMAD Method `document-project` workflow_
