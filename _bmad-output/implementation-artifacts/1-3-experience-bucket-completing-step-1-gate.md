---
baseline_commit: 960be3b4272a8c2011ace52b8d9fe195c41143ea
---

# Story 1.3: Experience Bucket, completing the Step 1 gate

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to indicate my experience level,
so that the product team understands our user base, without it affecting what gets suggested to me.

*Realizes FR3 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.1).*

## Acceptance Criteria

1. **Given** Step 1 is showing, **when** I view the Experience section, **then** I see a segmented control with 4 illustrative buckets (0–2 / 3–5 / 6–10 / 10+ yrs), implemented with real radio-group semantics, single-select.
2. **Given** I select a bucket, **when** it saves, **then** it is stored as `User.experience_bucket` and is never read by any Topic-suggestion computation path.
3. **Given** Field, Role, and Experience Bucket are all set, **when** I view Continue, **then** it is enabled; **given** any of the three is unset, it is disabled — the complete Step 1 gate.
4. **Given** I click Back from Step 2, **when** Step 1 re-mounts, **then** my previously selected Field/Role/Experience still show as selected, and the staggered entrance animation replays.
5. This story ships a new Alembic revision adding `User.experience_bucket`.

## Tasks / Subtasks

- [x] Task 1: `User.experience_bucket` + migration (AC: #2, #5)
  - [x] 1.1 Add `User.experience_bucket: str | None` — plain string column, no enum type (matches `Source.status`'s existing plain-string convention, AD-2). Unlike `field_name`/`role_name` there is no "Other" concept here — the PRD's 4 buckets are a fixed illustrative list (architecture's Deferred section: "this spine treats the bucket set as an illustrative, swappable value list, not a fixed schema constraint" — swappable later by a PM/content change, not by user free text now).
  - [x] 1.2 New Alembic revision, `down_revision = "b2c3d4e5f6a7"` (current head — re-confirm with `alembic heads` before writing, read-only). Just `op.add_column("users", sa.Column("experience_bucket", sa.String(), nullable=True))` + matching `downgrade()`. No new table — follow the single-column-add style of `a1b2c3d4e5f6`'s `field_name` addition, not `b2c3d4e5f6a7`'s more involved shape.
  - [x] 1.3 **Do not run `alembic upgrade head`** without asking first — migrations need explicit approval every time (project data-safety policy), regardless of what was approved for a previous story's migration.

- [x] Task 2: `services/profile.py` — Experience Bucket validation (AC: #2, #3)
  - [x] 2.1 `EXPERIENCE_BUCKETS: list[str] = ["0-2", "3-5", "6-10", "10+"]` constant in `services/profile.py`, next to `MAX_NAME_LENGTH`/`INVALID_PROFILE`. These are the stored values; display labels ("0–2 yrs", en dash) are a frontend-only concern.
  - [x] 2.2 Extend `save_profile(db, user, *, ..., experience_bucket: str | None) -> User`: `None` means "not submitted in this request" (same semantics as `role_name`) and leaves any existing value untouched. A non-`None` value must be in `EXPERIENCE_BUCKETS` or the call raises `ValueError(INVALID_PROFILE)` — same fixed, non-disclosing message every other rejection in this function already uses (don't add a bucket-specific message; that would let a client distinguish "bad bucket" from "bad name" by message shape, defeating the existing non-disclosure design). No suggestion-queue interaction — a bucket has no "Other" path and never touches `PendingTaxonomySuggestion`.
  - [x] 2.3 Set `user.experience_bucket` before the function's single `db.commit()` — same one-transaction shape as the Field/Role writes (AC #2's "stored" implies durability; don't introduce a second commit).

- [x] Task 3: API — extend the profile contract (AC: #2, #3)
  - [x] 3.1 `ProfileUpdateIn.experience_bucket: str | None = None`, `ProfileOut.experience_bucket: str | None` in `api/schemas/profile.py`.
  - [x] 3.2 `PUT /me/profile` in `api/routers/me.py` passes `experience_bucket` through to `profile.save_profile` — one more keyword argument, no new endpoint, no new router logic (the existing `ValueError → HTTPException(400)` translation already covers this field's validation failures).

- [x] Task 4: Frontend — Experience segmented control (AC: #1, #3)
  - [x] 4.1 Add a real `<fieldset>`/`<legend>` + 4 native `<input type="radio" name="experience-bucket">` (one shared `name`, so the browser gives correct radio-group keyboard semantics — arrow-key movement between options, single tab stop — for free; do **not** reimplement this with `<button aria-pressed>` chips like Field/Role, the AC explicitly calls for *radio-group* semantics, which Field/Role's chip pattern is not). Visually style as the DESIGN.md segmented-control token (pill row, selected segment highlighted) by visually hiding the native radio (a `sr-only`-style absolute-position-1px rule, **not** `display:none`, which would drop it from the tab order) and styling the `<label>` — add `:focus-within` on the label wrapper so the (visually hidden) radio's focus ring is still visible to a keyboard user.
  - [x] 4.2 Implement inline inside `AboutYouStep.vue`, not as a new shared component — unlike `ChipRow` (reused twice), this control has exactly one call site; extracting a component now would be speculative (per project convention: no abstraction for single-use code).
  - [x] 4.3 Local state: `experienceBucket = ref<string | null>(null)`, bound via `v-model` to the radio group. Display labels use en dash ("0–2 yrs", "3–5 yrs", "6–10 yrs", "10+ yrs"); the `value` attributes sent to the API are the plain-hyphen backend constants from Task 2.1 (`"0-2"`, `"3-5"`, `"6-10"`, `"10+"`) — keep these two representations distinct in code, do not derive one from the other by string manipulation.
  - [x] 4.4 Extend `canContinue` to `fieldSatisfied && roleSatisfied && experienceBucket.value !== null` (three-way gate, AC #3). Extend the `PUT /me/profile` call in `onContinue` to include `experienceBucket.value`.
  - [x] 4.5 `frontend/src/api/client.ts`: add `experienceBucket: string | null` to `ProfileUpdate`, `experience_bucket: string | null` to `Profile`, and thread it through `updateMyProfile`'s request body (`experience_bucket: update.experienceBucket`).

- [x] Task 5: Frontend — Back navigation + state persistence across steps (AC: #4)
  - [x] 5.1 **Root cause of AC #4 today: `ProfilePickerShell.vue`'s three step panels are `v-if`/`v-else-if`/`v-else`, so navigating away from Step 1 destroys the `AboutYouStep` component instance and every ref inside it** (this was flagged and explicitly deferred to this story in Story 1.1's review). Fix: replace with `v-show` on all three panels so none of them are ever unmounted — Field/Role/Experience selections then survive a Step 1 → 2 → 1 round trip for free, with no state-lifting needed. Placeholder Steps 2/3 have no meaningful state today, so switching them to `v-show` too is free and keeps all three panels handled uniformly.
  - [x] 5.2 Remove the `:key="currentStep"` on `.panel` — it was forcing the very destroy/recreate cycle Task 5.1 removes, which is *why* the entrance animation happened to replay before (an accidental side effect of losing state, not an intentional design). Replace it with an explicit replay mechanism (Task 5.3) so animation-replay and state-loss are no longer the same mechanism.
  - [x] 5.3 Add a `watch(currentStep, ...)` that, after `nextTick()`, finds the `.stagger` elements inside the now-visible panel and restarts their CSS animation via the reflow trick the approved mockup itself uses (`mockups/flow-hybrid-depth-steps.html`'s `goStep()`): `el.style.animation = 'none'; void el.offsetWidth; el.style.animation = ''`. Skip entirely when `prefers-reduced-motion` is set (reuse the existing `reducedMotion` flag already tracked in this component for the orb parallax).
  - [x] 5.4 Add a real `<button type="button">Back</button>` to the Step 2 and Step 3 placeholder panels, wired to `currentStep = 1` / `currentStep = currentStep - 1` respectively — EXPERIENCE.md: "Back link | Every step | Always available ... Never gated." Story 1.3's AC only exercises Back-from-Step-2, but Step 3's stub gets the same control for free and to avoid an inconsistent affordance (Back present on one stub but not the other) — this is a two-line addition, not new scope, since both are still placeholder panels owned by later stories.
  - [x] 5.5 **Do not** attempt full page-reload persistence (rehydrating from the server after a fresh page load) — AC #4 is scoped to Back-from-Step-2 within the same page session, which Task 5.1's `v-show` fix satisfies without any new read endpoint. A `GET /me/profile` for reload-survival is out of scope for this story (no AC requires it); don't add one speculatively.

- [x] Task 6: Tests (AC: all)
  - [x] 6.1 `tests/services/test_profile.py` — extend `_save()`'s default kwargs with `experience_bucket=None`; add: each of the 4 valid buckets saves correctly; an invalid bucket string raises `ValueError`; `experience_bucket=None` leaves an existing value untouched (mirrors the existing `role_name=None` test); the invalid-bucket rejection message equals `INVALID_PROFILE`, folded into the existing `test_every_rejection_uses_the_same_message` parametrization rather than a new standalone assertion.
  - [x] 6.2 `tests/api/routers/test_me.py` — `PUT /me/profile` with a valid `experience_bucket` returns it in `ProfileOut`; an invalid value gets 400.
  - [x] 6.3 `tests/models/test_models_smoke.py` — no new table, so no new row needed; confirm the existing `User(...)` construction still passes with the new nullable column (it will, by default `None` — a smoke-test run is sufficient, no new assertion required beyond that the suite stays green).
  - [x] 6.4 No frontend test runner exists in this project (confirmed in Stories 1.1/1.2 — do not add one). Verify with `cd frontend && npm run type-check` (`vue-tsc --noEmit`, must be clean). Live-verify in the browser per Story 1.2's pattern (locally-minted session cookie against the dev-only `NEWSAGENT_SESSION_SECRET`) if the migration is applied — **ask before running `alembic upgrade head`** even though a migration was approved for Story 1.2; that approval does not carry over.
  - [x] 6.5 Full suite green: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q` (176 passing at baseline — none may regress), plus `mypy` and `ruff` clean.

## Dev Notes

### Read these before writing code

- [`src/newsagent/services/profile.py`](../../src/newsagent/services/profile.py) — `save_profile`/`_apply`'s existing shape: `_clean()` for names, the `field`/`role` resolution, and the single trailing `db.commit()`. Experience Bucket validation is simpler (a fixed-set membership check, no curated-list lookup, no suggestion upsert) but must still route through the same `INVALID_PROFILE` message and land inside the same transaction.
- [`src/newsagent/api/routers/me.py`](../../src/newsagent/api/routers/me.py) — `update_my_profile`'s existing `ValueError → HTTPException(400)` translation already covers whatever `save_profile` raises; no router change beyond passing the new field through.
- [`frontend/src/components/profile-picker/AboutYouStep.vue`](../../frontend/src/components/profile-picker/AboutYouStep.vue) — owns `fieldName`/`roleName` state and the `canContinue` gate this story extends to three conditions. Read `ChipRow.vue` too, to see why it's *not* reused for Experience (button+`aria-pressed` vs. AC #1's requirement for native radio-group semantics — different accessibility contract).
- [`frontend/src/components/profile-picker/ProfilePickerShell.vue`](../../frontend/src/components/profile-picker/ProfilePickerShell.vue) — the `v-if/else-if/else` + `:key="currentStep"` step-switching this story replaces with `v-show` + an explicit animation-replay watcher. Also owns the `prefers-reduced-motion` `reducedMotion` flag and its `MediaQueryList` listener — reuse it for gating the animation-replay trick, don't add a second listener.
- [`mockups/flow-hybrid-depth-steps.html`](../planning-artifacts/ux-designs/ux-news-agent-2026-07-21/mockups/flow-hybrid-depth-steps.html) `goStep()` — the reference implementation for Task 5.2/5.3: it never destroys DOM nodes across step navigation (only toggles `.current`/`.active`/`.done` classes) and replays the entrance animation via the exact reflow trick this story's Task 5.3 copies. The current Vue implementation's `v-if`-based destroy/recreate is *less* faithful to the approved mockup than the fix this story makes, not a deviation from it.

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-1** — no new layer; `save_profile` grows one more validated field, router stays a thin pass-through.
- **AD-4** — Alembic only; single-column addition, same as `a1b2c3d4e5f6`'s `field_name` column.
- **AD-6 does not apply to Experience Bucket** — that AD is specifically about Field/Role's "Other" mechanism (a curated pick and typed free text stored identically). Experience Bucket has no free-text path; it is a closed fixed-set value, validated like an enum but stored as a plain string (AD-2's convention), not a foreign key to anything and not a `PendingTaxonomySuggestion` source.
- **Consistency Conventions → Frontend controls** — "real semantic elements... `<button>` with `aria-pressed`, or native `radio`/`checkbox` inputs — never `<div onclick>`." Experience Bucket is the first control in this feature to use the *native radio* half of that rule rather than the button+`aria-pressed` half; Field/Role/Back should stay on buttons.
- **Capability → Architecture Map, FR-3 row**: "`User.experience_bucket` | AD-6" — the epics/architecture map lists AD-6 against FR-3, but per the AD-6 text itself (which only discusses `field_name`/`role_name`) that reference is imprecise; treat AD-2 (plain-string-status convention) as the actually-applicable rule here, not AD-6's "Other" mechanism.

### Explicit scope boundary

- **AC #2's "never read by any Topic-suggestion computation path" is a forward constraint, not something to implement now** — no suggestion computation exists yet (Stories 1.5/1.6). Nothing in this story reads `experience_bucket` anywhere; there is nothing to test beyond "the column exists and is written correctly." Flag this constraint for whoever builds `services/suggestions` later rather than trying to prove a negative here.
- **Per-child staggered entrance timing** (each block fading up individually at .02s/.06s/.1s.../.26s, per `EXPERIENCE.md` and the mockup) **is not implemented by this story.** Today, and after this story, one `.stagger` wrapper covers each whole step's content as a single fade-up unit — a Story 1.1 review finding (`[MEDIUM]`) that remains open. This story's animation-replay fix (Task 5.3) makes that single-block fade-up *replay* correctly on Back; it does not add the finer-grained per-child staggering. Don't expand scope to fix it here.
- **Direct progress-stepper-dot navigation** stays unimplemented (architecture's Deferred section, EXPERIENCE.md § Component Patterns) — Continue/Back/Skip remain the only navigation controls.

### Project Structure Notes

- New backend files: one new `alembic/versions/*.py`.
- Changed backend files: `src/newsagent/models/user.py` (+ `experience_bucket`), `src/newsagent/services/profile.py` (+ `EXPERIENCE_BUCKETS`, validation), `src/newsagent/api/schemas/profile.py`, `tests/services/test_profile.py`, `tests/api/routers/test_me.py`.
- Changed frontend files: `frontend/src/components/profile-picker/AboutYouStep.vue` (+ segmented control, three-way gate), `frontend/src/components/profile-picker/ProfilePickerShell.vue` (`v-show` refactor, animation-replay watcher, Back buttons), `frontend/src/api/client.ts` (+ `experience_bucket`/`experienceBucket` threading).
- No new frontend files — Task 4.2 explicitly keeps the segmented control inline rather than extracting a component.
- No changes to `frontend/src/style.css` — still component-scoped styling, per Stories 1.1/1.2.
- No new dependencies.

### References

- [Source: epics.md#Story-1.3] — acceptance criteria, verbatim.
- [Source: prd-news-agent-2026-07-21/prd.md#4.1 FR-3] — Experience Bucket description, stats-only / never-influences-suggestions constraint, `[NOTE FOR PM]` on the illustrative bucket boundaries.
- [Source: ARCHITECTURE-SPINE.md#AD-1, #AD-2, #AD-4, #Deferred] — layering, plain-string-status convention, migration convention, "illustrative swappable value list" framing for the bucket set.
- [Source: EXPERIENCE.md#Component-Patterns row "Experience segmented control", row "Back link", #State-Patterns row "Step mount / re-entry"] — radio-group requirement, Back-always-available rule, replay-in-full-on-every-re-entry rule.
- [Source: 1-1-guided-flow-shell-field-selection.md#Review-Findings] — the deferred "no Back navigation" / "state dies on unmount" items this story resolves; the still-open per-child-stagger finding this story deliberately does not resolve.
- [Source: 1-2-role-selection-scoped-to-field.md] — the `save_profile`/`ProfileUpdateIn`/`ProfileOut` shapes this story extends, and the single-fixed-error-message pattern this story's Task 2.2 reuses rather than inventing a second one.

## Dev Agent Record

### Agent Model Used

Claude Opus 5

### Debug Log References

- Confirmed `b2c3d4e5f6a7` as head with `alembic heads` (read-only) before writing the new revision; re-checked afterwards for a single linear head (`c3d4e5f6a7b8`).
- Ran everything with `PYTHONPATH=src` (stale editable-install worktree issue, unchanged since Stories 1.1/1.2).
- `alembic upgrade head` was run **with explicit user approval**. Dev DB is now at `c3d4e5f6a7b8`.
- **Live browser verification, done in a follow-up round.** The user started the dev servers themselves; the backend on port 8000 turned out to be running from the *global* Python install (`uvicorn.exe` outside `.venv`), whose editable `newsagent` install resolves to a stale worktree (`.claude/worktrees/github-issues-review-6e1f99`) — the exact environment gotcha flagged in Story 1.1's Debug Log, now confirmed to actually bite when a shell doesn't have the project `.venv` active. `GET /me/fields` 404'd against it. Diagnosed via `Get-NetTCPConnection`/`Get-CimInstance Win32_Process`, reported to the user rather than silently killed (per standing instruction to confirm before touching processes); the user stopped it and restarted with the correct `.venv`, after which `/me/fields`, `/me/fields/{id}/roles` etc. were all present.
- Authenticated via the same locally-minted session-cookie technique as Stories 1.1/1.2 (`verify-story-1-1@example.com`, id=2).
- The Browser pane was not displayed on the client side during this session (`document.hidden === true`), which freezes the CSS animation timeline entirely (`getAnimations()[0].currentTime` stuck at `0` regardless of what triggered it) — confirmed this is an environment/display limitation, not a code defect, by: (a) reproducing the identical stuck state when manually running the exact same reflow-trick JS from the console outside any Vue/watcher code path, and (b) instrumenting a `MutationObserver` on the panel's `style` attribute, which recorded exactly the two expected writes (`animation: none` → `animation: ''`) at the moment `currentStep` changed — proving the replay watcher fires correctly; only the resulting animation's visible playback couldn't be observed in this session.

### Completion Notes List

**All 6 tasks complete.** 185 backend tests pass (9 added on top of the 176 baseline); `mypy` and `ruff` clean; `vue-tsc --noEmit` clean.

**Per acceptance criterion, now live-verified in the browser** (real seeded DB, authenticated session):

- AC #1 — confirmed via DOM inspection: 4 elements are genuine `<input type="radio" name="experience-bucket">` sharing one `name` (native single-select semantics, not custom ARIA), each wrapped in a `<label>` with the en-dash display text.
- AC #2 — `EXPERIENCE_BUCKETS` is a closed set validated server-side; `test_experience_bucket_never_creates_a_suggestion` pins that it never touches `PendingTaxonomySuggestion`. Live save confirmed `experience_bucket='6-10'` persisted alongside `field_name`/`role_name` in one `PUT /me/profile` request. Nothing in the codebase reads `experience_bucket` for suggestion purposes (nothing reads it at all yet — no suggestion computation exists), satisfying the AC vacuously as scoped in Dev Notes.
- AC #3 — reproduced live: Field=Tech + Role=Software Engineer alone left Continue `disabled=true`; selecting an Experience bucket flipped it to `false`. Matches `test_each_valid_bucket_saves`/`test_invalid_bucket_is_rejected`.
- AC #4 — reproduced live: selected Tech / Software Engineer / 6–10 yrs, clicked Continue (`PUT /me/profile → 200`, DB confirmed), clicked Back, and all three were still shown selected (`aria-pressed="true"` on the two chips, the `6-10` radio still `checked`) — the Role row was still scoped to Tech rather than reverting to the "Pick a field first" placeholder, which is only possible if the component was never destroyed. The animation-replay *trigger* was confirmed to fire correctly (see Debug Log's `MutationObserver` evidence); its visible playback could not be observed because the Browser pane wasn't displayed client-side during this session, freezing the CSS animation timeline for an unrelated, environment-level reason.
- AC #5 — migration applied cleanly; `alembic current` reports `c3d4e5f6a7b8`.

**Deliberately not done, per Dev Notes' explicit scope boundaries:**
- Per-child staggered entrance timing (Story 1.1 review finding, still open) — this story's animation-replay fix operates on the existing single whole-step `.stagger` block, not finer-grained per-child staggering.
- `GET /me/profile` for reload-survival — AC #4 is scoped to Back-from-Step-2 within the same page session, satisfied by the `v-show` fix with no new read endpoint.
- Direct progress-stepper-dot navigation remains unimplemented.

### File List

**New:**
- `alembic/versions/c3d4e5f6a7b8_user_experience_bucket.py`

**Changed:**
- `src/newsagent/models/user.py` (+ `experience_bucket`)
- `src/newsagent/services/profile.py` (+ `EXPERIENCE_BUCKETS`, validation, `_apply` signature)
- `src/newsagent/api/schemas/profile.py` (+ `experience_bucket` on both schemas)
- `src/newsagent/api/routers/me.py` (thread `experience_bucket` through)
- `frontend/src/components/profile-picker/AboutYouStep.vue` (+ segmented control, three-way gate)
- `frontend/src/components/profile-picker/ProfilePickerShell.vue` (`v-show` refactor, animation-replay watcher, Back buttons on Steps 2/3)
- `frontend/src/api/client.ts` (+ `experience_bucket`/`experienceBucket` threading)
- `tests/services/test_profile.py`
- `tests/api/routers/test_me.py`

## Change Log

- 2026-07-27: Story 1.3 implemented end-to-end — `User.experience_bucket`, closed-set validation in `services/profile.py`, extended `PUT /me/profile`, native radio-group segmented control in `AboutYouStep.vue`, and the `v-show`/animation-replay/Back-navigation fix in `ProfilePickerShell.vue`. 9 new tests (185 total). Migration `c3d4e5f6a7b8` applied to the local dev DB with approval.
- 2026-07-27: Live-verified in the browser (follow-up round) — AC #1, #2, #3, #4 all reproduced against a real running dev server. Along the way, diagnosed and (with the user's approval) fixed a stale-worktree backend caused by launching uvicorn outside the project `.venv`; found and fixed two stray lines of leaked tool-syntax at the end of this story file itself.
- 2026-07-27: Story 1.3 drafted. Key design call: fix Back-navigation/state-persistence (AC #4) by switching `ProfilePickerShell.vue`'s step panels from `v-if`/`v-else-if`/`v-else` to `v-show` — this preserves `AboutYouStep`'s local state across step navigation with no lifting/store needed, and matches the approved mockup's own never-destroy-DOM navigation technique more faithfully than the current implementation. Entrance-animation replay is decoupled from component-destruction and implemented separately via the mockup's own reflow trick.
