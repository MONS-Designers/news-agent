# NewsAgent

An automated news digest agent: fetches articles from admin-curated RSS sources, filters for
relevance per topic, summarizes and translates to Hebrew, and delivers a daily digest by email.

## MVP scope

- Email digest only, for 2 dogfood users (seeded, not self-registered)
- Admin source approval and user topic preferences via a small web UI
- Public signup and WhatsApp delivery are explicitly out of scope for MVP

See [ISSUES.md](ISSUES.md) for the full backlog, tracked as [issues on this
repo](https://github.com/MONS-Designers/news-agent/issues).

## Architecture

- **Backend** — FastAPI + SQLAlchemy, SQLite for MVP
- **Frontend** — Vue, two surfaces: admin source approval and user preferences
- **Auth** — Google OAuth (admin email allowlist / matched seeded user email), no separate
  login/password system
- **Pipeline** — scheduled process (fetch → filter → summarize/translate → build digest → send),
  separate from the API and reading/writing the DB directly

Backend, frontend, and pipeline are kept as separate layers, with the API as the only contract
between backend and frontend.

## Status

Early scaffolding — see open issues for current progress.
