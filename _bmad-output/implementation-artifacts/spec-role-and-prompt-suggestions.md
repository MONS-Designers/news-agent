---
title: 'Wire LLM-backed Role suggestions (merged with DB) and Suggested Prompts'
type: 'feature'
created: '2026-07-28'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '0f9154cd40a2e787de197ad6b9ca755229f1898e'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** `SuggestionSource.suggest_roles`/`suggest_prompts` exist on the interface and work (verified in a prior session) but nothing in the app calls them. Role selection (Step 1) only ever queries the DB-curated `Role` list per Field (Story 1.2); the Interests step (Step 2) shows no example prompts at all (FR-5 unimplemented).

**Approach:** On Field selection, merge DB-curated Roles with LLM-invented new ones (context-aware, capped at exactly 10, DB-first) into the existing Role picker, synchronously. On reaching the Interests step, fetch up to 3 LLM-generated example prompts using the user's already-saved Field/Role/Experience (no new state-lifting needed - Step 1 already persisted them). A role the user newly picks that isn't yet curated queues into the existing `PendingTaxonomySuggestion` admin-review flow, exactly like today's "Other" text.

## Boundaries & Constraints

**Always:**
- `suggestions/` stays DB-free (AD-3) - `services/taxonomy.py` queries curated Roles and passes names into `suggest_roles` as plain data (mirrors how `popularity` is passed into `suggest_topics`); the LLM never sees raw DB access.
- Role suggestion cap is exactly up to 10, DB-curated first (deduped by `normalize_taxonomy_text`, per AD-6), then LLM-invented new names filling the remainder - never fewer than 10 when the LLM can supply more, never more than 10 total.
- A user-selected new (not-yet-curated) Role queues via the **existing** `record_pending_suggestion(kind=KIND_ROLE, field_id=..., text=...)` (Epic 2) - no second review mechanism.
- Suggested Prompts are illustrative only (FR-5): fetching/showing them never writes anything; clicking one only fills the textarea (still freely editable).
- `llm/`, `MockLLMProvider`, `PopularitySuggestionSource`, and all Topic/`TopicSuggestion` code are untouched - this story is Roles + Prompts only (Topic new-candidate handling is separately deferred).
- `ChipRow.vue`'s existing Field-row behavior is unchanged; only the Role row gains "new" chips.

**Ask First:** none identified for implementation choices below - the design (merge order, cap, queue reuse, prompt context) was already confirmed with the user this session.

**Never:** change `TopicSuggestion`/Topic pending-status handling (deferred separately), add a second taxonomy review path, make any `suggestions/` adapter touch the DB directly, add streaming/async.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Field with 0 curated Roles | New/empty Field | LLM fills all 10 with new names | N/A |
| Field with 10+ curated Roles | Rich Field | Only curated shown, capped at 10, no LLM call needed (or LLM called but all filtered as duplicates) | N/A |
| LLM suggestion call fails | Local LLM unreachable | DB-curated Roles still shown (no error to user); log/typed error swallowed at this call site only | `SuggestionError` caught, curated-only list returned |
| User selects a new (LLM-only) Role | Chip not in curated list | `role_name` saved on `User` **and** queued via `record_pending_suggestion` | N/A |
| Duplicate new-Role resubmission | Same normalized text, still pending | `submission_count` increments (existing behavior) | N/A |
| Prompt fetch fails | Local LLM unreachable | Interests step shows no prompts (already the pre-LLM behavior) | `SuggestionError` caught, empty list returned |

</frozen-after-approval>

## Code Map

- `src/newsagent/suggestions/base.py`, `types.py` -- `suggest_roles` gains `existing_roles: Sequence[str]`; `suggest_prompts` gains `field_name`/`role_name`/`experience_bucket` (all `str | None`)
- `src/newsagent/suggestions/llm.py` -- update both prompts to use the new params (existing-roles context + "invent up to N new, non-duplicate" instruction; prompts framed by field/role/experience)
- `src/newsagent/suggestions/popularity.py` -- signature-only update (still returns `[]`)
- `src/newsagent/services/taxonomy.py` -- new `suggest_roles_for_field(db, field) -> list[RoleSuggestionView]` merging curated + LLM, capped at 10; `RoleSuggestionView` carries `name` + `is_curated`
- `src/newsagent/services/profile.py` -- new `suggest_prompts_for_user(user) -> list[str]`; loosen nothing in `_apply`'s existing validation (see Design Notes for why)
- `src/newsagent/api/routers/me.py` -- `GET /me/fields/{field_id}/roles` now returns the merged view (schema change); new `GET /me/prompt-suggestions`
- `src/newsagent/api/schemas/taxonomy.py` -- `RoleOut` -> include `is_curated: bool`
- `frontend/src/api/client.ts` -- `RoleOption` type gains `isCurated`; new `getPromptSuggestions()`
- `frontend/src/components/profile-picker/ChipRow.vue` -- new-chip click sets `isOther=true`/`otherText=name` internally (no text box shown) while keeping the chip visually selected
- `frontend/src/components/profile-picker/AboutYouStep.vue` -- pass `isCurated` through to `ChipRow`
- `frontend/src/components/profile-picker/InterestsStep.vue` -- fetch + display up to 3 prompts on mount, click-to-fill textarea

## Tasks & Acceptance

**Execution:**
- [x] `suggestions/base.py`, `types.py`, `llm.py`, `popularity.py` -- widen `suggest_roles`/`suggest_prompts` signatures, update prompts and the mock/popularity stubs to match
- [x] `services/taxonomy.py` -- `suggest_roles_for_field`: query curated, call `get_suggestion_source().suggest_roles(...)` inside a try/except `SuggestionError` (curated-only fallback on failure), dedupe+merge+cap at 10
- [x] `services/profile.py` -- `suggest_prompts_for_user`: read `user.field_name/role_name/experience_bucket`, call `suggest_prompts(...)`, catch `SuggestionError` -> `[]`
- [x] `api/routers/me.py` + `api/schemas/taxonomy.py` -- wire both endpoints
- [x] `frontend/src/api/client.ts`, `ChipRow.vue`, `AboutYouStep.vue`, `InterestsStep.vue` -- consume the new endpoints/shapes
- [x] Tests: `services/taxonomy.py` merge/cap/dedupe logic (incl. LLM-failure fallback), `services/profile.py` prompt fetch (incl. failure->empty), updated `suggestions/llm.py` contract tests for the new params

**Acceptance Criteria:**
- [x] Given a Field with 2 curated Roles, when selected, then up to 10 Role chips show (2 curated + up to 8 new, never a curated name duplicated by an LLM one).
- [x] Given the user picks a new (non-curated) Role chip and continues, then `User.role_name` is saved and exactly one new `PendingTaxonomySuggestion(kind='role')` row exists for it.
- [x] Given the user reaches the Interests step, then up to 3 example prompts appear, generated using their already-saved Field/Role/Experience.
- [x] Given the local LLM is unreachable, then Role selection still works (curated-only) and the Interests step shows no prompts - no error surfaced to the user in either case.

## Spec Change Log

## Design Notes

**Why `_apply`'s existing "claim must resolve" validation is untouched:** rather than loosening that server-side check (which would also weaken Field's unrelated guard), the frontend keeps sending `role_is_other=true` for a newly-picked LLM chip - same as manually-typed "Other" - so the existing, already-tested validation/queueing path handles it unchanged. `ChipRow.vue` decouples this from the UI: a "new" chip sets `isOther=true`/`otherText=<name>` under the hood but stays rendered as a selected chip (no free-text box), via a small per-option `isCurated` flag rather than a global toggle.

**Merge order:** curated Roles first (already vetted), LLM fills remaining slots to 10 with names not matching any curated Role (`normalize_taxonomy_text` comparison, AD-6) - mirrors how `suggest_topics`'s candidate-restriction already works.

## Verification

**Commands:**
- `pytest tests/services/test_taxonomy.py tests/services/test_profile.py tests/suggestions tests/llm` -- expected: all pass
- `mypy` / `ruff check` -- expected: clean on all changed files
- Manual: run the profile wizard in the browser preview, confirm Role chips and Interests-step prompts render, with `NEWSAGENT_SUGGESTION_PROVIDER=llm` and `mock` both.

## Suggested Review Order

**Role merge logic (backend) - entry point**

- Core merge/cap/dedupe, plus review-added blank/overlong-name filtering.
  [`taxonomy.py:133`](../../src/newsagent/services/taxonomy.py#L133)

- The plain-data view (`is_curated`) the router serializes instead of a raw `Role`.
  [`taxonomy.py:123`](../../src/newsagent/services/taxonomy.py#L123)

- The two guard constants: 10-item cap, 100-char name ceiling.
  [`taxonomy.py:23`](../../src/newsagent/services/taxonomy.py#L23)

**Prompt suggestion logic (backend)**

- Fetch + review-added cap-to-3 and blank-text filtering (was unbounded).
  [`profile.py:209`](../../src/newsagent/services/profile.py#L209)

**API surface**

- Role endpoint: now 404s on unknown `field_id` (needs `field.name` for the LLM call).
  [`me.py:48`](../../src/newsagent/api/routers/me.py#L48)

- New thin prompt-suggestions endpoint.
  [`me.py:92`](../../src/newsagent/api/routers/me.py#L92)

- `RoleOut` gains `is_curated` - the schema boundary the frontend keys off.
  [`taxonomy.py:12`](../../src/newsagent/api/schemas/taxonomy.py#L12)

**LLM adapter contract**

- Widened `suggest_roles`/`suggest_prompts` abstract signatures (existing-roles + profile context).
  [`base.py:34`](../../src/newsagent/suggestions/base.py#L34)

- New EXISTING_ROLES prompt block; review changed its separator from `,` to newline to avoid name-comma ambiguity.
  [`llm.py:77`](../../src/newsagent/suggestions/llm.py#L77)

**Frontend: Role chip selection state**

- Review fix: `otherButtonActive` is now derived, not local state - was desyncing when a parent reset `isOther` directly (e.g. on Field change).
  [`ChipRow.vue:73`](../../frontend/src/components/profile-picker/ChipRow.vue#L73)

- The three selection paths this derivation depends on staying consistent.
  [`ChipRow.vue:90`](../../frontend/src/components/profile-picker/ChipRow.vue#L90)

- Review addition: "Loading roles…" placeholder, since the fetch can now take noticeably longer (LLM call, not just a DB read).
  [`AboutYouStep.vue:127`](../../frontend/src/components/profile-picker/AboutYouStep.vue#L127)

**Frontend: Suggested Prompts**

- Fetch-on-mount, illustrative only; review fix: chip `:key` now includes index to avoid collisions on duplicate LLM text.
  [`InterestsStep.vue:59`](../../frontend/src/components/profile-picker/InterestsStep.vue#L59)

- `RoleOption`/`listRoles`/`getPromptSuggestions` - the typed client surface both steps consume.
  [`client.ts:36`](../../frontend/src/api/client.ts#L36)

**Peripherals**

- Merge/cap/dedupe/fallback coverage, plus review-added blank/overlong-name tests.
  [`test_taxonomy.py:497`](../../tests/services/test_taxonomy.py#L497)

- Prompt fetch coverage, plus review-added cap-to-3 and blank-filter tests.
  [`test_profile.py:484`](../../tests/services/test_profile.py#L484)

- Router-level coverage, plus review-added test for the `is_curated: false` path through the actual schema boundary.
  [`test_me.py:142`](../../tests/api/routers/test_me.py#L142)

- Contract tests for the widened LLM adapter signatures.
  [`test_llm_source.py:47`](../../tests/suggestions/test_llm_source.py#L47)
