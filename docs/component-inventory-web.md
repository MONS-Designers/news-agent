# Component Inventory - web

**Date:** 2026-09-10
**Part:** `web` (`frontend`)
**Convention:** Vue 3 single-file components, `<script setup lang="ts">`, Tailwind utility
classes. No scoped CSS, no component library.

## Design system

There is no third-party UI kit. The system is Tailwind version 4 theme tokens declared in
`frontend/src/style.css`, plus repeated utility-class constants inside the components that
need them.

### Two visual identities

| Identity | Where | Character |
| --- | --- | --- |
| Default light | shell, admin views, topic grid | Neutral greys, white sticky header, amber accent in the wordmark |
| Hybrid Depth | profile picker and its companions | Near-black background, indigo accents, fade-up motion |

Hybrid Depth is declared as `--color-hd-*` tokens in the `@theme` block rather than as
scoped CSS, so the picker uses the same utility-class convention as the rest of the app.

```text
--color-hd-bg        #0a0d16   void background
--color-hd-fg        #eef1f8   foreground
--color-hd-title     #f4f6fb
--color-hd-subtitle  #8b93a7
--color-hd-kicker    #6d7bff
--color-hd-muted     #767d92   raised 2026-09-09 to pass WCAG AA
--color-hd-label     #828a9e   raised 2026-09-09 to pass WCAG AA
--color-hd-body      #c4cadb   raised 2026-09-09 to pass WCAG AA
--color-hd-chip      #c4cadb
--color-hd-accent    #a9b1ff
--color-hd-accent-2  #6d7bff
--font-hd            system stack
--animate-fade-up    fadeUp 0.5s ease forwards
--animate-hd-twinkle hdTwinkle 1.3s ease-in-out infinite
```

The muted, label and body values were darkened on 2026-09-09 because the previous ones
measured 3.04 and 4.05 to 1 against the void background and failed the 4.5 to 1 floor.

### Shared button base

`AboutYouStep.vue`, `InterestsStep.vue` and `TopicsStep.vue` each declare an identical
`BTN_BASE` utility string, copied verbatim between them by the folder's own convention,
because the Back control has to look the same on every step. It encodes a 44 by 44 pixel
minimum hit area, a press-scale transition with a `motion-reduce` opt-out, and a visible
focus ring on the accent color.

## Shell and layout

### `App.vue` (131 lines)

The application shell. Sticky translucent header with a backdrop blur, the logo mark and the
NewsAgent wordmark, the navigation, and the router outlet.

Navigation is identity-driven. Three admin links render only when `me.is_admin`, and the
admin row collapses into a horizontally scrollable strip on narrow screens. The feedback
widget is gated on a session existing at all.

The logo link is explicitly `dir="ltr"` so the Latin wordmark is not reordered inside the
right-to-left page.

## Route views

| Component | Route | Audience | Size |
| --- | --- | --- | --- |
| `HomeView.vue` | `/` | everyone | 503 lines |
| `PreferencesView.vue` | `/preferences` | reader | 290 lines |
| `AdminView.vue` | `/admin` | admin | 130 lines |
| `TaxonomyQueueView.vue` | `/admin/taxonomy` | admin | 241 lines |
| `EngagementView.vue` | `/admin/engagement` | admin | 99 lines |

### `HomeView.vue`

The largest component in the app, and the one with the most states. It is the landing page
for an anonymous visitor, the first-run welcome for a freshly registered reader, and the host
for the profile picker.

It reads the router query to explain why a visitor arrived: `signin=required` from the auth
guard, `error=oauth_failed` and `error=capacity_full` from the OAuth callback. It also owns
the sign-in call to action and the Google marks.

### `PreferencesView.vue`

The reader's own surface. Seeds `profile-draft.ts` once through `initProfileDraft()`, then
hosts the profile picker and the topic grid. Also carries the delivery opt-out control.

Because the draft store is module-level, this view deliberately skips re-fetching data it
already has across single-page navigations.

### `AdminView.vue`

Pending source approval. Lists sources from `listPendingSources()` and calls
`setSourceStatus()` with `approved` or `rejected`. Handles `ApiError` inline.

### `TaxonomyQueueView.vue`

The Field and Role curation queue. Lists pending suggestions with their submission counts,
and lets the admin correct the spelling of the promoted name before approving, since the
dedupe key stored on the row is casefolded.

### `EngagementView.vue`

The opens-and-clicks report. A read-only table over `listDigestEngagement()`.

## Profile picker

Five components under `frontend/src/components/profile-picker/`. The three-step guided flow
that turns Field, Role, Experience and Interests into suggested Topics.

### `ProfilePickerShell.vue` (111 lines)

Props: `canExit?: boolean`. Emits: `topics-saved`, `back`.

The step indicator and the container. Holds the three step labels and orchestrates which
step is active. It does **not** relay data between steps; the steps read and patch the
shared draft store directly, so siblings see each other's changes without the shell in the
middle.

### `AboutYouStep.vue` (332 lines) - step 1

Props: `showBack?: boolean`. Emits: `continue`, `back`.

Field, Role and Experience selection. Field and Role each offer curated chips plus a free
text "Other" path, which is what feeds the admin taxonomy queue. Experience is a fixed
illustrative set with no "Other" concept.

### `InterestsStep.vue` (146 lines) - step 2

Props: `active: boolean`. Emits: `continue`, `back`.

Optional free-text interests, with prompt suggestions fetched from
`getPromptSuggestions()`. Saves `interest_free_text` on its own, which is why
`updateMyProfile()` builds its request body key by key rather than sending the whole shape.

### `TopicsStep.vue` (296 lines) - step 3

Props: `active: boolean`. Emits: `back`, `saved`.

Reviews, swaps and confirms the suggested topics. Two constants in this file are contracts
with the backend rather than local choices:

- `MAX_TOPICS = 4` must match `services/preferences.py`'s own cap.
- `POLL_INTERVAL_MS = 400`, with a roughly 45-second budget, paces the suggestion polling.
  The background computation it waits on makes two LLM calls, and the `pending_slow` status
  it may see is non-terminal, so the component keeps polling through it.

### `ChipRow.vue` (132 lines)

Props: `stepNum`, `label`, `options`, `otherPlaceholder`, `placeholderText`.

The reusable selectable-chip row used for Field, Role and Experience. When
`placeholderText` is set it renders that hint instead of any chips, which is how a dependent
row communicates that an earlier choice is still missing.

## Shared components

### `FeedbackWidget.vue` (131 lines)

The in-app feedback control: a one-to-five star rating, optional free text, or both. Posts to
`POST /me/feedback`. Mounted in `App.vue` only when a session exists.

This gating is the reason the email click-tracking thank-you page is standalone HTML rather
than a redirect into the app: a signed-out reader clicking a thumb in their email would land
on a page whose confirmation toast never mounts.

### `HybridDepthBackground.vue` (131 lines)

The animated void backdrop behind the profile picker. Mounted and unmounted with lifecycle
hooks so the animation does not keep running off-screen.

### `HybridSpinner.vue` (28 lines)

Props: `size: "inline" | "standalone"`.

A single sparkle taken from the logo mark, animated with the `hdTwinkle` keyframes declared
in `style.css`. Used wherever the picker waits on the backend.

## Assets

| File | Use |
| --- | --- |
| `src/assets/logo-mark.svg` | Header and spinner |
| `src/assets/google-g.svg` | Sign-in button |
| `src/assets/google-wordmark.svg` | Sign-in button |

All three are imported as modules so Vite fingerprints them.

## Reusable versus specific

**Reusable:** `ChipRow`, `HybridSpinner`, `HybridDepthBackground`, `FeedbackWidget`, and the
`BTN_BASE` utility string.

**Single-use by design:** every view, and the four picker components other than `ChipRow`.
They are not abstracted further because each is used exactly once, and a single-use
abstraction would be clutter rather than architecture.

## Test coverage

Every view and every profile-picker component has a colocated Vitest spec.

| Location | Specs |
| --- | --- |
| `src/__tests__/` | `App.spec.ts`, `gendered-copy.spec.ts`, `profile-draft.spec.ts` |
| `src/views/__tests__/` | one per view, five total |
| `src/components/__tests__/` | `FeedbackWidget`, `HybridDepthBackground`, `HybridSpinner` |
| `src/components/profile-picker/__tests__/` | one per component, five total |
| `e2e/` | `admin-taxonomy`, `preferences`, `profile-picker` |

`gendered-copy.spec.ts` is a content regression guard rather than a component test. It scans
`.vue` files for the most common gendered Hebrew phrasings. Being a word-boundary scan rather
than a parser, a genuinely new phrasing may need the denylist extended rather than the check
silenced.

---

_Generated using BMAD Method `document-project` workflow_
