# news-agent - Project Overview

**Date:** 2026-09-10
**Type:** multi-part repository
**Architecture:** layered service with swappable adapters, plus a separate pipeline process
and a thin single-page client

## Executive Summary

NewsAgent is a news digest agent for Hebrew-speaking readers. It pulls articles from
admin-curated RSS sources in any source language, scores each one for relevance to its topic,
extracts the article body, summarizes and translates it into Hebrew, ranks each reader's
candidates, and delivers a weekly email digest.

"In Hebrew" describes the output only. The source language is irrelevant; the agent
translates.

Fetching happens server-side on the reader's behalf. The client stays thin: a registration
touchpoint and a preferences surface. A pull-model website was considered and rejected, and
WhatsApp delivery is a later phase.

This repository is one of two. It holds the content engine and the reader-facing application.
The sibling repository `news-agent-infra` holds the server, the scheduler definitions, email
delivery infrastructure, the default source list, secrets and cost control.

## Project Classification

- **Repository type:** multi-part, three parts in one repository
- **Project types:** backend service, web single-page application, command-line application
- **Primary languages:** Python 3.12, TypeScript 5.6
- **Architecture pattern:** layered service. A domain layer with no web-framework imports is
  shared by an HTTP layer and a set of pipeline stages, with every external dependency behind
  a swappable adapter.

## Multi-Part Structure

### backend

- **Type:** backend service
- **Location:** `src/newsagent`
- **Purpose:** the HTTP API. Authenticates readers through Google, lets admins curate sources
  and taxonomy, lets readers set a profile and topic preferences, and records digest opens and
  clicks. It fetches, summarizes and sends nothing.
- **Tech stack:** FastAPI, SQLAlchemy 2.0, Alembic, Authlib, Pydantic, PostgreSQL on Neon

### web

- **Type:** web single-page application
- **Location:** `frontend`
- **Purpose:** five routes across two audiences. Admins approve sources, curate the Field and
  Role taxonomy, and read an engagement report. Readers work through a three-step guided
  profile picker and manage subscriptions. Copy is Hebrew, right to left.
- **Tech stack:** Vue 3 Composition API, vue-router, TypeScript strict, Tailwind CSS 4, Vite,
  Vitest, Playwright

### cli

- **Type:** command-line application
- **Location:** `src/newsagent/cli.py`, `src/newsagent/pipeline/`, `src/newsagent/scheduler.py`
- **Purpose:** the operator interface and the six content stages, plus a long-lived delivery
  loop that owns the send schedule in code rather than in an external cron.
- **Tech stack:** argparse, feedparser, trafilatura, httpx, Jinja2, smtplib

### How Parts Integrate

Two integration points, and no message queue anywhere.

The web app talks to the backend over REST and JSON, authenticated by a signed session
cookie. Every call goes through one typed client module whose base URL resolves to the
relative path `/api`, which Vite's dev proxy and nginx both strip before forwarding.

The command-line part and the scheduler are **not** clients of the API. They import the same
domain services directly and open their own session against the same PostgreSQL database. That
is the payoff of keeping the domain layer free of web-framework imports: one implementation
serves an HTTP request and a cron job.

See [integration-architecture.md](./integration-architecture.md).

## Technology Stack Summary

### backend Stack

| Category | Technology | Version |
| --- | --- | --- |
| Language | Python | >= 3.12 |
| Web framework | FastAPI | 0.139.2 |
| ASGI server | uvicorn | 0.51.0 |
| ORM | SQLAlchemy | 2.0.51 |
| Driver | psycopg | 3.3.4 |
| Migrations | Alembic | 1.18.5 |
| OAuth | Authlib | 1.7.2 |
| Session signing | itsdangerous | 2.2.0 |
| Settings | pydantic-settings | 2.14.2 |
| Templating | Jinja2 | 3.1.6 |
| HTTP client | httpx | 0.28.1 |
| Tests, types, lint | pytest 9.1.1, mypy 2.3.0, ruff 0.15.22 | |

Exact pins throughout.

### web Stack

| Category | Technology | Version |
| --- | --- | --- |
| Framework | Vue | ^3.5.11 |
| Routing | vue-router | ^4.4.0 |
| Language | TypeScript | ^5.6.3 |
| Styling | Tailwind CSS | ^4.3.3 |
| Build | Vite | ^5.4.10 |
| Unit tests | Vitest | ^4.1.10 |
| End to end | Playwright | ^1.62.1 |

Caret ranges throughout. The mismatch with the backend's exact pins is a known fact, not a
task.

### cli Stack

| Category | Technology | Version |
| --- | --- | --- |
| Argument parsing | argparse | stdlib |
| Feeds | feedparser | 6.0.12 |
| Extraction | trafilatura | 2.2.0 |
| Page fetching | httpx | 0.28.1 |
| SMTP | smtplib | stdlib |
| Concurrency | concurrent.futures | stdlib |

No dependency of its own; everything is already a backend dependency.

## Key Features

- **Self-registration through Google OAuth**, hard-capped at a configurable maximum, ten at
  launch. The cap is enforced atomically at the database level, not by an application-level
  count check. Overflow visitors are captured to a waitlist rather than hitting a dead end.
- **Guided profile picker.** Field, Role, Experience and Interests produce suggested Topics
  through a background computation the client polls for. Free-text "Other" submissions feed an
  admin curation queue with a demand count.
- **Admin curation.** RSS sources and the Field and Role taxonomy are admin-approved. Source
  auto-discovery from reader interests is explicitly out of scope.
- **Six-stage content pipeline** with per-article state machines and bounded retries, so a
  deterministically failing article reaches a terminal state and stops being billed for.
- **Weighted ranking** blending relevance, recency and interest, where interest itself blends
  an LLM signal with a personalization affinity derived from which past digests the reader
  actually opened. A topic-diversity floor guarantees each unrepresented topic one slot.
- **Hebrew right-to-left email**, inline-styled, with an LLM-composed editorial opener and
  closing joke reused across identical article sets rather than regenerated.
- **Open and click tracking** through unguessable per-digest and per-link tokens, feeding both
  the admin engagement report and the ranking personalization.
- **Per-call cost telemetry.** One row per outbound HTTP attempt, with the rate copied onto the
  row at write time so a later pricing refresh cannot change a historical cost.

## Architecture Highlights

**The domain layer imports no web framework.** `services/` is callable identically from an
HTTP handler and from a cron job. That single rule is what lets the API and the pipeline be
separate processes without a second implementation of anything.

**Three adapter families, one shape.** `llm/`, `suggestions/` and `mail/` each contain
`base.py` with the abstract contract, `factory.py` mapping a configuration string to a class,
`types.py` with the frozen boundary dataclasses, and `errors.py`. Swapping a provider is a
one-line configuration change. The LLM and suggestion families deliberately do not import each
other and are configured independently.

**Contracts speak domain language, never LLM language.** An article input is a title and clean
plain text; media and HTML handling happens upstream. A refusal is a first-class return value,
not an error. Purity is stated as a contract property, which is what makes a caching adapter
valid.

**Telemetry attribution is ambient, not threaded.** Two `contextvars` carry who a call is for,
so the adapter code never takes a purpose parameter. A call made outside any open run is still
recorded, as unattributed, rather than lost or attached to a fabricated run.

**Every log record is a database row.** There is no file or stream destination at all, and the
level setting takes precedence over uvicorn's own.

**Concurrency is bounded and session-free.** Four stages use a bounded thread pool; workers
receive plain URLs, never the database session, so all writes stay on the calling thread.

**Two guards against duplicate mail.** A single-row time-based lease claimed by one conditional
update, and a sequential loop that sleeps after the tick rather than on a wall clock.

## Development Overview

### Prerequisites

Python 3.12 or newer, Node 20 or newer, and a PostgreSQL database.

### Getting Started

Create a virtual environment, install `requirements-dev.txt` and the package editable, point
`NEWSAGENT_DATABASE_URL` at a database, and run `alembic upgrade head`. Then install the
frontend with `npm install` in `frontend/`. Run the two dev servers in separate terminals.

**Before any local pipeline run:** the checked-out `.env` carries real SMTP credentials and a
real LLM token, so a careless run sends real email and spends real money even though its
database is the test branch. Keep `NEWSAGENT_LLM_PROVIDER=mock` and
`NEWSAGENT_EMAIL_SENDER=console` unless you mean otherwise.

### Key Commands

#### backend

- **Install:** `pip install -r requirements-dev.txt && pip install -e .`
- **Dev:** `uvicorn newsagent.api.main:app --reload`
- **Test:** `pytest`
- **Types:** `mypy`
- **Lint:** `ruff check .`

#### web

- **Install:** `npm install`
- **Dev:** `npm run dev`
- **Test:** `npm run test`
- **Types:** `npm run type-check`

#### cli

- **Pipeline:** `python -m newsagent.cli fetch | filter | extract | summarize | build-digests | send-digests`
- **Scheduler:** `python -m newsagent.scheduler`

## Repository Structure

One repository, three parts. The backend and the command-line part share the installed
`newsagent` package under `src/`; the frontend is a self-contained npm project under
`frontend/`. Migrations live in `alembic/`, tests in `tests/`, and BMad planning and
implementation artifacts in `_bmad-output/`.

See [source-tree-analysis.md](./source-tree-analysis.md).

## Current Status and Known Gaps

The self-registration to profile to weekly-digest loop is built and shippable end to end,
including real SMTP delivery, full-text extraction, click and open tracking, and per-run LLM
usage accounting. Known gaps:

- **Never run end to end against real users**, issue 23.
- **Silent empty digest** when a reader subscribes to a topic with zero approved sources,
  issue 48.
- **Accessibility remediation incomplete** on the profile picker, issue 31, despite being
  scoped as a baseline requirement.
- **Send is at-least-once by design.** The window between sending and committing `sent_at`
  cannot be closed, only pointed at at-most-once delivery instead.
- **Deployment configuration discrepancies** flagged to the infrastructure owner and unfixed:
  raw App Service hostnames instead of the custom domain in Terraform, and a missing session
  cookie domain setting.

## Content Policies

Two policies constrain what ships, and both are absolute rather than best-effort.

**No images of women in the digest, with no exceptions.** Currently satisfied by dropping
images from the digest entirely, since no classifier can guarantee zero exceptions. Image
extraction is still in place so later classifier work is not blocked, but nothing renders.

**No user-facing Hebrew string may assume the reader's gender.** Hebrew has no gender-neutral
second-person present tense, so the technique is to rewrite around the problem rather than use
slashed forms. Regression guards scan the Vue files and the digest template.

## Documentation Map

- [index.md](./index.md) - master documentation index
- [architecture-backend.md](./architecture-backend.md)
- [architecture-web.md](./architecture-web.md)
- [architecture-cli.md](./architecture-cli.md)
- [integration-architecture.md](./integration-architecture.md)
- [source-tree-analysis.md](./source-tree-analysis.md)
- [api-contracts-backend.md](./api-contracts-backend.md)
- [data-models-backend.md](./data-models-backend.md)
- [component-inventory-web.md](./component-inventory-web.md)
- [deployment-guide.md](./deployment-guide.md)

---

_Generated using BMAD Method `document-project` workflow_
