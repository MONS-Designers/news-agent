---
name: Hybrid Depth
description: Visual identity for the Field / Role / Experience / Topic profile picker on the existing /me/preferences page — NewsAgent's first custom UI identity, independent of the spartan neutral-Tailwind baseline and of the unrelated dark/gold "Midnight" email brand.
status: final
updated: 2026-07-22
colors:
  bg-void: '#0a0d16'
  ink-primary: '#f4f6fb'
  ink-body: '#eef1f8'
  ink-secondary: '#c4cadb'
  ink-tertiary: '#8b93a7'
  ink-muted: '#6b7288'
  ink-faint: '#565f74'
  accent: '#6d7bff'
  accent-strong: '#a9b1ff'
  accent-gradient-start: '#7b86ff'
  accent-gradient-end: '#5c68e8'
  accent-soft: 'rgba(109,123,255,0.14)'
  accent-glow: 'rgba(109,123,255,0.35)'
  orb-indigo: '#4b3fae'
  orb-teal: '#1f6f78'
  orb-plum: '#7a3b6e'
  panel-surface: 'rgba(255,255,255,0.035)'
  panel-border: 'rgba(255,255,255,0.09)'
  panel-border-hover: 'rgba(255,255,255,0.22)'
  chip-surface: 'rgba(255,255,255,0.02)'
  chip-surface-hover: 'rgba(255,255,255,0.05)'
  grain-dot: 'rgba(255,255,255,0.045)'
  browserbar-dot-idle: '#3a3f52'
typography:
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif'
    fontSize: 30px
    fontWeight: '650'
    letterSpacing: -0.5px
  kicker:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif'
    fontSize: 11px
    fontWeight: '700'
    letterSpacing: 3px
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif'
    fontSize: 14px
    lineHeight: '1.55'
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif'
    fontSize: 11px
    fontWeight: '700'
    letterSpacing: 2px
  control:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif'
    fontSize: 13.5px
  button:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif'
    fontSize: 13.5px
    fontWeight: '600'
  caption:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif'
    fontSize: 12px
rounded:
  sm: 6px
  md: 10px
  lg: 12px
  xl: 16px
  full: 9999px
spacing:
  '1': 8px
  '2': 10px
  '3': 14px
  '4': 16px
  '5': 22px
  '6': 24px
  '7': 30px
  panel-padding: 30px
  chrome-max-width: 640px
components:
  chip:
    background: '{colors.chip-surface}'
    border: '{colors.panel-border}'
    hover-border: '{colors.panel-border-hover}'
    hover-background: '{colors.chip-surface-hover}'
    radius: '{rounded.md}'
    text: '{colors.ink-secondary}'
    padding: '11px 16px'
  chip-selected:
    background: 'linear-gradient(180deg, rgba(109,123,255,0.22), rgba(109,123,255,0.10))'
    border: 'rgba(109,123,255,0.55)'
    text: '#ffffff'
    shadow: '0 0 0 1px rgba(109,123,255,0.25), 0 8px 24px -8px rgba(109,123,255,0.45)'
  chip-other:
    borderStyle: dashed
    text: '{colors.ink-tertiary}'
  segmented-control:
    track: '{colors.chip-surface}'
    border: '{colors.panel-border}'
    radius: '{rounded.md}'
    idle-text: '{colors.ink-tertiary}'
    selected-background: '{colors.accent-soft}'
    selected-text: '#ffffff'
  panel:
    background: '{colors.panel-surface}'
    border: '{colors.panel-border}'
    radius: '{rounded.xl}'
    padding: '{spacing.panel-padding}'
    backdrop-blur: 18px
  progress-dot:
    size: 26px
    idle-border: '{colors.panel-border}'
    idle-text: '{colors.ink-faint}'
    active-border: '{colors.accent}'
    active-background: '{colors.accent-soft}'
    active-glow: '0 0 0 4px rgba(109,123,255,0.12)'
    done-background: '{colors.accent}'
    done-text: '#ffffff'
  button-primary:
    background: 'linear-gradient(180deg, {colors.accent-gradient-start}, {colors.accent-gradient-end})'
    text: '#ffffff'
    radius: '{rounded.md}'
    shadow: '0 10px 24px -10px rgba(109,123,255,0.6)'
    disabled-opacity: 0.35
  button-ghost:
    text: '{colors.ink-muted}'
    hover-text: '#9aa2b8'
    background: transparent
  topic-pill:
    idle-text: '{colors.ink-tertiary}'
    idle-border: '{colors.panel-border}'
    picked-background: 'linear-gradient(180deg, rgba(109,123,255,0.22), rgba(109,123,255,0.09))'
    picked-border: 'rgba(109,123,255,0.5)'
    picked-text: '#ffffff'
    faint-opacity: 0.45
    faint-borderStyle: dashed
    radius: '{rounded.full}'
  textarea:
    background: '{colors.chip-surface}'
    border: '{colors.panel-border}'
    radius: '{rounded.lg}'
    focus-border: '{colors.accent-glow}'
    placeholder-text: '{colors.ink-faint}'
  orb:
    blur: 70px
    opacity: 0.35
    colors: ['{colors.orb-indigo}', '{colors.orb-teal}', '{colors.orb-plum}']
  grain-overlay:
    dot-color: '{colors.grain-dot}'
    tile-size: '26px 26px'
    opacity: 0.35
---

## Brand & Style

Hybrid Depth is the visual identity for one specific surface: the Field / Role / Experience Bucket / Topic profile picker that lives inside the existing, always-editable `/me/preferences` page. It is deliberately not a redesign of the app — the rest of the app (including the plain Tailwind Topic toggle list this picker sits alongside) keeps its current spartan look, and the daily-digest email keeps its own separate "Midnight" identity. This is the first custom visual identity applied to the live app itself, scoped narrowly to the surface it was commissioned for.

The brief (per the run's decision log) was explicit: fresh, highly interactive, "most advanced and attractive," a superior professional finish — while staying serious and mysterious rather than playful or celebratory. Hybrid Depth answers that by combining two ingredients that were prototyped separately and rejected on their own: the restraint of a flat, minimal SaaS palette, and the interactive "choose your class" energy of a game-like selector. The synthesis routes the "interactive" feeling through motion and depth — parallax-drifting glow orbs behind a near-black canvas, glass panels, staggered entrance animation — rather than through saturated color or exclamation-mark copy. Nothing here is neon, nothing is a loud gradient card, and no microcopy performs enthusiasm at the user.

## Colors

The palette is a near-black void with three restrained, desaturated glows and a single indigo-violet accent — never more than one chromatic accent doing interactive work at a time.

- **Void (`{colors.bg-void}`)** is the page canvas. Not pure black — warmed just enough to read as "deep" rather than "off." Everything else sits on top of it.
- **Ink scale** (`{colors.ink-primary}` → `{colors.ink-faint}`) is the full text hierarchy, palest to dimmest: primary for headings, body for running text, secondary for chip/button label text, tertiary for sub-copy and unselected pill text, muted for chrome-level labels (URL bar, ghost buttons), faint for the least prominent state (unselected progress dots, captions).
- **Accent (`{colors.accent}`, indigo-violet)** is the single interactive color: selected chips, the active progress dot, focus rings, the primary button's gradient family (`{colors.accent-gradient-start}` → `{colors.accent-gradient-end}`), and picked-topic pills. `{colors.accent-strong}` is a lighter step of the same hue for small high-contrast accents (step-number badges, the "4" in the topic counter). This is the one color allowed to mean "selected" or "active" — it should never appear decoratively.
- **Orb trio** (`{colors.orb-indigo}`, `{colors.orb-teal}`, `{colors.orb-plum}`) are the three background glows that give the surface its depth and its interactivity (they drift with mouse position and scroll position). They are heavily blurred and low-opacity by construction — see Components — and are a background atmosphere, never a foreground UI color. Don't pull them into text, borders, or controls.
- **Panel and chip surfaces** (`{colors.panel-surface}`, `{colors.panel-border}`, `{colors.chip-surface}`, and their hover variants) are all translucent white-on-void overlays, not solid hex fills — the glass/depth effect depends on compositing over the orb layer showing through. This is a deliberate departure from the flat solid-hex palettes in the other rejected directions.

Avoid: introducing a second chromatic accent, using the orb colors anywhere outside the fixed background layer, solid opaque panel fills (breaks the depth read), and pure white/pure black at full opacity anywhere except the void base itself.

## Typography

No custom or brand webfont — the system UI stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif`) is used throughout, consistent with the fact that this feature ships into an existing Vue + Tailwind app with no typographic identity of its own to override. The identity here is carried by color, depth, and motion, not by type choice.

Roles, largest to smallest: `{typography.title}` for the single page heading ("Set up your profile"); `{typography.kicker}` for the small uppercase eyebrow above it ("Preferences") and `{typography.label}` for the uppercase step-section labels ("Field", "Role", "Experience", "Suggested topics") — both uppercase and letter-spaced, but the kicker runs in `{colors.accent}` while the label runs in `{colors.ink-muted}`, keeping only one "loud" uppercase moment per screen; `{typography.body}` for the descriptive sub-line under the heading and for helper copy; `{typography.control}` for chip, segmented-control, and topic-pill labels; `{typography.button}` (semibold) for Continue/Back/Skip/Save; `{typography.caption}` for the smallest chrome (URL bar text, the "Selected 4/4" counter, progress-step captions).

No display sizes beyond `title`, no italics, no serif moment — the register is a calm, confident quiz, not an editorial hero.

## Layout & Spacing

Single column, centered, capped at `{spacing.chrome-max-width}` (640px) — this is a focused, one-decision-at-a-time flow, not a dashboard, so there is no multi-column layout at any point. Only one step panel is visible on screen at a time; the other two are unmounted from view, not just scrolled away.

Spacing scale (`{spacing.1}` through `{spacing.7}`: 8 / 10 / 14 / 16 / 22 / 24 / 30px) governs internal rhythm — small values (`{spacing.1}`–`{spacing.2}`) between tightly related elements like chips in a row or progress dots and their connecting line; larger values (`{spacing.5}`–`{spacing.7}`) between structurally distinct blocks (block heading to its chip row, step panel to the nav row below it). The step panel itself uses `{spacing.panel-padding}` (30px) as fixed internal padding regardless of content.

No responsive breakpoint behavior has been designed for this layout — see `EXPERIENCE.md` § Responsive & Platform for that gap.

## Elevation & Depth

Depth is the core device of this identity, and it is built from three layers, back to front:

1. **The orb field** — three large (340–460px), heavily blurred (`{components.orb.blur}`, 70px) radial gradients (`{components.orb.colors}`) at low opacity (`{components.orb.opacity}`, 0.35), fixed behind all content, drifting continuously via both mouse-position and scroll-position parallax. This is the "alive" quality the brief asked for — motion instead of color for interactivity.
2. **The grain overlay** — a faint, fixed dot-tile texture (`{components.grain-overlay}`) at very low opacity, sitting above the orbs and below content, breaking up what would otherwise be a flat gradient wash.
3. **Panels and chips** — translucent glass surfaces (`{colors.panel-surface}`, `{colors.chip-surface}`) with backdrop-blur, sitting above both background layers so the orbs are visible, softened, through them.

Shadow use is minimal and reserved for the accent: the primary button and the active/selected states get a soft glow shadow in the accent color (`{components.button-primary.shadow}`, `{components.progress-dot.active-glow}`, `{components.chip-selected.shadow}`) — this is the only place elevation reads as a conventional drop shadow, and it always doubles as a state signal (this is active / this is selected), never pure decoration.

## Shapes

`{rounded.sm}` (6px) is reserved for the smallest fixed-size elements — the numbered step-badges inside each block heading. `{rounded.md}` (10px) is the workhorse radius: chips, buttons, the segmented control. `{rounded.lg}` (12px) steps up slightly for the interest textarea, the one multi-line input on the surface. `{rounded.xl}` (16px) is reserved for the step panel itself — the largest single surface gets the largest radius. `{rounded.full}` (pill/circle) is used only for elements that are tag-like or literally circular: topic pills, the small "suggested prompt" pills, and the progress-step dots.

The logic: radius scales with a surface's size and its "containing" role, and full-round is reserved for things that behave like tokens (topics, prompts, step markers) rather than for buttons or panels generally — buttons stay at `{rounded.md}`, not pill-shaped, keeping the register closer to "serious tool" than "friendly app."

## Components

- **Field / Role chip** (`{components.chip}`, `{components.chip-selected}`, `{components.chip-other}`) — single-select row of pill-corner-radius rectangles. Idle state is a barely-visible translucent surface; hover lifts and brightens the border slightly; selected state switches to the accent gradient fill with a glow shadow and white text. The "Other" variant uses a dashed border and dimmer text to visually mark it as an escape hatch, not a normal option, in both Field and Role rows.
- **Experience segmented control** (`{components.segmented-control}`) — a single-row, equal-width segment group (four segments: the illustrative Experience Bucket ranges) inside a shared track. Selected segment gets the accent-soft fill and white text; unselected segments are transparent with tertiary-ink text.
- **Step panel** (`{components.panel}`) — the one visible glass container per step. Only ever one `current` panel on screen; contents inside it animate in with a staggered fade-up (each direct block delayed slightly after the previous) on every mount, including on re-entry via Back.
- **Progress stepper** (`{components.progress-dot}`) — three numbered dots connected by a fill-on-completion line. Three states: idle (dim border/number), active (accent border + glow + filled number), done (solid accent fill, checkmark-style label recede). The connecting line between two dots animates its fill only when the earlier step transitions to done.
- **Interest textarea** (`{components.textarea}`) — full-width, single surface, glows on focus with `{colors.accent-glow}` border. Paired with small pill-shaped "suggested prompt" affordances above it (visually similar to topic pills but non-selectable illustrative text, not part of the chip/topic interaction family).
- **Topic pill** (`{components.topic-pill}`) — two visual states beyond idle: `picked` (accent gradient fill, white text, small "✕" affordance to remove) and `faint` (low-opacity, dashed border, representing an unpicked candidate available to swap in). No third "unavailable" state exists in the mock.
- **Primary / Ghost buttons** (`{components.button-primary}`, `{components.button-ghost}`) — primary carries the accent gradient and glow shadow, used once per step (Continue or Save preferences); ghost is text-only with no border or fill, used for Back and Skip. Primary has a distinct `disabled` visual (opacity 0.35, no shadow) used on Step 1's Continue until Field + Role + Experience are all set — see `EXPERIENCE.md` for the behavioral/gating rule, since the mock implements this gate as a manually-toggled `.disabled` class rather than the native HTML `disabled` attribute (the controls are `<div>`s, not real form controls — flagged as an accessibility gap in `EXPERIENCE.md`).
- **Orb field + grain overlay** (`{components.orb}`, `{components.grain-overlay}`) — fixed background decoration, `pointer-events: none`, present behind every step without exception.
- **Prototype browser-chrome bar** — the traffic-light-dot URL bar visible at the top of the working mockup is a presentation device to frame the mock as "this is a browser window," not a real in-app component. `/me/preferences` already renders inside the user's actual browser chrome; this element should not be built into the real UI.

## Do's and Don'ts

| Do | Don't |
|---|---|
| One chromatic accent (`{colors.accent}`) for all "selected / active" states | Add a second bright accent color, or use the orb hues for UI elements |
| Depth and motion (parallax orbs, blur, staggered entrance) as the "interactive" signal | Neon glows, saturated multi-color gradients, or playful bounce/scale motion |
| Serious, plain-language microcopy ("Continue," "Save preferences," "Change any of it later — this never locks in") | Exclamation marks, celebratory copy, gamified framing ("Level up your feed!") |
| Dashed border = "Other" / unselected-candidate semantic, consistently | Reuse dashed borders for anything else (e.g., disabled state) |
| Glass panels that let the orb field show through (translucent surfaces + backdrop-blur) | Opaque solid-fill panels — breaks the depth premise entirely |
| Accent glow shadows tied to a real state (active / selected / primary action) | Decorative shadows with no state meaning |
