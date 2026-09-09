---
title: 'GH #79 item 3 - Hybrid Depth visual pass on the profile summary + subscription toggle'
type: 'feature'
created: '2026-09-09'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'e28697be81d84eec37f13bd5ef6556230ef6f22a'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `PreferencesView.vue`'s returning-user summary (Field/Role/Experience, subscribed topics, edit button) and the weekly-email subscription-toggle row are still plain neutral-Tailwind - unstyled next to the Hybrid Depth wizard they lead to/from. This was deliberately deferred out of GH #79's items 1/2/4 (bugfixes) into its own pass; the UX design work for it is already done this session (`DESIGN.md`/`EXPERIENCE.md` extended, a working mock at `mockups/key-profile-summary.html`, `HybridSpinner.vue` already shipped).

**Approach:** Extract `ProfilePickerShell.vue`'s void/orb-parallax/grain background chrome into a new reusable `HybridDepthBackground.vue` (slot-based), so the summary can sit inside the identical background without duplicating ~100 lines of parallax/motion-reduce/hover-query logic. Restyle `PreferencesView.vue`'s summary panel, topics-stale alert, and subscription-toggle row to Hybrid Depth, wrapped in one `HybridDepthBackground` instance. The page's own top-level heading and its loading/error states stay in the plain baseline, per the UX spine's documented scope boundary - untouched.

## Boundaries & Constraints

**Always:** Reuse existing Tailwind class constants verbatim from sibling step components rather than re-deriving them - `TOPIC_PICKED`/`TOPIC_BASE` from `TopicsStep.vue` (read-only topic pills, minus the click handler and "✕"), `BTN_PRIMARY`/`BTN_BASE` from `AboutYouStep.vue`/`TopicsStep.vue` (edit-profile button, the topics-stale alert's action button). Orb parallax, motion-reduce, and hover-query logic moves verbatim from `ProfilePickerShell.vue` into `HybridDepthBackground.vue` - no behavior change to the wizard's existing parallax. No new copy - every Hebrew string in scope already exists in the current template unchanged (already gender-neutral-audited this session), this is a visual pass only.

**Ask First:** none anticipated - the shared-component extraction was already confirmed with the user this session.

**Never:** Don't touch `PreferencesView.vue`'s `loading`/`errorMessage` states, the page's own `<h1>`/subheading, or any gating logic from GH #79 items 1/2/4 (just shipped) - those stay exactly as committed. Don't change `ProfilePickerShell.vue`'s stepper/header/step-panel markup or behavior, only relocate its background chrome. Don't add responsive/mobile behavior beyond what the UX spine already specifies (dl-grid and subscription row already documented as collapsing at the wizard's existing `sm:` breakpoint - implement that convention, don't invent a new one).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Returning user, complete profile | `showSummary` true | Summary panel + subscribed-topic pills + edit button render inside `HybridDepthBackground`, matching `mockups/key-profile-summary.html`'s "מצב 1" | N/A |
| Profile changed, topics stale | `topicsStale` true | `alert-frame`-styled box (accent-tinted border, no second hue) renders above the summary panel with its primary "עדכון הנושאים שלי" button | N/A |
| Subscription active/paused | `subscription.unsubscribed` false/true | Toggle row shows "פעיל"/"מושהה - ... לא יישלח" with a `button-secondary`-styled toggle button | N/A |
| Subscription toggle in flight | `subscriptionSaving` true | Toggle button disables (existing behavior, now with Hybrid Depth's `disabled:opacity-50`-equivalent) | N/A |
| Narrow viewport (<640px) | Any of the above | Summary `dl` collapses to 1 column, subscription row stacks vertically - matches the wizard's existing `sm:` breakpoint convention | N/A |
| `prefers-reduced-motion` | User has it enabled | `HybridDepthBackground`'s orbs freeze (verbatim behavior moved from `ProfilePickerShell`, not reimplemented) | N/A |
| Wizard (`editing = true`) | User clicks "עריכת פרופיל" | `ProfilePickerShell` still renders correctly via `HybridDepthBackground` - no visual or behavioral regression from the extraction | N/A |

</frozen-after-approval>

## Code Map

- `frontend/src/components/HybridDepthBackground.vue` -- new. Void bg + 3 parallax orbs + grain overlay + motion-reduce/hover-query logic, extracted verbatim from `ProfilePickerShell.vue`; default slot for content
- `frontend/src/components/profile-picker/ProfilePickerShell.vue` -- refactored to render its header/stepper/step-panel content inside `<HybridDepthBackground>`; all orb/parallax refs and lifecycle logic removed (now lives in the extracted component)
- `frontend/src/views/PreferencesView.vue` -- summary panel, topics-stale alert, and subscription-toggle row restyled in Hybrid Depth Tailwind classes, wrapped in one `<HybridDepthBackground>`; loading/error states and the page's own heading untouched
- `frontend/src/components/__tests__/HybridDepthBackground.spec.ts` -- new, covers the extracted lifecycle (mounts/unmounts cleanly, freezes under `prefers-reduced-motion`)
- `frontend/src/components/profile-picker/__tests__/ProfilePickerShell.spec.ts` -- adjust if its existing lifecycle test now needs `HybridDepthBackground` context
- `frontend/src/views/__tests__/PreferencesView.spec.ts` -- extend for the restyled summary/subscription markup where existing assertions target specific classes

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/components/HybridDepthBackground.vue` -- create with the void/orb/grain template and the orb-parallax/motion-reduce/hover-query script logic moved verbatim from `ProfilePickerShell.vue` (see `## Boundaries & Constraints`); default `<slot />` for content
- [x] `frontend/src/components/profile-picker/ProfilePickerShell.vue` -- replace the outer `bg-hd-bg` div and its orb/grain markup with `<HybridDepthBackground>`, keeping the kicker/title/stepper/step-panel content as its slot; remove the now-relocated orb refs, `orbConfigs`, `applyOrbTransforms`, `onMouseMove`, `onScroll`, `motionQuery`/`hoverQuery` handling from its own script
- [x] `frontend/src/views/PreferencesView.vue` -- wrap the `showSummary` block (topics-stale alert + summary panel) and the subscription-toggle row together in one `<HybridDepthBackground>`; restyle the `dl` (Field/Role/Experience/Interests) as a Hybrid Depth panel (2-col `sm:grid-cols-2`, 1-col below), subscribed topics as read-only `TOPIC_PICKED`-style pills (no click handler, no "✕"), edit-profile button as `BTN_PRIMARY`, topics-stale as an `alert-frame` box with an inline `BTN_PRIMARY` action, and the subscription row as a `button-secondary`-styled toggle that stacks below `sm`
- [x] `frontend/src/components/__tests__/HybridDepthBackground.spec.ts` -- new: renders its slot content, attaches/detaches `matchMedia`/scroll listeners cleanly, freezes orb transforms under `prefers-reduced-motion`
- [x] Update `ProfilePickerShell.spec.ts` and `PreferencesView.spec.ts` per the I/O matrix above

**Acceptance Criteria:**
- Given a returning user with a complete profile, when `/preferences` loads, then the summary panel and subscription row render inside the Hybrid Depth void/orb background, matching `mockups/key-profile-summary.html`.
- Given `topics_stale_at` is set, when the summary renders, then the stale-topics warning uses the `alert-frame` treatment (accent-tinted border, no second hue), not the old amber Tailwind banner.
- Given the viewport is below 640px, when the summary renders, then the `dl` collapses to one column and the subscription row stacks vertically.
- Given `prefers-reduced-motion` is set, when either the wizard or the summary renders, then the orb parallax is frozen in both, with identical behavior to before the extraction.
- Given the wizard is entered via "עריכת פרופיל", when it renders, then `ProfilePickerShell`'s existing stepper/step behavior is unchanged - no visual or functional regression from the `HybridDepthBackground` extraction.

### Review Findings

- [x] [Review][Patch] `BTN_SECONDARY`'s `disabled:opacity-50` doesn't match the `disabled:opacity-35` convention every sibling button (`BTN_PRIMARY`/`BTN_BASE`, `TopicsStep.vue`, `AboutYouStep.vue`) uses [frontend/src/views/PreferencesView.vue:130] — carried over from the old plain-Tailwind button's `disabled:opacity-50` instead of adopting the new design system's value.
- [x] [Review][Patch] Topics-stale alert uses raw `border-[rgba(109,123,255,0.4)] bg-[rgba(109,123,255,0.14)]` instead of the codebase's established `hd-accent-2` token convention (e.g. `ChipRow.vue`/`ProfilePickerShell.vue` use `border-hd-accent-2/NN bg-hd-accent-2/[0.NN]`) [frontend/src/views/PreferencesView.vue:25], and the new test asserts on that raw rgba string [frontend/src/views/__tests__/PreferencesView.spec.ts:~137] — locks in the anti-pattern so a future token fix would break the test instead of being caught by it.
- [x] [Review][Patch] `HybridDepthBackground.spec.ts`'s "does not freeze orb transforms when prefers-reduced-motion is off" test never dispatches a `mousemove`/`scroll` event, so it passes even if the un-freeze code path is fully broken - tautological, not real coverage.
- [x] [Review][Patch] `ProfilePickerShell.spec.ts` was left untouched despite the spec's own checklist marking it done, and has no test asserting `ProfilePickerShell` now composes `HybridDepthBackground` - its existing lifecycle test only passes incidentally (the real child component renders unstubbed underneath it), not because anything asserts the composition explicitly.
- [x] [Review][Patch] Stale test comment in `PreferencesView.spec.ts` (~line 206) still describes "the template's second, independent v-if/v-else block," which this diff merged away into one chain - comment now misdescribes the actual implementation.
- [x] [Review][Defer] `BTN_BASE`/`BTN_PRIMARY` is now duplicated across 4 files (`InterestsStep.vue`, `TopicsStep.vue`, `AboutYouStep.vue`, `PreferencesView.vue`) with no shared constants module [frontend/src/views/PreferencesView.vue] — deferred, matches the pre-existing copy-paste convention already present before this diff across 3 files; a real DRY opportunity but not this diff's regression to fix alone.
- [x] [Review][Defer] `HybridDepthBackground`'s `mousemove`/`scroll` listeners are attached to `window` with no instance scoping [frontend/src/components/HybridDepthBackground.vue] — deferred, currently harmless (summary/wizard are mutually exclusive via `v-if`/`v-else`, only one instance ever mounts), but nothing prevents two simultaneous instances double-handling events if this component is ever reused a third place.
- [x] [Review][Defer] Reduced-motion handling now lives in three uncoordinated places (`HybridDepthBackground`'s persistent `matchMedia` listener, `ProfilePickerShell.replayEntrance`'s ad-hoc one-off `matchMedia` read, and Tailwind's `motion-reduce:` CSS variant on `STAGGER`) [frontend/src/components/profile-picker/ProfilePickerShell.vue] — deferred, a real maintainability note, not a defect; the split was a conscious tradeoff (see the file's own comment) rather than an oversight.
- [x] [Review][Defer] Orb `<div>`s keep `will-change-transform` in their static class list even when frozen under `prefers-reduced-motion` [frontend/src/components/HybridDepthBackground.vue] — deferred, trivial GPU-layer cost, not worth a special-cased class removal for this.
- [x] [Review][Defer] `replayEntrance`'s comment documents an implicit contract with `HybridDepthBackground`'s own reduced-motion handling rather than sharing state [frontend/src/components/profile-picker/ProfilePickerShell.vue] — deferred, already a conscious, documented tradeoff by the implementer (avoids unnecessary prop/emit plumbing for a same-frame CSS-suppressed animation).
- [x] [Review][Defer] Reduced-motion re-enable (`handleMotionChange` transitioning back to normal) doesn't recompute the orb transform until the next `mousemove`/`scroll` event, so orbs stay visually pinned at `translate(0,0)` briefly [frontend/src/components/HybridDepthBackground.vue] — deferred, confirmed pre-existing (moved verbatim from `ProfilePickerShell.vue`, not introduced by this diff).
- [x] [Review][Defer] `onMouseMove`'s `event.clientX / window.innerWidth` has no zero-guard against a 0×0 viewport [frontend/src/components/HybridDepthBackground.vue] — deferred, confirmed pre-existing (moved verbatim), and not practically reachable in normal browser usage.
- [x] [Review][Defer] No automated test covers the `dl`'s `grid-cols-1 sm:grid-cols-2` collapse or the subscription row's `flex-col sm:flex-row` stacking, nor `prefers-reduced-motion` from `PreferencesView`'s own tree (only `HybridDepthBackground.spec.ts` covers it in isolation) [frontend/src/views/__tests__/PreferencesView.spec.ts] — deferred, the spec's own Verification section already assigns this to manual browser-pane QA rather than automated coverage; acceptable as specified, revisit if this pattern recurs.

## Spec Change Log

- **2026-09-09 - the scope boundary this spec inherited was reversed.** This spec deliberately left `PreferencesView.vue`'s own `<h1>`, sub-line and loading/error states in the plain neutral-Tailwind baseline, per DESIGN.md's original carve-out. In review that read as a hard light/dark seam across the middle of the screen: a light heading and light spinner sitting directly on a near-black panel, jumping identity the moment the first fetch resolved, plus two stacked headings in wizard mode (this page's and `ProfilePickerShell`'s). Closed by moving the background and the heading up one level: `PreferencesView.vue` now owns a single `HybridDepthBackground` around all four states and the screen's one heading (text swapping per state), and `ProfilePickerShell.vue` is the stepper plus step panel only, with no background and no title of its own. DESIGN.md's Brand & Style paragraph updated to match.
- **2026-09-09 - the error banner moved into the accent alert frame.** It was still amber Tailwind (`border-amber-200 bg-amber-50 text-amber-800`), left untouched because it sat outside this spec's scope. Now that it renders inside Hybrid Depth, the anti-pattern table's "no second chromatic hue for warnings or errors" rule applies, so it uses the same accent-tinted frame as the topics-stale box.
- **2026-09-09 - a way out of the wizard, as Back on Step 1 (GH #79 follow-up).** A returning user entering the wizard from the summary had no way back out. Steps 2 and 3 already carry a `"חזרה →"` ghost button; Step 1 had none, because there was no step behind it. It now has the same control in the same place, and `ProfilePickerShell` forwards it to whoever opened the wizard (`@back`) rather than handling it itself - the shell owns navigation *between* steps, but stepping off the first one leaves the wizard, which only its caller can decide. `PreferencesView` passes `:can-exit="hasSavedProfile"` so a brand-new user, who has no summary behind Step 1, still sees no Back there, and handles `@back` by returning to the summary.
  Three earlier iterations were tried and dropped, in this order: a dedicated `"ביטול עריכה"` button in the heading row; the same button withdrawn once a step had written to the DB (rejected - it left a user past Step 1 with no route back at all); and that button relabelled to `"סיום עריכה"` after the first write (rejected by the product owner in favour of no extra button at all). Reusing the existing Back control avoids the whole problem: Back never claimed to undo anything, so it needs no save-state tracking, no fingerprinting, and no second label. The profile-fingerprint machinery introduced for those iterations was removed with them.
- **2026-09-09 - the surface got a height floor.** The panel visibly resized between states: the loading state collapsed it to a single line, and the summary, each wizard step and the error banner are all different heights (measured at 1100x800: summary 855px, wizard steps 686-764px). `min-h-[max(calc(100vh-8rem),56rem)]` pins it to the screen below the app header, or 56rem, whichever is larger - every desktop state now renders at the same height. A phone-width viewport, or an unusually long interests paragraph, still exceeds the floor and scrolls.

## Verification

**Commands:**
- `cd frontend && npx vue-tsc --noEmit` -- expected: no new type errors
- `cd frontend && npx vitest run` -- expected: full suite passes, including new/updated specs

**Manual checks (if no CLI):**
- Browser pane: view `/preferences` as a returning seeded user, compare visually against `mockups/key-profile-summary.html` at desktop and ~375px width. Toggle the subscription and confirm the button/state match. Re-enter the wizard via "עריכת פרופיל" and confirm no regression (steps, stepper, parallax still work).
