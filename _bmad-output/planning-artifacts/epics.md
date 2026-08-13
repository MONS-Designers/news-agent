---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md
  - _bmad-output/planning-artifacts/prds/prd-news-agent-2026-07-21/addendum.md
  - _bmad-output/planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-news-agent-2026-07-21/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-news-agent-2026-07-21/EXPERIENCE.md
---

# news-agent - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for news-agent's Profile-Based Topic Suggestions feature, decomposing the requirements from the PRD, UX Design spec ("Hybrid Depth"), and Architecture Spine into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can select one Field from an admin-curated list, or choose "Other" and enter free text; "Other" submissions queue as a Pending Taxonomy Suggestion for admin review.
FR2: After selecting a Field, user can select one Role from Suggestion-Source-generated options scoped to that Field, or choose "Other" and enter free text. Role is required to advance the guided flow.
FR3: User can select one Experience Bucket from a small fixed set of ranges (stats-only; never influences Topic suggestions).
FR4: User can optionally enter free text describing their interests (Interest Free-Text); stays skippable and never gates the guided flow.
FR5: System shows a small number of Suggestion-Source-generated example prompts near Interest Free-Text to help the user write it.
FR6: Admin can view all Pending Taxonomy Suggestions (Field or Role), grouped by normalized text with submission counts.
FR7: Admin can promote a Pending Taxonomy Suggestion into the curated Field/Role list, or dismiss it; promotion does not retroactively migrate earlier submitters onto the newly-curated entry.
FR8: System computes candidate Topics via the Suggestion Source asynchronously, triggered after the user has had the opportunity to provide Interest Free-Text, without blocking the save request.
FR9: If Field/Role has no meaningful match, or no LLM-backed Suggestion Source is connected, system still produces candidate Topics via a non-LLM popularity-based default - there is no dead end where a user gets zero suggestions.
FR10: User can select at most 4 Topics total (hard cap, platform-wide, applies to every save path), combined across all suggestion sources, and can swap which ones they keep.

### NonFunctional Requirements

NFR1: The Suggestion Source (Role options, Topic suggestions, Suggested Prompts) must be implemented behind a swappable interface - connecting the eventual local LLM must not require reworking the UI, API contract, or data model.
NFR2: Suggestion computation must not add perceptible latency to the profile save action (async, fire-and-forget from the caller's perspective).
NFR3: LLM-backed suggestion generation must be coordinated with news-agent-infra's LLM cost-control system as a distinct call path from the article-generation pipeline's LLM usage.

### Additional Requirements

- No starter template applies - this is a brownfield addition to the existing FastAPI/SQLAlchemy/Vue app (N/A for Epic 1 Story 1).
- Thin-router / domain-service layering: new routers validate + delegate; services own business rules and idempotency; services raise `ValueError`, routers translate to `HTTPException` (AD-1).
- Review-queue status shape for `PendingTaxonomySuggestion` mirrors `Source.status` exactly: plain string, `pending`/`approved`/`rejected` (AD-2).
- New sibling package `newsagent/suggestions/` mirrors `newsagent/llm/`'s exact shape (ABC + template-method retry, frozen-dataclass typed contracts, factory keyed by a new `NEWSAGENT_SUGGESTION_PROVIDER` setting); MVP ships a DB-free `popularity` adapter implementing only `suggest_topics` (AD-3).
- Schema changes ship as a new Alembic revision, following the project's existing, actively-used migration convention (`alembic/versions/`, 8 prior revisions) - not `create_all` or hand-written DDL (AD-4).
- Async suggestion computation runs as an in-process FastAPI `BackgroundTask` (no task queue, not piggybacked on the scheduled pipeline). The request handler synchronously sets `suggestion_status='pending'` and bumps `suggestion_request_seq` before returning; the BackgroundTask only writes its result if its captured seq is still current, so a superseded save discards its result instead of overwriting a newer one (AD-5).
- Profile fields (`field_name`, `role_name`, `experience_bucket`, `interest_free_text`) are flat columns on `User`, not a separate table. `field_name`/`role_name` are plain strings, not foreign keys - "Other" is a UI-only concept; a picked-from-list value and a typed "Other" value are stored identically. Matching a stored name against the curated `Field`/`Role` tables (for Suggestion Source scoping, or taxonomy-queue dedup) is a name-lookup at use time, never a stored FK (AD-6).
- Suggestion results surface via polling: `User.suggestion_status` (`none`/`pending`/`ready`/`failed`), `User.suggested_topic_ids` (JSON), `User.suggestion_request_seq`, and a new `GET /me/topic-suggestions` endpoint the frontend polls after save (AD-7).
- `PendingTaxonomySuggestion`: one row per unique `(kind: field|role, field_id nullable, normalized_text)` scoped to `status='pending'`, upserted with an incrementing `submission_count` - a resubmission matching an already-decided row creates a fresh pending row rather than mutating the decided one (AD-8).
- The 4-Topic hard cap (FR10) is enforced inside the existing shared `services/preferences.py:set_preferences` - the single mutation point for `UserTopicPreference` - via a dedicated `TopicCapExceededError(ValueError)` with a stable `detail={"error": "topic_cap_exceeded"}` shape, so every save path (old raw toggle grid and the new guided flow) surfaces the same failure identically (AD-9).
- New `admin_taxonomy.py` router (separate file from `admin.py`, same shape: `require_admin`, GET list-pending + promote/dismiss) (AD-10).
- Frontend convention: chip/pill/segmented-control components must be real semantic elements (`<button>` with `aria-pressed`, or native `radio`/`checkbox`), never `<div onclick>` (Consistency Conventions - tracked as news-agent#31).

### UX Design Requirements

UX-DR1: Implement the "Hybrid Depth" design tokens (colors, typography, rounded, spacing, component specs) from `DESIGN.md` as the visual system for the new profile-picker section only - not a redesign of the rest of the app.
UX-DR2: Build the 3-step guided flow (Step 1: Field + Role + Experience together; Step 2: Interests; Step 3: Topics) with exactly one step panel visible on screen at a time, per `EXPERIENCE.md` Information Architecture.
UX-DR3: Field chip row - single-select; "Other" reveals a free-text input in place of/alongside the chip.
UX-DR4: Role chip row - single-select, scoped to the currently selected Field; dynamically repopulates and clears prior selection when Field changes; "Other" reveals free-text.
UX-DR5: Experience segmented control - single-select among 4 illustrative buckets (0–2 / 3–5 / 6–10 / 10+ yrs, boundaries provisional per PRD `[NOTE FOR PM]`).
UX-DR6: Interest Free-Text textarea + Suggested Prompts (illustrative pills that never insert text or lock in a value).
UX-DR7: Topic pill grid - exactly 4 "picked" pills + any number of "faint" (unpicked candidate) pills; tapping a faint pill swaps it in for one of the 4; "Selected 4/4" counter.
UX-DR8: Step 1 hard gate - Continue is disabled (real semantic disabled state, not the mockup's CSS-only `.disabled` class) until Field, Role, and Experience are all set. Back is always available from any step regardless of fill state.
UX-DR9: Step 2 (Interests) has a "Skip for now" link alongside Continue - never gated, by deliberate, twice-confirmed decision.
UX-DR10: Staggered fade-up entrance animation for every step's elements, replayed in full on every mount (including re-entry via Back) - with `prefers-reduced-motion` handling (skip/shorten entrance) per the Accessibility Floor gap.
UX-DR11: Background depth system - 3 blurred glow orbs (indigo/teal/plum, not neon) with mouse-position + scroll-position parallax, plus a faint dot-grain overlay, per `DESIGN.md` Elevation & Depth.
UX-DR12: Progress stepper - 3 dots with idle/active/done states and a connecting-line fill animation on step completion.
UX-DR13: Voice/tone - plain, complete-sentence microcopy; no emoji, exclamation marks, or gamified language, per `EXPERIENCE.md`'s Do/Don't table.
UX-DR14: Accessibility remediation - real semantic controls (`<button>`/`aria-pressed`/native radio-checkbox) replacing the mockup's `<div onclick>` shortcut, visible focus rings, tab order matching reading order, verified color contrast, `aria-disabled` exposed on the Step 1 gate. Tracked as news-agent#31; must land with this feature's real build, not deferred indefinitely.
UX-DR15: Responsive/mobile design for the profile-picker (currently desktop-only mockup, no breakpoints/touch behavior designed). Tracked as news-agent#30 - real design work needed before this ships on anything but desktop.
UX-DR16: Admin Taxonomy Curation Queue UI follows the existing `AdminView.vue` / admin source-approval visual conventions, explicitly NOT the Hybrid Depth identity (out of scope for that visual spine per `EXPERIENCE.md` Information Architecture).

### FR Coverage Map

FR1: Epic 1 - Field selection + "Other"
FR2: Epic 1 - Role selection scoped to Field + "Other"
FR3: Epic 1 - Experience Bucket
FR4: Epic 1 - Interest Free-Text
FR5: Epic 1 - Suggested Prompts
FR6: Epic 2 - View pending taxonomy suggestions
FR7: Epic 2 - Promote/dismiss taxonomy suggestion
FR8: Epic 1 - Async suggestion generation
FR9: Epic 1 - Always-available fallback
FR10: Epic 1 - 4-Topic cap

## Epic List

### Epic 1: Profile-Based Topic Suggestions
A user can set up a Field/Role/Experience/Interests profile through the guided "Hybrid Depth" flow and get up to 4 suggested Topics - always non-empty, even with no Field/Role match - which they can review, swap, and save. Replaces the blank, unlimited Topic grid with a guided, capped experience. Includes the data model, the `suggestions/` package + popularity adapter, the BackgroundTask/polling design, 4-cap enforcement, the full frontend flow, and accessibility (real semantic controls) as a baseline requirement, not a follow-up. Responsive/mobile (#30) is explicitly out - no design exists for it yet.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR8, FR9, FR10 (+ NFR1, NFR2, NFR3)

### Epic 2: Admin Taxonomy Curation
An admin can view pending Field/Role "Other" submissions (grouped, with counts) and promote or dismiss them into the curated list - same review pattern as the existing source-approval panel. Builds on Epic 1's data model but stands alone as a complete admin capability.
**FRs covered:** FR6, FR7

## Epic 1: Profile-Based Topic Suggestions

A user can set up a Field/Role/Experience/Interests profile through the guided "Hybrid Depth" flow and get up to 4 suggested Topics - always non-empty, even with no Field/Role match - which they can review, swap, and save.

### Story 1.1: Guided flow shell + Field selection

*Realizes FR1.*

As a user,
I want to open my preferences page and see a guided setup flow with a Field picker,
So that I have a clear, low-effort starting point instead of a blank grid.

**Acceptance Criteria:**

**Given** I open `/me/preferences` for the first time
**When** the page loads
**Then** I see a 3-step progress stepper ("About you" / "Interests" / "Topics") with Step 1 active, styled per DESIGN.md's Hybrid Depth tokens (near-black background, orb parallax responding to mouse/scroll, dot-grain overlay)

**Given** Step 1 mounts
**When** its elements render
**Then** each animates in with a staggered fade-up entrance, and `prefers-reduced-motion` skips/shortens the entrance and freezes orb parallax

**Given** Step 1 is showing
**When** I view the Field section
**Then** I see Field chips from the admin-curated list plus "Other," implemented as real `<button>` elements with `aria-pressed` reflecting selection (never `<div onclick>`)

**Given** no Field is selected
**When** I view Continue
**Then** it is disabled both visually and via `aria-disabled`

**Given** I select a curated Field chip
**When** the selection registers
**Then** the chip shows selected state, ready to save as `User.field_name` (plain string, not a foreign key)

**Given** I select "Other"
**When** I type a value and it saves
**Then** it is recorded as `User.field_name` and as a `PendingTaxonomySuggestion` row (`kind='field'`, `status='pending'`, normalized text, `submission_count` incremented on a matching existing pending row)

**Given** I leave the flow without completing it
**When** I navigate away
**Then** the rest of the existing preferences page (including the Topic toggle grid) is unaffected - engaging this flow is optional

**And** this story ships a new Alembic revision adding the `fields` table, the `pending_taxonomy_suggestions` table (generic across `kind='field'`/`kind='role'` from the start, per AD-8 - Story 1.2 reuses it unchanged), and `User.field_name`

### Story 1.2: Role selection scoped to Field

*Realizes FR2.*

As a user,
I want to pick my Role once I've picked a Field,
So that my profile reflects my actual job, not just my industry.

**Acceptance Criteria:**

**Given** I have selected a Field in Step 1
**When** the Role section renders
**Then** I see Role chips scoped to that Field (from the curated `roles` table, `field_id`-scoped) plus "Other"

**Given** no Field is selected yet
**When** I view the Role section
**Then** it shows a "Pick a field first" placeholder state

**Given** I have a Role selected
**When** I change my Field
**Then** my Role selection clears and the Role row re-renders scoped to the new Field

**Given** I select "Other" for Role
**When** I type a value and it saves
**Then** it is recorded as `User.role_name` and a `PendingTaxonomySuggestion` row (`kind='role'`, `field_id` set to the current Field, same pending-scoped upsert as Field)

**Given** Field is selected but Role is not
**When** I view Continue
**Then** it remains disabled (gate now checks Field + Role)

**Given** both Field and Role are selected
**When** I check Continue
**Then** it becomes enabled

**Given** a Role chip or the "Other" input
**When** either renders
**Then** it is a real `<button>` (with `aria-pressed`) or native input element, never `<div onclick>` - same accessibility baseline as Story 1.1's Field chips

**And** this story ships a new Alembic revision adding the `roles` table (FK to `fields`) and `User.role_name` column

### Story 1.3: Experience Bucket, completing the Step 1 gate

*Realizes FR3.*

As a user,
I want to indicate my experience level,
So that the product team understands our user base, without it affecting what gets suggested to me.

**Acceptance Criteria:**

**Given** Step 1 is showing
**When** I view the Experience section
**Then** I see a segmented control with 4 illustrative buckets (0–2 / 3–5 / 6–10 / 10+ yrs), implemented with real radio-group semantics, single-select

**Given** I select a bucket
**When** it saves
**Then** it is stored as `User.experience_bucket` and is never read by any Topic-suggestion computation path

**Given** Field, Role, and Experience Bucket are all set
**When** I view Continue
**Then** it is enabled; **given** any of the three is unset, it is disabled - the complete Step 1 gate

**Given** I click Back from Step 2
**When** Step 1 re-mounts
**Then** my previously selected Field/Role/Experience still show as selected, and the staggered entrance animation replays

**And** this story ships a new Alembic revision adding `User.experience_bucket`

### Story 1.4: Optional Interest Free-Text, Step 2

*Realizes FR4, FR5.*

As a user,
I want to optionally describe my interests in my own words,
So that suggestions can be sharper than my Field/Role alone would produce, without being forced to.

**Acceptance Criteria:**

**Given** I click Continue from a completed Step 1
**When** Step 2 mounts
**Then** I see an optional free-text textarea and a "Skip for now" link alongside Continue, with the staggered entrance animation

**Given** the textarea is empty
**When** I view Continue and Skip
**Then** both are enabled - Step 2 is never gated

**Given** I type text (or leave it empty) and click Continue or Skip
**When** either action completes
**Then** my text, if any, saves as `User.interest_free_text` and the flow advances to Step 3

**Given** no LLM-backed Suggestion Source is connected (MVP default)
**When** Step 2 renders
**Then** no Suggested Prompts are shown near the textarea - it remains fully usable without them

**Given** the Continue and Skip controls on this step
**When** they render
**Then** they are real `<button>` elements (keyboard-focusable, `Enter`/`Space`-activatable), never `<div onclick>` - same accessibility baseline as Story 1.1

**Given** I click Back from Step 3
**When** Step 2 re-mounts
**Then** my previously entered Interest Free-Text, if any, is still shown

**And** this story ships a new Alembic revision adding `User.interest_free_text`

### Story 1.5: Suggestion Source interface + always-available popularity fallback

*Realizes FR9, NFR1.*

As a user,
I want to always receive topic suggestions, even if my Role doesn't match anything curated yet,
So that I'm never left with an empty starting point.

**Acceptance Criteria:**

**Given** the `newsagent/suggestions/` package does not yet exist
**When** this story is implemented
**Then** it contains an ABC (`SuggestionSource`) with template-method retry mirroring `llm/base.py`'s shape, frozen-dataclass typed contracts (`types.py`), and a factory (`factory.py`) keyed by a new `NEWSAGENT_SUGGESTION_PROVIDER` setting

**Given** the MVP configuration
**When** the factory resolves a provider
**Then** it returns a `PopularitySuggestionSource` implementing only `suggest_topics` - `suggest_roles` and `suggest_prompts` return empty results

**Given** a user has no Field/Role set, or an "Other" Role with no promoted match
**When** `suggest_topics` is called for them
**Then** it returns a non-empty candidate list drawn from cross-user Topic-selection popularity, queried by the calling service and passed in as plain data - the provider itself makes no DB queries

**Given** two different users with no profile match
**When** they each request suggestions
**Then** they may receive the same generally-popular candidate set - expected and correct for a fallback

### Story 1.6: Async suggestion computation after save

*Realizes FR8, NFR2, NFR3.*

As a user,
I want my profile save to complete instantly, with suggestions appearing shortly after,
So that saving never feels slow.

**Acceptance Criteria:**

**Given** I complete Step 2 (Continue or Skip) and the profile save request is sent
**When** the request handler processes it
**Then** it synchronously sets `User.suggestion_status='pending'` and increments `User.suggestion_request_seq` before returning - the response never waits on suggestion computation

**Given** the save response has returned
**When** the frontend needs suggestions
**Then** it calls `GET /me/topic-suggestions`, which returns the current `suggestion_status` and `suggested_topic_ids`

**Given** a `BackgroundTask` was scheduled at save time
**When** it completes
**Then** it writes `suggested_topic_ids` and sets `suggestion_status='ready'` (or `'failed'` on error) only if its captured `suggestion_request_seq` still matches the current value on `User` - a superseded computation discards its result instead of overwriting a newer one

**Given** suggestion generation fails or times out
**When** the BackgroundTask's error path runs
**Then** `suggestion_status` becomes `'failed'`, no Topic selections change, and the earlier save is unaffected

**And** this story ships a new Alembic revision adding `User.suggestion_status`, `User.suggested_topic_ids`, `User.suggestion_request_seq`

### Story 1.7: Review, swap, and confirm up to 4 Topics, Step 3

*Realizes FR10.*

As a user,
I want to see my suggested topics, adjust them if needed, and save, capped at a focused 4,
So that I don't have to configure an open-ended grid myself.

**Acceptance Criteria:**

**Given** Step 2 completes and the flow advances
**When** Step 3 mounts
**Then** it polls `GET /me/topic-suggestions` until `suggestion_status` is `ready` or `failed`, showing a brief loading state in between

**Given** suggestions are `ready`
**When** Step 3 renders
**Then** up to 4 candidate Topics appear pre-picked as highlighted pills, any additional candidates appear as "faint" swappable options, and a "Selected N / 4" counter is shown

**Given** suggestions `failed`, or Field/Role/Interest yielded nothing beyond the popularity fallback
**When** Step 3 renders
**Then** it still shows a non-empty set of picked Topics - never a dead end

**Given** I tap a "faint" candidate
**When** I do
**Then** it swaps into my picked set in place of one existing pick, keeping my total at exactly 4; attempting a 5th without deselecting one first has no effect

**Given** a Topic pill (picked or faint) or the "Save preferences" control
**When** either renders
**Then** it is a real `<button>` element with `aria-pressed` reflecting picked state, never `<div onclick>` - same accessibility baseline as Story 1.1

**Given** I click "Save preferences"
**When** the save request is sent
**Then** it calls the same `services/preferences.py:set_preferences` the existing raw Topic toggle grid already uses, enforcing the platform-wide 4-Topic cap via a dedicated `TopicCapExceededError` with a stable `{"error": "topic_cap_exceeded"}` detail, surfaced identically regardless of which UI path triggered it

**Given** I already had more than 4 Topics selected from the old unlimited grid before this feature shipped
**When** I next save via either path
**Then** the cap applies going forward - retroactive migration/backfill of pre-existing over-cap selections is explicitly out of scope for this story (tracked as an open PRD question)

## Epic 2: Admin Taxonomy Curation

An admin can view pending Field/Role "Other" submissions (grouped, with counts) and promote or dismiss them into the curated list - same review pattern as the existing source-approval panel. The `pending_taxonomy_suggestions` table already exists from Epic 1 Story 1.1; this epic adds no new tables, only the admin-facing router, service functions, and UI.

*File-overlap note (validation check): this epic shares `services/taxonomy.py` and the `Field`/`Role`/`PendingTaxonomySuggestion` models with Epic 1. Consolidation into Epic 1 was considered and rejected - the overlap is a shared data-layer module, not repeated re-touching of the same end-to-end feature; the two epics serve genuinely different actors (end-user profile setup vs. admin review) and deliver independently valuable, separately shippable capability, matching the standard "distinct user type on shared foundation" pattern rather than the file-churn anti-pattern.*

### Story 2.1: View pending taxonomy suggestions

*Realizes FR6.*

As an admin,
I want to see all pending Field/Role "Other" submissions grouped by normalized text with counts,
So that I can tell which ones real users actually need without duplicate noise.

**Acceptance Criteria:**

**Given** there are rows in `pending_taxonomy_suggestions` with `status='pending'`
**When** I view the admin Taxonomy Curation Queue (`GET` endpoint on a new `admin_taxonomy.py` router, `require_admin`)
**Then** I see each pending suggestion with its kind (field/role), associated Field name (for role-kind rows), normalized text, and `submission_count`

**Given** multiple identical `(kind, field_id, normalized_text)` submissions were made
**When** I view the queue
**Then** they appear as one row with the incremented `submission_count` (per AD-8), never as separate rows

**Given** no pending submissions exist
**When** I view the queue
**Then** I see an empty state consistent with the existing admin panel's conventions (`AdminView.vue`'s look, not Hybrid Depth - this surface is explicitly out of that visual spine per EXPERIENCE.md)

**Given** I am not an admin
**When** I try to access this endpoint or view
**Then** I am denied, via the same `require_admin` dependency the existing `admin.py` source-approval router already uses

### Story 2.2: Promote or dismiss a pending taxonomy suggestion

*Realizes FR7.*

As an admin,
I want to promote a pending submission into the curated Field/Role list, or dismiss it,
So that I control how the picker's options grow, the same way I already control approved sources.

**Acceptance Criteria:**

**Given** a pending taxonomy suggestion of kind `field`
**When** I promote it
**Then** a new row is created (or an existing matching one reused) in the `fields` table with that name, and the suggestion's `status` becomes `approved`

**Given** a pending taxonomy suggestion of kind `role`
**When** I promote it
**Then** a new row is created in the `roles` table, scoped to its `field_id`, and the suggestion's `status` becomes `approved`

**Given** I promote a suggestion
**When** the promotion completes
**Then** users who originally typed that text as free text are NOT retroactively migrated onto the newly-curated entry - their stored `field_name`/`role_name` is unchanged (per PRD FR7's consequence)

**Given** a pending taxonomy suggestion
**When** I dismiss it instead
**Then** its `status` becomes `rejected` and it is removed from the pending list without being added to `fields`/`roles`

**Given** a promoted or dismissed (non-pending) suggestion exists
**When** a user later submits matching "Other" text again
**Then** a fresh `pending` row is created rather than mutating the decided one (per AD-8) - it reappears in the admin queue as a new item, not silently lost

**Given** I am not an admin
**When** I attempt to promote or dismiss
**Then** I am denied via `require_admin`, matching the existing pattern in `admin.py`
