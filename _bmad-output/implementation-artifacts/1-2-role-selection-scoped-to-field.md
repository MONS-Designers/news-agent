---
baseline_commit: cd36a24aa1430437fcd3e699e85a98700a89e146
---

# Story 1.2: Role selection scoped to Field

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to pick my Role once I've picked a Field,
so that my profile reflects my actual job, not just my industry.

*Realizes FR2 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.1).*

## Acceptance Criteria

1. **Given** I have selected a Field in Step 1, **when** the Role section renders, **then** I see Role chips scoped to that Field (from the curated `roles` table, `field_id`-scoped) plus "Other".
2. **Given** no Field is selected yet, **when** I view the Role section, **then** it shows a "Pick a field first" placeholder state (no chips, no "Other").
3. **Given** I have a Role selected, **when** I change my Field, **then** my Role selection clears (including any typed "Other" text) and the Role row re-renders scoped to the new Field.
4. **Given** I select "Other" for Role, **when** I type a value and it saves, **then** it is recorded as `User.role_name` and as a `PendingTaxonomySuggestion` row (`kind='role'`, `field_id` set to the curated Field matching my `field_name`, same pending-scoped upsert as Field).
5. **Given** my Field is itself an uncurated "Other" value, **when** I submit an "Other" Role, **then** the `PendingTaxonomySuggestion` is still created with `kind='role'` and `field_id = NULL` — an unmatchable Field must not lose the Role submission.
6. **Given** Field is selected but Role is not, **when** I view Continue, **then** it remains disabled both visually and via `aria-disabled` (the gate now checks Field **and** Role).
7. **Given** both Field and Role are selected, **when** I check Continue, **then** it becomes enabled, and clicking it saves Field + Role in a **single** `PUT /me/profile` request.
8. **Given** a Role chip or the "Other" input, **when** either renders, **then** it is a real `<button>` (with `aria-pressed`) or a native `<input>` — never `<div onclick>` — same accessibility baseline as Story 1.1's Field chips.
9. **Given** a save that sets both Field and Role, **when** any part of it fails, **then** nothing is persisted — the profile write and both taxonomy suggestion upserts share one transaction/commit.
10. This story ships a new Alembic revision adding the `roles` table (FK to `fields`, unique per `(field_id, name)`) and the `User.role_name` column.

## Tasks / Subtasks

- [x] Task 1: `Role` model + migration (AC: #1, #10)
  - [x] 1.1 Add `Role` model (`src/newsagent/models/role.py`): `id`, `field_id` (FK → `fields.id`, **not null**), `name`, `created_at` — mirrors `Field`'s shape (`models/field.py`) plus the FK. Add `__table_args__ = (UniqueConstraint("field_id", "name", name="uq_roles_field_name"),)` and a plain (non-unique) index on `name`. **Do not** mark `name` globally unique — "Researcher" legitimately exists under both Healthcare and Education.
  - [x] 1.2 Add `User.role_name: str | None` — plain string, **not a foreign key** (AD-6, same rule as `field_name`).
  - [x] 1.3 Register `Role` in `src/newsagent/models/__init__.py` (import + `__all__`), alongside the existing `Field` / `PendingTaxonomySuggestion` entries.
  - [x] 1.4 New Alembic revision, `down_revision = "a1b2c3d4e5f6"` (current head — re-confirm with `alembic heads` before writing, read-only). Creates `roles`, adds `users.role_name`. Follow `alembic/versions/a1b2c3d4e5f6_field_and_pending_taxonomy_suggestion.py`'s style exactly (hand-written `op.create_table` / `op.add_column`, `server_default=sa.text("(CURRENT_TIMESTAMP)")` for `created_at`, matching `downgrade()`).
  - [x] 1.5 **Do not run `alembic upgrade head`.** Applying a migration to the dev DB requires explicit user approval (project data-safety policy). Verify with `alembic heads` / `alembic check`-style read-only commands only, and note in Completion Notes that the dev DB is still at `a1b2c3d4e5f6`.

- [x] Task 2: `services/taxonomy.py` — Role primitives + extracted suggestion upsert (AC: #1, #4, #5)
  - [x] 2.1 `add_role(db, field: Field, name: str) -> tuple[Role, bool]` — get-or-create by `(field_id, name)`, mirroring `add_field` / `services/sources.py:add_source`. Commits (seeding path).
  - [x] 2.2 `list_roles(db, field_id: int) -> list[Role]` — Roles for one Field, ordered by name (same query style as `list_fields`).
  - [x] 2.3 `find_field_by_name(db, name: str) -> Field | None` — the AD-6 name-lookup-at-use-time. Compare `normalize_taxonomy_text()` on both sides in Python over `list_fields(db)` (the curated list is tiny — a handful of rows); do **not** rely on DB collation or `LOWER()` SQL, which behaves differently across SQLite/Postgres.
  - [x] 2.4 Extract the `PendingTaxonomySuggestion` upsert currently inlined in `record_field_selection` into `record_pending_suggestion(db, *, kind: str, field_id: int | None, text: str) -> None`. Same rules as today: normalize the text, match only rows with `status == STATUS_PENDING` **and** the same `kind` **and** the same `field_id` (`.is_(None)` when None), increment `submission_count` on a match, otherwise insert a new pending row. **This function must NOT commit** — it only `db.add`s / mutates. The caller (Task 3) owns the single commit (AC #9).
  - [x] 2.5 `DEFAULT_ROLES: dict[str, list[str]]` + `seed_default_roles(db) -> SeedReport` — mirrors `seed_default_sources`'s two-level shape: get-or-create the Field, then each Role under it. Extend `SeedReport` with `roles_created`. Seed content (from the approved mockup, `mockups/flow-hybrid-depth-steps.html`, and matching `DEFAULT_FIELDS`):
    - Tech: Software Engineer, Product Manager, Data Scientist, Founder / Exec
    - Finance: Analyst, Portfolio Manager, Accountant, Founder / Exec
    - Healthcare: Physician, Nurse, Researcher, Administrator
    - Education: Teacher, Researcher, Administrator, Student
    - Design: Product Designer, Researcher, Art Director, Student
  - [x] 2.6 New `seed-roles` CLI subcommand in `cli.py`, alongside `seed-fields` / `seed-sources`. Idempotent (get-or-create), safe to re-run. Do **not** rename or fold `seed-fields` into it.

- [x] Task 3: `services/profile.py` (NEW) — single profile-save entry point (AC: #4, #5, #7, #9)
  - [x] 3.1 Create `src/newsagent/services/profile.py` per the architecture's Structural Seed. **Move** `record_field_selection` out of `taxonomy.py` and replace it with `save_profile(db, user, *, field_name: str, field_is_other: bool, role_name: str | None, role_is_other: bool) -> User`. `taxonomy.py` keeps only taxonomy primitives (add/list/find/upsert/seed); `profile.py` owns profile-write orchestration. Dependency direction is `profile → taxonomy` (never the reverse) per the architecture's Dependency direction diagram.
  - [x] 3.2 `save_profile` behavior, in order, with **exactly one `db.commit()` at the end** followed by `db.refresh(user)`:
    1. `user.field_name = field_name`
    2. if `field_is_other` → `record_pending_suggestion(kind=KIND_FIELD, field_id=None, text=field_name)`
    3. if `role_name` is not None → `user.role_name = role_name`
    4. if `role_name` is not None and `role_is_other` → resolve `field = find_field_by_name(db, field_name)`; `record_pending_suggestion(kind=KIND_ROLE, field_id=field.id if field else None, text=role_name)` (AC #5 — a `None` field_id is valid, not an error)
  - [x] 3.3 `role_name=None` means "not submitted in this request" — leave `user.role_name` untouched. An empty/whitespace-only `role_name` is invalid input: raise `ValueError` (router → `HTTPException(400)`, AD-1). Same for a blank `field_name`.
  - [x] 3.4 Delete `record_field_selection` from `taxonomy.py` once callers are moved — do not leave a duplicate write path (that is exactly the "two shapes for the same operation" failure AD-6/AD-8 exist to prevent).

- [x] Task 4: API — roles endpoint + extended profile contract (AC: #1, #2, #4, #7)
  - [x] 4.1 `RoleOut` (`id: int`, `name: str`) in `api/schemas/taxonomy.py`, next to `FieldOut`. Export from `api/schemas/__init__.py`.
  - [x] 4.2 Extend `api/schemas/profile.py`:
    - `ProfileUpdateIn`: `field_name: str`, `field_is_other: bool = False`, `role_name: str | None = None`, `role_is_other: bool = False`
    - `ProfileOut`: `field_name: str | None`, `role_name: str | None`
    - **Rename** the existing `is_other` → `field_is_other`. The asymmetric `is_other` / `role_is_other` pair is a real defect in a contract this story extends; the field is one commit old and has no external consumers. Update the Story 1.1 router tests and `client.ts` accordingly — do not leave both names accepted.
  - [x] 4.3 `GET /me/fields/{field_id}/roles` → `list[RoleOut]` in `api/routers/me.py`, `require_user`, thin (delegates to `taxonomy.list_roles`). An unknown `field_id` returns `[]`, not 404 — this is a list endpoint and the empty case is a legitimate UI state ("this Field has no curated Roles yet"), so the frontend needs no error branch.
  - [x] 4.4 Point `PUT /me/profile` at `profile.save_profile` (was `taxonomy.record_field_selection`), passing all four values, and wrap the call in `try/except ValueError → HTTPException(400, detail=str(error))` — matching `update_my_preferences`'s existing shape in the same file.

- [x] Task 5: Frontend — shared `ChipRow` + Role row (AC: #1, #2, #3, #6, #7, #8)
  - [x] 5.1 New `frontend/src/components/profile-picker/ChipRow.vue` — presentational chip row extracted from `FieldStep.vue`'s existing markup + CSS (chips, `chip-other`, `other-input`, `block-head`). Two call sites in this story (Field, Role), so this is real reuse, not speculation. Use Vue 3.5 `defineModel` for three-way binding:
    - `defineModel<string | null>('selectedName')`, `defineModel<boolean>('isOther')`, `defineModel<string>('otherText')`
    - props: `stepNum` (string), `label` (string), `options` ({ id: number; name: string }[]), `otherPlaceholder` (string), `placeholderText` (string | null — when non-null, render *only* this dimmed placeholder instead of any chips)
    - Move the chip / other-input `<style scoped>` rules from `FieldStep.vue` into this component; leave `.nav-row` / `.btn` styles with the step component that owns Continue.
    - Keep real `<button type="button" :aria-pressed>` for every chip and a native `<input>` for "Other" (AC #8, architecture Consistency Conventions → "Frontend controls").
  - [x] 5.2 Rename `FieldStep.vue` → `AboutYouStep.vue` (it now owns Step 1's Field + Role; Story 1.3 adds Experience to this same component). It renders two `<ChipRow>`s and owns: `fields`, `roles`, both selections, the Continue gate, and the save call.
  - [x] 5.3 Role row state:
    - `placeholderText = "Pick a field first"` while no Field is selected (AC #2)
    - when a **curated** Field is selected → fetch `listRoles(field.id)` and render those chips + "Other"
    - when Field is **"Other"** (no curated id) → render "Other" only (no fetch, no placeholder); the user's typed Field has no curated Roles by definition
    - watch the selected Field; on any change clear `roleName`, `roleIsOther`, `roleOtherText` and re-fetch (AC #3)
  - [x] 5.4 Continue gate: `canContinue = fieldSatisfied && roleSatisfied`, where each is "a curated chip is selected, **or** Other is selected and its trimmed text is non-empty". Keep the existing `:aria-disabled` + `.disabled` + `pointer-events:none` + in-handler guard pattern (AC #6).
  - [x] 5.5 On Continue, one call: `updateMyProfile({ fieldName, fieldIsOther, roleName, roleIsOther })` (AC #7). Surface a save failure to the user instead of swallowing it — the current handler's bare `try/finally` silently discards errors; add a visible error line next to Continue (reuse the existing `.load-error` style) and do **not** advance the step on failure.
  - [x] 5.6 `frontend/src/api/client.ts`: add `RoleOption` type, `listRoles(fieldId: number): Promise<RoleOption[]>` → `GET /me/fields/${fieldId}/roles`, extend `Profile` with `role_name: string | null`, and change `updateMyProfile` to take a single object argument (four positional params, two of them booleans, is a call-site footgun). Same `request` / `ApiError` pattern as the existing helpers.
  - [x] 5.7 `ProfilePickerShell.vue`: update the import and tag (`FieldStep` → `AboutYouStep`). No other change — the stepper, orbs, grain, `prefers-reduced-motion` handling and `.stagger` entrance stay exactly as they are.

- [x] Task 6: Tests (AC: all)
  - [x] 6.1 `tests/services/test_profile.py` (NEW) — move the four `record_field_selection` tests out of `test_taxonomy.py` and retarget them at `save_profile`, then add: curated Role saves `role_name` with **zero** suggestions; "Other" Role creates `kind='role'` with `field_id` = the curated Field's id; "Other" Role under an "Other" Field creates `kind='role'` with `field_id=None` (AC #5); a repeat matching "Other" Role increments `submission_count`; a matching **approved** role row is NOT reused (a fresh pending row is created — AD-8); `role_name=None` leaves an existing `user.role_name` untouched; blank `role_name` raises `ValueError`.
  - [x] 6.2 `tests/services/test_taxonomy.py` — keep the existing Field/normalize/seed tests; add `add_role` idempotency, same role name under two different Fields coexisting, `list_roles` scoping + ordering, `find_field_by_name` matching case/whitespace variants and returning `None` for an unmatched name, `seed_default_roles` idempotency.
  - [x] 6.3 `tests/api/routers/test_me.py` — `GET /me/fields/{id}/roles`: 401 unauthenticated, scoped result for a seeded Field, `[]` for an unknown id. `PUT /me/profile`: with a curated Role, with an "Other" Role (asserting the suggestion's `kind`/`field_id`), and 400 on a blank `role_name`. Update the existing Story 1.1 tests for the `is_other` → `field_is_other` rename and the new `role_name` key in `ProfileOut`'s response body.
  - [x] 6.4 `tests/models/test_models_smoke.py` — extend in place with a `Role` row and its count assertion, matching how `Field` was added.
  - [x] 6.5 No frontend test runner exists in this project (confirmed in Story 1.1 — do not add one). Verify with `cd frontend && npm run type-check` (`vue-tsc --noEmit`, must be clean). Live browser verification against the dev server is **blocked** this story: the new migration cannot be applied without explicit approval (Task 1.5), so `users.role_name` and `roles` won't exist in the dev DB. Ask for approval to run `alembic upgrade head` if live verification is wanted; otherwise state plainly in Completion Notes that only static + backend-test verification was done.
  - [x] 6.6 Full suite green: `.venv/Scripts/python.exe -m pytest -q` (133 tests passing at baseline — none may regress), plus `mypy` and `ruff` clean.

## Dev Notes

### Read these before writing code

- [`src/newsagent/services/taxonomy.py`](../../src/newsagent/services/taxonomy.py) — the file you extend and partly empty out. `record_field_selection` there is the exact upsert logic Task 2.4 extracts; `add_field` / `list_fields` are the shape `add_role` / `list_roles` must mirror.
- [`src/newsagent/services/sources.py`](../../src/newsagent/services/sources.py) — `seed_default_sources`'s two-level (Topic → Sources) seeding shape is precisely what `seed_default_roles` (Field → Roles) copies.
- [`src/newsagent/models/field.py`](../../src/newsagent/models/field.py) and [`models/pending_taxonomy_suggestion.py`](../../src/newsagent/models/pending_taxonomy_suggestion.py) — `Role` mirrors `Field`; `KIND_ROLE` / `STATUS_PENDING` constants already exist, reuse them, don't redefine.
- [`src/newsagent/api/routers/me.py`](../../src/newsagent/api/routers/me.py) — 45 lines, all four existing endpoints. `update_my_preferences` shows the `ValueError → HTTPException(400)` translation Task 4.4 copies.
- [`alembic/versions/a1b2c3d4e5f6_field_and_pending_taxonomy_suggestion.py`](../../alembic/versions/a1b2c3d4e5f6_field_and_pending_taxonomy_suggestion.py) — current head; the new revision's direct parent and style template.
- [`frontend/src/components/profile-picker/FieldStep.vue`](../../frontend/src/components/profile-picker/FieldStep.vue) — the component being split and renamed. Its chip CSS moves to `ChipRow.vue` verbatim; don't restyle it.
- [`mockups/flow-hybrid-depth-steps.html`](../planning-artifacts/ux-designs/ux-news-agent-2026-07-21/mockups/flow-hybrid-depth-steps.html) `renderRoles()` — the approved Field→Role behavior (clear-on-field-change, per-chip stagger delay, "Other" appended last). Copy the *behavior*; its `<div onclick>` markup is an explicit anti-pattern here (AC #8).

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-1** — routers stay thin: `me.py` validates and delegates; `services/profile.py` and `services/taxonomy.py` own the rules and raise `ValueError`. No new layer.
- **AD-4** — Alembic is the *only* schema-change mechanism here. 9 revisions exist and are actively used; `create_all` is not how this project manages schema.
- **AD-6** — `User.role_name` is a plain string, never an FK to `Role`. Resolving a stored name against the curated list (Task 2.3) is a normalized name-lookup at use time, never a stored relationship.
- **AD-8** — the pending upsert stays scoped to `status='pending'`, now keyed on `(kind, field_id, normalized_text)`. `kind='role'` rows carry a `field_id`; `kind='field'` rows carry `NULL`. Epic 2's admin queue reads these rows unchanged — getting the `field_id` wrong here surfaces as a mis-grouped admin queue later.
- **Consistency Conventions → Frontend controls** — every chip is a real `<button aria-pressed>`; a `<div onclick>` is a regression, not a shortcut.

### Scope boundaries — deliberately NOT in this story

- **Experience Bucket** and the three-way Continue gate → Story 1.3. This story's gate checks Field + Role only.
- **`suggestions/` package, `suggest_roles`, the Suggestion Source interface** → Story 1.5. Roles come from the curated `roles` table here, full stop. Do not create `newsagent/suggestions/` or a `NEWSAGENT_SUGGESTION_PROVIDER` setting.
- **Admin promote/dismiss of pending Role suggestions** → Epic 2. This story only *writes* the rows.
- **Steps 2 and 3** stay placeholders in `ProfilePickerShell.vue`.
- **Responsive/mobile layout** (news-agent#30) and the **full accessibility audit** including contrast verification (news-agent#31) remain open follow-ups, not this story's job beyond the semantic-element baseline.

### Known drift, resolved

The PRD's FR-2 says Role options come from the Suggestion Source and that "until the Suggestion Source is LLM-connected, Role option generation produces no curated options." The epics' Story 1.2 and the architecture's `models/role.py` instead specify a curated, admin-owned `roles` table. **Resolution (user decision, 2026-07-26): the curated `roles` table is the source of Role options for this story, and it ships seeded with `DEFAULT_ROLES`** — so a user sees real chips from day one rather than only "Other." The Suggestion Source layers on top later (Story 1.5) without changing this table or the API contract. Story 1.5 must not be written as if the Role list is empty.

### Project Structure Notes

- New backend files: `models/role.py`, `services/profile.py`, one new `alembic/versions/*.py`, `tests/services/test_profile.py`.
- Changed backend files: `models/__init__.py`, `models/user.py`, `services/taxonomy.py` (gains Role primitives + the extracted upsert, loses `record_field_selection`), `api/schemas/profile.py`, `api/schemas/taxonomy.py`, `api/schemas/__init__.py`, `api/routers/me.py`, `cli.py`, `tests/services/test_taxonomy.py`, `tests/api/routers/test_me.py`, `tests/models/test_models_smoke.py`.
- New frontend files: `frontend/src/components/profile-picker/ChipRow.vue`.
- Renamed frontend files: `FieldStep.vue` → `AboutYouStep.vue` (use `git mv` so the rename is visible in the diff).
- Changed frontend files: `ProfilePickerShell.vue`, `frontend/src/api/client.ts`.
- No changes to `frontend/src/style.css` — Hybrid Depth stays component-scoped, per Story 1.1.
- No new dependencies. The architecture's Stack section is explicit: this feature adds none.

### References

- [Source: epics.md#Story-1.2] — acceptance criteria, verbatim (AC #1–#4, #6–#8, #10).
- [Source: prd-news-agent-2026-07-21/prd.md#4.1] — FR-2 and its testable consequences (Field-scoped options, clear-on-Field-change, "Other" → Pending Taxonomy Suggestion, "Other" satisfies the gate).
- [Source: ARCHITECTURE-SPINE.md#AD-1, #AD-4, #AD-6, #AD-8, #Structural-Seed, #Dependency-direction] — layering, migration convention, `role_name` shape, upsert shape, `services/profile.py` placement.
- [Source: EXPERIENCE.md#Component-Patterns] — "Role chip row … Empty/placeholder state ('Pick a field first') shown before any Field is chosen"; [#Edge-Cases] — "Field changed after Role was set → Role selection silently clears".
- [Source: 1-1-guided-flow-shell-field-selection.md] — established patterns this story extends, plus the `PYTHONPATH=src` local-environment gotcha (a stale editable install points `python -m newsagent.cli` at another worktree).

## Dev Agent Record

### Agent Model Used

Claude Opus 5

### Debug Log References

- Confirmed `a1b2c3d4e5f6` as head with `alembic heads` (read-only) before writing the new revision, and re-checked `alembic history` afterwards to confirm a single linear head.
- Ran everything with `PYTHONPATH=src`: the editable `newsagent` install still resolves to `.claude/worktrees/github-issues-review-6e1f99` (pre-existing, recorded in `deferred-work.md`).
- `alembic upgrade head` was run **with explicit user approval**, together with `seed-roles` (0 new fields, 20 new roles). Dev DB is now at `b2c3d4e5f6a7`.
- Live browser verification required freeing ports 8000 and 5173, both held by an earlier session's dev servers. The backend on 8000 was serving Story 1.1 code (its `/openapi.json` had no `/me/fields/{field_id}/roles`), so verifying against it would have proved nothing. Killed both with user approval and started this session's own servers.
- Authenticated the browser with a locally-minted session cookie (itsdangerous, signed with the dev-only `NEWSAGENT_SESSION_SECRET` already in `.env`) for the throwaway user `verify-story-1-1@example.com` (id=2), since Google OAuth is not configured locally. Deliberately used the throwaway user, not the real dogfood row.
- One DB row displays as `?????` in the Windows console; dumping codepoints confirmed it is intact Hebrew text (U+05DC U+05D7 U+05D9 U+05DC U+05D9), a console rendering artifact and not corruption.
- No screenshot captured: the Browser pane was not displayed, so the page was not compositing frames. Verification is structural (`read_page`, DOM/JS assertions), network (`PUT → 200`), and direct DB inspection.

### Completion Notes List

**All 6 tasks complete.** 176 backend tests pass (43 added on top of the 133 baseline); `mypy` and `ruff` clean; `vue-tsc --noEmit` clean.

**Live-verified in the browser, per acceptance criterion:**

- AC #1 — selecting "Tech" populated Role chips scoped to it (Data Scientist, Founder / Exec, Product Manager, Software Engineer) plus "Other".
- AC #2 — with no Field chosen, the Role row rendered only the "Pick a field first" hint, no chips.
- AC #3 — with "Software Engineer" selected, switching Field to Healthcare cleared the Role (only "Healthcare" left with `aria-pressed="true"`), re-rendered Healthcare's roles, and re-disabled Continue.
- AC #4 — "Other" Role "Clinical Data Lead" under curated Healthcare persisted `User.role_name` and a `kind='role'` suggestion with `field_id=3` (Healthcare).
- AC #5 — "Other" Field ("Marine Biology") plus "Other" Role ("Reef Survey Lead") persisted the role suggestion with `field_id=NULL`, submission intact. The pre-existing pending `marine biology` row incremented to `submission_count=2` rather than duplicating, confirming the AD-8 upsert.
- AC #6 — Continue carried the native `disabled` attribute and could not receive focus (`element.focus()` left `document.activeElement` on `<body>`).
- AC #7 — with both rows satisfied Continue enabled, and a single `PUT /api/me/profile` returned 200. Zero console errors.
- AC #8 — every chip is a real `<button type="button">` with `aria-pressed`; both "Other" inputs are native `<input type="text">` with `aria-label`.
- AC #9 — covered by test, not browser: `test_rejected_save_persists_nothing` asserts a rejected save leaves no row.
- AC #10 — migration applied cleanly; `alembic current` reports `b2c3d4e5f6a7`.

**Story 1.1 review findings folded in** (all touch files this story rewrote; folding them in avoided a later conflicting edit):

- *Patch 120* — the swallowed save failure. `onContinue` now catches and surfaces a visible message, and does not advance the step on failure.
- *Patch 121 / 125* — input validation and raw storage. Names are trimmed, blank and over-`MAX_NAME_LENGTH` input rejected, and a **curated** pick is stored with its canonical spelling so the AD-6 name-lookup keeps matching.
- *Patch 124* — normalization now strips Unicode category `Cf` (the invisible RLM/LRM marks a Hebrew IME inserts) and unifies NFC/NFD. Story 1.2 pushes free-text Role through the same pipe, doubling the exposure in a Hebrew-first product.
- *Patch 126* — accessibility: `:focus-visible` rings on every chip, the "Other" inputs and Continue; `outline: none` removed; Continue uses native `disabled` so it leaves the tab order instead of `pointer-events: none`.
- *Patch 129* — dropped the tautological `assert ... is not None` and added negative-path coverage (uncurated name claimed as curated, blank input, identical-error-message assertion).
- *Patch 132* — `selectOther()` clears stale `otherText`, so switching curated → Other no longer resubmits a previous value.
- *Patch 133* — `__all__` in `api/schemas/__init__.py` restored to alphabetical order.

**Decisions resolved during this story** (three of Story 1.1's five open "Decisions needed"):

- *Client-declared `is_other` bypass (HIGH).* Resolved as option (a): the flags are treated as claims, and a request asserting a curated pick is rejected unless the name resolves against the curated list — so free text can no longer be stored as "curated" while skipping the review queue. Every rejection returns one fixed message (`Invalid profile selection.`), asserted identical across causes by test, so a probe cannot enumerate the curated list. Option (b) — ignoring the flag and deriving it server-side — subsumes this and additionally normalizes "Other" text that duplicates a curated entry; worth revisiting, not implemented here.
- *No DB backstop for AD-8 (MEDIUM).* Added a partial unique index (`WHERE status='pending'`) plus a single `IntegrityError` retry in `save_profile`. **The obvious form of this index would not have worked:** `kind='field'` rows always carry `field_id=NULL`, and NULLs never compare equal in a unique index, so a plain three-column index would have silently protected Role rows only. The index is on `(kind, COALESCE(field_id, -1), normalized_text)`. Three tests pin this: field-row uniqueness, role-row uniqueness, and decided rows staying exempt.
- *Lost display casing (MEDIUM).* Added `raw_text`, populated on create and left untouched on increment so the first submitter's spelling stays stable while the row sits in the queue. Nullable, because rows written before the column genuinely have no display form (the two Story 1.1 rows show `raw=None`).

**Deliberately not done:**

- *PUT → PATCH (MEDIUM, Story 1.1 review).* Left as `PUT`. The blocking half — a contract that could not express "Field curated, Role Other" — is resolved by splitting `is_other` into `field_is_other` / `role_is_other`. What remains is verb semantics only (an omitted `role_name` means "leave it alone", which is PATCH-shaped), not a functional gap. Raised with the user, who chose to leave it.
- Experience Bucket and the three-way gate (Story 1.3), the `suggestions/` package (Story 1.5), admin promote/dismiss (Epic 2), responsive layout (news-agent#30).

**Concurrency note:** another agent session is active in this working tree. It added the "Review Findings" section to Story 1.1's file and created `_bmad-output/implementation-artifacts/deferred-work.md` mid-session, and `users.role_name` for user id=1 was already populated before this story's flow was exercised. Nothing was lost, but the two sessions are editing overlapping files.

### File List

**New:**
- `src/newsagent/models/role.py`
- `src/newsagent/services/profile.py`
- `alembic/versions/b2c3d4e5f6a7_role_and_user_role_name.py`
- `tests/services/test_profile.py`
- `frontend/src/components/profile-picker/ChipRow.vue`

**Renamed:**
- `frontend/src/components/profile-picker/FieldStep.vue` → `AboutYouStep.vue` (rewritten: owns both rows, the gate and the save)

**Changed:**
- `src/newsagent/models/__init__.py` (+ `Role` export)
- `src/newsagent/models/user.py` (+ `role_name`)
- `src/newsagent/models/pending_taxonomy_suggestion.py` (+ `raw_text`, + partial unique index)
- `src/newsagent/services/taxonomy.py` (+ Role primitives, `find_field_by_name`, `find_role_by_name`, `record_pending_suggestion`, `DEFAULT_ROLES`, `seed_default_roles`; − `record_field_selection`; Unicode-aware normalization)
- `src/newsagent/api/routers/me.py` (+ `GET /me/fields/{field_id}/roles`, `PUT /me/profile` → `profile.save_profile` with `ValueError` → 400)
- `src/newsagent/api/schemas/profile.py` (`is_other` → `field_is_other`, + `role_name`, + `role_is_other`, + `role_name` on `ProfileOut`)
- `src/newsagent/api/schemas/taxonomy.py` (+ `RoleOut`)
- `src/newsagent/api/schemas/__init__.py` (+ `RoleOut`, `__all__` re-alphabetized)
- `src/newsagent/cli.py` (+ `seed-roles`)
- `frontend/src/components/profile-picker/ProfilePickerShell.vue` (import/tag rename only)
- `frontend/src/api/client.ts` (+ `RoleOption`, `listRoles`, `ProfileUpdate`; `updateMyProfile` takes one object)
- `tests/services/test_taxonomy.py`
- `tests/services/test_profile.py`
- `tests/api/routers/test_me.py`
- `tests/models/test_models_smoke.py`

## Change Log

- 2026-07-26: Story 1.2 implemented end-to-end — `Role` model/table, `User.role_name`, Role primitives + Unicode-aware normalization in `services/taxonomy.py`, new `services/profile.py` owning the profile-save transaction, `GET /me/fields/{field_id}/roles`, extended `PUT /me/profile`, `seed-roles` CLI, shared `ChipRow.vue` + `AboutYouStep.vue`. 43 new tests (176 total). Migration `b2c3d4e5f6a7` applied to the local dev DB with explicit approval. Live-verified in the browser against a real seeded DB and authenticated session.
- 2026-07-26: Folded in eight Story 1.1 code-review patches touching the same files, and resolved three of its five open decisions — server-side curated-name enforcement with a single fixed error message, a partial unique index keyed on `COALESCE(field_id, -1)` as the AD-8 backstop, and a `raw_text` column preserving submission casing.
- 2026-07-26: Story 1.2 drafted. Three decisions taken with the user before drafting: (1) seed `DEFAULT_ROLES` rather than shipping an empty `roles` table, resolving the PRD/epics drift above; (2) create `services/profile.py` per the architecture's Structural Seed and move profile-save orchestration out of `taxonomy.py`; (3) extract a shared `ChipRow.vue` used by both the Field and Role rows rather than duplicating the chip markup and CSS.
</content>
</invoke>
