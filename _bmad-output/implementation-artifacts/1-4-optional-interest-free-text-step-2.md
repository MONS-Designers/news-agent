---
baseline_commit: 52eb95a
---

# Story 1.4: Optional Interest Free-Text, Step 2

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to optionally describe my interests in my own words,
so that suggestions can be sharper than my Field/Role alone would produce, without being forced to.

*Realizes FR4, FR5 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.1).*

## Acceptance Criteria

1. **Given** I click Continue from a completed Step 1, **when** Step 2 mounts, **then** I see an optional free-text textarea and a "Skip for now" link alongside Continue, with the staggered entrance animation.
2. **Given** the textarea is empty, **when** I view Continue and Skip, **then** both are enabled — Step 2 is never gated.
3. **Given** I type text (or leave it empty) and click Continue or Skip, **when** either action completes, **then** my text, if any, saves as `User.interest_free_text` and the flow advances to Step 3.
4. **Given** no LLM-backed Suggestion Source is connected (MVP default), **when** Step 2 renders, **then** no Suggested Prompts are shown near the textarea — it remains fully usable without them.
5. **Given** the Continue and Skip controls on this step, **when** they render, **then** they are real `<button>` elements (keyboard-focusable, `Enter`/`Space`-activatable), never `<div onclick>` — same accessibility baseline as Story 1.1.
6. **Given** I click Back from Step 3, **when** Step 2 re-mounts, **then** my previously entered Interest Free-Text, if any, is still shown.
7. This story ships a new Alembic revision adding `User.interest_free_text`.

## Tasks / Subtasks

- [x] Task 1: `User.interest_free_text` + migration (AC: #3, #7)
  - [x] 1.1 Add `User.interest_free_text: str | None` — plain string column, no length constraint at the DB level (matches the existing `field_name`/`role_name` columns' shape).
  - [x] 1.2 New Alembic revision, `down_revision = "c3d4e5f6a7b8"` (current head — re-confirmed with `alembic heads` before writing, read-only). `op.add_column("users", sa.Column("interest_free_text", sa.String(), nullable=True))` + matching `downgrade()`. Same single-column-add shape as `c3d4e5f6a7b8`'s `experience_bucket`.
  - [x] 1.3 **Do not run `alembic upgrade head`** without asking first — migrations need explicit approval every time, regardless of what was approved for a previous story's migration.

- [x] Task 2: `services/profile.py` — Interest Free-Text + make `field_name` independently optional (AC: #2, #3)
  - [x] 2.1 **Design call, read before touching this file:** `save_profile`'s `field_name` parameter is currently required (`str`, no default) — every prior story's Continue action always had Field/Role/Experience in scope together. Step 2's save only has `interest_free_text` to send; it must not resend Field/Role (resending an "Other" value would call `taxonomy.record_pending_suggestion` again and double-count `submission_count` for a user who didn't actually resubmit anything — a real correctness bug, not a style choice). Fix: change `field_name: str` to `field_name: str | None`, with the same "`None` = not submitted in this request, leave untouched" semantics `role_name`/`experience_bucket` already use. `field_is_other` stays a plain `bool` — it's only consulted when `field_name` is not `None`.
  - [x] 2.2 In `_apply`: wrap the existing `field = taxonomy.find_field_by_name(...)` / `user.field_name = ...` / Field-"Other"-suggestion block in `if field_name is not None:`. Skip it entirely when `field_name is None` — `user.field_name` stays whatever it already was.
  - [x] 2.3 Guard the Role block: Role resolution (`taxonomy.find_role_by_name(db, field.id, ...)`) depends on a `field` object that only exists inside the `if field_name is not None:` branch from 2.2. If `role_name is not None and field_name is None`, raise `ValueError(INVALID_PROFILE)` immediately, before touching anything, at the top of `_apply` — this combination has no valid caller today and would otherwise be a `NameError`/crash, not a graceful 400.
  - [x] 2.4 Added `MAX_INTEREST_LENGTH = 2000` next to `MAX_NAME_LENGTH`. Extended `save_profile`/`_apply` with `interest_free_text: str | None`. `_clean_interest` validates the length cap and strips, but deliberately does NOT collapse blank to `None` itself — that conversion happens in `_apply` at the point of assignment (`user.interest_free_text = interest_free_text or None`), so a submitted-but-blank string (clears the field) stays distinguishable from a not-submitted field (`None`, left untouched) all the way through the call. Over-length raises `ValueError(INVALID_PROFILE)`, the same shared message. No suggestion-queue interaction.
  - [x] 2.5 `user.interest_free_text` is set before the function's single trailing `db.commit()` — same one-transaction shape as every other profile field.

- [x] Task 3: API — extend the profile contract (AC: #3)
  - [x] 3.1 `ProfileUpdateIn.field_name: str | None = None` (was required) and `ProfileUpdateIn.interest_free_text: str | None = None` added in `api/schemas/profile.py`. `ProfileOut.interest_free_text: str | None` added.
  - [x] 3.2 `PUT /me/profile` in `api/routers/me.py` passes `interest_free_text` through to `profile.save_profile`.

- [x] Task 4: Frontend — `InterestsStep.vue` (AC: #1, #2, #3, #4, #5)
  - [x] 4.1 New file `frontend/src/components/profile-picker/InterestsStep.vue`: step-2 block heading ("Interests (optional)"), a `<textarea>` (mockup's placeholder copy), and a nav row with three real `<button type="button">` elements — Back (ghost, emits `back`), "Skip for now →" (ghost), "Continue" (primary, `:disabled="saving"` only, never gated).
  - [x] 4.2 No Suggested Prompts markup — confirmed absent, per AC #4 and FR-5's own assumption.
  - [x] 4.3 `interestFreeText = ref("")`. Both Continue and Skip call the same `advance()`: non-empty trimmed text saves via `updateMyProfile({ interestFreeText: text })` then emits `continue`; empty text skips the network call and emits immediately. `saving`/`saveError` mirror `AboutYouStep.vue`'s pattern; a failed save does not emit.
  - [x] 4.4 No `onMounted` fetch, no `GET /me/profile`. AC #6 relies entirely on `v-show` keeping the component mounted.

- [x] Task 5: Frontend — wire `InterestsStep` into the shell + `client.ts` (AC: #1, #3)
  - [x] 5.1 `ProfilePickerShell.vue`'s Step 2 placeholder replaced with `<InterestsStep @continue="currentStep = 3" @back="currentStep = 1" />`, inside the unchanged `v-show`/`ref="step2El"`/`class="stagger"` wrapper. Step 3's placeholder is untouched.
  - [x] 5.2 `frontend/src/api/client.ts`: `ProfileUpdate`'s `fieldName`/`fieldIsOther`/`roleName`/`roleIsOther` made optional, `interestFreeText?: string` added. `updateMyProfile` now builds the request body conditionally (only keys the caller actually set) instead of always sending all five fields. `Profile.interest_free_text: string | null` added. `AboutYouStep.vue`'s call site unaffected (still passes all five fields it always has).

- [x] Task 6: Tests (AC: all)
  - [x] 6.1 `tests/services/test_profile.py`: `_save()` default kwargs extended with `interest_free_text=None`. Added tests for trimmed save, blank-stores-None vs. None-leaves-untouched (two distinct behaviors), over-length rejection, no-suggestion-created, `field_name=None` leaving Field/Role untouched while saving interest text (the exact call shape `InterestsStep` uses), and `role_name` without `field_name` being rejected. Both new rejection causes folded into `test_every_rejection_uses_the_same_message`.
  - [x] 6.2 `tests/api/routers/test_me.py`: existing exact-dict-equality assertions updated for the new `interest_free_text` key in `ProfileOut`; added a test for `PUT /me/profile` with only `{"interest_free_text": ...}` in the body (no `field_name` key at all) against a user whose Field was already saved by a prior call, and an over-length-gets-400 test.
  - [x] 6.3 `tests/models/test_models_smoke.py`: no change needed — nullable column, existing `User(...)` construction still passes.
  - [x] 6.4 `cd frontend && npm run type-check` clean. Live-verified in the browser (see Debug Log / Completion Notes).
  - [x] 6.5 Full suite green: 195 passed (10 new on top of the 185 baseline); `mypy` and `ruff` clean.

## Dev Notes

### Read these before writing code

- [`src/newsagent/services/profile.py`](../../src/newsagent/services/profile.py) — the file this story changes the most. `_apply`'s Field block computes a `field` local the Role block depends on; Task 2's changes preserve that dependency once the Field block becomes conditional.
- [`src/newsagent/api/routers/me.py`](../../src/newsagent/api/routers/me.py) — `update_my_profile`'s existing `ValueError → HTTPException(400)` translation already covers whatever `save_profile` raises.
- [`frontend/src/components/profile-picker/AboutYouStep.vue`](../../frontend/src/components/profile-picker/AboutYouStep.vue) — the pattern `InterestsStep.vue` follows: `saving`/`saveError` refs, a single async handler that calls `updateMyProfile` then emits.
- [`frontend/src/components/profile-picker/ProfilePickerShell.vue`](../../frontend/src/components/profile-picker/ProfilePickerShell.vue) — owns the `v-show` step-switching and animation-replay watcher (both unchanged, built by Story 1.3).
- [`frontend/src/api/client.ts`](../../frontend/src/api/client.ts) — this story is what first requires a partial `updateMyProfile` payload.
- [`mockups/flow-hybrid-depth-steps.html`](../planning-artifacts/ux-designs/ux-news-agent-2026-07-21/mockups/flow-hybrid-depth-steps.html) lines 215–232 — reference markup/copy for Step 2. Its `.prompt` divs (lines 218–221) are the Suggested Prompts this story explicitly does not build.

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-1** — no new layer; `save_profile` grows one more validated field and a relaxed-but-still-service-owned validation rule. Router stays a thin pass-through.
- **AD-4** — Alembic only; single-column addition, same as `c3d4e5f6a7b8`.
- **AD-6** — `interest_free_text` is flat on `User`, plain string, same shape as `field_name`/`role_name`/`experience_bucket`. No "Other" concept.
- **Consistency Conventions → Frontend controls** — Continue/Skip/Back are real `<button>` elements.
- **FR Coverage Map** — this story realizes FR4 and FR5 jointly; FR5 by its explicit absence (Suggested Prompts require a connected Suggestion Source per the PRD's own FR-5 assumption).

### Explicit scope boundary

- No part of `newsagent/suggestions/` was built — that's Story 1.5.
- No `GET /me/profile` endpoint was added — Back-persistence is satisfied by `v-show`.
- Step 3's placeholder panel/Back button are unchanged.
- The `field_name: str | None` relaxation was necessary for correctness (avoids double-counting an "Other" submission's `submission_count` if Step 2 had to resend Field/Role), not a drive-by refactor.
- No character counter or client-side length-cap UI was built — `MAX_INTEREST_LENGTH` is a server-side safety bound only.

### Project Structure Notes

- New backend file: `alembic/versions/d4e5f6a7b8c9_user_interest_free_text.py`.
- Changed backend files: `src/newsagent/models/user.py`, `src/newsagent/services/profile.py`, `src/newsagent/api/schemas/profile.py`, `src/newsagent/api/routers/me.py`, `tests/services/test_profile.py`, `tests/api/routers/test_me.py`.
- New frontend file: `frontend/src/components/profile-picker/InterestsStep.vue`.
- Changed frontend files: `frontend/src/components/profile-picker/ProfilePickerShell.vue`, `frontend/src/api/client.ts`.
- No changes to `frontend/src/style.css`. No new dependencies.

### References

- [Source: epics.md#Story-1.4] — acceptance criteria, verbatim.
- [Source: prd-news-agent-2026-07-21/prd.md#4.1 FR-4, FR-5] — Interest Free-Text optionality, Suggested Prompts' Suggestion-Source-required assumption.
- [Source: ARCHITECTURE-SPINE.md#AD-1, #AD-4, #AD-6] — layering, migration convention, flat-column profile shape.
- [Source: EXPERIENCE.md#Component-Patterns, #State-Patterns] — ungated-Step-2 rule, Skip-only-on-Step-2 rule, Suggestion-Source-not-connected treatment.
- [Source: mockups/flow-hybrid-depth-steps.html lines 215–232] — Step 2 reference markup/copy.
- [Source: 1-3-experience-bucket-completing-step-1-gate.md] — the `v-show`/animation-replay mechanism this story relies on, and conventions this story's Task 2 extends.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- Confirmed `c3d4e5f6a7b8` as head with `alembic heads` (read-only) before writing the new revision; re-checked afterwards for a single linear head (`d4e5f6a7b8c9`).
- Ran everything with `PYTHONPATH=src` (same stale editable-install quirk as prior stories).
- `alembic upgrade head` was run **with explicit user approval**. Dev DB is now at `d4e5f6a7b8c9`.
- **Live browser verification.** Found the backend on port 8000 owned by a process (reported PID 14848) launched via the global Python interpreter rather than `.venv` — the same stale-environment class of issue flagged in Story 1.3's Debug Log. Flagged to the user rather than silently killed (per standing instruction); user approved stopping it. After the stop, OS-level process tools (`Get-Process`, WMI, `tasklist`) all agreed PID 14848 no longer existed, yet `netstat` continued to report it `LISTENING` on port 8000 for a period, and a raw `TcpListener` bind confirmed the port was still genuinely held at the kernel level — an unresolved discrepancy between the reported owning PID and actual process state, not chased further at the user's direction. Proceeded to verify directly against the already-running frontend (port 5173) and whatever now serves port 8000; live requests (`GET /api/me/fields`, `PUT /api/me/profile`) returned correct 200s reflecting the new `interest_free_text` schema, confirming the backend in front of that port was in fact serving current code regardless of the PID-reporting anomaly.
- Authenticated via the persisted session cookie from a prior story's verification session (`verify-story-1-1@example.com`).

### Completion Notes List

**All 6 tasks complete.** 195 backend tests pass (10 added on top of the 185 baseline); `mypy` and `ruff` clean; `vue-tsc --noEmit` clean.

**Per acceptance criterion, live-verified in the browser** (real seeded DB, authenticated session):

- AC #1 — confirmed via DOM read: after completing Step 1 (Tech / Software Engineer / 6–10 yrs) and clicking Continue, Step 2 mounted showing "INTERESTS (OPTIONAL)", a textarea, and Back/Skip/Continue controls.
- AC #2 — confirmed both Skip and Continue rendered enabled with the textarea empty (no `disabled` state, no gate logic present).
- AC #3 — typed interest text, clicked Continue; network capture showed `PUT /api/me/profile` with body `{"interest_free_text": "Curious about applied ML and dev tooling."}` (Field/Role/Experience correctly omitted), response `200` with the full merged profile (`field_name`/`role_name`/`experience_bucket` from Step 1 preserved, `interest_free_text` newly set); the flow advanced to the Step 3 placeholder.
- AC #4 — confirmed via DOM read: no prompt pills rendered near the textarea.
- AC #5 — confirmed via accessibility-tree read: Back/Skip/Continue are genuine `<button type="button">` elements, not `<div onclick>`.
- AC #6 — clicked Back from the Step 3 placeholder; `document.querySelector('textarea').value` still returned the previously typed text, confirming `v-show` persistence.
- AC #7 — migration applied cleanly; `alembic current` reports `d4e5f6a7b8c9`.

**Deliberately not done, per Dev Notes' explicit scope boundaries:**
- No `suggestions/` package or Suggested Prompts (Story 1.5+).
- No `GET /me/profile` endpoint.
- No character counter or client-side length-cap UI.

### File List

**New:**
- `alembic/versions/d4e5f6a7b8c9_user_interest_free_text.py`
- `frontend/src/components/profile-picker/InterestsStep.vue`

**Changed:**
- `src/newsagent/models/user.py` (+ `interest_free_text`)
- `src/newsagent/services/profile.py` (+ `MAX_INTEREST_LENGTH`, `_clean_interest`, `field_name`-optional handling, `interest_free_text` validation)
- `src/newsagent/api/schemas/profile.py` (+ `interest_free_text` on both schemas, `field_name` optional)
- `src/newsagent/api/routers/me.py` (thread `interest_free_text` through)
- `frontend/src/components/profile-picker/ProfilePickerShell.vue` (Step 2 placeholder → `InterestsStep`)
- `frontend/src/api/client.ts` (optional `ProfileUpdate` fields, `interestFreeText`/`interest_free_text` threading, conditional request body)
- `tests/services/test_profile.py`
- `tests/api/routers/test_me.py`

## Change Log

- 2026-07-27: Story 1.4 implemented end-to-end — `User.interest_free_text`, `field_name` relaxed to optional with None-untouched semantics (avoiding double-counted "Other" resubmissions), `InterestsStep.vue` with real Back/Skip/Continue controls and no Suggested Prompts, `client.ts`'s partial-payload support. 10 new tests (195 total). Migration `d4e5f6a7b8c9` applied to the local dev DB with approval. Live-verified in the browser against all 7 ACs.
- 2026-07-27: Story 1.4 drafted. Key design call: relax `save_profile`'s `field_name` from required to `str | None` (matching `role_name`/`experience_bucket`'s existing "not submitted, leave untouched" semantics) so Step 2's save can send `interest_free_text` alone — resending Field/Role from Step 2 would double-count an "Other" submission's `submission_count`. Deliberately excludes Suggested Prompts (Story 1.5+) and any `GET /me/profile` endpoint (Back-persistence already solved by Story 1.3's `v-show` mechanism).
