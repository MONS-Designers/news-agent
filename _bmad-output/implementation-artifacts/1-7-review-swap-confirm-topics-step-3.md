---
baseline_commit: e72e881
---

# Story 1.7: Review, swap, and confirm up to 4 Topics, Step 3

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to see my suggested topics, adjust them if needed, and save, capped at a focused 4,
so that I don't have to configure an open-ended grid myself.

*Realizes FR10 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.3).*

## Acceptance Criteria

1. **Given** Step 2 completes and the flow advances, **when** Step 3 mounts, **then** it polls `GET /me/topic-suggestions` until `suggestion_status` is `ready` or `failed`, showing a brief loading state in between.
2. **Given** suggestions are `ready`, **when** Step 3 renders, **then** up to 4 candidate Topics appear pre-picked as highlighted pills, any additional candidates appear as "faint" swappable options, and a "Selected N / 4" counter is shown.
3. **Given** suggestions `failed`, or Field/Role/Interest yielded nothing beyond the popularity fallback, **when** Step 3 renders, **then** it still shows a non-empty set of picked Topics - never a dead end.
4. **Given** I tap a "faint" candidate, **when** I do, **then** it swaps into my picked set in place of one existing pick, keeping my total at exactly 4; attempting a 5th without deselecting one first has no effect.
5. **Given** a Topic pill (picked or faint) or the "Save preferences" control, **when** either renders, **then** it is a real `<button>` element with `aria-pressed` reflecting picked state, never `<div onclick>` - same accessibility baseline as Story 1.1.
6. **Given** I click "Save preferences", **when** the save request is sent, **then** it calls the same `services/preferences.py:set_preferences` the existing raw Topic toggle grid already uses, enforcing the platform-wide 4-Topic cap via a dedicated `TopicCapExceededError` with a stable `{"error": "topic_cap_exceeded"}` detail, surfaced identically regardless of which UI path triggered it.
7. **Given** I already had more than 4 Topics selected from the old unlimited grid before this feature shipped, **when** I next save via either path, **then** the cap applies going forward - retroactive migration/backfill of pre-existing over-cap selections is explicitly out of scope for this story (tracked as an open PRD question).

## Tasks / Subtasks

- [x] Task 1: `services/preferences.py` - the 4-Topic cap (AC: #6, #7)
  - [x] 1.1 `MAX_TOPICS = 4` and `TopicCapExceededError(ValueError)` with `self.detail = {"error": "topic_cap_exceeded", "max_topics": MAX_TOPICS}`.
  - [x] 1.2 `set_preferences`'s first check: `if len(set(topic_ids)) > MAX_TOPICS: raise TopicCapExceededError()`. Applies to every save through this function, including the existing raw-grid path with zero frontend changes there.
  - [x] 1.3 Cap-check ordered before the unknown-id check - deterministic, tested.

- [x] Task 2: API - surface the cap error's structured detail (AC: #6)
  - [x] 2.1 `update_my_preferences` catches `preferences.TopicCapExceededError` before the generic `except ValueError`, returns `HTTPException(400, detail=error.detail)`.

- [x] Task 3: Frontend - `client.ts` additions (AC: #1)
  - [x] 3.1 `TopicSuggestions` interface + `getTopicSuggestions()` → `GET /me/topic-suggestions`.

- [x] Task 4: Frontend - `TopicsStep.vue` (AC: #1, #2, #3, #4, #5)
  - [x] 4.1–4.9 as planned: polling with a bounded budget, parallel fetch of suggestions + full preferences, ranked-candidates-vs-fallback population, FIFO swap mechanic, real `<button>` pills with `aria-pressed`, local save/error feedback, Back button, `back`/`saved` emits.
  - **Correction found during live verification (not in the original plan):** the component originally called its `load()` function unconditionally at `<script setup>` top level. Because `ProfilePickerShell.vue` keeps all three steps mounted via `v-show` (Story 1.3's design, so state survives Back navigation), this meant `load()` fired at *page load*, before the user had even filled in Step 1 - capturing stale `suggested_topic_ids` from a previous session/save instead of the fresh one this flow's own save produces. Fixed by adding an `active: boolean` prop (`ProfilePickerShell` passes `:active="currentStep === 3"`) and a `watch` that calls `load()` only the first time `active` becomes `true`. This is a real fix, not a refinement - the original code violated AC #1's "when Step 3 mounts" in the user-facing sense.

- [x] Task 5: Frontend - wire `TopicsStep` into the shell and the page (AC: #1)
  - [x] 5.1 `ProfilePickerShell.vue`: Step 3 placeholder → `<TopicsStep :active="currentStep === 3" @back="currentStep = 2" @saved="emit('topics-saved')" />`; `topics-saved` added to the shell's `defineEmits`.
  - [x] 5.2 **Corrected from the original plan.** The plan called for `<ProfilePickerShell @topics-saved="loadPreferences" />`, reusing the existing `loadPreferences`. Live verification caught a real bug in that plan: `loadPreferences` sets `loading.value = true` for its duration, and `loading` gates `ProfilePickerShell` behind a `v-if` in `PreferencesView.vue` - so wiring it this way destroyed and recreated the entire guided flow immediately after a successful Step 3 save, snapping the user back to a blank Step 1 right after they finished. Fixed with a new `refreshPreferencesQuietly()` function that re-fetches `preferences.value` without touching `loading` (or `errorMessage`), wired as `@topics-saved="refreshPreferencesQuietly"` instead.

- [x] Task 6: Tests (AC: all)
  - [x] 6.1 `tests/services/test_preferences.py` - exactly-4 succeeds; 5 raises `TopicCapExceededError` with the correct `.detail`; cap checked before unknown-id; 0 ids still succeeds.
  - [x] 6.2 `tests/api/routers/test_me.py` - 5 ids → 400 with the structured detail dict.
  - [x] 6.3 `npm run type-check` clean.
  - [x] 6.4 **Live-verified in the browser**, including finding and fixing the two bugs above - see Debug Log / Completion Notes for the full walkthrough (Steps 1→2→3, swap mechanic with a real 5th topic, deselect, Save preferences, Back-from-Step-3 with Step 2's text intact).
  - [x] 6.5 Full suite green: 223 passed (5 new); `mypy` and `ruff` clean; `vue-tsc` clean.

## Dev Notes

### Read these before writing code

- [`src/newsagent/services/preferences.py`](../../src/newsagent/services/preferences.py) - `set_preferences`'s shape; the cap is one new guard clause.
- [`frontend/src/views/PreferencesView.vue`](../../frontend/src/views/PreferencesView.vue) - owns `preferences`/`loading`/`saving`/`saveMessage`/`errorMessage`, `loadPreferences`/`savePreferences`. **`loading` gates `ProfilePickerShell` via `v-if`** - this is the fact that made the original Task 5.2 plan wrong; any future code that wants to refresh `preferences` from a child of `ProfilePickerShell` must not go through `loadPreferences`.
- [`frontend/src/components/profile-picker/AboutYouStep.vue`](../../frontend/src/components/profile-picker/AboutYouStep.vue), [`InterestsStep.vue`](../../frontend/src/components/profile-picker/InterestsStep.vue) - the established per-step pattern.
- [`frontend/src/components/profile-picker/ProfilePickerShell.vue`](../../frontend/src/components/profile-picker/ProfilePickerShell.vue) - **all three step components mount immediately and stay mounted via `v-show`** (Story 1.3). Any child step that fetches session-specific data on its own `onMounted`/setup-time (rather than reacting to when it actually becomes the visible step) will fetch too early. `TopicsStep` is the first step in this feature to actually need fresh-per-visit data (Field/Role options in `AboutYouStep` are static/global, not session-save-dependent), which is why this gotcha hadn't surfaced in Stories 1.1–1.4.
- [`src/newsagent/suggestions/popularity.py`](../../src/newsagent/suggestions/popularity.py), [`src/newsagent/services/profile.py:_topic_popularity`](../../src/newsagent/services/profile.py) - why `suggested_topic_ids` is already the full topic universe, ranked, uncapped.
- [`mockups/flow-hybrid-depth-steps.html`](../planning-artifacts/ux-designs/ux-news-agent-2026-07-21/mockups/flow-hybrid-depth-steps.html) lines 236–249 - reference markup/copy. No working swap JS to reverse-engineer.

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-9** - the cap lives in exactly one place, `services/preferences.py:set_preferences`. Step 3 calls the same `updateMyPreferences` client function the raw grid already uses.
- **Consistency Conventions → Frontend controls** - every topic pill and the Save/Back buttons are real `<button>` elements with `aria-pressed` where applicable.
- **No AD-1/AD-3/AD-5/AD-7 changes.**

### Explicit scope boundary

- No retroactive migration/backfill for existing over-cap users (AC #7).
- No distinct frontend copy for the cap-exceeded error.
- No changes to the raw grid's own UI to visually enforce or warn about the 4-cap.
- No direct progress-stepper-dot navigation, no "flow complete" indicator.
- No frontend unit tests (no test runner exists in this project).

### Project Structure Notes

- New frontend file: `frontend/src/components/profile-picker/TopicsStep.vue`.
- Changed backend files: `src/newsagent/services/preferences.py`, `src/newsagent/api/routers/me.py`, `tests/services/test_preferences.py`, `tests/api/routers/test_me.py`.
- Changed frontend files: `frontend/src/api/client.ts`, `frontend/src/components/profile-picker/ProfilePickerShell.vue`, `frontend/src/views/PreferencesView.vue`.
- No migration. No new dependencies.

### References

- [Source: epics.md#Story-1.7] - acceptance criteria, verbatim.
- [Source: ARCHITECTURE-SPINE.md#AD-9, Dependency-direction, Consistency-Conventions].
- [Source: EXPERIENCE.md#Component-Patterns rows "Topic pill grid", "Save preferences button", #State-Patterns rows "Step 3, first load", "Save"].
- [Source: DESIGN.md#Components "Topic pill"].
- [Source: 1-6-async-suggestion-computation-after-save.md] - `GET /me/topic-suggestions`'s response shape; that story's own identity-map test-fixture gotcha (different issue, same "watch for staleness" theme as this story's two live-verification findings).
- [Source: 1-3-experience-bucket-completing-step-1-gate.md] - the `v-show`/animation-replay/Back-button mechanism, and the exact reason all three steps stay mounted (which is also what caused this story's Task 4.1 bug).

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- Confirmed no migration needed for this story (no schema change).
- **Live verification uncovered two real frontend bugs, both fixed before completion** (see Tasks 4.1 and 5.2 above for the technical detail):
  1. `TopicsStep.vue` polling fired at page load instead of at Step-3-entry, due to the `v-show`-always-mounted architecture - fixed with an `active` prop + one-shot `watch`.
  2. Wiring `@topics-saved` to the existing `loadPreferences` reset the entire guided flow to Step 1 after a successful Step 3 save, because `loadPreferences` toggles `loading`, which gates `ProfilePickerShell` behind `v-if` - fixed with a new `refreshPreferencesQuietly()` that doesn't touch `loading`.
- Both bugs were caught only through live browser verification, not through `vue-tsc` (which stayed clean throughout) or the backend test suite (unaffected, since both bugs were pure frontend wiring issues) - reinforcing why this story's live-verification step was not skippable despite no schema change.
- Verification environment notes: the dev backend needed restarting twice - once because it was running via the global Python interpreter (same class of issue as Story 1.3/1.4), and once because the local dev DB was missing Story 1.6's migration (`e5f6a7b8c9d0`), applied with the user's approval. Temporary test topics ("Robotics", "Astronomy") were added directly to the dev DB to exercise the faint-pill swap mechanic (the seeded install only ships 3 topics, not enough to produce a faint pill) and removed afterward, along with their `UserTopicPreference` rows, once verification was complete.
- Authenticated via the same locally-minted session-cookie technique as prior stories (`verify-story-1-1@example.com`, id=2).

### Completion Notes List

**All 6 tasks complete, including two bug fixes found during live verification.** 223 backend tests pass (5 added on top of the 218 baseline); `mypy`, `ruff`, and `vue-tsc` all clean.

**Per acceptance criterion, live-verified in the browser** (real seeded DB, authenticated session, plus two temporary extra topics to exercise the swap mechanic):

- AC #1 - confirmed the poll correctly waits for `ready`/`failed` and (after the Task 4.1 fix) only starts once the user actually reaches Step 3, not at page load.
- AC #2 - confirmed 4 picked pills (accent-styled, `✕`) + faint candidates + a live "Selected N / 4" counter, using real suggestion data from `GET /me/topic-suggestions`.
- AC #3 - the fallback-to-existing-subscriptions path (Task 4.4) was implemented and unit-reasoned through; not separately forced in the browser (would require simulating a `failed` status), but the same code path is exercised whenever the ready-branch condition is false, which is directly readable and was not touched by either bug fix.
- AC #4 - swap mechanic verified live: tapping a faint pill ("Astronomy") correctly dropped the oldest pick ("AI", FIFO) and added the new one, staying at exactly 4; tapping a picked pill correctly deselected it (dropping to 3/4).
- AC #5 - confirmed via `aria-pressed` inspection on every pill; all controls are genuine `<button>` elements.
- AC #6 - confirmed `PUT /api/me/preferences` succeeds and the raw grid below updates to match (via the corrected `refreshPreferencesQuietly`), without resetting the guided flow.
- AC #7 - covered by the backend unit tests (`test_set_preferences_over_cap_raises` et al.); not separately re-verified live (would require an existing over-cap user, not present in this dev DB).

### File List

**New:**
- `frontend/src/components/profile-picker/TopicsStep.vue`

**Changed:**
- `src/newsagent/services/preferences.py` (+`MAX_TOPICS`, `TopicCapExceededError`, cap check)
- `src/newsagent/api/routers/me.py` (+cap-error branch)
- `frontend/src/api/client.ts` (+`TopicSuggestions`, `getTopicSuggestions`)
- `frontend/src/components/profile-picker/ProfilePickerShell.vue` (Step 3 placeholder → `TopicsStep` with `:active` prop, +`topics-saved` emit, removed now-orphaned `.placeholder`/`.nav-row`/`.btn-back` styles)
- `frontend/src/views/PreferencesView.vue` (+`refreshPreferencesQuietly`, listener wiring)
- `tests/services/test_preferences.py`
- `tests/api/routers/test_me.py`

## Change Log

- 2026-07-27: Story 1.7 implemented end-to-end - `MAX_TOPICS`/`TopicCapExceededError` in `services/preferences.py`, structured 400 detail in the router, `TopicsStep.vue` with polling/swap/save. 5 new backend tests (223 total). Live browser verification found and fixed two real frontend bugs: premature polling caused by the `v-show`-always-mounted architecture (fixed with an `active` prop), and a full guided-flow reset after Step 3's save caused by reusing `loadPreferences` (fixed with a new non-`loading`-touching refresh function). Both are documented in Dev Notes so the same class of mistake isn't repeated in a future story that adds another `v-show`-mounted step needing its own fresh-per-visit data.
- 2026-07-27: Story 1.7 drafted. Key design calls: single-mutation-point 4-cap; `TopicsStep` owns its own save/feedback rather than lifting state; FIFO swap (oldest pick drops first); non-empty-always fallback prefers the user's existing subscriptions.
