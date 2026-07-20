---
name: Midnight — Daily Digest Email
status: final
updated: 2026-07-20
---

# Midnight — Daily Digest Email — Experience Spine

> Issue #13. Single HTML email surface, RTL Hebrew, dark premium "nightly briefing" personality. Paired with `DESIGN.md` (Midnight) for all visual tokens.

## Foundation

The form factor is a single HTML email, not a live app UI — there is no client-side runtime, no interactivity beyond standard links, and no component library to inherit conventions from. It is rendered server-side by `src/newsagent/pipeline/render.py` from a Jinja2 template at `src/newsagent/templates/digest.html.j2` (visual reference: [`mockups/midnight-digest.html`](mockups/midnight-digest.html) — this spine and `DESIGN.md` win on any conflict), then delivered into and consumed entirely inside third-party email clients (Gmail, Outlook desktop/web, Apple Mail, mobile mail apps) whose CSS support varies widely. The "UI system" referenced throughout this spine is therefore a hand-rolled, email-safe HTML/CSS system (inline styles, table-safe layout) rather than a design-system library — every pattern below must survive being interpreted by the least capable client in that set.

## Information Architecture

Single-screen, fixed top-to-bottom order — there is no navigation, no secondary surface:

| Section | Component | Notes |
|---|---|---|
| 1. Masthead | `{DESIGN.components.masthead}` | Kicker, title, date/reading-time meta |
| 2. Personal intro line | `{DESIGN.components.personal-intro}` | LLM-generated per digest |
| 3. 30-second scan block | `{DESIGN.components.scan-block}` | All included headlines, one line each |
| 4. Article cards (up to 5) | `{DESIGN.components.article-card}` | Topic-diverse selection, separated by `{DESIGN.components.divider}` |
| 5. קינוח (dad-joke corner) | `{DESIGN.components.fortune-corner}` | Conditional — see State Patterns |
| 6. Footer | `{DESIGN.components.footer}` | Preferences link, warm microcopy |

Article selection today is a **placeholder ordering**: round-robin across the user's subscribed topics, filling to 5 so no single topic dominates a digest. This is temporary — issue #25 (weighted per-user ranking engine: relevance + recency + interest, personalized from open-tracking history) will replace it with a true weighted top-5. Nothing downstream of this spine should assume the current ordering is final.

## Voice and Tone

The product's voice is warm and personal — like a person curated this for you, not a generic content digest. Two pieces of copy are generated fresh per digest rather than templated:

- **Personal intro line** and **dad joke (קינוח punchline)** both come from a new LLM contract method, `compose_digest_voice(headlines) -> DigestVoice(intro_he, dad_joke_he)`, composed from that day's actual article headlines — never static boilerplate.
- **Footer microcopy** is warm and conversational by design, not administrative: "בוא נכוונן יחד" ("let's tune this together"), not a blunt "עדכון העדפות" ("update preferences").
- Mock/dev-provider content is visibly prefixed (`[דמה]` / `[תרגום דמה]`) so it's never mistaken for real provider output in lower environments; the real provider removes these markers entirely.

## Component Patterns

Behavioral rules only — visual specification lives in `DESIGN.md.Components`.

| Component | Behavior |
|---|---|
| Article card | Bullets are sourced from `Article.bullets_he` (up to 3). Each bullet is individually HTML-escaped, then `**markdown**` keyword spans are converted to `<strong>` server-side — the LLM output is never trusted or rendered as raw HTML. |
| Topic tag | Label + color resolved from a fixed per-topic map (AI, Cybersecurity, Space today). Any topic not in the map falls back to a neutral slate tag (`{DESIGN.colors.tag-default}`) showing the raw topic name — never an empty or broken tag. |
| קינוח corner | Renders only when **both** `intro_he` and `dad_joke_he` are present on the `Digest` row. Voice composition is best-effort: a provider refusal or error during `compose_digest_voice` leaves the digest without this section rather than failing the whole digest build. |
| Scan block | Populated from the same set of articles as the cards below it (see State Patterns for the known count mismatch). |

## State Patterns

| State | Trigger | Treatment |
|---|---|---|
| No joke | `compose_digest_voice` failed or refused | קינוח section is entirely absent — not rendered empty, no placeholder. |
| Single-topic digest | User subscribed to (or only has articles for) one topic | Round-robin diversity selection degrades gracefully to filling all 5 slots from that one topic. |
| Fewer than 5 articles | Fewer than 5 qualifying articles that day | Show only what exists — no padding or placeholder cards. |
| Reading time total | Always | Recalculated only from the articles actually displayed (the capped top-5), not the full undelivered candidate set. |

**Known temporary inconsistency** (flagged in the memlog, not a bug to silently fix): the personal intro line and dad joke are composed at build time from **all** of that day's headlines, while only 5 articles are shown at render time. This means the intro's implied article count can mismatch what the reader actually sees below it. This will resolve naturally once issue #25 unifies build-time ranking and render-time selection into a single top-5 pass — until then, it is an accepted, known gap.

## Interaction Primitives

This is a **read-only, non-interactive** HTML email: no JavaScript, no forms. The only interactive elements are standard links — the per-article source link, the footer preferences link, and the tracking-pixel image request (silent, records `opened_at`).

Note for future work: the קינוח's "surprising and interactive-looking" brief was explored in the rejected Broadsheet direction as a literal scratch-ticket/lottery-card texture (dashed border, foil-strip graphic, perforated edges — see `.working/directions.html`). The **chosen** Midnight direction achieves the same "surprising, interactive-looking" feeling through the glowing orb / fortune-telling visual metaphor instead — a static, image-like effect with no scratch interaction of any kind. Do not assume a literal scratch/reveal interaction exists anywhere in this design; there is none.

## Accessibility Floor

- Root `<html>` carries `dir="rtl" lang="he"` — the entire surface is Hebrew RTL.
- **Every color token used as text must meet or exceed WCAG AA — 4.5:1 for normal text, 3:1 for 18px+/14px-bold+ — against whatever background it renders on**, not just the primary body-text pair. This is not a nice-to-have: the user explicitly complained mid-session that the original serif treatment was hard to read (`קשה לי לקרוא`), which drove the font change (Frank Ruhl Libre → Rubik) and a deliberate contrast/line-height increase; body/bullet line-height must not drop below 1.5 (`{DESIGN.typography.article-bullet}` = 1.7). The accessibility review that followed found three other color pairs failing this same bar despite the primary pair passing comfortably — an implementer must check every pair in `DESIGN.md.Colors`, not spot-check one, and any future palette or type change must re-verify all of them.
- Font fallback stacks are an accessibility requirement, not cosmetic polish: Gveret Levin degrading to Rubik (`{DESIGN.typography.fortune-punchline}`) must never produce tofu boxes or missing glyphs in clients that block external font loading (Outlook desktop, many mobile mail apps). Separately, the punchline length cap (~60 characters, see `DESIGN.md.Components`) exists because the decorative face carries its own legibility risk even when it *does* load.
- Every article's source name and reading time must remain in plain text — never conveyed by color alone.
- English brand/source names and inline Latin fragments embedded in Hebrew copy (e.g. "TechCrunch AI", "40%") must be wrapped in `<bdi>` (or `dir="ltr"` span) in the Jinja template, so mixed-direction runs don't reorder unpredictably next to adjacent Hebrew punctuation and numerals.
- Masthead title, scan-block label, and each article headline must use real heading tags (`<h1>` for the masthead title, `<h2>` for the scan-block label and each article headline) rather than styled `<div>`s, so screen-reader users can navigate the email by heading landmarks.
- The tracking-pixel `<img>` must carry `alt=""` — it conveys no content and must never be announced as a meaningless image.

## Key Flows

### Flow 1 — Sunday morning scan (Noam, phone, first coffee)

1. Noam opens the digest email on his phone, half-awake, expecting the usual noise.
2. The masthead and personal intro line greet him by name — the first line already tells him something specific happened overnight in AI, not a generic "here's your news."
3. He skims the 30-second scan block, three headlines deep, checking for anything urgent before he commits to reading further.
4. Nothing's on fire. He relaxes into the AI article card, its bolded key phrases letting him read the shape of the story without reading every word, then does the same for the Space card.
5. He scrolls past the footer's edge and hits the glowing orb — unexpected, out of place with everything serious above it.
6. **Climax:** he reads the dad joke. It's actually about last night's AI headline, so it lands as a wink from whoever curated this, not a canned filler. He smiles — the small proof that a person (or something that feels like one) was behind this, not a template.
7. He taps through to the source article on OpenAI's pricing drop, or simply closes the email — either way, the tracking pixel silently records that he opened it, feeding tomorrow's personalization (issue #25) so the next digest leans slightly more toward what actually held his attention today.

Failure branch: if `compose_digest_voice` failed to produce a joke that morning, step 5–6 simply doesn't happen — the email ends cleanly at the footer, and Noam never knows a joke was supposed to be there.
