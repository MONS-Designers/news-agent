---
title: 'Switch default DB from SQLite to Postgres (Neon), fix waitlist upsert for dual-dialect support'
type: 'chore'
created: '2026-08-13'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '33e3ef19e420ca4bb9768139572f297c6a5d9119'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** The app's SQLAlchemy engine defaults to a local SQLite file. The user is moving the real
dogfood data to a Neon Postgres branch and wants Postgres to be the app's default going forward
(SQLite becomes test-only). One service currently uses SQLite-only upsert syntax that will crash
outright against Postgres.

**Approach:** Add a Postgres driver dependency, make the one SQLite-dialect-specific upsert
(`waitlist.py`) dispatch by dialect so it keeps working under the SQLite-in-memory test fixtures
while also working against Postgres, flip `config.py`'s default connection string to Postgres, and
update the two docs (`README.md`, `CLAUDE.md`) that state "SQLite for MVP" as a locked decision.

## Boundaries & Constraints

**Always:**
- Do not touch or reference any real Neon connection string, secret, or `.env` file - none of this
  step involves connecting to the real database.
- `tests/services/test_waitlist.py` must keep passing unmodified against its existing
  `sqlite:///:memory:` fixture.
- Do not modify files with pre-existing uncommitted changes from parallel work: `me.py`,
  `tracking.py`, `schemas/__init__.py`, `digest_link.py`, `user.py`, `digest.py`, `render.py`,
  `send.py`, `digest.html.j2`, and their corresponding test files.
- Match existing dialect-dispatch style already used in
  `src/newsagent/models/pending_taxonomy_suggestion.py` (side-by-side `sqlite_where=`/
  `postgresql_where=` kwargs) - i.e. support both dialects explicitly, not a lowest-common-
  denominator rewrite.
- Pin the new dependency to an exact version in `requirements.txt`, consistent with existing pins.

**Ask First:** None - scope is fully settled per prior conversation (user already chose "full
switch to Postgres as default" and "user adds the connection string to `.env` themselves").

**Never:**
- Never run `alembic upgrade head` or any script against a real database in this step.
- Never add speculative config knobs (e.g. a `db_dialect` flag) - the dispatch is a two-way
  `if/else` on `db.bind.dialect.name`, nothing more.
- Never remove SQLite support entirely - tests keep using it.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Waitlist upsert, SQLite session (existing tests) | `capture_to_waitlist(db, email, name)` with a `sqlite:///:memory:` session | Same behavior as today: insert-or-update-on-conflict by email | N/A |
| Waitlist upsert, Postgres session | Same call with a `postgresql+psycopg://...` session | Uses `sqlalchemy.dialects.postgresql.insert` + `on_conflict_do_update` instead of the sqlite variant | N/A |
| App started with no `NEWSAGENT_DATABASE_URL` set | `Settings()` instantiated with no env override | `database_url` defaults to a Postgres URL string (placeholder, not a real secret) instead of the SQLite file path | N/A - connecting with the placeholder will fail loudly at engine-use time, which is expected until `.env` is set |

</frozen-after-approval>

## Code Map

- `requirements.txt` -- add `psycopg[binary]==3.3.4`
- `src/newsagent/services/waitlist.py` -- dialect-dispatch the upsert (sqlite vs postgresql)
- `src/newsagent/config.py:8` -- change `database_url` default from `sqlite:///./newsagent.db` to a Postgres placeholder
- `.env.example` -- update the commented default/example to match
- `README.md:14,50,59` -- update "SQLite for MVP" mentions and the documented default env value
- `CLAUDE.md:8` -- update "(SQLite for MVP)" parenthetical

## Tasks & Acceptance

**Execution:**
- [x] `requirements.txt` -- add `psycopg[binary]==3.3.4` on its own line -- Postgres driver for SQLAlchemy; nothing imports it yet but the engine needs it at connect time
- [x] `.venv` -- run `pip install -r requirements.txt` -- installs the new driver locally so the app/tests can use it
- [x] `src/newsagent/services/waitlist.py` -- replace the unconditional `from sqlalchemy.dialects.sqlite import insert as sqlite_insert` + `sqlite_insert(...)` call with a dispatch on `db.get_bind().dialect.name` (`"postgresql"` -> `sqlalchemy.dialects.postgresql.insert`, else -> the existing sqlite variant), preserving the exact same `on_conflict_do_update` args -- today's code crashes on any non-sqlite engine
- [x] `src/newsagent/config.py:8` -- change the default to a Postgres-shaped placeholder, e.g. `postgresql+psycopg://user:password@host/dbname` -- makes Postgres the implicit default while making clear at a glance it must be overridden in `.env`
- [x] `.env.example` -- update the commented `NEWSAGENT_DATABASE_URL` line and its description to reflect the new default and mention Neon -- keeps the example file honest
- [x] `README.md` -- update line 14 ("SQLite for MVP" -> reflect Postgres as the real DB), line 50 (the `alembic upgrade head` comment about creating the SQLite file), line 55-59 (the "defaults work out of the box" claim and the documented default value in the env var table) -- keeps onboarding docs accurate
- [x] `CLAUDE.md` -- update line 8's "(SQLite for MVP)" parenthetical to reflect Postgres -- this file is shared context read by both repos' Claude sessions

**Acceptance Criteria:**
- Given a `postgresql+psycopg://` session, when `capture_to_waitlist` runs twice for the same email, then the second call updates the existing row (no duplicate, same as the SQLite path today)
- Given no `NEWSAGENT_DATABASE_URL` env var set, when `Settings()` is instantiated, then `settings.database_url` starts with `postgresql`
- Given the full test suite, when run after these changes, then it passes with no new failures (tests bind their own SQLite engines, independent of `config.py`'s default)

## Design Notes

`waitlist.py`'s dispatch reads the *bound engine's* dialect at call time (`db.bind.dialect.name` /
or `db.get_bind().dialect.name` depending on what's available on a `Session`), not
`settings.database_url` - this way the function is correct for whatever engine the session was
actually constructed with, matching how the existing test fixture (a separate in-memory SQLite
engine) and the real app (Postgres) each get correct behavior without any settings coupling.

## Verification

**Commands:**
- `pytest tests/services/test_waitlist.py -v` -- expected: all 4 existing tests pass unmodified
- `pytest` -- expected: full suite passes, no regressions from the config default change (tests don't read `settings.database_url`)
- `python -c "from newsagent.config import Settings; print(Settings().database_url)"` -- expected: prints a `postgresql...` URL, not `sqlite:...`

**Actual results:** 510 passed, 6 pre-existing failures unrelated to this change (caused by this machine's `.env` overriding `llm_provider`/`email_sender`/`suggestion_provider` away from their defaults - already tracked in `deferred-work.md`, confirmed by re-running with those three vars forced back to default: 47/47 pass). Verified the config-default check via `Settings.model_fields["database_url"].default` instead of instantiating `Settings()`, to avoid ever loading the real Neon connection string now present in this machine's `.env`.

## Suggested Review Order

**Dialect-safe upsert (the actual bug fix)**

- The reason this diff exists: the old unconditional `sqlite_insert` call would crash on any non-SQLite engine.
  [`waitlist.py:14`](../../src/newsagent/services/waitlist.py#L14)
- Dispatch point - reads the bound engine's dialect at call time, not `settings.database_url`, so it's correct for whatever engine the session actually uses.
  [`waitlist.py:35`](../../src/newsagent/services/waitlist.py#L35)

**Default DB flip**

- The core change: default connection string is now a Postgres-shaped placeholder that must be overridden in `.env`.
  [`config.py:8`](../../src/newsagent/config.py#L8)
- New driver the Postgres dialect needs at connect time.
  [`requirements.txt:2`](../../requirements.txt#L2)

**Docs kept honest**

- `.env.example`'s example now matches the new default and calls out that it's required, not optional.
  [`.env.example:3`](../../.env.example#L3)
- `README.md`'s "SQLite for MVP" architecture line and onboarding/env-table mentions updated to Postgres.
  [`README.md:14`](../../README.md#L14)
- `CLAUDE.md`'s shared cross-repo description updated so Moshe's sessions see the same picture.
  [`claude.md:8`](../../claude.md#L8)

**Regression coverage (peripheral)**

- Pure-function tests for the new dialect dispatch - no DB session needed, covers the postgres/sqlite/unsupported branches directly.
  [`test_waitlist.py:49`](../../tests/services/test_waitlist.py#L49)
- Guards the config default without ever loading the real `.env` override.
  [`test_config.py:12`](../../tests/test_config.py#L12)
