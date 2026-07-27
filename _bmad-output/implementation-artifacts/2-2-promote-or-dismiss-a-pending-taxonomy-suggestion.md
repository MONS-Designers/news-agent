---
baseline_commit: 80b1a25
---

# Story 2.2: Promote or dismiss a pending taxonomy suggestion

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an admin,
I want to promote a pending submission into the curated Field/Role list, or dismiss it,
so that I control how the picker's options grow, the same way I already control approved sources.

*Realizes FR7 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.2 FR-7).*

**Closes Epic 2.** Story 2.1 shipped the read path (`GET /admin/taxonomy`, `services/taxonomy.py:list_pending_suggestions`, `TaxonomyQueueView.vue`). This story adds the write path on top of the same data layer: a `PATCH` endpoint, one service function, and Promote/Dismiss controls on the existing view. **No new tables, columns, or migration** — `add_field` and `add_role` already exist and are already idempotent.

## Acceptance Criteria

1. **Given** a pending taxonomy suggestion of kind `field`, **when** I promote it, **then** a new row is created (or an existing matching one reused) in the `fields` table with that name, and the suggestion's `status` becomes `approved`.
2. **Given** a pending taxonomy suggestion of kind `role`, **when** I promote it, **then** a new row is created in the `roles` table, scoped to its `field_id`, and the suggestion's `status` becomes `approved`.
3. **Given** I promote a suggestion, **when** the promotion completes, **then** users who originally typed that text as free text are NOT retroactively migrated onto the newly-curated entry — their stored `field_name`/`role_name` is unchanged (per PRD FR7's consequence).
4. **Given** a pending taxonomy suggestion, **when** I dismiss it instead, **then** its `status` becomes `rejected` and it is removed from the pending list without being added to `fields`/`roles`.
5. **Given** a promoted or dismissed (non-pending) suggestion exists, **when** a user later submits matching "Other" text again, **then** a fresh `pending` row is created rather than mutating the decided one (per AD-8) — it reappears in the admin queue as a new item, not silently lost.
6. **Given** I am not an admin, **when** I attempt to promote or dismiss, **then** I am denied via `require_admin`, matching the existing pattern in `admin.py`.

### Additional acceptance criteria — decisions taken during story creation

7. **Given** a pending suggestion of kind `role` whose `field_id` is `NULL` (a Role typed as "Other" underneath a Field that was itself uncurated "Other" text — this exists in the real dev DB), **when** I try to promote it, **then** the request is refused with `HTTPException(400, detail={"error": "role_has_no_field"})` and **nothing is written** — no `Role` row, and the suggestion stays `pending`. In the queue UI its Promote control is disabled with a short explanation; Dismiss stays available. *(`Role.field_id` is a non-nullable FK, so there is no correct row to write. The admin promotes the parent Field first, after which a resubmission carries a real `field_id`.)*
8. **Given** any pending suggestion, **when** I promote it, **then** I can edit the name that gets written to `fields`/`roles` first; the editable value defaults to the suggestion's display text. The decided suggestion row itself is never rewritten — only the curated `Field`/`Role` name comes from my edit. *(Needed because rows written before the `raw_text` column existed carry only the casefolded `normalized_text`, so promoting them verbatim would mint a lowercase "marine biology" sitting next to "Tech".)*
9. **Given** a suggestion whose `status` is already `approved` or `rejected`, **when** a decision request targets it, **then** it is refused with `HTTPException(400, detail={"error": "suggestion_not_pending"})` and nothing changes — decided rows are terminal (AD-8), never re-decided. An unknown id returns 404, matching `admin.py`'s unknown-source behaviour.

## Tasks / Subtasks

- [x] Task 1: `services/taxonomy.py` — typed failures (AC: #7, #9)
  - [x] 1.1 `class SuggestionNotPendingError(ValueError)` with `self.detail = {"error": "suggestion_not_pending"}`.
  - [x] 1.2 `class RoleHasNoFieldError(ValueError)` with `self.detail = {"error": "role_has_no_field"}`.
  - [x] 1.3 Both follow the precedent set by `preferences.TopicCapExceededError`: a named `ValueError` subclass carrying a **stable `detail` dict**, not a bare string the frontend would have to sniff (Consistency Conventions → "Data & formats"). Read that class before writing these.

- [x] Task 2: `services/taxonomy.py` — `decide_pending_suggestion` (AC: #1, #2, #3, #4, #7, #8, #9)
  - [x] 2.1 Signature: `decide_pending_suggestion(db: Session, suggestion_id: int, *, status: str, name: str | None = None) -> PendingSuggestionView | None`. Returns `None` for an unknown id — same "return None, let the router 404" contract as `sources.set_source_status`, which the router already mirrors.
  - [x] 2.2 If `row.status != STATUS_PENDING` → raise `SuggestionNotPendingError`. Check this **before** any write.
  - [x] 2.3 `status == STATUS_REJECTED` → set `row.status`, commit, return the view. **No `Field`/`Role` row is created** (AC #4).
  - [x] 2.4 `status == STATUS_APPROVED`, `kind == 'field'` → resolve the curated name (Task 2.6), then `add_field(db, resolved_name)`. `add_field` is already get-or-create, which is exactly AC #1's "or an existing matching one reused" — do not reimplement that check.
  - [x] 2.5 `status == STATUS_APPROVED`, `kind == 'role'` → if `row.field_id is None` raise `RoleHasNoFieldError` **before writing anything**; otherwise load the `Field` and call `add_role(db, field, resolved_name)` (already get-or-create, scoped by `(field_id, name)`).
  - [x] 2.6 Resolved name = `(name or row.raw_text or row.normalized_text).strip()`. If it is empty, raise a plain `ValueError` — the router turns that into a 400 string, no special code needed.
  - [x] 2.7 Set `row.status` to the decided value, commit, return the updated `PendingSuggestionView`.
  - [x] 2.8 **Write nothing else.** No touching `User.field_name`/`User.role_name` — AC #3 is satisfied by *absence* of code, and its test exists to keep a future refactor from "helpfully" adding a backfill.
  - [x] 2.9 AC #5 needs **no new code**: `record_pending_suggestion` already scopes its match to `status='pending'`, and the partial unique index already excludes decided rows. It needs a test (Task 5.9), not an implementation.

- [x] Task 3: API layer (AC: #1, #2, #4, #6, #7, #9)
  - [x] 3.1 `api/schemas/taxonomy.py`: `TaxonomySuggestionDecision(BaseModel)` with `status: Literal["approved", "rejected"]` and `name: str | None = None`. `Literal` is what makes a bogus status a 422 without any service-layer check — same trick `SourceStatusUpdate` already uses. Export from `api/schemas/__init__.py` (import block **and** the alphabetically-sorted `__all__`).
  - [x] 3.2 `api/routers/admin_taxonomy.py`: `@router.patch("/taxonomy/{suggestion_id}", response_model=PendingTaxonomySuggestionOut)`. Body → `taxonomy.decide_pending_suggestion(...)`. `None` → `HTTPException(404, "Suggestion not found")`, matching `admin.py`'s wording for an unknown source.
  - [x] 3.3 Catch `taxonomy.SuggestionNotPendingError` and `taxonomy.RoleHasNoFieldError` **before** the generic `except ValueError`, returning `HTTPException(400, detail=error.detail)`. Subclass-before-base ordering matters — `me.py:update_my_preferences` is the working example. Generic `ValueError` → `HTTPException(400, detail=str(error))`.
  - [x] 3.4 `require_admin` already covers this endpoint via the router-level `dependencies=[...]` — do not add it per-route.

- [x] Task 4: Frontend (AC: #1, #2, #4, #7, #8)
  - [x] 4.1 `client.ts`: `decideTaxonomySuggestion(id: number, status: "approved" | "rejected", name?: string): Promise<PendingTaxonomySuggestion>` → `PATCH /admin/taxonomy/{id}`. Mirror `setSourceStatus`'s shape exactly (method, headers, JSON body). Omit `name` from the body when undefined.
  - [x] 4.2 `TaxonomyQueueView.vue`: per row, an editable `<input>` pre-filled with `suggestion.text` (AC #8), plus **Promote** and **Dismiss** `<button>`s. Copy `AdminView.vue`'s Approve/Reject button classes verbatim (dark for the affirmative action, red for the negative) and its `pendingId` single-in-flight guard.
  - [x] 4.3 Promote is `:disabled` when `suggestion.kind === 'role' && suggestion.field_name === null` (AC #7), with a short inline explanation — reuse the existing `context()` helper's "Field not curated" case rather than adding a second source of truth for that condition. Dismiss stays enabled.
  - [x] 4.4 On success remove the row from the local list (it is no longer pending), exactly as `AdminView.vue` does after a status change. On failure show the existing `actionError` banner — **add that banner to this view**, it currently only exists in `AdminView.vue`.
  - [x] 4.5 Real `<button>` elements, native `<input>` — the Consistency Conventions "Frontend controls" rule. No `<div onclick>`.
  - [x] 4.6 Voice/tone: plain complete sentences, no emoji or exclamation marks (EXPERIENCE.md).

- [x] Task 5: Tests (AC: all)
  - [x] 5.1 `tests/services/test_taxonomy.py`: promoting a `field` row creates the `Field` and sets `status='approved'`.
  - [x] 5.2 Promoting a `field` row whose name already exists reuses the existing `Field` (no duplicate) — AC #1's "or an existing matching one reused".
  - [x] 5.3 Promoting a `role` row creates a `Role` under its own `field_id`, not a global one.
  - [x] 5.4 Promoting a `role` row with `field_id=None` raises `RoleHasNoFieldError`, creates **no** `Role`, and leaves `status='pending'` — AC #7.
  - [x] 5.5 Dismissing sets `status='rejected'` and creates neither a `Field` nor a `Role` — AC #4.
  - [x] 5.6 A decided row raises `SuggestionNotPendingError` on a second decision, and nothing changes — AC #9.
  - [x] 5.7 An unknown id returns `None`.
  - [x] 5.8 A `name` override is what lands in `fields`/`roles`, while the suggestion's own `raw_text`/`normalized_text` are left untouched — AC #8. Also cover the no-override path falling back to `raw_text`, then to `normalized_text`.
  - [x] 5.9 **AC #3:** a `User` whose `field_name` is the free text being promoted still has the identical `field_name` afterwards — no retroactive migration.
  - [x] 5.10 **AC #5:** after a decision, calling `record_pending_suggestion` with the same text creates a **new** `pending` row (count 1, not 2), and `list_pending_suggestions` shows it again.
  - [x] 5.11 `tests/api/routers/test_admin_taxonomy.py`: unauthenticated → 401 and non-admin → 403 on `PATCH` (AC #6); promote → 200 with the updated row; dismiss → 200 and the row leaves `GET /admin/taxonomy`; unknown id → 404; bogus status → 422; role-with-no-field → 400 with `{"error": "role_has_no_field"}`; already-decided → 400 with `{"error": "suggestion_not_pending"}`.
  - [x] 5.12 `ruff check`, `mypy`, `vue-tsc` clean; full pytest suite green with no regression against the 233-test baseline.

- [x] Task 6: Live browser verification (AC: #1, #2, #4, #7, #8)
  - [x] 6.1 With an authenticated admin session, promote a `field`-kind row **using the name-edit field** (the real queue holds `marine biology`, a pre-`raw_text` row — promote it as `Marine Biology` and confirm the curated `Field` gets the edited casing).
  - [x] 6.2 Confirm the promoted Field then appears as a real chip in the guided picker's Field row at `/preferences` — the end-to-end point of the whole feature.
  - [x] 6.3 Promote a `role`-kind row that has a Field ("Clinical Data Lead" under Healthcare) and confirm it appears under that Field's Role list, not another's.
  - [x] 6.4 Confirm the Promote control is disabled for "Reef Survey Lead" (role, no Field) and that Dismiss still works on it.
  - [x] 6.5 Dismiss a row and confirm it leaves the queue and creates nothing.
  - [x] 6.6 Confirm a non-admin session gets 403 on `PATCH`.
  - [x] 6.7 **The dev DB's real queue rows are the test data.** Decisions are one-way and there is no un-decide path, so restore whatever was consumed: record each row's prior state first, and afterwards reset decided rows back to `status='pending'` and delete any `Field`/`Role` created purely for verification. **Ask before writing to the dev DB.**

## Dev Notes

### Read these before writing code

- [`src/newsagent/services/taxonomy.py`](../../src/newsagent/services/taxonomy.py) — **the file you extend.** `add_field` and `add_role` are already get-or-create and already commit; `record_pending_suggestion` shows why AC #5 needs no code; `list_pending_suggestions` + `PendingSuggestionView` are Story 2.1's read path, which the new function returns.
- [`src/newsagent/services/preferences.py`](../../src/newsagent/services/preferences.py) `TopicCapExceededError` — the exact precedent for a `ValueError` subclass carrying a stable `detail` dict.
- [`src/newsagent/services/sources.py`](../../src/newsagent/services/sources.py) `set_source_status` — the "return None on unknown id" contract this story copies.
- [`src/newsagent/api/routers/admin.py`](../../src/newsagent/api/routers/admin.py) — the `PATCH` + 404 shape, and `SourceStatusUpdate`'s `Literal` status.
- [`src/newsagent/api/routers/me.py`](../../src/newsagent/api/routers/me.py) `update_my_preferences` — subclass-before-base exception ordering at the router boundary.
- [`frontend/src/views/AdminView.vue`](../../frontend/src/views/AdminView.vue) — Approve/Reject button classes, `pendingId` in-flight guard, `actionError` banner, and remove-row-on-success.
- [`frontend/src/views/TaxonomyQueueView.vue`](../../frontend/src/views/TaxonomyQueueView.vue) — Story 2.1's view, which this story edits in place. Its `context()` helper already encodes the "role with no curated Field" condition AC #7 keys off.
- [`src/newsagent/models/role.py`](../../src/newsagent/models/role.py) — `field_id: Mapped[int]` is **non-nullable**; that fact is the entire reason AC #7 exists.

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-2** — "promote" transitions the row to `approved` **and separately** upserts the real `Field`/`Role`; "dismiss" transitions it to `rejected`. Plain string statuses via the `STATUS_*` constants, no enum, no separate state table, no `promoted`/`dismissed` boolean.
- **AD-8** — decided rows are terminal. A later matching submission creates a fresh `pending` row; nothing here reopens or mutates a decided one.
- **AD-10** — the endpoint lands in `admin_taxonomy.py`. `admin.py` stays untouched.
- **AD-6** — promotion creates curated rows only. Stored `User.field_name`/`role_name` remain plain strings and are never rewritten (AC #3); the match between a stored name and a curated row is a name-lookup at use time, never a stored FK.
- **AD-1** — router validates and delegates; the service owns the rules, the get-or-create idempotency, and the transaction, and raises `ValueError` subclasses the router translates.
- **Consistency Conventions** — `PATCH /admin/taxonomy/{id}` is the shape the spine names verbatim. Domain-identifiable failures carry `detail={"error": "<code>"}`.

### UX compliance

- Stays on `AdminView.vue`'s light Tailwind conventions — explicitly **not** the Hybrid Depth spine (EXPERIENCE.md Information Architecture, UX-DR16). Import nothing from `components/profile-picker/`.

### Explicit scope boundary — do NOT build

- **No retroactive migration/backfill** of users who typed the promoted text (AC #3 — a PRD non-goal, and listed in the spine's Deferred section). Do not add it, do not add a flag for it.
- **No un-promote / un-dismiss** path, and no admin edit of already-curated `Field`/`Role` rows.
- **No migration and no schema change.** If you reach for Alembic, you have misread the story.
- **No automated or LLM-driven curation** — admin stays the sole owner (PRD §4.2 Notes, tracked separately as news-agent#29).
- **No changes to the writer side** (`record_pending_suggestion`, `save_profile`) and none to `admin.py`.
- **No pagination, search, sorting controls, or bulk actions** on the queue.
- **No frontend unit tests** — this project has no frontend test runner.

### Previous story intelligence (Story 2.1 and Epic 1)

- **Live verification catches what the type-checker and the backend suite cannot.** Story 2.1's `context()` helper only exists because the real DB held a `kind='role'` row with `field_id=NULL` that the plan had not imagined — the same row that AC #7 is now written around. Story 1.7 found two frontend wiring bugs the same way. Task 6 is not optional.
- **This story's live verification is destructive in a way Story 2.1's was not.** 2.1 only read; promoting and dismissing consume real queue rows one-way. Task 6.7's record-and-restore step is the mitigation, and **writing to the dev DB needs explicit approval first**.
- Run every backend command with `PYTHONPATH=src` — the editable install still resolves to a stale worktree (Story 1.1 deferred-work note).
- The dev backend must be **restarted** to pick up a new route; the Vite server on 5173 belongs to another session, reloads via HMR, and must be left alone.
- Admin authentication for live verification: mint a session cookie with `itsdangerous.TimestampSigner` over `settings.session_secret` and set it via `document.cookie`. `nomimagnus@gmail.com` is the sole `admins` row. Story 2.1's Debug Log has the exact recipe.
- `ruff` is now pinned at `0.15.22` with an explicit `select` (commit `d60efe5`) — do not bump it or add rule codes as a side effect of this story.

### Project Structure Notes

- Changed backend files: `src/newsagent/services/taxonomy.py`, `src/newsagent/api/schemas/taxonomy.py`, `src/newsagent/api/schemas/__init__.py`, `src/newsagent/api/routers/admin_taxonomy.py`, `tests/services/test_taxonomy.py`, `tests/api/routers/test_admin_taxonomy.py`.
- Changed frontend files: `frontend/src/api/client.ts`, `frontend/src/views/TaxonomyQueueView.vue`.
- No new files. No migration. No new dependencies.

### References

- [Source: epics.md#Story-2.2] — acceptance criteria 1–6, verbatim.
- [Source: prd.md#4.2-FR-7] — promotion consequences, including the explicit no-retroactive-migration assumption.
- [Source: ARCHITECTURE-SPINE.md#AD-1, #AD-2, #AD-6, #AD-8, #AD-10, #Consistency-Conventions, #Deferred].
- [Source: EXPERIENCE.md#Information-Architecture], [Source: epics.md#UX-DR16].
- [Source: 2-1-view-pending-taxonomy-suggestions.md#Debug-Log-References] — the real-data findings, admin-cookie recipe, and dev-environment gotchas this story inherits.
- ACs 7–9 were decided with the user during story creation; the reasoning is recorded inline with each.

## Dev Agent Record

### Agent Model Used

Claude Opus 5

### Debug Log References

- ACs 7–9 were settled with the user before implementation rather than discovered mid-build, because Story 2.1's live verification had already surfaced the underlying data: a `kind='role'` row with `field_id=NULL`, and two rows carrying only casefolded `normalized_text`. Both would have been silent wrong-behaviour bugs if the story had been written from the epics text alone.
- `add_field`/`add_role` already commit internally, so `decide_pending_suggestion` does not wrap the curated-row write and the status transition in one transaction. Acceptable here and left as-is: the promote path's only failure after the curated write is a commit error, and re-promoting a row whose curated entry already exists is idempotent (both helpers are get-or-create). Flagged rather than fixed because changing the commit boundary would mean touching `add_field`/`add_role`, which Epic 1's seeding path also calls — out of this story's scope.
- The two exception classes were initially written above the module's `DEFAULT_FIELDS`/`DEFAULT_ROLES` constants and moved down next to `decide_pending_suggestion`, the only function that raises them, to keep the module's read order intact.
- **Live verification was destructive and ran against the real dev DB with the user's explicit approval**, since promote/dismiss are one-way with no un-decide path. State was recorded first (4 pending suggestions, 5 fields, 20 roles) and restored afterwards: suggestions 1/3/4 reset to `pending`, and the `Marine Biology` Field plus the `Clinical Data Lead` Role deleted. Post-restore state verified identical to the pre-run snapshot.
- The backend was restarted so the new `PATCH` route would register (`uvicorn` runs without `--reload`). The Vite server on 5173 belongs to another session and was left running — HMR picked up the frontend changes.
- **AC #3 could not be observed live**: no user in the dev DB has a `field_name` matching any queued suggestion, so there was nothing to observe *not* changing. It is covered by `test_promotion_does_not_migrate_earlier_submitters`, which seeds exactly that user.

### Completion Notes List

**All 6 tasks complete.** 254 backend tests pass (21 added on top of the 233 baseline); `ruff check`, `mypy` (63 files) and `vue-tsc` all clean. No migration, no new files, no new dependencies, no changes to `admin.py` or to the writer side.

Per acceptance criterion, live-verified in the browser as an authenticated admin against the real dev DB:

- **AC #1 + #8** — promoted the `marine biology` row (a pre-`raw_text` row) after editing the name to `Marine Biology`. The curated `Field` was created with the **edited** casing, the suggestion moved to `approved` and left the queue, and its own `normalized_text` was left untouched — the queue row stays a record of what the user typed.
- **AC #2** — promoted `Clinical Data Lead`; exactly one `Role` was created, with `field_id=3` (Healthcare) and not under any other Field.
- **End-to-end (Task 6.2/6.3)** — `GET /me/fields` then listed `Marine Biology`, `GET /me/fields/3/roles` listed `Clinical Data Lead`, and `Marine Biology` rendered as a real selectable Field chip in the guided picker at `/preferences`. That closes the whole feature loop: a user types "Other" → an admin promotes it → it becomes a curated option for everyone.
- **AC #4** — dismissed `Reef Survey Lead` from the UI: status became `rejected`, the row left the queue, and the `fields`/`roles` counts were unchanged (6 and 21, exactly as the two promotions had left them).
- **AC #6** — `PATCH` with a non-admin session cookie returned **403**.
- **AC #7** — the orphan-role row rendered with Promote and the name input disabled plus an inline explanation, while Dismiss stayed enabled and worked. `PATCH` against it returned **400 `{"error": "role_has_no_field"}`** and wrote nothing.
- **AC #9** — re-deciding an already-approved row returned **400 `{"error": "suggestion_not_pending"}`**; an unknown id returned **404**.
- **AC #5** is verified by test only (`test_resubmitting_decided_text_opens_a_fresh_row`) — reproducing it live would require driving a second user through the guided picker's "Other" flow, which the unit test covers directly and deterministically.

No browser console errors and no server errors throughout.

### File List

**Modified**
- `src/newsagent/services/taxonomy.py`
- `src/newsagent/api/schemas/taxonomy.py`
- `src/newsagent/api/schemas/__init__.py`
- `src/newsagent/api/routers/admin_taxonomy.py`
- `tests/services/test_taxonomy.py`
- `tests/api/routers/test_admin_taxonomy.py`
- `frontend/src/api/client.ts`
- `frontend/src/views/TaxonomyQueueView.vue`

## Change Log

- 2026-07-27 — Story 2.2 implemented, closing Epic 2: `PATCH /admin/taxonomy/{id}` plus `services/taxonomy.py:decide_pending_suggestion`, and Promote/Dismiss controls with an editable curated name on the existing queue view. 21 tests added. No schema change.
