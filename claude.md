# NewsAgent — project overview

One product, two sibling repos, developed by two people. This file is shared context for
Claude Code sessions opened in either repo — Claude Code reads CLAUDE.md files from parent
directories automatically.

**news-agent/** — Nomi (dev). The content engine + user-facing app: fetch, filter,
  summarize/translate, build digest, send. Backend FastAPI + SQLAlchemy (Postgres, via Neon),
  frontend Vue (admin source-approval + user preferences), auth via Google OAuth. Pipeline is a
  separate scheduled process from the API, reads/writes the DB directly. Repo:
  github.com/MONS-Designers/news-agent
**news-agent-infra/** — Moshe (DevOps). Server, daily scheduler, email delivery, default
  source list, secrets, LLM cost control. Planned using the BMad method — see
  news-agent-infra/_bmad-output/ for the full planning trail (forged idea, market research).
  Repo: github.com/MONS-Designers/news-agent-infra

## What NewsAgent is

A news digest agent for Hebrew-speaking readers: pulls articles from RSS/web sources (any
source language), summarizes and translates to Hebrew, categorizes by topic, and delivers as a
weekly email. Output language is Hebrew; source language is irrelevant.

## Current MVP scope (per news-agent/README.md, 2026-07-17; cadence updated 2026-08-07)

**Weekly** email digest only, for 2 seeded dogfood users — **not** self-registered
Admin approves RSS sources and sets user topic preferences via a small web UI
Public signup and WhatsApp delivery are explicitly out of scope for MVP

## Locked product decisions (per BMad forge-idea, 2026-07-14)

Sources: RSS preferred, free/web search not excluded, English sources fine
"In Hebrew" = output language only; agent translates + summarizes into Hebrew
Architecture: fetching happens server-side, on the user's behalf — client stays thin
  (registration touchpoint + mailbox only)
Delivery: daily email for MVP; WhatsApp is phase 2; a pull-model website was rejected
  — **superseded 2026-08-07: the MVP cadence is weekly, not daily.** WhatsApp-as-phase-2
  and the rejection of a pull-model website still stand.
Open technical risk (unresolved, carried to build): how the agent judges source quality when
  discovering sources from a user's stated interests (vs. picking a random low-quality blog)

## ⚠️ Known drift to resolve

The BMad idea doc (2026-07-14) describes **self-registration** and the agent **auto-discovering
sources** from user interests. The news-agent README (2026-07-17) describes a narrower MVP:
**seeded users, admin-curated sources, no auto-discovery**. Unclear if this is a deliberate
MVP scope-cut or accidental drift — resolve explicitly in the PRD rather than assuming either
version.

## Where to look for more

Full decision log: news-agent-infra/_bmad-output/forge/daily-digest-agent/forged-idea.md
Market research: news-agent-infra/_bmad-output/planning-artifacts/research/
Informal architecture flow diagram: news-agent-infra/_bmad-output/planning-artifacts/architecture-flow-diagram-2026-07-14.md
Nomi's backlog: GitHub issues on news-agent