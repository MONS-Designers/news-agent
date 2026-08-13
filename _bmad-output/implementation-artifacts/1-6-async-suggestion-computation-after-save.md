---
baseline_commit: 5d4a3d7
---

# Story 1.6: Async suggestion computation after save

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want my profile save to complete instantly, with suggestions appearing shortly after,
so that saving never feels slow.

*Realizes FR8, NFR2, NFR3 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.3).*

## Acceptance Criteria

1. **Given** I complete Step 2 (Continue or Skip) and the profile save request is sent, **when** the request handler processes it, **then** it synchronously sets `User.suggestion_status='pending'` and increments `User.suggestion_request_seq` before returning - the response never waits on suggestion computation.
2. **Given** the save response has returned, **when** the frontend needs suggestions, **then** it calls `GET /me/topic-suggestions`, which returns the current `suggestion_status` and `suggested_topic_ids`.
3. **Given** a `BackgroundTask` was scheduled at save time, **when** it completes, **then** it writes `suggested_topic_ids` and sets `suggestion_status='ready'` (or `'failed'` on error) only if its captured `suggestion_request_seq` still matches the current value on `User` - a superseded computation discards its result instead of overwriting a newer one.
4. **Given** suggestion generation fails or times out, **when** the BackgroundTask's error path runs, **then** `suggestion_status` becomes `'failed'`, no Topic selections change, and the earlier save is unaffected.
5. This story ships a new Alembic revision adding `User.suggestion_status`, `User.suggested_topic_ids`, `User.suggestion_request_seq`.

## Tasks / Subtasks

- [x] Task 1: `User` columns + migration (AC: #1, #5)
  - [x] 1.1 Module-level constants in `user.py`: `SUGGESTION_STATUS_NONE = "none"`, `SUGGESTION_STATUS_PENDING = "pending"`, `SUGGESTION_STATUS_READY = "ready"`, `SUGGESTION_STATUS_FAILED = "failed"`.
  - [x] 1.2 Three columns on `User`: `suggestion_status` (NOT NULL, `default`/`server_default="none"`), `suggested_topic_ids` (nullable `JSON`), `suggestion_request_seq` (NOT NULL `Integer`, `default`/`server_default=0`).
  - [x] 1.3 New Alembic revision `e5f6a7b8c9d0`, `down_revision="d4e5f6a7b8c9"` (re-confirmed via `alembic heads`). Three `op.add_column` calls + matching `downgrade()`.
  - [x] 1.4 `alembic upgrade head` not run without asking first (pending user approval before live verification, per every prior story's standing rule).

- [x] Task 2: `services/profile.py` - synchronous pending+seq bump (AC: #1)
  - [x] 2.1 `_apply` unconditionally sets `suggestion_status = SUGGESTION_STATUS_PENDING` and bumps `suggestion_request_seq` before the trailing `db.commit()`, on every successful save regardless of which fields were submitted.
  - [x] 2.2 Constants imported from `newsagent.models.user`.

- [x] Task 3: `services/profile.py` - BackgroundTask entrypoint + computation (AC: #3, #4)
  - [x] 3.1 `_topic_popularity(db)` - `SELECT` from `Topic` with an outer join to `UserTopicPreference`, `GROUP BY Topic.id`, so zero-selection topics are included (an inner-join or `UserTopicPreference`-first query would silently drop them).
  - [x] 3.2 `_compute_and_store_suggestions(db, user_id, expected_seq)` - computes via `get_suggestion_source().suggest_topics(...)`, catches `SuggestionError` specifically → `'failed'`; the race-guard (`db.refresh(user)` then compare `suggestion_request_seq`) happens immediately before the write, not at function entry.
  - [x] 3.3 `run_suggestion_computation(engine, user_id, expected_seq)` - the actual `BackgroundTasks` target; opens its own `Session(engine)` since the request-scoped session is already closed by the time a background task runs.
  - [x] 3.4 All imports added: `Topic`, `UserTopicPreference`, `SuggestionError`, `TopicPopularity`, `get_suggestion_source`, `func`, `select`, `Engine`, `Connection`.

- [x] Task 4: API - `PUT /me/profile` schedules the task; new `GET /me/topic-suggestions` (AC: #1, #2)
  - [x] 4.1 `update_my_profile` takes a `background_tasks: BackgroundTasks` param; after a successful save, `background_tasks.add_task(profile.run_suggestion_computation, db.get_bind(), updated.id, updated.suggestion_request_seq)`. `ProfileOut` unchanged - no suggestion fields added to it.
  - [x] 4.2 New `TopicSuggestionsOut` schema (`suggestion_status: str`, `suggested_topic_ids: list[int] | None`).
  - [x] 4.3 New `GET /me/topic-suggestions`, `require_user`-guarded, returns the injected `user` directly - no new service function (pure read).
  - [x] 4.4 Exported from `api/schemas/__init__.py`.

- [x] Task 5: Tests (AC: all)
  - [x] 5.1 `test_profile.py`: successful saves set `pending` and bump `suggestion_request_seq` (first save 0→1, second save 1→2); a rejected save leaves both at their defaults.
  - [x] 5.2 New `test_profile_suggestions.py`: `_topic_popularity` includes zero-selection topics; successful computation writes `ready` + correct `suggested_topic_ids`; **the race guard** (stale `expected_seq` discards the write entirely - the story's highest-risk behavior); failure path (`SuggestionProviderError` via a local test double) sets `failed` and leaves `suggested_topic_ids` untouched; a deleted user is a no-op; end-to-end ranking sanity check with the real `PopularitySuggestionSource`.
  - [x] 5.3 `test_me.py`: unauthenticated → 401; before any save → `{"suggestion_status": "none", "suggested_topic_ids": null}`; full `PUT` → `GET` round trip shows `ready` with non-empty `suggested_topic_ids`.
  - [x] 5.4 Full suite green: 218 passed (11 new on top of the 207 baseline); `mypy` and `ruff` clean.

## Dev Notes

### Read these before writing code

- [`src/newsagent/services/profile.py`](../../src/newsagent/services/profile.py) - `_apply`'s existing shape; the pending/seq bump lands inside its single trailing `db.commit()`, same transaction as every other field write.
- [`src/newsagent/api/deps.py`](../../src/newsagent/api/deps.py), [`tests/api/conftest.py`](../../tests/api/conftest.py) - `seeded_db`'s `StaticPool` in-memory engine and its `get_db` override; this is why `db.get_bind()` (not `newsagent.db.SessionLocal`) is the only mechanism that resolves to the *same* database in both production and tests.
- [`src/newsagent/db.py`](../../src/newsagent/db.py) - confirms `db.get_bind()` returns the same production `engine` `SessionLocal` is bound to, so the engine-passing approach isn't a test-only hack.
- [`src/newsagent/models/pending_taxonomy_suggestion.py`](../../src/newsagent/models/pending_taxonomy_suggestion.py), [`src/newsagent/models/article.py`](../../src/newsagent/models/article.py) (`relevance_status`) - the `STATUS_*` constant convention and the `nullable=False` + matching `default`/`server_default` pair convention this story's three new `User` columns follow.
- [`src/newsagent/suggestions/base.py`](../../src/newsagent/suggestions/base.py) (Story 1.5) - `suggest_topics(*, field_name, role_name, interest_free_text, popularity)`'s exact signature; `popularity` is data the caller queries and passes in (AD-3).
- [`src/newsagent/api/auth.py`](../../src/newsagent/api/auth.py) - `require_user` does `db.get(User, identity.user_id)` fresh per request in production, so no staleness there; **but see the identity-map gotcha below, which only bites the test fixture.**

### Which save triggers computation

`PUT /me/profile` is shared by Step 1 (Field/Role/Experience) and Step 2 (Interest Free-Text alone). The pending/seq bump (Task 2.1) is unconditional on *every* successful save - no step-distinguishing flag was added. This is safe because the seq race-guard (Task 3.2) makes an earlier, premature computation harmless once a later save supersedes it, regardless of which BackgroundTask finishes first; by the time Step 3 (a later story) polls for results, the *last* save's computation is authoritative. Adding a flag to distinguish "which step" would be unrequested complexity with no AC asking for it.

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-5** - in-process `BackgroundTask`, no task queue. `suggestion_status='pending'` and the seq bump are synchronous, inside `_apply`'s existing transaction. The race-guard check happens immediately before the write (`db.refresh(user)` right before commit), not at function entry - entry-only checking would not protect against a concurrent save landing *during* the (potentially slow, future-LLM) computation.
- **AD-7** - `GET /me/topic-suggestions` is the only read path; `ProfileOut` is untouched.
- **AD-3** - `services/profile.py` is the only file importing from `newsagent.suggestions`; `_topic_popularity`'s query lives in `profile.py`, not in the provider package (providers never touch the DB).
- **AD-1** - no new service function for the `GET` endpoint; it's a pure read of already-fetched `user` fields, matching the router's existing simple-`GET` pattern.
- **NFR2** - satisfied structurally: the response returns immediately after `db.commit()` inside `save_profile`; `suggest_topics` and its DB query only run inside the BackgroundTask, after the response has been sent.

### A real gotcha found and worked around during testing (not a production bug)

The end-to-end router test (`test_profile_save_triggers_background_computation_visible_via_get`) initially failed: `PUT` → `GET` showed `suggestion_status == "pending"` instead of `"ready"`, even though the BackgroundTask genuinely ran and committed correctly (confirmed via isolated diagnostics: `Session.get_bind()` returns the right `Engine`, and cross-session/cross-thread visibility against the same `StaticPool` in-memory engine works correctly). The actual cause: `tests/api/conftest.py`'s `seeded_db` fixture is **one long-lived `Session` reused across every request in a test** (unlike production, where `get_db` opens a fresh `SessionLocal()` per request). SQLAlchemy's `Session.get()` returns an already-loaded object straight from the identity map without hitting the DB - and `seeded_db`'s copy of the `User` row was only ever expired by *its own* commits, not by the BackgroundTask's separate session committing a change. Fix: the test calls `seeded_db.expire_all()` between the `PUT` and the `GET`, simulating what a fresh per-request session would naturally see. This is a test-fixture-only artifact; do not "fix" it by changing `get_bind()`/session-passing in the actual implementation, and expect the same `expire_all()` pattern to be needed in Story 1.7's own polling tests if they reuse `seeded_db` similarly.

### Explicit scope boundary

- **No frontend changes.** Step 3 (the UI polling `GET /me/topic-suggestions`) is Story 1.7. No live browser verification was performed for this story - nothing user-visible changed; correctness was verified via the full `TestClient` suite, including a genuine end-to-end round trip through the real BackgroundTask machinery.
- **No 4-Topic cap enforcement.** `suggested_topic_ids` may contain any number of candidates the provider returns - capping for display/selection is Story 1.7 (AD-9).
- **No retry/backoff configuration added around the BackgroundTask call site** - `SuggestionSource._run` (Story 1.5) already owns retry for transient provider errors; this story only catches the typed `SuggestionError` that surfaces after those retries exhaust.
- **No UI/copy for the "failed" state** - nothing renders this data yet.

### Project Structure Notes

- New backend file: `alembic/versions/e5f6a7b8c9d0_user_suggestion_polling_columns.py`.
- Changed backend files: `src/newsagent/models/user.py`, `src/newsagent/services/profile.py`, `src/newsagent/api/schemas/profile.py`, `src/newsagent/api/schemas/__init__.py`, `src/newsagent/api/routers/me.py`, `tests/services/test_profile.py`, `tests/api/routers/test_me.py`.
- New test file: `tests/services/test_profile_suggestions.py`.
- No frontend changes. No new dependencies.

### References

- [Source: epics.md#Story-1.6] - acceptance criteria, verbatim.
- [Source: ARCHITECTURE-SPINE.md#AD-5, #AD-7, #AD-3, Dependency-direction] - BackgroundTask/race-guard rule, polling-column/endpoint shape, `profile → suggestions` edge.
- [Source: prd-news-agent-2026-07-21/prd.md#4.3 FR-8] - "triggered after the user has had the opportunity to provide Interest Free-Text," the source of the "which save triggers computation" design note.
- [Source: 1-5-suggestion-source-interface-popularity-fallback.md] - the `suggestions/` package this story is the first real caller of.
- [Source: 1-4-optional-interest-free-text-step-2.md] - established the `field_name`-optional / partial-payload shape of `PUT /me/profile` this story's unconditional trigger relies on.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- Confirmed `d4e5f6a7b8c9` as head with `alembic heads` (read-only) before writing the new revision; re-confirmed `e5f6a7b8c9d0` as the single linear head afterward. Migration **not** applied - no live verification needed for this backend-only, not-yet-user-visible story (see Explicit scope boundary); will ask before running `alembic upgrade head` whenever a story that actually needs it comes up.
- Diagnosed and fixed the identity-map-staleness test gotcha described above in "A real gotcha found and worked around during testing" - isolated it with three standalone scripts (bind-type check, same-thread cross-session visibility, cross-thread cross-session visibility) before concluding the engine-passing mechanism itself was correct and the fixture reuse was the actual cause.
- `PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q` → 218 passed; `mypy src` and `ruff check .` both clean.

### Completion Notes List

**All 5 tasks complete.** 218 backend tests pass (11 added on top of the 207 baseline); `mypy` and `ruff` clean.

- AC #1 - `test_successful_save_sets_pending_and_bumps_seq`/`test_second_successful_save_bumps_seq_again` prove the synchronous, unconditional pending+seq bump directly at the service layer, independent of any BackgroundTask.
- AC #2 - `test_topic_suggestions_before_any_save_is_none` and the end-to-end round-trip test prove `GET /me/topic-suggestions` is a correct, working read path.
- AC #3 - `test_stale_seq_discards_the_result` directly exercises the race guard: a computation whose captured seq no longer matches writes nothing.
- AC #4 - `test_failure_sets_failed_status_and_leaves_topic_ids_untouched` proves the failure path sets `'failed'`, leaves prior `suggested_topic_ids` untouched, and touches zero `UserTopicPreference` rows.
- AC #5 - migration `e5f6a7b8c9d0` created and verified as head; not applied (no live verification required this story).

**Deliberately not done, per Dev Notes' explicit scope boundaries:**
- No frontend work, no live browser verification (Story 1.7 territory).
- No 4-Topic cap (Story 1.7 / AD-9).
- No extra retry layer around the BackgroundTask (Story 1.5's provider-level retry already covers transient errors).

### File List

**New:**
- `alembic/versions/e5f6a7b8c9d0_user_suggestion_polling_columns.py`
- `tests/services/test_profile_suggestions.py`

**Changed:**
- `src/newsagent/models/user.py` (+3 columns, +4 `SUGGESTION_STATUS_*` constants)
- `src/newsagent/services/profile.py` (+`_topic_popularity`, `_compute_and_store_suggestions`, `run_suggestion_computation`, pending/seq bump in `_apply`)
- `src/newsagent/api/schemas/profile.py` (+`TopicSuggestionsOut`)
- `src/newsagent/api/schemas/__init__.py` (+export)
- `src/newsagent/api/routers/me.py` (+`BackgroundTasks` param, +`GET /me/topic-suggestions`)
- `tests/services/test_profile.py`
- `tests/api/routers/test_me.py`

## Change Log

- 2026-07-27: Story 1.6 implemented end-to-end - `User` suggestion-polling columns, synchronous pending/seq bump in `_apply`, the BackgroundTask computation (`_topic_popularity` → `get_suggestion_source().suggest_topics(...)` → race-guarded write), `PUT /me/profile`'s new `BackgroundTasks` scheduling, and `GET /me/topic-suggestions`. 11 new tests (218 total). Migration `e5f6a7b8c9d0` created, not yet applied. Along the way, diagnosed and worked around a test-fixture-only identity-map staleness issue in the end-to-end round-trip test (documented in Dev Notes so it doesn't get mistaken for a real bug in a future story).
- 2026-07-27: Story 1.6 drafted. Key design calls: (1) the pending/seq bump in `_apply` is unconditional across both Step 1 and Step 2 saves; (2) the BackgroundTask receives an `Engine` (`db.get_bind()`), not the request-scoped `Session`; (3) the race-guard check happens immediately before the write, not at function entry.
