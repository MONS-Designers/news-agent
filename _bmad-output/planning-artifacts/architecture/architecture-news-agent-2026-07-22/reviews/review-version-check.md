# Review: Version / Reality-Check Audit - ARCHITECTURE-SPINE.md (Profile-Based Topic Suggestions)

**Lens:** Verify every committed decision was web-researched or reality-checked rather than
asserted from training data - version claims, library existence/fit, and (for greenfield
pieces) starter defaults. Flag anything that looks asserted-from-memory and unconfirmed.

**Method:** Read the spine in full; read `pyproject.toml`, `requirements.txt`,
`requirements-dev.txt`, `frontend/package.json`; inspected `src/newsagent/llm/*`,
`src/newsagent/models/article.py`, `alembic/` (config, `env.py`, `versions/`), and `git log --
alembic/`; ran targeted web searches for FastAPI `BackgroundTasks` restart/crash behavior,
SQLAlchemy `JSON` column mutation-tracking on SQLite, and current pytest/mypy major versions.

---

## Finding 1 (Critical) - AD-4's core factual premise is wrong: Alembic is wired in and actively used, not "installed-but-unwired"

AD-4 states: *"Alembic is an installed-but-unwired dependency; schema setup today is
`create_all`-style."* The same claim, in near-identical wording, is asserted in
`.memlog.md` line 11: *"no `alembic/` directory or migration convention exists in-repo;
schema setup is ad-hoc/`create_all`-style."*

This is factually false and was not reality-checked against the repo it describes:

- `alembic/env.py` is fully wired: it imports `newsagent.config.settings` and
  `newsagent.models.Base`, sets `sqlalchemy.url` from the app's real settings, and points
  `target_metadata` at `Base.metadata` - this is a working, connected Alembic setup, not a
  stub.
- `alembic/versions/` contains **7 real migrations**, the earliest being
  `7de791f6b76c_initial_schema.py` (the actual initial schema - meaning the DB was never
  created via `create_all` in the first place) and the most recent,
  `d1a2b3c4d5e6_article_image_url.py`, dated 2026-07-21 - four days before this spine
  was drafted.
- `git log --oneline -- alembic/` shows migrations added continuously across the project's
  history, from "Issue #1: DB models, config, and Alembic migrations" through "Issue #24:
  Article images."
- A repo-wide search for `create_all` in `src/` returns zero hits - the `create_all`
  claim isn't just outdated, it never matched this codebase.

**Impact:** AD-4 is built on an inverted premise. The spine defers "migration tooling
strategy" as an open question needing a future decision, when in reality the project has
an established, working convention (hand-written Alembic revision files, reviewed and
merged per feature) that this feature's new tables/columns (`fields`, `roles`,
`pending_taxonomy_suggestions`, new `User` columns) should almost certainly just follow.
This should be corrected before the spine is treated as authoritative - at minimum AD-4's
"Rule" and the "Deferred" bullet on migration tooling need to be rewritten to reflect that
Alembic is already the answer, not an open question.

## Finding 2 (Moderate) - SQLAlchemy `JSON` column: mutation-tracking caveat is real but not addressed, though usage pattern is probably safe

Verified via SQLAlchemy docs: the plain `JSON` type does **not** detect in-place mutation
(e.g. `user.suggested_topic_ids.append(5)`) - only whole-attribute reassignment
(`user.suggested_topic_ids = [...]`) reliably marks the column dirty, unless
`sqlalchemy.ext.mutable.MutableList` is used. This is a known, documented footgun with
SQLAlchemy's JSON type generally (not SQLite-specific - SQLite has no native JSON type
either way; SQLAlchemy stores it as serialized TEXT on that dialect, which is fine for a
flat list of ints).

The spine's design (AD-7: "written by the BackgroundTask") reads as a one-shot whole
assignment, which would sidestep the mutation-tracking issue - but the spine never states
this explicitly, so it isn't clear whether this was verified/considered or is coincidentally
safe. Since `article.py`'s existing `bullets_he: Mapped[list[str] | None]` uses the same
bare `JSON` type today (confirming the "no new package required" claim is accurate for
storage), the precedent is consistent, but the same latent footgun exists there too if any
future code ever mutates in place. Worth one sentence in AD-7 confirming the write is
always a full reassignment.

## Finding 3 (Low) - FastAPI `BackgroundTask` limitation described accurately, and already explicitly acknowledged

AD-5's own text ("Accepted tradeoff: lost on crash/restart, retried only via the provider
adapter's own retry") matches current documented FastAPI behavior, confirmed by web search:
`BackgroundTasks` run in the same OS process/worker as the API request, are memory-only,
and any task not yet completed is lost on redeploy/crash/restart - exactly what the spine
says. No correction needed here; flagging only because the task asked to confirm it
specifically. This is the one place in the spine where a claim that could have been
asserted from training data was, in fact, checked and stated correctly.

## Finding 4 (Informational) - No numeric version claims in the spine itself; existing pinned versions are plausible and not the issue

The spine names frameworks generically (FastAPI, SQLAlchemy, "Pydantic v2 / pydantic-settings",
Vue 3 + Tailwind CSS, SQLite) and states no new dependency is introduced - it makes no
specific version-number assertions to fact-check. Cross-checked against what's actually
pinned:

- `requirements.txt`: `SQLAlchemy==2.0.51`, `alembic==1.18.5`, `pydantic-settings==2.14.2`,
  `fastapi==0.139.2`, `uvicorn==0.51.0`, `Authlib==1.7.2`, `feedparser==6.0.12`,
  `Jinja2==3.1.6`.
- `requirements-dev.txt`: `pytest==9.1.1`, `mypy==2.3.0`, `httpx==0.28.1`.
- `frontend/package.json`: Tailwind `^4.3.3` via `@tailwindcss/vite`, Vue `^3.5.11`.

Spot-checked the two version claims that looked like they could be stale training-data
artifacts if asserted (they weren't asserted by the spine, but worth confirming the stack
itself is current): pytest 9.x (released Nov 2025, patched into 2026) and mypy 2.x
(mypy 2.0 shipped May 2026, 2.1 blogged May 2026) are both real, current major versions -
the pins are consistent with a mid-2026 project and not hallucinated or outdated. No action
needed; this is the one area of the review that came back clean.

---

## Summary

| # | Finding | Severity | Verified against |
| - | --- | --- | --- |
| 1 | AD-4 wrongly claims Alembic is unwired; repo has a working Alembic setup with 7 real migrations through 2026-07-21 | Critical | `alembic/env.py`, `alembic/versions/*`, `git log`, grep for `create_all` |
| 2 | SQLAlchemy `JSON` mutation-tracking caveat not explicitly addressed for `suggested_topic_ids` | Moderate | SQLAlchemy docs (web), `models/article.py` precedent |
| 3 | AD-5's BackgroundTask crash/restart tradeoff is accurate and already acknowledged | Low (no fix needed) | Web search of current FastAPI behavior |
| 4 | Spine makes no numeric version claims; actual pinned versions (pytest 9.x, mypy 2.x, etc.) are real and current for 2026 | Informational | `pyproject.toml`, `requirements*.txt`, `package.json`, web search |
