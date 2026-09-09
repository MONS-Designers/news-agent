---
name: Hybrid Depth
description: Visual identity for the /me/preferences page's profile system - the Field/Role/Experience/Topic picker wizard, plus the returning-user summary/edit screen and the weekly-email subscription toggle. NewsAgent's first custom UI identity, independent of the spartan neutral-Tailwind baseline elsewhere in the app and of the unrelated dark/gold "Midnight" email brand.
status: final
updated: 2026-09-08
colors:
  bg-void: '#0a0d16'
  ink-primary: '#f4f6fb'
  ink-body: '#eef1f8'
  ink-secondary: '#c4cadb'
  ink-tertiary: '#8b93a7'
  ink-muted: '#828a9e'    # raised 2026-09-09 from #6b7288 (4.05:1, failed WCAG AA) - see EXPERIENCE.md Accessibility Floor
  ink-faint: '#767d92'    # raised 2026-09-09 from #565f74 (3.04:1, failed WCAG AA) - see EXPERIENCE.md Accessibility Floor
  accent: '#6d7bff'
  accent-strong: '#a9b1ff'
  accent-gradient-start: '#434ed2'   # revised 2026-09-09, twice - see EXPERIENCE.md Accessibility Floor for the full history (original #7b86ff failed WCAG AA; two intermediate revisions read as flat, then as muddy/unprofessional, then as too-bright/industrial)
  accent-gradient-end: '#231666'     # revised 2026-09-09 alongside accent-gradient-start
  accent-gradient-border: 'rgba(169,177,255,0.3)'  # new 2026-09-09 - see EXPERIENCE.md; darkening the fill past a point needs a border to stay visible against bg-void
  # IMPORTANT: must be interpolated `in oklch`, not the plain sRGB default - a
  # plain `linear-gradient(accent-gradient-start, accent-gradient-end)` crosses
  # a visibly desaturated/muddy band around the midpoint (measured). See the
  # component implementations' `linear-gradient(to bottom in oklch, ...)`.
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
  button-secondary:
    background: '{colors.chip-surface}'
    hover-background: '{colors.chip-surface-hover}'
    border: '{colors.panel-border}'
    hover-border: '{colors.panel-border-hover}'
    text: '{colors.ink-secondary}'
    radius: '{rounded.md}'
    disabled-opacity: 0.5
  alert-frame:
    background: '{colors.accent-soft}'
    border: 'rgba(109,123,255,0.4)'
    radius: '{rounded.lg}'
    heading-text: '{colors.ink-primary}'
    body-text: '{colors.ink-secondary}'
  spinner:
    size-inline: 16px
    size-standalone: 22px
    color: currentColor
    shape: logo-mark-single-sparkle
    sparkle-scale: 2.4x
    motion: twinkle
    twinkle-scale: '0.82 - 1.08'
    twinkle-opacity: '0.3 - 1'
    twinkle-duration: 1.3s
    twinkle-easing: ease-in-out
    # Confirmed live 2026-09-08 (round 2's twinkle motion - see .memlog.md).
    # Two follow-up tweaks same session: size-inline 14px -> 16px and
    # twinkle-opacity's low end 0.55 -> 0.3 (wider swing), both because the
    # inline/button-context spinner read as "really weak" at the original
    # values. size-standalone and twinkle-scale unchanged - the complaint was
    # specific to the small inline context, not the pattern itself.
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

Hybrid Depth is the visual identity for the profile system on the existing, always-editable `/me/preferences` page: the Field / Role / Experience Bucket / Topic picker wizard, the returning-user summary/edit screen it leads to, and the weekly-email subscription toggle beside it (extended 2026-09-08 - originally wizard-only, see `.memlog.md`). It is deliberately not a redesign of the whole app - the page's own top-level heading, its loading/error states, and the rest of the app (including the plain Tailwind Topic toggle list below this picker) keep their current spartan look, and the daily-digest email keeps its own separate "Midnight" identity. This is the first custom visual identity applied to the live app itself, scoped to the profile surfaces it was commissioned for.

The brief (per the run's decision log) was explicit: fresh, highly interactive, "most advanced and attractive," a superior professional finish - while staying serious and mysterious rather than playful or celebratory. Hybrid Depth answers that by combining two ingredients that were prototyped separately and rejected on their own: the restraint of a flat, minimal SaaS palette, and the interactive "choose your class" energy of a game-like selector. The synthesis routes the "interactive" feeling through motion and depth - parallax-drifting glow orbs behind a near-black canvas, glass panels, staggered entrance animation - rather than through saturated color or exclamation-mark copy. Nothing here is neon, nothing is a loud gradient card, and no microcopy performs enthusiasm at the user.

## Colors

The palette is a near-black void with three restrained, desaturated glows and a single indigo-violet accent - never more than one chromatic accent doing interactive work at a time.

- **Void (`{colors.bg-void}`)** is the page canvas. Not pure black - warmed just enough to read as "deep" rather than "off." Everything else sits on top of it.
- **Ink scale** (`{colors.ink-primary}` → `{colors.ink-faint}`) is the full text hierarchy, palest to dimmest: primary for headings, body for running text, secondary for chip/button label text, tertiary for sub-copy and unselected pill text, muted for chrome-level labels (URL bar, ghost buttons), faint for the least prominent state (unselected progress dots, captions).
- **Accent (`{colors.accent}`, indigo-violet)** is the single interactive color: selected chips, the active progress dot, focus rings, the primary button's gradient family (`{colors.accent-gradient-start}` → `{colors.accent-gradient-end}`), and picked-topic pills. `{colors.accent-strong}` is a lighter step of the same hue for small high-contrast accents (step-number badges, the "4" in the topic counter). This is the one color allowed to mean "selected" or "active" - it should never appear decoratively.
- **Orb trio** (`{colors.orb-indigo}`, `{colors.orb-teal}`, `{colors.orb-plum}`) are the three background glows that give the surface its depth and its interactivity (they drift with mouse position and scroll position). They are heavily blurred and low-opacity by construction - see Components - and are a background atmosphere, never a foreground UI color. Don't pull them into text, borders, or controls.
- **Panel and chip surfaces** (`{colors.panel-surface}`, `{colors.panel-border}`, `{colors.chip-surface}`, and their hover variants) are all translucent white-on-void overlays, not solid hex fills - the glass/depth effect depends on compositing over the orb layer showing through. This is a deliberate departure from the flat solid-hex palettes in the other rejected directions.

Avoid: introducing a second chromatic accent, using the orb colors anywhere outside the fixed background layer, solid opaque panel fills (breaks the depth read), and pure white/pure black at full opacity anywhere except the void base itself.

## Typography

No custom or brand webfont - the system UI stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif`) is used throughout, consistent with the fact that this feature ships into an existing Vue + Tailwind app with no typographic identity of its own to override. The identity here is carried by color, depth, and motion, not by type choice.

Roles, largest to smallest: `{typography.title}` for the single page heading ("Set up your profile"); `{typography.kicker}` for the small uppercase eyebrow above it ("Preferences") and `{typography.label}` for the uppercase step-section labels ("Field", "Role", "Experience", "Suggested topics") - both uppercase and letter-spaced, but the kicker runs in `{colors.accent}` while the label runs in `{colors.ink-muted}`, keeping only one "loud" uppercase moment per screen; `{typography.body}` for the descriptive sub-line under the heading and for helper copy; `{typography.control}` for chip, segmented-control, and topic-pill labels; `{typography.button}` (semibold) for Continue/Back/Skip/Save; `{typography.caption}` for the smallest chrome (URL bar text, the "Selected 4/4" counter, progress-step captions).

No display sizes beyond `title`, no italics, no serif moment - the register is a calm, confident quiz, not an editorial hero.

## Layout & Spacing

Single column, centered, capped at `{spacing.chrome-max-width}` (640px) - this is a focused, one-decision-at-a-time flow, not a dashboard, so there is no multi-column layout at any point. Only one step panel is visible on screen at a time; the other two are unmounted from view, not just scrolled away.

Spacing scale (`{spacing.1}` through `{spacing.7}`: 8 / 10 / 14 / 16 / 22 / 24 / 30px) governs internal rhythm - small values (`{spacing.1}`–`{spacing.2}`) between tightly related elements like chips in a row or progress dots and their connecting line; larger values (`{spacing.5}`–`{spacing.7}`) between structurally distinct blocks (block heading to its chip row, step panel to the nav row below it). The step panel itself uses `{spacing.panel-padding}` (30px) as fixed internal padding regardless of content.

No responsive breakpoint behavior has been designed for this layout - see `EXPERIENCE.md` § Responsive & Platform for that gap.

## Elevation & Depth

Depth is the core device of this identity, and it is built from three layers, back to front:

1. **The orb field** - three large (340–460px), heavily blurred (`{components.orb.blur}`, 70px) radial gradients (`{components.orb.colors}`) at low opacity (`{components.orb.opacity}`, 0.35), fixed behind all content, drifting continuously via both mouse-position and scroll-position parallax. This is the "alive" quality the brief asked for - motion instead of color for interactivity.
2. **The grain overlay** - a faint, fixed dot-tile texture (`{components.grain-overlay}`) at very low opacity, sitting above the orbs and below content, breaking up what would otherwise be a flat gradient wash.
3. **Panels and chips** - translucent glass surfaces (`{colors.panel-surface}`, `{colors.chip-surface}`) with backdrop-blur, sitting above both background layers so the orbs are visible, softened, through them.

Shadow use is minimal and reserved for the accent: the primary button and the active/selected states get a soft glow shadow in the accent color (`{components.button-primary.shadow}`, `{components.progress-dot.active-glow}`, `{components.chip-selected.shadow}`) - this is the only place elevation reads as a conventional drop shadow, and it always doubles as a state signal (this is active / this is selected), never pure decoration.

## Shapes

`{rounded.sm}` (6px) is reserved for the smallest fixed-size elements - the numbered step-badges inside each block heading. `{rounded.md}` (10px) is the workhorse radius: chips, buttons, the segmented control. `{rounded.lg}` (12px) steps up slightly for the interest textarea, the one multi-line input on the surface. `{rounded.xl}` (16px) is reserved for the step panel itself - the largest single surface gets the largest radius. `{rounded.full}` (pill/circle) is used only for elements that are tag-like or literally circular: topic pills, the small "suggested prompt" pills, and the progress-step dots.

The logic: radius scales with a surface's size and its "containing" role, and full-round is reserved for things that behave like tokens (topics, prompts, step markers) rather than for buttons or panels generally - buttons stay at `{rounded.md}`, not pill-shaped, keeping the register closer to "serious tool" than "friendly app."

## Components

- **Field / Role chip** (`{components.chip}`, `{components.chip-selected}`, `{components.chip-other}`) - single-select row of pill-corner-radius rectangles. Idle state is a barely-visible translucent surface; hover lifts and brightens the border slightly; selected state switches to the accent gradient fill with a glow shadow and white text. The "Other" variant uses a dashed border and dimmer text to visually mark it as an escape hatch, not a normal option, in both Field and Role rows.
- **Experience segmented control** (`{components.segmented-control}`) - a single-row, equal-width segment group (four segments: the illustrative Experience Bucket ranges) inside a shared track. Selected segment gets the accent-soft fill and white text; unselected segments are transparent with tertiary-ink text.
- **Step panel** (`{components.panel}`) - the one visible glass container per step. Only ever one `current` panel on screen; contents inside it animate in with a staggered fade-up (each direct block delayed slightly after the previous) on every mount, including on re-entry via Back.
- **Progress stepper** (`{components.progress-dot}`) - three numbered dots connected by a fill-on-completion line. Three states: idle (dim border/number), active (accent border + glow + filled number), done (solid accent fill, checkmark-style label recede). The connecting line between two dots animates its fill only when the earlier step transitions to done.
- **Interest textarea** (`{components.textarea}`) - full-width, single surface, glows on focus with `{colors.accent-glow}` border. Paired with small pill-shaped "suggested prompt" affordances above it (visually similar to topic pills but non-selectable illustrative text, not part of the chip/topic interaction family).
- **Topic pill** (`{components.topic-pill}`) - two visual states beyond idle: `picked` (accent gradient fill, white text, small "✕" affordance to remove) and `faint` (low-opacity, dashed border, representing an unpicked candidate available to swap in). No third "unavailable" state exists in the mock.
- **Primary / Ghost buttons** (`{components.button-primary}`, `{components.button-ghost}`) - primary carries the accent gradient and glow shadow, used once per step (Continue or Save preferences); ghost is text-only with no border or fill, used for Back and Skip. Primary has a distinct `disabled` visual (opacity 0.35, no shadow) used on Step 1's Continue until Field + Role + Experience are all set - see `EXPERIENCE.md` for the behavioral/gating rule, since the mock implements this gate as a manually-toggled `.disabled` class rather than the native HTML `disabled` attribute (the controls are `<div>`s, not real form controls - flagged as an accessibility gap in `EXPERIENCE.md`).
- **Orb field + grain overlay** (`{components.orb}`, `{components.grain-overlay}`) - fixed background decoration, `pointer-events: none`, present behind every step without exception.
- **Prototype browser-chrome bar** - the traffic-light-dot URL bar visible at the top of the working mockup is a presentation device to frame the mock as "this is a browser window," not a real in-app component. `/me/preferences` already renders inside the user's actual browser chrome; this element should not be built into the real UI.
- **Summary panel** (reuses `{components.panel}`) - the returning-user read-only view (Field/Role/Experience, Interest Free-Text if set, subscribed topics) sits inside the same glass panel as a wizard step. No new container token; this is the "done" counterpart to the step panel, not a distinct surface family. The Field/Role/Experience grid is two columns (`grid-cols-2`) at `sm` and above, single column below it - same breakpoint convention as the wizard's own `sm:` usage, not a new one (added 2026-09-08).
- **Read-only topic pill** (reuses `{components.topic-pill}`'s `picked` state) - the subscribed-topics list on the summary screen uses the exact picked-pill visual (accent gradient fill, white text), minus the "✕" remove affordance and the tap-to-swap behavior - it communicates "this is selected," same as Step 3, just non-interactive here.
- **Edit-profile button** (reuses `{components.button-primary}`) - same primary gradient treatment as Continue/Save; it's the one primary action on the summary screen.
- **Subscription-toggle row** (`{components.button-secondary}`, new) - the weekly-email pause/resume control is a lighter-weight action than Edit profile, but heavier than a text-only Back/Skip - `button-ghost` (no border) read as too weak here, `button-primary` (gradient + glow) too heavy for a low-stakes toggle. `button-secondary` is a bordered, unfilled control: idle `{colors.chip-surface}` fill with `{colors.panel-border}`, brightening to `{colors.panel-border-hover}` on hover (hover gated to `hover:hover` devices, matching the wizard's own convention) - visually a step down from primary, a step up from ghost. The row itself stacks label-above-button below `sm` and returns to `justify-between` side-by-side at `sm` and above (added 2026-09-08, mirrors the wizard footer nav rows' `flex-col ... sm:flex-row`).
- **Alert frame** (`{components.alert-frame}`, new) - the "profile changed, topics unchanged" warning uses a bordered, tinted panel in the *existing* accent color (`accent-soft` fill, a stronger accent-tinted border) rather than a second chromatic hue - attention is signaled by framing and contrast, not a new color family. Houses its own inline primary-styled action button (`{components.button-primary}`, "עדכון הנושאים שלי" / update my topics).
- **Spinner** (`{components.spinner}`, new, iterated four times 2026-09-08 across two rounds) - not a generic ring, and not the full logo mark either. v1 reused the whole mark (sparkle-pair + three bars); read as a static logo, not a loading state. v2 dropped the three bars but kept both sparkles as one rigid group rotating around an external point - "the 2 stars move together," rejected on sight, doesn't read as a clean spin. v3 dropped the second sparkle too - a single sparkle, the larger of the original pair, scaled ~2.4x (`sparkle-scale`) and rotating around its own true center. User's verdict on v3: "better but not perfect, needs to be worked on seriously" - not rejected outright, but not confirmed either.

  **Round 2 diagnosis:** rotating that shape has a structural problem, not a tuning one. The sparkle glyph is 4-fold symmetric (its four points are identical), so a full rotation repeats its own silhouette every 90° - at 14px inline size this reads as a wobble/shape-change (especially at the 45° "diamond" position) rather than a clean continuous spin, and a solid filled shape has no varying visual weight around its rotation axis, so it lacks the cue classic ring/arc spinners rely on to read as "turning" at all. Two repair attempts (breaking the symmetry with a marker dot; layering an independent breathing-scale on top of a slowed rotation) and one alternate motif (the mark's own three bars, as a sequential wave pulse) were rendered and visually compared in `.working/spinner-directions-2026-09-08.html` alongside v3 - full reasoning for each rejection in `.memlog.md`.

  **Proposed current direction: sparkle twinkle** (`motion: twinkle`) - same single sparkle at the same 2.4x scale and position, but **no rotation at all**: a `twinkle-scale` (0.82→1.08) + `twinkle-opacity` (0.55→1) pulse, `ease-in-out`, over `twinkle-duration` (1.3s). This sidesteps the rotation-symmetry problem entirely rather than patching it, keeps a single moving element (the restrained-motion principle below), and arguably reads as the more honest motion metaphor for this glyph - sparkles conventionally twinkle rather than spin in comparable icon systems (Gemini's sparkle, Apple's "sparkles" SF Symbol). **Not yet confirmed live by the user** - this round ran standalone, without a live session to verify against on the spot the way v1/v2/v3 each were; treat this as the strongest current recommendation, not a settled decision, until confirmed.

  Unchanged from v3: fills with `currentColor`, not a hardcoded hex - inside Hybrid Depth that resolves to `{colors.accent}` (never the brand's literal gold, which would violate the single-accent rule below); a plain neutral-Tailwind screen elsewhere on the site is free to set the ambient text color to the actual brand gold if that reads better there - one component, context-themed. Two sizes: `size-inline` (14px, beside a button's label, replacing bare "טוען…"/"שומר…" text-only treatment) and `size-standalone` (22px, page-level loads like `PreferencesView.vue`'s initial fetch). `prefers-reduced-motion` freezes the pulse at rest (full scale/opacity); the static sparkle alone still reads as "busy," never disappears. The three bars and the second sparkle still exist unchanged in the real logo/favicon elsewhere - only this component's composition changes.

## Do's and Don'ts

| Do | Don't |
|---|---|
| One chromatic accent (`{colors.accent}`) for all "selected / active" states | Add a second bright accent color, or use the orb hues for UI elements |
| Depth and motion (parallax orbs, blur, staggered entrance) as the "interactive" signal | Neon glows, saturated multi-color gradients, or playful bounce/scale motion |
| Serious, plain-language microcopy ("Continue," "Save preferences," "Change any of it later - this never locks in") | Exclamation marks, celebratory copy, gamified framing ("Level up your feed!") |
| Dashed border = "Other" / unselected-candidate semantic, consistently | Reuse dashed borders for anything else (e.g., disabled state) |
| Glass panels that let the orb field show through (translucent surfaces + backdrop-blur) | Opaque solid-fill panels - breaks the depth premise entirely |
| Accent glow shadows tied to a real state (active / selected / primary action) | Decorative shadows with no state meaning |
| Reuse existing tokens (`panel`, `topic-pill`, `button-primary`) across the wizard and the summary screen | Invent a parallel visual language for "done" state that doesn't read as the same product |
| Signal a warning via framing/contrast within the existing accent (`{components.alert-frame}`) | Introduce amber/red/yellow or any second chromatic hue for warnings or errors |
| Communicate "busy" with a real spinner (`{components.spinner}`) wherever a loading state persists more than a beat | Leave a disabled control with no visual explanation, or rely on text alone ("טוען…") as the only busy signal |
| Spinner fills with `currentColor` so it resolves to `{colors.accent}` inside Hybrid Depth | Hardcode the brand mark's literal gold (`#f0b429`) anywhere inside a Hybrid Depth surface - that's a second accent, banned above, even though the spinner's *shape* is the real logo |
