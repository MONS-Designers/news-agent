---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - "conversation: launch-readiness scope decision, 2026-08-07 (authoritative)"
  - _bmad-output/planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-news-agent-2026-07-21/EXPERIENCE.md
  - _bmad-output/implementation-artifacts/deferred-work.md
  - "GitHub issues: #9, #19, #30, #36, #37"
  - "codebase (src/newsagent, frontend/src) read directly"
---

# news-agent - Launch Readiness Epic Breakdown

## Overview

This document covers the work between the current build and a **friends-scale launch** —
roughly ten self-registered users, technical and non-technical, receiving a weekly Hebrew
digest they judge on content quality alone.

It is a **companion to `epics.md`**, not a replacement. `epics.md` owns Epic 1
(Profile-Based Topic Suggestions) and Epic 2 (Admin Taxonomy Curation), both shipped; its
`FR1`–`FR10` belong to that feature and are unrelated to the `FR`s numbered here.

### Why the requirements are not extracted from the PRD

`prds/prd-news-agent-2026-07-21/prd.md` and `ARCHITECTURE-SPINE.md` are both scoped, in
their own frontmatter, to *Profile-Based Topic Suggestions*. Neither covers registration,
email delivery, article-text extraction, ranking diversity, or cost accounting. Requirements
here are therefore sourced from the 2026-08-07 scope decision, the open GitHub issues, the
deferred-work log, and direct reading of the code. Only the Spine's **cross-cutting**
invariants (`AD-1`, `AD-4`) are carried in, because they govern anything built in this repo.

### The audience change that drives this epic

The MVP was specified for **2 seeded dogfood users**. The actual target is now **friends —
technical and non-technical — who want fast, simple signup and content that matches their
interests**. This resolves, in favour of the original idea document, the "Known drift to
resolve" that `CLAUDE.md` has carried since 2026-07-17: self-registration is in, seeded-only
is out.

## Requirements Inventory

### Functional Requirements

FR1: A visitor whose email matches no existing `Admin` or `User` row can sign in with Google and have a `User` row created automatically on first successful authentication, with no admin action and no separate registration form.
FR2: Self-registration is capped at a configurable maximum number of users (10 at launch). Once the cap is reached, a first-time sign-in is refused; users who already have an account are never affected by the cap.
FR3: The cap check and the user-row insert are atomic — two concurrent first-time sign-ins can never both pass the check and push the total past the cap.
FR4: The pipeline can deliver a digest through a real email provider selected by the existing `NEWSAGENT_EMAIL_SENDER` configuration value, with no change to `pipeline/send.py` or any other pipeline module.
FR5: For an article that has already passed relevance filtering, the system fetches the source page and extracts the full article text, storing it in the existing `Article.full_text` column before the summarize stage runs.
FR6: Full-text extraction failure is non-fatal: the article keeps a null `full_text`, `summarize` falls back to `rss_summary` exactly as it does today, and the run continues.
FR7: Digest selection guarantees at least one slot per subscribed topic that has any eligible candidate, filling the remaining slots by `final_score` as it does today.
FR8: An article whose summarize call fails is retried a bounded number of times and then reaches a terminal state, after which it is never selected for summarization again.
FR9: Token usage for every LLM call is recorded per pipeline run and is readable after the run without re-reading raw logs.
FR10: Topic-suggestion computation runs its two independent LLM calls concurrently rather than sequentially.
FR11: A visitor who authenticates with Google after the cap is full has their email (and any name Google provides) captured in a waitlist, rather than being shown a message with nothing recorded. Added 2026-08-07 — Nomi rejected a message-only capacity screen as "letting them log in for free with nothing to show for it."

### NonFunctional Requirements

NFR1: The profile picker is fully usable on a phone viewport (320px and up) — layout, touch targets, and every affordance that is hover-only today.
NFR2: Topic suggestions are ready within 8 seconds for a typical first-run profile. This is the abandonment threshold the scope decision set, not a stretch goal.
NFR3: Full-text extraction must not silently multiply LLM spend: extracted text is length-capped before it reaches a prompt, and FR9's accounting must be in place before extraction ships.
NFR4: Opening registration exposes the app to anyone with the link. No unauthenticated route may create rows, and the cap is the only admission control at launch — this is accepted deliberately, not overlooked.
NFR5: Email-provider credentials are read from configuration only, never logged and never committed (extends `#17`'s rule to the new adapter).
NFR6: Full-text fetching must respect the source site — a per-request timeout, a bounded number of concurrent fetches, and a real user agent — so a pipeline run can neither hang nor look like a scraper.

### Additional Requirements

- `AD-1` (Spine) — thin-router / domain-service layering: routers validate and delegate, services own business rules and idempotency, services raise `ValueError` and routers translate to `HTTPException`. Applies to the registration path and the user-cap check.
- `AD-4` (Spine) — every schema change ships as a new Alembic revision. Applies to the summarize terminal-state column and to any usage-accounting table.
- `mail/base.py` already defines the `EmailSender` ABC and `EmailSendError`; `mail/factory.py` selects by config and currently raises for anything but `console`. FR4 is a new adapter plus one factory branch — the pipeline contract is already correct and must not change.
- `api/auth.py::resolve_identity` returns `None` for any email with no `Admin`/`User` row, and the caller rejects the login. This is the single change point for FR1, and it inverts a deliberate original decision: OAuth authenticates but never creates.
- `models/article.py` already has a `full_text` column and `pipeline/summarize.py:63` already reads `article.full_text or article.rss_summary or article.title`. Nothing populates `full_text` today, so the fallback is always taken. FR5 fills an existing, already-wired seam.
- `pipeline/relevance.py:81` reads `article.rss_summary or article.title` and does **not** consult `full_text`. This is correct and must stay: extraction runs after relevance, so relevance necessarily judges on the snippet. [OPEN] — see Open Questions.
- The LLM base class already exposes `_record_usage`, and reports already carry `usage_input_units` / `usage_output_units`. FR9 is persistence and reporting, not new instrumentation.
- The select-then-insert TOCTOU pattern is already documented three times in `deferred-work.md` (`add_topic`, `add_field`, `add_source`). FR3 makes it reachable from the open internet for the first time, which is why FR3 states atomicity rather than inheriting the existing pattern.
- `services/profile.py::_compute_and_store_suggestions` is being changed under `GH #36` in a parallel work stream, including a new `pending_slow` suggestion status. FR10 must be reconciled with that work rather than duplicating it.

### UX Design Requirements

UX-DR1: Responsive breakpoint behavior for the Field/Role chip rows and the Topic pill grid below 640px, including verified flex-wrap behavior down to 320px (`EXPERIENCE.md` § Responsive & Platform is currently unspecified here).
UX-DR2: Touch equivalents for every hover-only affordance in the picker — chip, topic-pill, and button lift-and-brighten states have no defined touch behavior.
UX-DR3: Decide and implement the parallax behavior on touch devices: the mouse-position half of the background-orb parallax is meaningless without a pointer, and blur-heavy fixed backgrounds carry unverified mobile GPU cost.
UX-DR4: Resolve whether the picker follows `PreferencesView.vue`'s existing Tailwind responsive convention (`sm:flex-row` and similar) or defines its own breakpoints — one convention, decided explicitly.
UX-DR5: A "capacity reached" screen for a visitor who authenticates with Google after the user cap is full, which also confirms their email was captured to a waitlist (FR11) — not a dead-end message with nothing recorded.
UX-DR6: A first-run state for a freshly self-registered user, who lands with no profile, no topics, and no digest history — distinct from the returning-user summary that `HomeView.vue` shows today.
UX-DR7: Touch-target sizing across the picker meets a minimum tap area, alongside the semantic-control work already tracked as `#31`.

### Open Questions

- **OQ1 — What does user #11 see? RESOLVED 2026-08-07.** A message-only capacity screen was rejected: "אין טעם לאפשר למשתמש לבצע לוגין לחינם, אלא אם כן ניתן להכניס אותו לרשימת המתנה" — if the login can't result in an account, it must at least result in a captured waitlist entry. `FR11` added. Admin visibility into the waitlist (a list view, a manual promote-from-waitlist action) is deliberately deferred as a fast-follow, not built in this epic — DB storage only for launch.
- **OQ2 — Does relevance ever get the full text?** Extraction currently must run after relevance filtering, precisely so full-text fetching is limited to articles worth fetching. That means relevance is permanently judged on an RSS snippet — sometimes on a headline alone. Accepted for this epic, but it caps how good relevance can get, and a future re-score pass after extraction is the obvious lever.
- **OQ3 — Is the 8s budget met by concurrency alone?** `#36` measures the two calls at ~11.4s and ~14.0s, both against `LOCAL_LLM_BASE_URL` pointed at a remote OpenRouter model (`local` names a config, not a physical machine — see AD-3). Concurrency alone yields ~14s, still above NFR2's 8 seconds. **RESOLVED for this epic (2026-08-07):** self-hosted-on-own-hardware inference is deliberately deferred to a later stage — it mainly removes the network hop, not the compute time, and needs its own hardware/ops decision this epic doesn't own. NFR2 must be met within this epic by the levers that don't wait on hardware: a smaller/faster model on the existing remote provider, prompt/context trimming, and/or partial rendering (surface Role suggestions as soon as they arrive instead of blocking on both calls).

### FR Coverage Map

FR1: Epic A - Self-registration creates a User row on first Google sign-in
FR2: Epic A - Registration hard-capped at 10 users
FR3: Epic A - Cap check + insert are atomic
FR4: Epic B - Real email sender adapter
FR5: Epic D - Full-text extraction for relevance-passed articles
FR6: Epic D - Non-fatal extraction failure, falls back to rss_summary
FR7: Epic D - Topic-diversity floor in digest selection
FR8: Epic C - Terminal state for deterministically-failing summarize
FR9: Epic C - Per-run LLM token usage accounting
FR10: Epic E - Concurrent suggestion-source calls (tracks GH #36, in flight)
FR11: Epic A - Waitlist capture when the cap is full

NFR1: Epic E - Profile picker usable at 320px+
NFR2: Epic E - Topic suggestions ready within 8s
NFR3: Epic D - Extraction spend bounded; depends on Epic C's usage accounting
NFR4: Epic A - Open registration is deliberate, cap is the only gate
NFR5: Epic B - Email credentials from config only
NFR6: Epic D - Full-text fetch is polite (timeout, concurrency cap, real UA)

UX-DR1: Epic E - Chip/pill breakpoint behavior below 640px, verified to 320px
UX-DR2: Epic E - Touch equivalents for hover-only affordances
UX-DR3: Epic E - Touch-device parallax behavior decided
UX-DR4: Epic E - One responsive convention for the picker, decided explicitly
UX-DR5: Epic A - Capacity-reached state after Google sign-in, confirms waitlist capture
UX-DR6: Epic A - First-run state for a freshly self-registered user
UX-DR7: Epic E - Touch-target sizing across the picker

## Epic List

### Epic E: The wizard works on a phone and doesn't make you wait
Any visitor — not just desktop users — can complete the Field/Role/Experience/Topics
picker on a phone from 320px up, with real touch equivalents for every hover-only
affordance, and see Topic suggestions inside 8 seconds. Concurrent suggestion-source
calls (tracked in GH #36, already in flight in a parallel work stream) are verified and
integrated here rather than rebuilt. No dependency on any other epic in this document —
runs first per the approved build order.
**Covers:** FR10, NFR1, NFR2, UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR7

### Epic A: Any friend can get in
A visitor with no seeded account can sign in with Google and land with a working
account immediately — no admin step, no separate registration form. Registration is
open but hard-capped at 10 total users; a visitor arriving after the cap is full is
captured to a waitlist rather than shown a dead-end message, and a freshly-created user
sees a first-run state instead of the returning-user summary. Standalone: touches only
the auth path, one new table, and two new UI states. Admin visibility into the waitlist
is a deliberate fast-follow, not built here.
**Covers:** FR1, FR2, FR3, FR11, NFR4, UX-DR5, UX-DR6

### Epic B: The digest actually lands in an inbox
A user's weekly digest is delivered through a real email provider, configured the same
way every other swappable adapter in this codebase is configured — no code change
outside `mail/`. Standalone: one new adapter class plus one factory branch.
**Covers:** FR4, NFR5

### Epic C: The pipeline stops paying for what already failed
An article whose summarize call fails deterministically is retried a bounded number of
times, then reaches a terminal state and is never billed for again. Every pipeline run's
token usage is recorded and readable without grepping raw logs. Not directly
user-facing, but it is what keeps the product affordable to keep running once friends
start joining. Standalone: `pipeline/summarize.py` plus a new usage-reporting path.
Must land before Epic D, which is the first feature that meaningfully increases LLM
spend per article.
**Covers:** FR8, FR9

### Epic D: Every digest is worth reading
Summaries are written from the actual article, not a headline — full article text is
fetched and extracted for any article that already passed relevance filtering, with a
non-fatal fallback to today's RSS-snippet behavior on failure. Digest selection
guarantees at least one slot per subscribed topic that has an eligible candidate, so a
high-volume topic can no longer take every slot in a week. Depends on Epic C: NFR3
requires usage accounting to exist before extraction can ship, so this epic cannot start
before Epic C is done.
**Covers:** FR5, FR6, FR7, NFR3, NFR6

**Approved build order:** E → A → B → C → D. This is one deliberate change from the
build order approved earlier in conversation (which had Epic D's #9 before Epic C's
#19) — corrected per NFR3, approved 2026-08-07.

## Epic E: The wizard works on a phone and doesn't make you wait

Any visitor — not just desktop users — can complete the Field/Role/Experience/Topics
picker on a phone from 320px up, with real touch equivalents for every hover-only
affordance, and see Topic suggestions inside 8 seconds. Concurrent suggestion-source
calls (tracked in GH #36, already in flight in a parallel work stream) are verified and
integrated here rather than rebuilt. No dependency on any other epic — runs first per
the approved build order.

### Story E.1: Responsive breakpoints for the profile picker

As a visitor completing the profile picker on my phone,
I want the Field, Role, and Topic selections to lay out correctly at my screen width,
So that I can complete setup without pinch-zooming or fighting overflow.

**Acceptance Criteria:**

**Given** the picker is open at a viewport width of 320px
**When** I view the Field or Role chip row
**Then** the chips wrap onto multiple lines with no horizontal overflow and no text truncation

**Given** the picker is open at a viewport width of 320px
**When** I view the Topic pill grid in Step 3
**Then** all picked and faint pills are visible without horizontal scrolling

**Given** the app already uses `PreferencesView.vue`'s Tailwind responsive convention (e.g. `sm:flex-row`) elsewhere
**When** breakpoints are added to the picker
**Then** the same convention is used rather than a second, bespoke breakpoint system (UX-DR4)

**Given** the viewport is resized from desktop to 320px while a step is open
**When** the resize completes
**Then** no selected/picked state is lost and the currently active step remains the same

### Story E.2: Touch equivalents for hover-only interactions

As a visitor using the picker on a touchscreen,
I want every chip, pill, and button to respond correctly to a tap,
So that hover-only affordances don't leave me unable to select or see feedback.

**Acceptance Criteria:**

**Given** a chip currently shows a hover lift-and-brighten effect on desktop
**When** the same chip is tapped on a touch device
**Then** the selected/pressed state is visibly and immediately reflected without requiring hover

**Given** any interactive control in the picker (chip, topic pill, Continue/Back button)
**When** measured on a touch viewport
**Then** its tap target is at least 44x44 CSS pixels (UX-DR7)

**Given** a user taps a control and lifts their finger
**When** the tap completes
**Then** no residual `:hover` style is stuck active (the common mobile Safari/Chrome sticky-hover bug)

### Story E.3: Touch-appropriate background behavior

As a visitor on a touch device,
I want the background depth effect to behave sensibly without a mouse,
So that the page doesn't feel broken or waste battery on effects that can't render as intended.

**Acceptance Criteria:**

**Given** the picker's background uses mouse-position parallax on desktop
**When** viewed on a touch device with no persistent pointer
**Then** the mouse-position half of the parallax is disabled and only scroll-position parallax (if any) applies

**Given** the background renders 3 blurred glow orbs plus a dot-grain overlay
**When** measured on a mid-tier mobile device
**Then** frame rate does not visibly drop during scroll (spot-checked, not benchmarked)

### Story E.4: Topic suggestions ready within 8 seconds

As a user who just saved their profile,
I want Step 3's suggestions to be ready quickly,
So that I don't abandon the wizard while waiting.

**Acceptance Criteria:**

**Given** GH #36's concurrent suggestion-source calls have landed
**When** a user saves their profile
**Then** `suggest_topics` and `suggest_new_topics` run concurrently, not sequentially

**Given** even concurrent calls measure close to the slower of the two (~14s per GH #36's measurement)
**When** the combined time exceeds the 8s budget
**Then** at least one additional latency lever from OQ3's resolution (a smaller/faster model dedicated to this call, a trimmed prompt/context, or partial rendering of whichever result arrives first) is applied until typical first-run latency is under 8 seconds

**Given** suggestion computation still exceeds a reasonable ceiling despite the above
**When** the existing `pending_slow` status (from the parallel GH #36 work) is reached
**Then** the frontend shows that state rather than appearing frozen or silently falling back

**Given** a user profile with no prior suggestion history
**When** end-to-end latency (save to ready) is measured across at least 5 manual runs
**Then** the observed latency is documented in the story's implementation notes as evidence NFR2 is met

## Epic A: Any friend can get in

A visitor with no seeded account can sign in with Google and land with a working
account immediately — no admin step, no separate registration form. Registration is
open but hard-capped at 10 total users; a visitor arriving after the cap is full is
captured to a waitlist rather than shown a dead-end message, and a freshly-created user
sees a first-run state instead of the returning-user summary. Standalone: touches only
the auth path, one new table, and two new UI states. Admin visibility into the waitlist
is a deliberate fast-follow, not built here.

### Story A.1: Self-registration with an atomic 10-user cap

As a friend with no existing account,
I want to sign in with Google and get a working account immediately,
So that I don't need Nomi to manually add me before I can use the product.

**Acceptance Criteria:**

**Given** I authenticate successfully with Google using an email that matches no existing `Admin` or `User` row
**And** the total `User` count is below the configured cap (10)
**When** `resolve_identity` runs
**Then** a new `User` row is created for my email and I land in the app as that user, with no separate registration form

**Given** I authenticate successfully with Google using an email that matches no existing `Admin` or `User` row
**And** the total `User` count has already reached the cap
**When** `resolve_identity` runs
**Then** no `User` row is created and I am not signed in as a user

**Given** two visitors authenticate with Google at the same moment when exactly 1 slot remains under the cap
**When** both requests race to create their `User` row
**Then** exactly one of them succeeds and the other is treated as arriving after the cap was full — never both, never neither (FR3's atomicity, enforced at the DB level, not by an application-level count check)

**Given** an email that already matches an existing `Admin` or `User` row
**When** that email signs in
**Then** existing sign-in behavior is unchanged — the cap and the create-on-first-sign-in logic never apply to it

**Given** the cap value
**When** it needs to change
**Then** it is read from configuration (a new `NEWSAGENT_*` setting), not hardcoded

**Given** an unauthenticated request to any route
**When** it is made
**Then** no `User` row can be created — row creation happens only inside `resolve_identity`, reached only from a successful Google auth callback, never from any other code path (NFR4's "the cap is the only admission control" holds only if nothing else can create a row)

### Story A.2: Waitlist capture when the cap is full

As a visitor who arrives after the cap is full,
I want my registration attempt to leave a real trace,
So that there's a chance I get invited when a slot opens up.

**Acceptance Criteria:**

**Given** I authenticate successfully with Google after the cap is already full
**When** the sign-in completes
**Then** my email (and name, if Google provides one) is saved to a new waitlist table, with a timestamp

**Given** I attempted to register and was captured to the waitlist
**When** I view the result
**Then** I see a screen that plainly states capacity is full **and** that my email was saved for future priority — not a generic error, not a blank page

**Given** I already exist on the waitlist
**When** I try to sign in again
**Then** no duplicate waitlist row is created for the same email — the timestamp updates instead

**Given** the waitlist is stored in the DB
**When** this epic is done
**Then** there is no admin screen to view it — that is a declared fast-follow, not a forgotten gap

### Story A.3: First-run state for a freshly self-registered user

As a user who just created my account by signing in,
I want the home page to guide me into setting up my profile,
So that I'm not looking at a blank returning-user summary with no history to summarize.

**Acceptance Criteria:**

**Given** I am a `User` with no saved profile (`field_name` not set) and no digest history
**When** I land on the home page after signing in
**Then** I see a first-run state that invites me to complete the profile picker, distinct from the returning-user summary `HomeView.vue` already shows for users with history

**Given** I complete the profile picker for the first time
**When** I return to the home page afterward
**Then** I no longer see the first-run state

## Epic B: The digest actually lands in an inbox

A user's weekly digest is delivered through a real email provider, configured the same
way every other swappable adapter in this codebase is configured — no code change
outside `mail/`. Standalone: one new adapter class plus one factory branch.

### Story B.1: Real email delivery adapter

As a user, I want my weekly digest delivered to my actual inbox,
So that the product works end-to-end instead of writing HTML to a local folder.

**Acceptance Criteria:**

**Given** `NEWSAGENT_EMAIL_SENDER` is set to the new provider's config value **[provider: TBD — Nomi to confirm before implementation]**
**When** `send_pending_digests` calls `sender.send(to, subject, html_body)`
**Then** the email is sent through the provider's API, implementing the existing `EmailSender` ABC exactly as-is, with no change to `pipeline/send.py` or any other pipeline module

**Given** the provider rejects a send (auth failure, invalid recipient, rate limit, transient 5xx)
**When** `send()` fails
**Then** it raises `EmailSendError` exactly as the ABC's docstring specifies, so `send_pending_digests`'s existing `report.failed` handling and retry-next-run behavior work unchanged

**Given** provider credentials
**When** the adapter is configured
**Then** they are read from configuration only (a new `NEWSAGENT_*` or provider-conventional env var), never hardcoded, never logged (NFR5)

**Given** the digest is Hebrew RTL HTML
**When** it's sent through the new adapter
**Then** rendering in a real inbox is manually verified at least once before this story is considered done (the exact gap GH #23 flags — this story closes it for the email-rendering slice only, not the full dogfood run)

**Given** the console sender remains available
**When** `NEWSAGENT_EMAIL_SENDER=console`
**Then** behavior is completely unchanged — the new adapter is additive, not a replacement of the existing dev path

## Epic C: The pipeline stops paying for what already failed

An article whose summarize call fails deterministically is retried a bounded number of
times, then reaches a terminal state and is never billed for again. Every pipeline run's
token usage is recorded and readable without grepping raw logs. Not directly
user-facing, but it is what keeps the product affordable to keep running once friends
start joining. Standalone: `pipeline/summarize.py` plus a new usage-reporting path.
Must land before Epic D, which is the first feature that meaningfully increases LLM
spend per article.

### Story C.1: Terminal state for deterministically-failing articles

As the operator running the pipeline,
I want an article that keeps failing to summarize to stop being retried forever,
So that a handful of bad articles don't burn LLM spend indefinitely.

**Acceptance Criteria:**

**Given** a new `summarize_attempts` integer column added to `Article` via an Alembic migration (AD-4), defaulting to 0 for every existing row
**When** the migration runs
**Then** no existing article's `summary_status` changes — this only adds the counter, and existing rows start fresh with it

**Given** an article's summarize call raises `LLMError`
**When** the `summarize` pipeline stage handles it
**Then** `summarize_attempts` increments by 1, in addition to today's existing `summary_status = "error"` handling

**Given** an article's `summarize_attempts` reaches a configured max (3, matching `LLMProvider`'s own internal retry default — consistency, not a separate justification)
**When** the failing attempt is recorded
**Then** `summary_status` is set to a new terminal value (`"failed"`) instead of `"error"`, and `_SUMMARIZABLE` no longer selects it on any future run

**Given** an article already in `summary_status = "failed"`
**When** any future `summarize` run executes
**Then** that article is not selected, not sent to the provider, and not billed for

**Given** an article that fails once or twice, then succeeds on a later run
**When** it succeeds
**Then** `summary_status` becomes `"summarized"` exactly as today; `summarize_attempts`'s value at that point is irrelevant since a summarized article is never re-selected anyway

**Given** the configured max-attempts value
**When** it needs to change
**Then** it is read from configuration (a new `NEWSAGENT_*` setting), not hardcoded

### Story C.2: Per-run LLM usage accounting

As the operator running the pipeline,
I want token usage from every LLM call recorded per run,
So that I can see spend without re-reading raw logs, especially before Epic D adds new LLM-adjacent cost.

**Acceptance Criteria:**

**Given** each pipeline stage that calls an LLM (`filter`, `summarize`, and any future stage) already computes `usage_input_units`/`usage_output_units` in its `Report`
**When** that stage's CLI command completes
**Then** a new row is persisted (stage name, provider, input units, output units, unit, timestamp) via a new Alembic-migrated table, in addition to the report already printed today

**Given** usage rows exist across multiple past runs
**When** the operator wants to see spend
**Then** a new CLI command (e.g. `python -m newsagent.cli usage-report`) prints a summary — total units per stage, and/or per day — without opening any log file

**Given** a stage's LLM calls partially fail (matching FR8's retries)
**When** usage is recorded
**Then** failed attempts' usage is included exactly as it already is in `provider.drain_usage()` today — no double-counting, no silent zero; this story persists what's already computed, it doesn't change the accounting mechanic itself

**Given** this table exists
**When** Epic D's full-text extraction ships next
**Then** it already gives visibility into whether extraction meaningfully raised spend per article — this is what makes Epic D buildable per the approved order

## Epic D: Every digest is worth reading

Summaries are written from the actual article, not a headline — full article text is
fetched and extracted for any article that already passed relevance filtering, with a
non-fatal fallback to today's RSS-snippet behavior on failure. Digest selection
guarantees at least one slot per subscribed topic that has an eligible candidate, so a
high-volume topic can no longer take every slot in a week. Depends on Epic C: NFR3
requires usage accounting to exist before extraction can ship, so this epic cannot start
before Epic C is done. Split into three stories rather than two after final validation
flagged the original D.1 as oversized (new dependency + fetch/parse/store/retry logic +
concurrency/timeout/politeness all in one story) — D.2 now carries the
networking-politeness concern on its own.

### Story D.1: Full-text extraction with a terminal failure state and a spend cap

As a user, I want the summary I receive to be written from the full article, not a headline,
So that the digest actually reflects what happened.

**Acceptance Criteria:**

**Given** new columns on `Article` — `extraction_status` (`pending`/`done`/`failed`, same shape as `relevance_status`/`summary_status`) and `extraction_attempts` (integer, default 0) — added via an Alembic migration
**When** the migration runs
**Then** existing articles start at `pending`/`0`, and no other status column changes

**Given** an article with `relevance_status == relevant` and `extraction_status == pending`
**When** the new `extract` CLI stage runs
**Then** the source page is fetched and parsed, and on success the extracted text — length-capped before it could ever reach a prompt (NFR3; cap value documented in the story's implementation notes) — is stored in `full_text`, and `extraction_status` becomes `done`

**Given** the fetch or extraction fails
**When** that happens
**Then** `extraction_attempts` increments, `full_text` stays null, and the run continues to the next article without aborting (FR6). Once `extraction_attempts` reaches a configured cap (2), `extraction_status` becomes `failed` and is never re-fetched again — the same pattern as Story C.1, applied here so this story doesn't reintroduce the exact endless-retry problem Epic C exists to fix

**Given** an article whose extraction never ran, or failed permanently
**When** `summarize` runs
**Then** the fallback to `rss_summary`/title is exactly what it is today — `summarize.py` itself is unchanged; this AC exists to catch a regression, not to add new behavior

**Given** this story introduces a new production dependency (e.g. `trafilatura`) to do the extraction
**When** implementation begins
**Then** that dependency is confirmed explicitly before it's added — flagged here so it isn't discovered mid-implementation

### Story D.2: Bounded, polite concurrent fetching

As the operator running the pipeline,
I want the extraction stage to fetch politely and predictably,
So that a pipeline run can't hang on one slow source or get an approved source's IP blocked for looking like a scraper.

**Acceptance Criteria:**

**Given** Story D.1's `extract` stage exists
**When** it fetches an article whose source is slow or unresponsive
**Then** a per-request timeout is enforced — a request that hangs past the timeout is treated as a failure, incrementing `extraction_attempts` exactly per D.1's existing mechanic

**Given** the `extract` stage processes many articles in one invocation
**When** it fetches sources
**Then** concurrent in-flight fetches are bounded to a configured limit — not fully serial, not unbounded

**Given** a request is sent to a source's site
**When** it's made
**Then** it carries a real, identifying User-Agent string, not a default/blank one that reads as an anonymous bot

**Given** the timeout, concurrency-limit, and User-Agent values
**When** they need to change
**Then** they are read from configuration, not hardcoded

### Story D.3: Topic-diversity floor in digest selection

As a user subscribed to multiple topics,
I want every topic I picked to get real representation,
So that one high-volume topic can't win every slot in my digest.

**Acceptance Criteria:**

**Given** a user subscribed to N topics, each with at least one eligible candidate article
**When** `select_top` runs with a limit L >= N
**Then** the result includes at least one article from each of the N topics

**Given** more topics with candidates than available slots (N > L)
**When** `select_top` runs
**Then** the guaranteed slots go to the topics ranked by their single best-scoring candidate — not by raw global score — until slots run out; any remaining slots are filled by global score among the leftover candidates

**Given** a subscribed topic has zero eligible candidates this run
**When** `select_top` runs
**Then** no slot is wasted trying to cover it — the guarantee applies only to topics that have something to show

**Given** a same-day rerun that already attached some articles to this digest (`digest.py`'s existing `already_attached` accounting)
**When** the rerun fills the remaining slots
**Then** the diversity floor is computed against topics not yet represented among the digest's already-attached articles — not recomputed from zero

**Given** all eligible candidates belong to a single topic (as in the existing fixtures in `test_ranking.py`, which default to `source_id=1`)
**When** `select_top` runs
**Then** behavior is identical to today's pure top-N-by-score selection, and the existing tests for that behavior continue to pass unchanged — a single topic gives the diversity floor nothing to do
