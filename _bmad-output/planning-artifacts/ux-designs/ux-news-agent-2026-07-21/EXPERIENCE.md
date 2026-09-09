---
name: Hybrid Depth - Profile-Based Topic Suggestions
status: final
sources:
  - {planning_artifacts}/prds/prd-news-agent-2026-07-21/prd.md
  - {planning_artifacts}/prds/prd-news-agent-2026-07-21/addendum.md
  - .memlog.md
  - mockups/flow-hybrid-depth-steps.html
  - mockups/key-profile-summary.html
  - GitHub issue #79 (item 3 - profile screen visual design pass)
updated: 2026-09-08
---

# Hybrid Depth - Experience Spine

> Scope: the Field / Role / Experience Bucket / Interest Free-Text / Topic profile picker on the existing `/me/preferences` page (PRD: Profile-Based Topic Suggestions), **plus** (extended 2026-09-08) the returning-user summary/edit screen it leads to and the weekly-email subscription toggle beside it. Paired with `DESIGN.md` (Hybrid Depth). Independent of, and not to be confused with, the unrelated "Midnight" email-brand UX spine in the sibling `ux-news-agent-2026-07-20` folder.

## Foundation

Single-surface responsive web, Vue 3 + Tailwind CSS. There is no existing component library (`frontend/src/style.css` is a bare `@import "tailwindcss";` - no shadcn/MUI/PrimeNG), so every control in this picker (chips, segmented control, topic pills, buttons) is a custom Tailwind-built component, not inherited from a system. `DESIGN.md` is the visual identity reference for that custom layer; this spine is the experience.

This is the first custom visual identity applied to the live app itself. **Correction (2026-09-08):** this section originally claimed the picker's UI copy was English "consistent with the rest of the app." That was never accurate for the shipped code - `PreferencesView.vue` and every `profile-picker/` component render Hebrew UI copy throughout (labels, buttons, error/save text), and always have. Every string this spine or `DESIGN.md` quotes as an example should be read as illustrative of *register*, not as literal copy to translate - the real copy is Hebrew, and new Hebrew strings must follow the gender-neutral phrasing rule in project `CLAUDE.md` (issue #61 - avoid present-tense/imperative forms that assume the reader's gender). Output language (the Hebrew digest email) and UI language were never actually separate concerns here, unlike the rest of the app's English UI.

As of 2026-09-08, Hybrid Depth covers the full profile system on this page: the picker wizard, the returning-user summary/edit screen (`showSummary` state), and the weekly-email subscription-toggle row. What is *not* restyled: the page's own top-level heading/subheading, and its `loading`/`errorMessage` states - those stay in the plain neutral-Tailwind baseline (see § Responsive & Platform for why this boundary was drawn where it was, not deeper).

Critically, this picker is not a registration gate or wizard. It renders inside `/me/preferences`, which is already always-editable; a user can open it, partially fill it, leave, and come back anytime without losing access to anything else on the page. Once a profile is complete, the page defaults to the read-only summary instead of the wizard - editing is opt-in via the summary's "עריכת פרופיל" (edit profile) button, not a re-entry into the wizard automatically.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| `/me/preferences` | Existing app nav (authenticated) | Single page: profile summary or wizard (whichever applies), the subscription toggle, plus the existing Topic toggle list |
| Profile summary | Default state on page load, once `profile.field_name` is set | Read-only Field/Role/Experience/Interests, subscribed topics, "עריכת פרופיל" (edit) entry point into the wizard |
| Subscription toggle | Always visible alongside the summary or the wizard | Pause/resume the weekly digest email |
| Step 1 - About you | Wizard default (no profile yet), or "עריכת פרופיל" from the summary, or "Back" from Step 2 | Field, Role, Experience Bucket |
| Step 2 - Interests | "Continue" from Step 1 | Interest Free-Text + Suggested Prompts (optional) |
| Step 3 - Topics | "Continue"/"Skip" from Step 2 | Suggested Topics, capped at 4, swap in/out |
| Admin Taxonomy Curation Queue | Admin nav (separate role) | Review/promote/dismiss Pending Taxonomy Suggestions (Field/Role "Other" submissions) - styled per the existing admin source-approval panel (#22) conventions, **not** Hybrid Depth; out of scope for this visual spine |

One step panel visible at a time within `/me/preferences`; the other two steps are unmounted, not scrolled-to. No modal stacking - the whole picker is inline page content, not a dialog. The profile summary and the wizard are mutually exclusive on this page (governed by `showSummary`) - never both visible at once. The existing Topic toggle grid remains on the same page below/alongside whichever of the two is showing, and now observes the platform-wide 4-Topic cap (FR-10) that Step 3 also enforces.

→ Composition reference: `mockups/flow-hybrid-depth-steps.html` (wizard), `mockups/key-profile-summary.html` (summary, subscription toggle, topics-stale alert - added 2026-09-08). Spine wins on conflict.

## Voice and Tone

Microcopy only. Brand voice and aesthetic posture live in `DESIGN.md` § Brand & Style. **All UI copy is Hebrew** (see § Foundation correction, 2026-09-08) - every new string must also satisfy project `CLAUDE.md`'s gender-neutral Hebrew copy rule (issue #61): no present-tense/imperative form that assumes the reader's gender; prefer past tense, noun phrases, or `יש ל-` + infinitive over a bare imperative.

| Do (real shipped copy) | Don't |
|---|---|
| "עריכת פרופיל" (edit profile - noun phrase, gender-neutral) | "בוא נבנה לך פיד מושלם! 🚀" (gamified, gendered imperative) |
| "השמירה נכשלה. ניתן לבדוק את החיבור ולנסות שוב." (save failed - impersonal "ניתן," not "תוכל/י") | "כמעט הצלחת, אלוף!" (gendered, celebratory) |
| "Continue" / "← Back" / "Selected 4 / 4" *(as designed - stepper chrome only, see below)* | "רמה הבאה!" |
| "עדכון הנושאים שלי" (update my topics - possessive noun phrase) | "!מיצית את הבחירות שלך 🎉" |
| Plain, complete sentences; no emoji | Exclamation marks, gamified framing, streaks |
| "טעינה…" / "טעינת תפקידים…" (a noun, alongside `{components.spinner}`, added 2026-09-08) | "טוען…" / "טוען תפקידים…" (a conjugated verb - gendered by form even in generic system-status use) |

**Open gap, not yet resolved:** the wizard's own step chrome (Continue/Back/Skip/Save button labels, the "Selected 4/4" counter, step headings) was designed and mocked in English (`mockups/flow-hybrid-depth-steps.html`) but the shipped component code renders those in Hebrew too - no Hebrew equivalents for the wizard's own English-designed strings were ever specified in this spine. Out of scope for this 2026-09-08 update (which only extends Hybrid Depth to the summary/subscription surfaces, already Hebrew-native); worth a dedicated pass to reconcile the wizard's designed English microcopy against its actual Hebrew implementation.

The rejected RPG-flavored and gradient-startup directions (see § Inspiration & Anti-patterns) both leaned toward exactly the tone this table forbids - the copy discipline is as deliberate a rejection as the palette one.

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md.components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Field chip row | Step 1 | Single-select. Selecting a Field re-populates the Role chip row scoped to that Field and clears any previously selected Role (FR-2 consequence). "Other" reveals a free-text input in place of/alongside the chip. |
| Role chip row | Step 1 | Single-select, options scoped to the currently selected Field. Empty/placeholder state ("Pick a field first") shown before any Field is chosen. "Other" reveals free-text. |
| Experience segmented control | Step 1 | Single-select among the illustrative buckets (0–2 / 3–5 / 6–10 / 10+ yrs - **provisional**, PRD §4.1 FR-3 flags exact boundaries as unconfirmed, `[NOTE FOR PM]`). Stats-only; never affects Topic suggestion (FR-3). |
| Continue button (Step 1) | Step 1 → Step 2 | **Hard-gated.** Disabled until Field, Role, and Experience are all set. Implemented as a real `.disabled` class + `pointer-events:none` + a JS guard inside the click handler - not the native HTML `disabled` attribute, because these are `<div>`-based controls, not real form elements (native `:disabled` only applies to real form controls). See § Accessibility Floor for the consequence of that choice. |
| Back link | Every step | Always available, regardless of how much of the current step is filled. Never gated. |
| Skip link | Step 2 only | Advances to Step 3 without requiring Interest Free-Text. Step 2 is intentionally ungated - see the Step 2 row in § State Patterns for why. |
| Interest textarea + Suggested Prompts | Step 2 | Free text, optional. Suggested Prompts (FR-5) are illustrative only - clicking/viewing one never inserts text or locks in a value; the textarea stays freely editable regardless. If no Suggestion Source is connected yet, the field still renders and works, just without prompts (FR-5 assumption). |
| Topic pill grid | Step 3 | Multi-select capped at exactly 4 "picked" pills plus any number of "faint" (unpicked candidate) pills. Tapping a faint pill swaps it in for one of the 4 - there is no "add a 5th" state; selecting past 4 requires deselecting one first (FR-10). |
| Save preferences button | Step 3 | Not gated - Topic selection can be saved at any count up to 4, including the pre-populated default. Save must succeed even if Topic suggestion generation failed or is still pending (FR-8 consequence) - nothing here blocks on suggestion latency. |
| Progress stepper | All steps | Reflects current/done state per step; clicking a stepper dot is not a navigation affordance in the mock (only Continue/Back/Skip move steps) - treat direct-dot-click navigation as unimplemented, not intentionally removed. |
| Summary panel | Profile summary | Read-only. Shows Field/Role/Experience as a two-column definition list, Interest Free-Text (if set) full-width below, then subscribed topics. No inline editing anywhere in this panel - the only mutation entry point is the Edit-profile button. |
| Subscribed-topic pill (read-only) | Profile summary | Same visual as a Step 3 `picked` topic pill, no "✕", no click handler - purely informational. Empty state ("עדיין אין" / none yet) renders as plain muted text, not an empty pill. |
| Edit-profile button | Profile summary | Single click sets `editing = true`, which swaps the summary out for the wizard (Step 1, pre-filled from the saved profile). No confirmation step - editing is non-destructive since nothing saves until a step's Continue/Save fires. |
| Subscription-toggle row | Profile summary and wizard (persistent) | Shows current state ("פעיל" / active, or "מושהה - ... לא יישלח" / paused) plus a single toggle button ("השהיה" / pause, or "המשך" / resume) that flips it. Button disables and shows a saving state while the request is in flight - no optimistic flip before the server confirms. |
| Topics-stale alert | Profile summary, conditional | Shown only when `profile.topics_stale_at` is set (profile changed since topics were last computed). Uses `{components.alert-frame}` - framed, accent-tinted, never a second hue (see `DESIGN.md`). Houses its own inline "עדכון הנושאים שלי" primary button. |
| Spinner | Any loading state whose text alone was the only busy signal (added 2026-09-08, iterated across two rounds, confirmed live) | `{components.spinner}` - a single sparkle from the real brand mark (not the pair, not the bars - both dropped after user feedback), colored via `currentColor` (accent inside Hybrid Depth). **Motion: twinkle** (scale + opacity pulse), not rotation - v3's own-center rotation read as a wobble, not a clean spin, because the sparkle's 4-fold symmetry repeats its own silhouette every 90 degrees (full reasoning in `DESIGN.md` and `.memlog.md`). Confirmed live by the user ("יותר טוב"), with two follow-up tweaks for the inline/button context specifically - size 14px -> 16px and the twinkle's opacity floor 0.55 -> 0.3 - after the original values read as "really weak" next to button text. Always pairs with the noun-form loading copy ("טעינה…" / "טעינת תפקידים…"), never a bare conjugated verb ("טוען…") and never text-free - see § Voice and Tone. Inline size (16px) inside buttons/rows; standalone size (22px) for a page-level load like `PreferencesView.vue`'s initial fetch. One generic component, usable site-wide, not scoped to Hybrid Depth surfaces only. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Step mount / re-entry (incl. via Back) | Any step | Every direct child block fades up with a staggered entrance animation, replayed in full on every mount - not just the first time a step is shown. |
| Step 1, 0–2 of 3 fields set | Step 1 | Continue stays visually and functionally disabled (`{components.button-primary.disabled-opacity}`); no error text, just an inert button. |
| Step 1, all 3 fields set | Step 1 | Continue becomes active immediately, no confirmation step. |
| Field changed after Role was set | Step 1 | Role selection silently clears; Role chip row re-renders for the new Field; Continue re-gates until a new Role is picked. |
| Step 2, empty | Step 2 | Textarea shows placeholder copy; Skip and Continue are both available (no gate either way). |
| Step 3, first load | Step 3 | Exactly 4 Topic pills pre-picked based on Field/Role and/or Interest Free-Text (or the non-LLM popularity fallback per FR-9 when there's no match) - never zero, per PRD FR-9's "always produces something" guarantee. |
| Topic suggestion generation fails/times out | Step 3 (async, post-save) | No error shown for this specific failure - the save already succeeded (FR-8). Whatever Topics were already selected remain unchanged. |
| Suggestion Source not yet connected (MVP default) | Step 1 Role row / Step 2 prompts / Step 3 Topics | Role row shows minimal/no generated options ("Other" is the practical path); Suggested Prompts area is empty or shows a static illustrative example; Topic suggestions still populate via the always-available popularity-based fallback (FR-9) - the surface never dead-ends into "nothing to pick." |
| Role suggestions still loading (added 2026-09-08, GH #79 item 4) | Step 1 | Continue stays gated (same disabled treatment as an unset field) until the Role-suggestion fetch resolves, in addition to the existing Field/Role/Experience-set condition - closes the gap where "Next" was reachable mid-fetch with a stale/empty Role row. Hard gate, matching Step 1's existing all-fields-mandatory rule (not a new precedent). Label reads "טוען…" with an inline `{components.spinner}`, mirroring the existing `saving` → "שומר…" treatment - a disabled button always says why. Minimum viable version for this spec; an extended-wait fallback (mirroring Step 3's `extendedWait` "עדיין מנסים…" copy for the rare worst-case ~90s fetch) is deferred, not built here (party-mode decision, 2026-09-08). |
| Suggested Prompts still loading (added 2026-09-08, GH #79 item 4) | Step 2 | **Soft wait, not a gate:** Continue/Skip stay available the whole time (Step 2 is never forward-gated - see § Interaction Primitives Banned list). The prompts row itself simply doesn't render until the fetch resolves (or fails, per its existing best-effort empty fallback) - this prevents an empty-row-to-populated-row flash, it never blocks navigation. |
| Page-level initial load (added 2026-09-08) | `/me/preferences`, before `showSummary`/wizard is decided | Standalone `{components.spinner}` replaces the plain "טוען…" text-only state (GH #79 item 2's fix) - same busy-signal upgrade as the button-level spinners, applied at page scale. |
| Pending "Other" submission (Field or Role) | Step 1 | Saves normally as free text against the user's profile; separately queued as a Pending Taxonomy Suggestion for the Admin Taxonomy Curation Queue - no visible confirmation of the queueing on this surface. |
| Save | Step 3 | Existing `/me/preferences` save-feedback convention applies (see `PreferencesView.vue`'s "Saved." / "Failed to save preferences." text pattern) - this picker should not invent a different save-confirmation idiom from the rest of the page. |
| Returning user, profile already complete | Page load | Summary renders directly - the wizard never flashes first. (Implementation note, not a design decision: today's `loading` ref starts `false` and the summary/wizard branches aren't gated on it, causing exactly this flash - GH #79 items 1-2, a separate logic/state fix tracked outside this UX pass.) |
| Edit clicked | Profile summary → Step 1 | No special cross-fade between summary and wizard - the wizard's own existing step-mount stagger (see the first row of this table) is the only entrance treatment; the summary simply unmounts. |
| Subscription toggle, saving | Subscription-toggle row | Button disables (`{components.button-secondary.disabled-opacity}`) and its label stays unchanged (no separate "שומר…" / saving text was designed) until the request resolves, then flips to the new state. |
| Topics-stale alert, shown | Profile summary | Appears above the summary panel whenever `topics_stale_at` is set; clicking its action button is out of this pass's scope (existing backend recompute flow) - only the alert's visual treatment is new here. |

## Interaction Primitives

- Tap/click to select - every chip, segment, and topic pill is a single-click toggle (single-select for Field/Role/Experience, capped multi-select for Topics).
- Continue / Back / Skip are the only step-navigation controls; there is no swipe, no keyboard step-jump, no direct click-through on the progress stepper (see § Component Patterns).
- Background orb parallax responds continuously to mouse position and scroll position - decorative and `pointer-events: none`; it must never intercept clicks or be mistaken for an interactive layer.
- Hover states (chip/topic/button border-brighten + slight lift) are gated to `(hover: hover) and (pointer: fine)` devices - resolved in the shipped wizard (see § Responsive & Platform), not yet extended to the new summary/subscription surfaces.
- **Banned:** forward navigation past Step 1 while any of Field/Role/Experience is unset; a forward gate on Step 2 (explicitly rejected twice in this run's decision log - Interest Free-Text must stay skippable to avoid recreating the "blank textarea is homework" problem the whole picker exists to solve); selecting a 5th Topic without first deselecting one of the 4.
- Edit-profile button and subscription-toggle button are both single-click, no confirmation dialog - consistent with the wizard's own no-modal-stacking rule.
- Subscription toggle has no undo affordance beyond clicking it again (it's a two-state flip, not a destructive action).

## Accessibility Floor

Behavioral. Visual contrast values live in `DESIGN.md`.

**Correction (2026-09-08):** this section previously described the *original prototype's* (`mockups/flow-hybrid-depth-steps.html`) gaps as if they still applied to the shipped wizard. They don't. The real implementation (`ChipRow.vue`, `AboutYouStep.vue`, `TopicsStep.vue`, `ProfilePickerShell.vue`) already closed the controls/motion gaps below - checked against actual code, not the prototype, during this update:

- **Resolved - semantic controls:** every chip, segment, and topic pill is a real `<button type="button">` with `aria-pressed`; the Experience bucket is a real `<input type="radio">` group (visually hidden via `sr-only`, keyboard/screen-reader native); `role="group"` + `aria-label` on each chip row and the topic grid; `aria-live="polite"` on the Topics-step loading text. Matches what GH #31 asked for - **that issue looks stale and closeable, but wasn't closed as part of this UX pass; flag it to the user rather than closing it unilaterally.**
- **Resolved - the Continue gate:** real `disabled` attribute on the `<button>` (`:disabled="!canContinue || saving"`), not a CSS-only `.disabled` class - natively exposed to assistive tech, no extra `aria-disabled` needed.
- **Resolved - motion:** `ProfilePickerShell.vue` checks `matchMedia("(prefers-reduced-motion: reduce)")` and gates the parallax/stagger accordingly; hover-lift effects are gated behind `matchMedia("(hover: hover) and (pointer: fine)")` so touch never gets a stuck-hover state.
- Visible focus rings (`focus-visible:outline`) are already on every interactive element site-wide.
- **Still open - contrast unverified:** the near-black `{colors.bg-void}` base against the ink text scale, and text on `chip-selected`/`topic-pill picked` gradient fills, still haven't been measured against WCAG thresholds. This is the one real carryover gap from the original prototype era.
- **New surfaces (summary panel, read-only topic pills, edit-profile button, subscription-toggle row, alert frame, 2026-09-08):** the buttons are real `<button>` elements from day one (this section's controls gap never applied to them), and they inherit the same `prefers-reduced-motion`/`hover:hover` handling by living inside the same `ProfilePickerShell`-managed surface once implemented. Contrast is the one gap that does carry over here too, same as the wizard.

## Responsive & Platform

**Correction (2026-09-08):** this section previously described the wizard as having no responsive/mobile design at all. That was true of the original prototype but is no longer true of the shipped implementation - **GH #30 (responsive/mobile design for the profile-picker) is closed.** Checked against actual code during this update:

- `ProfilePickerShell.vue` uses `p-4 sm:p-[30px]` (tighter padding below the `sm` breakpoint) and disables the mouse-parallax half entirely on non-hover/non-fine-pointer devices (scroll-parallax still runs).
- `InterestsStep.vue` and `TopicsStep.vue`'s footer nav rows use `flex-col ... sm:flex-row` (stacked buttons on narrow viewports, side-by-side above `sm`).
- Every interactive control across `ChipRow.vue`/`AboutYouStep.vue`/`InterestsStep.vue`/`TopicsStep.vue` has `min-h-[44px] min-w-[44px]` - touch-target sizing was designed in, not left as a gap.
- Chip/topic-pill hover-lift is gated behind `hover:hover`, so tapping on a touchscreen never leaves a chip visually stuck in its hover state.

**Still open, 2026-09-08 - the new summary/subscription surfaces don't have this treatment yet.** They were only just added to Hybrid Depth's scope in this update, restyled for color/surface/typography but not yet redesigned for narrow viewports:
- Summary panel's two-column `dl` (reuses `{components.panel}`, per Component Patterns) should collapse to a single column below the `sm` breakpoint, mirroring the wizard's own `sm:` convention rather than inventing a new one.
- Subscription-toggle row's `justify-between` layout (label left, button right) should stack vertically below `sm`, same `flex-col sm:flex-row` pattern as the wizard's footer nav rows.
- Edit-profile and subscription-toggle buttons already meet the `min-h-[44px] min-w-[44px]` touch-target rule by construction (same button tokens as the wizard); no new sizing decision needed there.
- These surfaces sit inside the same `ProfilePickerShell`-style orb/void background once implemented, so they inherit the wizard's already-solved hover-touch and parallax-on-touch handling for free - no separate decision needed.

## Inspiration & Anti-patterns

- **Lifted from "RPG Class Select"** (`.working/direction-rpg-class-select.html`) - the ambition of an interactive, "choose your class" feeling for Field/Role selection (the addendum's own framing: "pick a world, then it reveals your class options within it"). Rejected as delivered in that direction (neon violet/pink/cyan, chunky glow borders, celebratory tone) - too playful/neon for the "serious, mysterious, professional" brief. Hybrid Depth keeps the ambition, drops the neon and the game-show energy, and delivers the "interactive" feeling through parallax/blur motion instead.
- **Lifted from "Crisp Minimal SaaS"** (`.working/direction-crisp-minimal-saas.html`) - the restraint: one accent color, hairline borders, no visual noise. Rejected as delivered (flat off-white dashboard palette) for reading as too generic/static against the "most advanced and attractive" brief - restraint alone wasn't enough.
- **Rejected - "Gradient Startup"** (`.working/direction-gradient-startup.html`) - glossy multi-color mesh-gradient glassmorphism. Rejected for being "gradient-loud" and closer to marketing-page energy than a serious profile tool.
- **Rejected - "Editorial Premium"** (`.working/direction-editorial-premium.html`) - warm-paper serif/hairline register. Rejected for not being "highly interactive" - too quiet for a picker meant to feel like a live, responsive quiz.
- **Precursor, not rejected - `.working/direction-hybrid-depth.html`** - the single-page (non-stepped) version that established the void/orb/grain palette and the depth concept. Refined into the current 3-step, one-panel-at-a-time flow with real gating logic in `mockups/flow-hybrid-depth-steps.html`, which is the artifact this spine and `DESIGN.md` are drawn from.

## Key Flows

### Flow 1 - Noa sets up her digest for the first time (backend engineer, one of two seeded dogfood users, first visit to `/me/preferences`)

1. Noa opens `/me/preferences` for the first time. Step 1 mounts with its staggered entrance; Field, Role placeholder, and Experience controls fade up in sequence.
2. She taps "Tech" in the Field chip row. It becomes `chip-selected`; the Role row re-renders with Tech-scoped options.
3. She taps "Backend Engineer" in the newly populated Role row, then "6–10 yrs" in the Experience segmented control.
4. Continue (previously disabled) becomes active the moment all three are set - no separate confirmation needed. She clicks it; Step 2 mounts.
5. She optionally jots a line or two in the Interest Free-Text textarea, glancing at a Suggested Prompt for phrasing, then clicks Continue (not Skip, though either was available).
6. Step 3 mounts. Suggested Topics are already computed from her Field/Role and interest text.
7. **Climax:** four Topic pills appear already `picked` - AI & Machine Learning, Developer Tools, Startups, Open Source - with the counter reading "Selected 4 / 4." She recognizes most of them as relevant on sight; she taps one faint candidate ("Cloud & Infra") to swap it in for one she's less interested in.
8. She clicks "Save preferences." The page gives the existing save-feedback ("Saved.") - nothing about the async suggestion computation was visible or blocking at any point.

Failure: if Topic suggestion generation had failed or timed out server-side, her save still succeeds silently with no candidate Topics shown, and she can still hand-pick up to 4 from the existing Topic toggle list below the picker (FR-8 consequence).

### Flow 2 - Amir's role isn't on the list (DevRel, Tech field already picked, mid-profile-setup)

1. Amir is on Step 1 with "Tech" already selected as Field; the Role row shows Tech's current options (Software Engineer, Product Manager, Data Scientist, Founder / Exec) plus "Other."
2. He scans the row - none of them are Developer Relations. He taps the dashed "Other" chip.
3. A free-text input reveals itself in place of a plain chip selection. He types "Developer Relations."
4. Role now counts as set (Continue's gate only checks that a Role value exists, not that it came from the curated list); he picks an Experience bucket and clicks Continue.
5. He skips Step 2 via the Skip link - no interest text, no penalty, no gate.
6. Step 3 mounts. Because "Developer Relations" has no promoted Role match yet, the Suggestion Source has nothing Field/Role-specific to key off; the always-available popularity-based fallback (FR-9) still populates 4 Topic pills.
7. **Climax:** even with an unmatched, freshly-typed Role, Amir never hits a dead end - four Topics are already picked, not zero, and he can swap or hand-adjust them exactly as Noa could. The "always produces something" guarantee holds even for the worst-case profile input.
8. He saves. His profile records "Developer Relations" as free text; separately (invisibly to him, on this surface) it's queued as a Pending Taxonomy Suggestion for an admin to review on the Admin Taxonomy Curation Queue - a different surface, styled per the existing admin panel conventions, not Hybrid Depth.

Edge case not yet resolved by this spine: whether "Developer Relations" being typed by Amir today and later promoted by an admin retroactively updates his stored profile - per the PRD (§4.2 FR-7 consequence), it explicitly does not; he'd keep his free-text value unless he manually reselects the promoted entry later.

### Flow 3 - Noa comes back a week later (added 2026-09-08, extending Hybrid Depth to the summary/subscription surfaces)

1. Noa opens `/me/preferences` again, weeks after her first visit. Her profile is already complete, so the page renders the profile summary directly, on the same void/orb/glass surface as the wizard - not the wizard, and not the old spartan list.
2. She sees her Field/Role/Experience laid out in the summary panel, her interest text below it, and her four subscribed topics as read-only pills in the same accent-gradient style she picked them in originally.
3. Below that, the subscription-toggle row shows "פעיל" (active) - her weekly digest is running.
4. **Climax:** she's changed jobs since she set this up. She clicks "עריכת פרופיל" - the summary unmounts and Step 1 of the wizard mounts in its place, pre-filled with her old Field/Role/Experience, using the exact same staggered fade-up entrance as a first-time visit. Nothing about re-entering the wizard feels like a different product from the summary she just left.
5. She updates her Field and Role, steps through to Step 3, adjusts her topics, and saves. The page returns to the summary - now showing her new values - and (per FR-8) nothing about the background topic-suggestion recompute blocked or delayed this.
6. On a later visit, before topics have been recomputed for a different profile edit, she'd instead see the topics-stale alert framed above the summary - same accent family as everything else, not a jarring amber banner.

### Flow 4 - Noa pauses her digest before a two-week trip

1. From the profile summary, Noa clicks "השהיה" (pause) on the subscription-toggle row.
2. The button disables briefly while the request is in flight - no optimistic flip, no separate loading spinner elsewhere on the page.
3. **Climax:** the row updates to "מושהה - ה{{ DIGEST_NOUN_WEEKLY }} לא יישלח" (paused - the digest won't be sent), and the button's own label flips to "המשך" (resume). Nothing else on the page reacts - her profile and topic selections are untouched by pausing delivery.
4. Two weeks later she returns and clicks "המשך"; the row flips back to "פעיל" with no other side effect.
