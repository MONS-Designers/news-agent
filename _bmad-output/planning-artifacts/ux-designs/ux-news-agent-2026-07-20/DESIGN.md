---
name: Midnight
status: final
updated: 2026-07-20
mockups: [mockups/midnight-digest.html]
colors:
  background: '#0b1020'
  surface: '#0b1020'
  surface-container: 'rgba(240,180,41,.055)'
  ink: '#eef2fb'
  ink-dim: '#a3adc4'
  ink-body: '#cfd7e8'
  ink-heading: '#ffffff'
  gold: '#f0b429'
  gold-soft: 'rgba(240,180,41,.9)'
  gold-border: 'rgba(240,180,41,.22)'
  gold-border-strong: 'rgba(240,180,41,.4)'
  divider: 'rgba(255,255,255,.07)'
  tag-ai: '#4ade80' # ~7.1:1
  tag-cybersecurity: '#f87171' # ~4.5:1
  tag-space: '#818cf8' # ~5.0:1
  tag-default: '#94a3b8' # ~6.5:1
typography:
  kicker:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 11px
    fontWeight: '700'
    lineHeight: '1.4'
    letterSpacing: 5px
    textTransform: uppercase
    color: '{colors.gold}'
  masthead-title:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 38px
    fontWeight: '900'
    lineHeight: '1.1'
    letterSpacing: -0.5px
    color: '{colors.ink-heading}'
  meta:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 12.5px
    fontWeight: '400'
    lineHeight: '1.4'
    letterSpacing: 0.3px
    color: '{colors.ink-dim}'
  intro:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 19px
    fontWeight: '500'
    lineHeight: '1.7'
    color: '#d7deef'
  scan-heading:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 11px
    fontWeight: '700'
    lineHeight: '1.4'
    letterSpacing: 2px
    textTransform: uppercase
    color: '{colors.gold}'
  scan-item:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 14.5px
    fontWeight: '400'
    lineHeight: '1.5'
    color: '#dbe2f2'
  article-headline:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 24px
    fontWeight: '800'
    lineHeight: '1.35'
    letterSpacing: -0.2px
    color: '{colors.ink-heading}'
  article-tag:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 10px
    fontWeight: '700'
    lineHeight: '1.3'
    letterSpacing: 1.5px
    textTransform: uppercase
  article-bullet:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.7'
    color: '{colors.ink-body}'
  article-source:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.4'
    color: '#7a85a0'
  fortune-kicker:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 11px
    fontWeight: '700'
    lineHeight: '1.4'
    letterSpacing: 3px
    textTransform: uppercase
    color: '{colors.gold}'
  fortune-punchline:
    fontFamily: "'Gveret Levin', 'Rubik', 'Segoe UI', cursive, sans-serif"
    fontSize: 26px
    fontWeight: '400'
    lineHeight: '1.55'
    color: '#fde9c7'
  footer:
    fontFamily: "'Rubik', 'Segoe UI', Arial, sans-serif"
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.6'
    color: '{colors.ink-dim}'
rounded:
  card: 16px
  inner-box: 12px
  pill: 20px
  fortune-card: 18px
spacing:
  frame-width: 600px
  card-padding-h: 32px
  section-padding-v: 24px
  gutter: 16px
components:
  masthead: '.head'
  kicker: '.kicker'
  personal-intro: '.intro'
  scan-block: '.scan'
  article-card: '.art'
  topic-tag: '.tag'
  divider: '.divider'
  fortune-corner: '.fortune'
  footer: '.foot'
---

## Brand & Style

Midnight is a dark, premium, nightly-briefing aesthetic - the visual voice of someone who stayed up reading the wires so you don't have to, and is handing you a clean, considered debrief over coffee. It reads as a late-night newsroom terminal crossed with a boutique newsletter: deep navy canvas, near-white ink, and a single restrained gold accent used the way a broadsheet uses a masthead rule - sparingly, to mark structure, never to decorate.

This is an **HTML email**, not a web or app surface. Every visual decision is constrained by email-client rendering: inline CSS in the production Jinja2 template (this mockup's `<style>` block is a build-time convenience only), no JavaScript, no animation, and full-width degradation testing against Outlook desktop, which ignores `@font-face`/`@import` web fonts entirely. The design must look intentional even when every font falls back to a system sans-serif. Content is Hebrew, right-to-left, in a fixed 600px column.

An earlier direction, "Broadsheet" (light editorial, ink+red accent, serif drop-cap, scratch-ticket קינוח), was built and rejected - see Do's and Don'ts. Midnight is the sole chosen direction; do not reintroduce Broadsheet's light/newspaper visual language.

The chosen direction is realized in [`mockups/midnight-digest.html`](mockups/midnight-digest.html) (user-approved). Where this spine and the mockup disagree, **this spine wins** - the mockup uses a `<style>` block and a bespoke `#dc2626`/`#475569` tag palette that predate the accessibility corrections recorded in Colors below; the production Jinja template follows this spine, not the mockup, on those points.

## Colors

| Token | Value | Use |
|---|---|---|
| `colors.background` | `#0b1020` | Email body canvas and card surface (deep night navy) |
| `colors.ink` | `#eef2fb` | Primary near-white text |
| `colors.ink-dim` | `#a3adc4` | De-emphasized meta text (date, reading time) |
| `colors.ink-body` | `#cfd7e8` | Bullet body copy |
| `colors.ink-heading` | `#ffffff` | Headlines (masthead title, article headline) |
| `colors.gold` | `#f0b429` | Kickers, dividers, tag/border accents, links |
| `colors.gold-soft` | `rgba(240,180,41,.9)` | Softer gold for large-area accents (orb glow) |
| `colors.gold-border` | `rgba(240,180,41,.22)` | Masthead bottom border |
| `colors.gold-border-strong` | `rgba(240,180,41,.4)` | קינוח card border |
| `colors.divider` | `rgba(255,255,255,.07)` | Hairline separators (source line, footer top border) |
| `colors.tag-ai` | `#4ade80` | AI (בינה מלאכותית) topic tag |
| `colors.tag-cybersecurity` | `#f87171` | Cybersecurity (סייבר) topic tag |
| `colors.tag-space` | `#818cf8` | Space (חלל) topic tag |
| `colors.tag-default` | `#94a3b8` | Fallback slate tag for any topic not in the fixed map |

The gold accent is a **premium accent, not a primary color**: it never fills a large area. It appears only as text color on kickers/labels, 1px borders, the inter-card divider gradient, and small glyphs (bullet dash, tag border). Topic tag colors are a fixed per-topic palette that must stay consistent everywhere the topic appears in the product, not just in this email.

**Every color token used as text color must clear WCAG AA contrast (4.5:1 normal text, 3:1 for 18px+/14px-bold+) against whatever background it sits on** - this table's original `tag-cybersecurity` (`#dc2626`, ~3.9:1) and `tag-default` (`#475569`, ~2.5:1) both failed this against `colors.background` and were corrected to the values above; `typography.footer`'s color was likewise moved off a bespoke `#6b7590` (~4.1:1) onto the already-passing `colors.ink-dim` (~8.4:1) rather than inventing a new near-miss shade. Any future palette change must re-verify every text/background pair in this table, not spot-check one.

## Typography

All UI and body text is set in **Rubik** (Google Fonts, weights 400–900), with a literal fallback stack of `'Rubik', 'Segoe UI', Arial, sans-serif`. This is a deliberate reversal of an earlier choice: the direction originally paired a serif display face (Frank Ruhl Libre) with Heebo for body, but the user found the serif hard to read (`קשה לי לקרוא`) - Rubik now carries both display and body roles, distinguished only by weight (800–900 for headlines, 400–500 for body).

The single exception is the קינוח (dessert/joke-corner) punchline, set in **Gveret Levin** (Google Fonts, exact family name `Gveret Levin` - not `Gveret Levin AlefAlefAlef`), a decorative handwriting face used only for that one line of text, at `{typography.fortune-punchline}` (26px/400). Its fallback stack is `'Gveret Levin', 'Rubik', 'Segoe UI', cursive, sans-serif` - this is load-bearing, not cosmetic: Outlook desktop and many mobile mail clients block external font loading entirely, and the punchline must degrade to readable Rubik rather than tofu or a broken glyph.

Heading weights run 800 (article headline) to 900 (masthead title); body and meta text run 400–500. Kickers and section labels use uppercase with wide letter-spacing (2–5px) at 10–11px to read as structural labels, not body copy.

## Layout & Spacing

Fixed-width 600px column (`{spacing.frame-width}`), centered, RTL. Horizontal card padding is 32px (`{spacing.card-padding-h}`); vertical rhythm between major sections is roughly 20–28px. The whole email is a single rounded card (`{rounded.card}` = 16px) sitting on a slightly lighter page background, with a soft ambient shadow (see Elevation) rather than a hard outline.

Because this renders inside email clients, layout must be table-safe in production (the Jinja2 template implementation uses inline styles / table structure, not the `<style>` block shown in the mockup) and tolerate clients that strip `border-radius` or `box-shadow` gracefully - the design should still read correctly as flat rectangles with visible borders/dividers if rounding or shadow is dropped.

## Elevation & Depth

Depth is minimal and atmospheric, not skeuomorphic: a single diffused drop shadow under the whole email card (`0 24px 50px -12px rgba(0,0,0,.5)`) separates it from the page background. Inside the card, sections are distinguished by hairline borders (`{colors.divider}`, `{colors.gold-border}`) rather than nested shadows. The one exception is the קינוח card, which uses an `inset` glow (`inset 0 0 50px rgba(240,180,41,.1)`) to suggest the orb is casting light onto its own container - this inset glow is unique to that component and should not be reused elsewhere.

## Shapes

| Token | Value | Use |
|---|---|---|
| `rounded.card` | 16px | Outer email card |
| `rounded.fortune-card` | 18px | קינוח container |
| `rounded.inner-box` | 12px | 30-second scan block |
| `rounded.pill` | 20px | Topic tags (fully rounded pill) |

Corners are soft throughout - nothing sharp, nothing pill-shaped except tags. The orb in the קינוח is the one fully circular (`border-radius:50%`) element in the system, reserved for that single signature moment.

## Components

**Masthead (`{components.masthead}`)** - kicker label ("תדרוך יומי"), masthead title (38px/900, e.g. "חדשות הבוקר"), meta line (weekday · Hebrew-month Gregorian date · total reading time), bottom border in `{colors.gold-border}`.

**Personal intro line (`{components.personal-intro}`)** - one warm, LLM-generated sentence directly under the masthead, set at 19px/500 in a slightly softened ink (`#d7deef`), sitting between masthead and scan block.

**30-second scan block (`{components.scan-block}`)** - a distinct bordered/tinted callout (`rgba(240,180,41,.055)` fill, `{colors.gold-border-strong}`-adjacent border at `.28` alpha, `{rounded.inner-box}` corners) listing every included article's headline in one line each, gold kicker label, bold gold lead-in per line, hairline dividers between rows. This is a summary component, distinct from and preceding the article cards.

**Article card (`{components.article-card}`)** - topic tag pill (colored border + colored text, transparent background, `{rounded.pill}`) → headline (`{typography.article-headline}`) → up to 3 bullets, each prefixed with a gold em-dash marker, keyword phrases bolded white via `<strong>` → source line (outlet name · reading time · "למקור" link in gold) above a hairline top border.

**Divider (`{components.divider}`)** - 1px horizontal line, gradient `transparent → rgba(240,180,41,.3) → transparent`, placed between article cards only.

**קינוח / fortune corner (`{components.fortune-corner}`)** - **the signature component of this design.** A "magic 8-ball fortune" card: radial-gradient background sweeping from navy-blue (`#22305a`) at the top to the base background (`#0b1020`) by 72%, a `{colors.gold-border-strong}` 1px border, and an inset gold glow. Inside: a gold uppercase kicker ("✨ קינוח · הכדור הקסום של החדשות"), a 74px circular glowing orb (radial gold-to-brown gradient, outer gold glow shadow, inner dark shadow for sphere depth, centered 🔮 emoji), and the punchline text in Gveret Levin (or its Rubik fallback). This component carries the entire "surprising / delightful" personality of the email; every other component is deliberately restrained so this one can stand out. **The punchline must stay to one short sentence (~10–12 words / ~60 characters):** Gveret Levin is a connected handwriting face, and the same legibility risk that got Frank Ruhl Libre rejected applies to it at length - short is what keeps it charming instead of straining.

**Footer (`{components.footer}`)** - small, dim, warm microcopy with a preferences link, above a hairline top border.

## Do's and Don'ts

**Do**
- Use Rubik for every piece of text except the קינוח punchline.
- Keep the gold accent restrained: borders, dividers, kickers, small accents - never a large fill area.
- Always specify non-web-font fallbacks literally (e.g. `'Rubik', 'Segoe UI', Arial, sans-serif`) since Outlook and many mobile clients block `@import`/`@font-face`.
- Keep topic tag colors consistent for a given topic everywhere in the product, not only in this email.
- Escape all LLM-provided bullet/keyword text (`html.escape`) before converting `**markdown**` to `<strong>` - the content pipeline output must never be trusted as raw HTML (XSS risk).

**Don't**
- Don't drift toward the light "Broadsheet" look (cream background, ink+red accent, serif drop-cap, newspaper double-rule) - that direction was explicitly built, compared, and rejected for this product.
- Don't reintroduce Frank Ruhl Libre (or any serif display face) - it was tried and explicitly rejected by the user as hard to read.
- Don't let the gold accent dominate the layout - it is a premium accent color, not a primary brand color.
- Don't render provider-generated bullet or keyword content as raw HTML under any circumstances.
