---
name: Hybrid Depth — Profile-Based Topic Suggestions
status: final
sources:
  - {planning_artifacts}/prds/prd-news-agent-2026-07-21/prd.md
  - {planning_artifacts}/prds/prd-news-agent-2026-07-21/addendum.md
  - .memlog.md
  - mockups/flow-hybrid-depth-steps.html
updated: 2026-07-22
---

# Hybrid Depth — Experience Spine

> Scope: the Field / Role / Experience Bucket / Interest Free-Text / Topic profile picker added to the existing `/me/preferences` page (PRD: Profile-Based Topic Suggestions). Paired with `DESIGN.md` (Hybrid Depth). Independent of, and not to be confused with, the unrelated "Midnight" email-brand UX spine in the sibling `ux-news-agent-2026-07-20` folder.

## Foundation

Single-surface responsive web, Vue 3 + Tailwind CSS. There is no existing component library (`frontend/src/style.css` is a bare `@import "tailwindcss";` — no shadcn/MUI/PrimeNG), so every control in this picker (chips, segmented control, topic pills, buttons) is a custom Tailwind-built component, not inherited from a system. `DESIGN.md` is the visual identity reference for that custom layer; this spine is the experience.

This is the first custom visual identity applied to the live app itself. Today's `PreferencesView.vue` is a plain, spartan neutral-Tailwind list (English UI copy) — that baseline is not being restyled; Hybrid Depth applies only to the new profile-picker section being added to the same page. The picker's own UI copy is also English, consistent with the rest of the app, even though the product's digest email output is Hebrew — output language and UI language are separate concerns (see project `CLAUDE.md`).

Critically, this picker is not a registration gate or wizard. It renders inside `/me/preferences`, which is already always-editable; a user can open it, partially fill it, leave, and come back anytime without losing access to anything else on the page.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| `/me/preferences` | Existing app nav (authenticated) | Single page: this profile picker, plus the existing Topic toggle list it feeds |
| Step 1 — About you | Default state on page load / "Back" from Step 2 | Field, Role, Experience Bucket |
| Step 2 — Interests | "Continue" from Step 1 | Interest Free-Text + Suggested Prompts (optional) |
| Step 3 — Topics | "Continue"/"Skip" from Step 2 | Suggested Topics, capped at 4, swap in/out |
| Admin Taxonomy Curation Queue | Admin nav (separate role) | Review/promote/dismiss Pending Taxonomy Suggestions (Field/Role "Other" submissions) — styled per the existing admin source-approval panel (#22) conventions, **not** Hybrid Depth; out of scope for this visual spine |

One step panel visible at a time within `/me/preferences`; the other two steps are unmounted, not scrolled-to. No modal stacking — the whole picker is inline page content, not a dialog. The existing Topic toggle grid remains on the same page below/alongside the picker and now observes the platform-wide 4-Topic cap (FR-10) that Step 3 also enforces.

→ Composition reference: `mockups/flow-hybrid-depth-steps.html`. Spine wins on conflict.

## Voice and Tone

Microcopy only. Brand voice and aesthetic posture live in `DESIGN.md` § Brand & Style.

| Do | Don't |
|---|---|
| "Set up your profile" | "Let's build your perfect feed! 🚀" |
| "Three quick steps. Change any of it later — this never locks in." | "Just 3 easy steps to feed nirvana!" |
| "Continue" / "← Back" / "Skip for now →" / "Save preferences" | "Next level!" / "Almost there, champ!" |
| "Selected 4 / 4" | "You've maxed out your picks! 🎉" |
| "Tap a faint topic to swap it in for one of your 4." | Exclamation marks anywhere in body copy |
| Plain, complete sentences; no emoji | Gamified framing, streaks, celebratory language |

The rejected RPG-flavored and gradient-startup directions (see § Inspiration & Anti-patterns) both leaned toward exactly the tone this table forbids — the copy discipline is as deliberate a rejection as the palette one.

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md.components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Field chip row | Step 1 | Single-select. Selecting a Field re-populates the Role chip row scoped to that Field and clears any previously selected Role (FR-2 consequence). "Other" reveals a free-text input in place of/alongside the chip. |
| Role chip row | Step 1 | Single-select, options scoped to the currently selected Field. Empty/placeholder state ("Pick a field first") shown before any Field is chosen. "Other" reveals free-text. |
| Experience segmented control | Step 1 | Single-select among the illustrative buckets (0–2 / 3–5 / 6–10 / 10+ yrs — **provisional**, PRD §4.1 FR-3 flags exact boundaries as unconfirmed, `[NOTE FOR PM]`). Stats-only; never affects Topic suggestion (FR-3). |
| Continue button (Step 1) | Step 1 → Step 2 | **Hard-gated.** Disabled until Field, Role, and Experience are all set. Implemented as a real `.disabled` class + `pointer-events:none` + a JS guard inside the click handler — not the native HTML `disabled` attribute, because these are `<div>`-based controls, not real form elements (native `:disabled` only applies to real form controls). See § Accessibility Floor for the consequence of that choice. |
| Back link | Every step | Always available, regardless of how much of the current step is filled. Never gated. |
| Skip link | Step 2 only | Advances to Step 3 without requiring Interest Free-Text. Step 2 is intentionally ungated — see the Step 2 row in § State Patterns for why. |
| Interest textarea + Suggested Prompts | Step 2 | Free text, optional. Suggested Prompts (FR-5) are illustrative only — clicking/viewing one never inserts text or locks in a value; the textarea stays freely editable regardless. If no Suggestion Source is connected yet, the field still renders and works, just without prompts (FR-5 assumption). |
| Topic pill grid | Step 3 | Multi-select capped at exactly 4 "picked" pills plus any number of "faint" (unpicked candidate) pills. Tapping a faint pill swaps it in for one of the 4 — there is no "add a 5th" state; selecting past 4 requires deselecting one first (FR-10). |
| Save preferences button | Step 3 | Not gated — Topic selection can be saved at any count up to 4, including the pre-populated default. Save must succeed even if Topic suggestion generation failed or is still pending (FR-8 consequence) — nothing here blocks on suggestion latency. |
| Progress stepper | All steps | Reflects current/done state per step; clicking a stepper dot is not a navigation affordance in the mock (only Continue/Back/Skip move steps) — treat direct-dot-click navigation as unimplemented, not intentionally removed. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Step mount / re-entry (incl. via Back) | Any step | Every direct child block fades up with a staggered entrance animation, replayed in full on every mount — not just the first time a step is shown. |
| Step 1, 0–2 of 3 fields set | Step 1 | Continue stays visually and functionally disabled (`{components.button-primary.disabled-opacity}`); no error text, just an inert button. |
| Step 1, all 3 fields set | Step 1 | Continue becomes active immediately, no confirmation step. |
| Field changed after Role was set | Step 1 | Role selection silently clears; Role chip row re-renders for the new Field; Continue re-gates until a new Role is picked. |
| Step 2, empty | Step 2 | Textarea shows placeholder copy; Skip and Continue are both available (no gate either way). |
| Step 3, first load | Step 3 | Exactly 4 Topic pills pre-picked based on Field/Role and/or Interest Free-Text (or the non-LLM popularity fallback per FR-9 when there's no match) — never zero, per PRD FR-9's "always produces something" guarantee. |
| Topic suggestion generation fails/times out | Step 3 (async, post-save) | No error shown for this specific failure — the save already succeeded (FR-8). Whatever Topics were already selected remain unchanged. |
| Suggestion Source not yet connected (MVP default) | Step 1 Role row / Step 2 prompts / Step 3 Topics | Role row shows minimal/no generated options ("Other" is the practical path); Suggested Prompts area is empty or shows a static illustrative example; Topic suggestions still populate via the always-available popularity-based fallback (FR-9) — the surface never dead-ends into "nothing to pick." |
| Pending "Other" submission (Field or Role) | Step 1 | Saves normally as free text against the user's profile; separately queued as a Pending Taxonomy Suggestion for the Admin Taxonomy Curation Queue — no visible confirmation of the queueing on this surface. |
| Save | Step 3 | Existing `/me/preferences` save-feedback convention applies (see `PreferencesView.vue`'s "Saved." / "Failed to save preferences." text pattern) — this picker should not invent a different save-confirmation idiom from the rest of the page. |

## Interaction Primitives

- Tap/click to select — every chip, segment, and topic pill is a single-click toggle (single-select for Field/Role/Experience, capped multi-select for Topics).
- Continue / Back / Skip are the only step-navigation controls; there is no swipe, no keyboard step-jump, no direct click-through on the progress stepper (see § Component Patterns).
- Background orb parallax responds continuously to mouse position and scroll position — decorative and `pointer-events: none`; it must never intercept clicks or be mistaken for an interactive layer.
- Hover states (chip/topic/button border-brighten + slight lift) are a `md`+ affordance; see § Responsive & Platform for the open question on touch/small-viewport behavior, since none of this has been tested off desktop.
- **Banned:** forward navigation past Step 1 while any of Field/Role/Experience is unset; a forward gate on Step 2 (explicitly rejected twice in this run's decision log — Interest Free-Text must stay skippable to avoid recreating the "blank textarea is homework" problem the whole picker exists to solve); selecting a 5th Topic without first deselecting one of the 4.

## Accessibility Floor

Behavioral. Visual contrast values live in `DESIGN.md`.

**No accessibility audit or testing has been performed on this design.** The interactive prototype (`mockups/flow-hybrid-depth-steps.html`) was built and functionally verified (Field→Role population, step gating, animations) but never checked for color contrast, keyboard navigation, or screen-reader behavior. Treat everything below as required follow-up work before implementation, not a compliance claim.

- **Known gap — non-semantic controls:** every chip, segmented-control segment, topic pill, and nav button in the prototype is a `<div>` with an `onclick` handler, not a real `<button>` (or `<input type="radio">`/`<input type="checkbox">` where applicable). This is a mockup shortcut, not an approved pattern — it means no native keyboard focus, no native `Enter`/`Space` activation, and no screen-reader button/selected-state semantics out of the box. The real implementation must use genuine interactive elements (`<button>` with `aria-pressed`, or native form controls) rather than reproducing the div+onclick pattern.
- **Known gap — contrast unverified:** the near-black `{colors.bg-void}` base against the ink text scale (`{colors.ink-primary}` through `{colors.ink-faint}`), and the translucent panel/chip surfaces over the orb field, have not been measured against WCAG contrast thresholds. Verify before build, especially for `{colors.ink-faint}` (the dimmest text role) and text on `chip-selected`/`topic-pill picked` gradient fills.
- **Known gap — the Step 1 Continue gate:** since it's implemented via a manually-toggled `.disabled` class rather than the native `disabled` attribute (see § Component Patterns), the real build must ensure the disabled state is also exposed to assistive tech (e.g., `aria-disabled` + actually removing it from the tab order or handling activation-attempt announcements) — a CSS-only/JS-guard-only disabled state is invisible to a screen reader.
- **Known gap — motion:** the parallax orb drift and staggered fade-up entrance have no `prefers-reduced-motion` handling in the prototype. Needs one before build — at minimum, skip/shorten the entrance stagger and freeze orb parallax under reduced motion.
- Once real controls are used, standard expectations apply: visible focus rings on every interactive element, tab order matching the step's reading order (Field → Role → Experience → Continue), and topic pill selection announced as a state change (selected/not selected), not just a visual swap.

## Responsive & Platform

**Open gap — no responsive or mobile design exists for this picker.** Every working artifact (the winning prototype and all five explored directions) is a desktop-width browser-frame mockup only; no breakpoint behavior, touch-target sizing, or small-viewport layout was designed or tested for the panel/chip/orb-parallax system. This must be scoped as real design work before implementation, not inferred from this spine.

Specific open questions to resolve before build:
- Chip rows (`{components.chip}`) and the topic-pill grid (`{components.topic-pill}`) use `flex-wrap`, which will reflow at narrow widths, but wrap behavior hasn't been visually checked below the prototype's ~640px chrome width.
- Hover-dependent affordances (chip/topic/button lift-and-brighten) have no defined touch equivalent.
- The mouse-position-driven half of the orb parallax has no meaning on touch devices; scroll-position parallax alone may or may not read as intentional at small viewport heights, and blur-heavy fixed backgrounds carry real mobile GPU/perf cost that hasn't been evaluated.
- The existing `PreferencesView.vue` baseline already uses responsive Tailwind utilities (e.g. `sm:flex-row`) for its simple list — whether the new picker should follow that same breakpoint convention, or needs its own, is undecided.

## Inspiration & Anti-patterns

- **Lifted from "RPG Class Select"** (`.working/direction-rpg-class-select.html`) — the ambition of an interactive, "choose your class" feeling for Field/Role selection (the addendum's own framing: "pick a world, then it reveals your class options within it"). Rejected as delivered in that direction (neon violet/pink/cyan, chunky glow borders, celebratory tone) — too playful/neon for the "serious, mysterious, professional" brief. Hybrid Depth keeps the ambition, drops the neon and the game-show energy, and delivers the "interactive" feeling through parallax/blur motion instead.
- **Lifted from "Crisp Minimal SaaS"** (`.working/direction-crisp-minimal-saas.html`) — the restraint: one accent color, hairline borders, no visual noise. Rejected as delivered (flat off-white dashboard palette) for reading as too generic/static against the "most advanced and attractive" brief — restraint alone wasn't enough.
- **Rejected — "Gradient Startup"** (`.working/direction-gradient-startup.html`) — glossy multi-color mesh-gradient glassmorphism. Rejected for being "gradient-loud" and closer to marketing-page energy than a serious profile tool.
- **Rejected — "Editorial Premium"** (`.working/direction-editorial-premium.html`) — warm-paper serif/hairline register. Rejected for not being "highly interactive" — too quiet for a picker meant to feel like a live, responsive quiz.
- **Precursor, not rejected — `.working/direction-hybrid-depth.html`** — the single-page (non-stepped) version that established the void/orb/grain palette and the depth concept. Refined into the current 3-step, one-panel-at-a-time flow with real gating logic in `mockups/flow-hybrid-depth-steps.html`, which is the artifact this spine and `DESIGN.md` are drawn from.

## Key Flows

### Flow 1 — Noa sets up her digest for the first time (backend engineer, one of two seeded dogfood users, first visit to `/me/preferences`)

1. Noa opens `/me/preferences` for the first time. Step 1 mounts with its staggered entrance; Field, Role placeholder, and Experience controls fade up in sequence.
2. She taps "Tech" in the Field chip row. It becomes `chip-selected`; the Role row re-renders with Tech-scoped options.
3. She taps "Backend Engineer" in the newly populated Role row, then "6–10 yrs" in the Experience segmented control.
4. Continue (previously disabled) becomes active the moment all three are set — no separate confirmation needed. She clicks it; Step 2 mounts.
5. She optionally jots a line or two in the Interest Free-Text textarea, glancing at a Suggested Prompt for phrasing, then clicks Continue (not Skip, though either was available).
6. Step 3 mounts. Suggested Topics are already computed from her Field/Role and interest text.
7. **Climax:** four Topic pills appear already `picked` — AI & Machine Learning, Developer Tools, Startups, Open Source — with the counter reading "Selected 4 / 4." She recognizes most of them as relevant on sight; she taps one faint candidate ("Cloud & Infra") to swap it in for one she's less interested in.
8. She clicks "Save preferences." The page gives the existing save-feedback ("Saved.") — nothing about the async suggestion computation was visible or blocking at any point.

Failure: if Topic suggestion generation had failed or timed out server-side, her save still succeeds silently with no candidate Topics shown, and she can still hand-pick up to 4 from the existing Topic toggle list below the picker (FR-8 consequence).

### Flow 2 — Amir's role isn't on the list (DevRel, Tech field already picked, mid-profile-setup)

1. Amir is on Step 1 with "Tech" already selected as Field; the Role row shows Tech's current options (Software Engineer, Product Manager, Data Scientist, Founder / Exec) plus "Other."
2. He scans the row — none of them are Developer Relations. He taps the dashed "Other" chip.
3. A free-text input reveals itself in place of a plain chip selection. He types "Developer Relations."
4. Role now counts as set (Continue's gate only checks that a Role value exists, not that it came from the curated list); he picks an Experience bucket and clicks Continue.
5. He skips Step 2 via the Skip link — no interest text, no penalty, no gate.
6. Step 3 mounts. Because "Developer Relations" has no promoted Role match yet, the Suggestion Source has nothing Field/Role-specific to key off; the always-available popularity-based fallback (FR-9) still populates 4 Topic pills.
7. **Climax:** even with an unmatched, freshly-typed Role, Amir never hits a dead end — four Topics are already picked, not zero, and he can swap or hand-adjust them exactly as Noa could. The "always produces something" guarantee holds even for the worst-case profile input.
8. He saves. His profile records "Developer Relations" as free text; separately (invisibly to him, on this surface) it's queued as a Pending Taxonomy Suggestion for an admin to review on the Admin Taxonomy Curation Queue — a different surface, styled per the existing admin panel conventions, not Hybrid Depth.

Edge case not yet resolved by this spine: whether "Developer Relations" being typed by Amir today and later promoted by an admin retroactively updates his stored profile — per the PRD (§4.2 FR-7 consequence), it explicitly does not; he'd keep his free-text value unless he manually reselects the promoted entry later.
