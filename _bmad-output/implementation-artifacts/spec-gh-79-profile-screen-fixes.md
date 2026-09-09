---
title: 'GH #79 - Profile screen: auth guard, load flash, and step-transition waits'
type: 'bugfix'
created: '2026-09-08'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '0024938d7fb7edc6be2b1413a16350466b9adccd'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An unauthenticated visitor can land on `/preferences` and only discover they need to sign in via a 401 from the API. A returning user's page flashes the wizard before showing their saved summary, and the same layout gap lets `ProfilePickerShell` render underneath the loading/error state too (a related, already-tracked bug). Steps 1-2 of the profile wizard let the user advance, or see stale suggestion content, while their own step-local LLM-backed suggestion call is still in flight.

**Approach:** Add a client-side `requiresAuth` router guard reusing the existing `ensureMe()` auth source. Fix `PreferencesView.vue`'s initial loading state and gate its second `v-if` chain on `loading`/`errorMessage` so neither the summary nor the wizard render prematurely. Gate `AboutYouStep`'s Continue on its own `rolesLoading`; clear `InterestsStep`'s stale Suggested Prompts before each re-fetch. A shared `HybridSpinner` component (new, per the Hybrid Depth UX spine's `{components.spinner}` token added 2026-09-08) replaces the plain "טוען…" text-only states this spec touches.

## Boundaries & Constraints

**Always:** Reuse `ensureMe()` (`frontend/src/auth.ts`) for the new guard, same pattern as the existing `requiresAdmin` branch. Step 2 (`InterestsStep`) stays never-forward-gated (twice-rejected decision, Hybrid Depth UX spine) - no Continue/Skip blocking there. Step 1's fix is the same hard-gate treatment `canContinue` already applies to Field/Role/Experience, not a new pattern.

**Ask First:** none anticipated.

**Never:** Don't touch the topic-suggestion background computation or its `suggestion_request_seq`/`BackgroundTask` mechanism (AD-5) - out of scope, would conflict with NFR2. Don't restyle `PreferencesView.vue` - the visual pass is GH #79 item 3, tracked separately in the Hybrid Depth UX spine (`_bmad-output/planning-artifacts/ux-designs/ux-news-agent-2026-07-21/`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Unauthenticated visit | `ensureMe()` resolves null | Redirected to `/` before `PreferencesView` mounts | N/A |
| Returning user, complete profile | `profile.field_name` set | Loading shown first; summary renders directly, no wizard flash | N/A |
| New user, no profile yet | `profile.field_name` null | Loading shown first; wizard renders, no summary/toggle flash | N/A |
| Load fails | `getMyProfile`/`listMyPreferences` throws | Error banner shown; neither summary nor wizard render underneath it | Existing `errorMessage` branch now also suppresses the second chain |
| Field just selected | `rolesLoading = true` | Continue stays disabled, its label switches to "טעינה…" (same pattern as the existing `saving` -> "שומר…" state; noun form per CLAUDE.md's gender-neutral copy rule, not the verb "טוען…") until the Role fetch resolves | Existing `loadError` message still applies |
| Re-entering Step 2 | `props.active` flips true again, prompts already loaded once | Old prompts cleared before the new fetch starts - no stale-then-replaced flash | Fetch failure -> empty prompts, same as today |

</frozen-after-approval>

## Code Map

- `frontend/src/router/index.ts` -- add `requiresAuth` meta + guard branch, reusing `ensureMe()`
- `frontend/src/components/HybridSpinner.vue` -- new. Reuses `frontend/src/assets/logo-mark.svg`'s sparkle+bars path data (`currentColor` fills, not the mark's literal navy/gold), only the sparkle rotating; `size: 'inline' | 'standalone'` prop; respects `prefers-reduced-motion`. Per `DESIGN.md`'s `{components.spinner}` token (revised 2026-09-08 to the logo-based shape)
- `frontend/src/views/PreferencesView.vue` -- `loading` initial value; gate the second `v-if`/`v-else` chain on `!loading && !errorMessage`; pair the existing "טוען…" text with `<HybridSpinner size="standalone" />` and change it to "טעינה…" (noun form, not replaced by the spinner alone)
- `frontend/src/components/profile-picker/AboutYouStep.vue` -- `canContinue` gains `!rolesLoading.value`; Continue button gains an inline `<HybridSpinner size="inline" />` + "טעינה…" label while `rolesLoading`; `rolePlaceholder`'s "טוען תפקידים…" becomes "טעינת תפקידים…" (same noun-form rule)
- `frontend/src/components/profile-picker/InterestsStep.vue` -- reset `promptSuggestions` at the top of the `props.active` watch handler

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/router/index.ts` -- add `meta: { requiresAuth: true }` to the `/preferences` route; add a `beforeEach` branch that calls `ensureMe()` and redirects to `/` when it resolves null -- closes item 1
- [x] `frontend/src/components/HybridSpinner.vue` -- new component, inline SVG reusing a single sparkle path from `frontend/src/assets/logo-mark.svg` (the mark's second sparkle and its 3 bars both dropped) with a `currentColor` fill instead of the mark's hardcoded gold; scaled ~2.4x via a nested `<g transform="translate(32,32) scale(2.4) translate(-46,-17)">`. **Motion: twinkle, not rotation** -- CSS `@keyframes` scale (0.82 to 1.08) + opacity (**0.3** to 1, widened from 0.55) pulse, 1.3s ease-in-out, frozen at rest under `prefers-reduced-motion` (no rotation transform - the sparkle glyph is 4-fold symmetric, so rotating it reads as a wobble, not a spin). `size: 'inline' | 'standalone'` prop, `size-inline` = **16px** (not 14px) -- both size and opacity-floor widened same-session after the inline/button context read as "really weak." Confirmed live by the user (party-mode + a dedicated UX subagent round, 2026-09-08) -- ready to build, not pending sign-off
- [x] `frontend/src/views/PreferencesView.vue` -- change `const loading = ref(false)` to `ref(true)`; change the second chain's `v-if="showSummary"` / `v-else` to `v-if="!loading && !errorMessage && showSummary"` / `v-else-if="!loading && !errorMessage"`; change `<div v-if="loading">טוען…</div>` to `<div v-if="loading"><HybridSpinner size="standalone" /> טעינה…</div>` (spinner pairs with the noun-form text, never replaces it) -- closes item 2, the related 2026-08-17 deferred-work entry about this same chain rendering under the loading/error state, and the party-mode loading-UX ask
- [x] `frontend/src/components/profile-picker/AboutYouStep.vue` -- change `canContinue` to `fieldSatisfied.value && roleSatisfied.value && experienceBucket.value !== null && !rolesLoading.value` -- closes the Step 1 half of item 4
- [x] `frontend/src/components/profile-picker/AboutYouStep.vue` -- Continue button gains `<HybridSpinner size="inline" />` + label `{{ rolesLoading ? "טעינה…" : (saving ? "שומר…" : "המשך") }}` -- gives the disabled state a visible reason instead of a silently dead button (party-mode round, 2026-09-08)
- [x] `frontend/src/components/profile-picker/InterestsStep.vue` -- add `promptSuggestions.value = [];` as the first line inside the `watch(() => props.active, ...)` handler, before the fetch -- closes the Step 2 half of item 4
- [x] Update/extend `PreferencesView.spec.ts` and `AboutYouStep.spec.ts` per the I/O matrix above, plus a small `HybridSpinner.spec.ts` (renders, respects `prefers-reduced-motion`)

**Acceptance Criteria:**
- Given no active session, when a visitor navigates to `/preferences`, then they are redirected to `/` before `PreferencesView` mounts.
- Given a returning user with a complete profile, when `/preferences` loads, then the summary renders directly with no wizard flash beforehand.
- Given a load error, when the error banner renders, then neither the summary nor `ProfilePickerShell` render underneath it.
- Given a Field was just selected, when the Role-suggestion fetch is in flight, then Continue stays disabled, shows a spinner, and reads "טעינה…" until it resolves.
- Given `/me/preferences` is loading, when the initial fetch is in flight, then a spinner appears beside the (now noun-form) "טעינה…" text.
- Given Suggested Prompts already loaded once, when the user leaves and returns to Step 2, then no stale prompt is visible before the fresh fetch resolves.

### Review Findings

- [x] [Review][Decision] InterestsStep chip flicker on every Step 2 re-entry — resolved: user chose "clean only when something really changed." Replaced the unconditional `promptSuggestions.value = []` with a Field/Role/Experience-Bucket key comparison (`lastPromptsProfileKey`) — re-fetches (and only then clears) when that key actually differs from the last successful fetch; an unchanged re-entry now skips the network call entirely and leaves existing chips untouched. [frontend/src/components/profile-picker/InterestsStep.vue] Covered by two new tests in `InterestsStep.spec.ts` ("keeps existing prompt chips across a re-entry when unchanged" / "re-fetches when Field/Role changed").
- [x] [Review][Patch] `AboutYouStep.vue`'s Continue button unexpectedly changed `"שומר…"` to `"שמירה..."` [frontend/src/components/profile-picker/AboutYouStep.vue:68] — fixed, reverted to `"שומר…"`, matching this spec's own `"טעינה…"` and `InterestsStep.vue`/`TopicsStep.vue`.
- [x] [Review][Defer] Router `beforeEach`'s new `requiresAuth` branch has no direct test coverage [frontend/src/router/index.ts] — deferred, matches the pre-existing untested `requiresAdmin` branch in the same file/pattern.
- [x] [Review][Defer] Signed-out visit to `/admin` double-redirects (`/admin` → `/preferences` → `/`) [frontend/src/router/index.ts:46-58] — deferred, invisible to the user (Vue Router guards resolve before render), low severity.
- [x] [Review][Defer] `requiresAuth` redirect doesn't preserve the intended destination (no `redirect`/`next` query param) [frontend/src/router/index.ts:53-58] — deferred, matches the existing `requiresAdmin` pattern's identical limitation, out of scope for this bugfix.
- [x] [Review][Defer] `InterestsStep`'s Suggested Prompts fetch has no request-token guard against rapid `props.active` toggling [frontend/src/components/profile-picker/InterestsStep.vue:84-95] — deferred, pre-existing race that predates this diff's one-line addition.
- [x] [Review][Defer] No `aria-live` region for the new loading-state transitions (Continue button label swap, PreferencesView loading→content) [frontend/src/views/PreferencesView.vue, frontend/src/components/profile-picker/AboutYouStep.vue] — deferred, consistent with the project-wide accessibility gap already tracked as open in the Hybrid Depth UX spine's Accessibility Floor section.
- [x] [Review][Defer] `PreferencesView`'s loading/error state and its summary/wizard state are two independently-gated `v-if` chains rather than one unified chain [frontend/src/views/PreferencesView.vue] — deferred, matches this spec's own literal Task 53 instructions and the pre-existing two-chain architecture; a valid simplification idea but not required for correctness.
- [x] [Review][Defer] `canContinue` computed references `rolesLoading` before its declaration in the same script block [frontend/src/components/profile-picker/AboutYouStep.vue:146-162] — deferred, cosmetic only; Vue's lazy computed evaluation makes this functionally safe, confirmed by two independent reviewers.

## Spec Change Log

- **2026-09-09 - the `"שומר…"` review finding above was wrong, and is reversed.** That finding treated `"שמירה…"` as an unintended drift and restored `"שומר…"` for consistency with the sibling step components. But `"שומר…"` is masculine present tense, exactly the shape CLAUDE.md's gender-neutral Hebrew rule tells us to rewrite around, and the noun form was the correct instinct. All three step components (`AboutYouStep`, `InterestsStep`, `TopicsStep`) now read `"שמירה…"`, matching the `"טעינה…"` this spec already chose on the same reasoning. The regression guard did not catch it because its denylist only carries the imperative `"שמור"`, not the present-tense `"שומר"`.
- **2026-09-09 - a second gendered string surfaced in the same audit.** `InterestsStep.vue`'s textarea placeholder opened with the masculine imperative `"כתוב בחופשיות..."`; reworded to `"אפשר לכתוב בחופשיות..."` and `"כתוב"` added to `gendered-copy.spec.ts`'s sentence-start denylist.

## Verification

**Commands:**
- `cd frontend && npx vue-tsc --noEmit` -- expected: no new type errors
- `cd frontend && npx vitest run` -- expected: full suite passes, including updated `PreferencesView.spec.ts` / `AboutYouStep.spec.ts`

**Manual checks (if no CLI):**
- Browser pane: sign out, navigate directly to `/preferences`, confirm redirect to `/`. Sign in as a returning seeded user, confirm no wizard flash and a spinner beside "טעינה…" during the page's own load. Select a Field and confirm Continue shows the spinner + "טעינה…" while disabled, the Role row placeholder reads "טעינת תפקידים…", and the spinner freezes (no twinkle) with `prefers-reduced-motion` emulated.
