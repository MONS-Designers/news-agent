---
title: Profile-Based Topic Suggestions
status: final
created: 2026-07-21
updated: 2026-07-22
---

# PRD: Profile-Based Topic Suggestions
*Working title — confirm.*

## 0. Document Purpose

This PRD is for the news-agent team (PM, dev, UX) and downstream workflow owners (UX spec, architecture, epics/stories). It defines a new capability on top of the existing self-serve preferences page: a Field + Role profile picker, an optional free-text interest field, and an LLM-pluggable suggestion mechanism that proposes Topics for the user's digest. Vocabulary is Glossary-anchored (§3); FRs are grouped by feature and globally numbered; inline `[ASSUMPTION]` tags are indexed in §9. A finalized UX spec exists for this feature — `DESIGN.md` and `EXPERIENCE.md` at `_bmad-output/planning-artifacts/ux-designs/ux-news-agent-2026-07-21/` ("Hybrid Depth") — this PRD builds on it and does not duplicate its interaction choreography or visual tokens; where the two documents describe the same behavior, the UX spec owns exactly how it's built and this PRD owns why/what's required.

## 1. Vision

Today, a user's only way to set their digest content is the preferences page's blank Topic toggle grid (#21) — a wall of unlabeled checkboxes with zero guidance. Most people don't know what to pick, and free-form "tell us what interests you" text is a harder cold-start than it looks: staring at a blank box about yourself is friction, not a feature, unless something helps you fill it.

This feature replaces that cold start with a short, structured profile — Field, then Role (Role options generated for the chosen Field), an experience level, and an optional free-text interest description with suggested prompts to help the user write it — and uses all of it to suggest up to 4 Topics for the user to confirm or swap. It turns Topic selection from "guess what's on this grid" into "confirm what we already got mostly right." It also gives the product a second, quieter payoff: structured Field/Role/Experience data the team can actually query for who's using this product and how.

The suggestion mechanism is designed to be LLM-driven end to end, but the specific local LLM model that powers it hasn't been chosen yet. This PRD scopes the full product surface — including the free-text interest capture and its LLM-suggested prompts — on the assumption that the underlying model gets connected once available, without requiring rework of the UI or data model when it is. It's an extension of the preferences page, not a new gate — nothing here blocks account use, and everything here stays editable for as long as the user's job, interests, or the model behind it, change.

## 2. Target User

### 2.1 Jobs To Be Done

- As a user setting up my digest, I want to be told what to pick instead of facing a blank grid, so setting preferences feels fast and low-effort.
- As a user, I want the system to get my starting Topics roughly right without me having to think hard about it, so I get value before I've done any real configuration work.
- As a user who has more specific interests than my job title captures, I want a place to describe them in my own words and get help doing so, without that being the *only* way to get started.
- As a user whose job, role, or interests change, I want to update my profile at any time, not just once at signup.
- As the product owner, I want structured signal on who our users are professionally, so I can reason about product-market fit with real data instead of guesses.

### 2.3 Key User Journeys

- **UJ-1. Noa sets up her digest for the first time.**
  - **Persona + context:** Noa, a backend engineer, is one of the two seeded dogfood users. She's authenticated and opens her preferences page for the first time.
  - **Entry state:** Authenticated, on `/me/preferences`, Topic toggle grid currently empty.
  - **Path:** She taps "Tech" as her Field, and a Role chip row appears — populated by the Suggestion Source for that Field (or, before a local LLM is connected, a minimal set plus "Other"). She taps "Backend Engineer" (or types it via "Other" if it's not offered yet), picks "6-10 years" from an experience control, and optionally types a line or two about what she's into — the system shows her a couple of suggested prompts nearby to help her get started. She saves.
  - **Climax:** Shortly after, up to 4 candidate Topics appear, already checked. She recognizes most as relevant, swaps one out for a different suggested option, and leaves.
  - **Resolution:** Her digest going forward reflects a profile she barely had to think about filling in, capped at a focused 4 Topics rather than an open-ended grid.
  - **Edge case:** If suggestion generation fails or times out, her save still succeeds with no candidate Topics shown — nothing blocks on the suggestion, and she can still select Topics manually up to the 4-Topic cap.

- **UJ-2. Amir's role isn't on the list.**
  - **Persona + context:** Amir works in DevRel, a role not offered by the Suggestion Source yet.
  - **Entry state:** Authenticated, mid-profile-setup, Field already picked ("Tech").
  - **Path:** He scans the Role options, doesn't find a fit, taps "Other," types "Developer Relations," saves.
  - **Climax:** His profile saves with the free-text role recorded. He still gets Topic suggestions — the fallback "generally popular" default always produces something, even without a Field/Role match.
  - **Resolution:** He can swap or manually adjust his (at most 4) Topics himself; his "Other" submission is queued for admin review. Realizes FR-2, FR-9.

## 3. Glossary

- **Topic** — Existing domain entity (`topics` table) a user can select in the preferences grid to shape their digest content. Referred to informally as "category" in conversation; this PRD uses Topic exclusively, per existing codebase vocabulary.
- **Field** — A new, admin-curated top-level grouping describing a user's professional/industry domain (e.g., "Tech," "Finance," "Healthcare"). Selectable from a list, or via "Other" free text (queued for review, see Pending Taxonomy Suggestion).
- **Role** — A new job-function value scoped under exactly one Field (e.g., "Backend Engineer" under "Tech"). Options are generated per-Field by the Suggestion Source rather than a single fixed master list; user can also submit free text via "Other."
- **Experience Bucket** — A new, coarse-grained years-of-experience range (e.g., "0-2," "3-5," "6-10," "10+") a user selects. Stats-only; does not affect Topic suggestions.
- **Interest Free-Text** — A new, optional field where the user describes their interests in their own words. Feeds the Suggestion Source as additional signal for Topic suggestions.
- **Suggested Prompts** — Short example prompts shown near Interest Free-Text, generated by the Suggestion Source, to help the user write it.
- **Suggestion Source** — The pluggable mechanism that produces Role options, Topic suggestions, and Suggested Prompts. Backed by a local LLM once one is connected; produces a non-LLM popularity-based default for Topic suggestions in the interim (see FR-9). Deliberately independent of the LLM used elsewhere in the pipeline for article summarization/translation.
- **Pending Taxonomy Suggestion** — A free-text Field or Role submission made via "Other," queued for admin review and possible promotion into the curated list. Mirrors the existing Source approval states (`pending` / `approved` / `rejected`, see `Source.status`).
- **Suggested Topics** — The candidate set of Topics proposed to a user (from Field/Role and/or Interest Free-Text), of which the user may keep at most 4.

## 4. Features

### 4.1 Profile: Field, Role, Experience, Interests

**Description:** Adds a profile section to the existing preferences page (`/me/preferences`), above or alongside the Topic toggle grid: Field, Role, Experience Bucket, and an optional Interest Free-Text field with Suggested Prompts. Presented as a guided, step-gated flow (Field + Role + Experience together, then Interest Free-Text, then Topic suggestions — exact interaction in the UX spec's `EXPERIENCE.md`). **Engaging with this flow at all is optional** — a user who never opens it keeps using the preferences page exactly as before, Topic grid included. **Once engaged, Field, Role, and Experience Bucket must all be set before the flow advances to Topic suggestions** — this is a within-flow completion requirement, not an account-level gate; the user can always back out, leave, and resume later, and nothing here blocks saving preferences overall. Interest Free-Text stays genuinely skippable within the flow (confirmed decision, see FR-4) — forcing it would recreate the exact cold-start friction (blank textarea as homework) this feature exists to avoid. Field and/or Interest Free-Text are what feed Topic suggestions (§4.3); Experience Bucket is captured independently and never influences suggestions. Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-1: Field selection
User can select one Field from an admin-curated list, or choose "Other" and enter free text.

**Consequences (testable):**
- "Other" Field submissions are recorded as a Pending Taxonomy Suggestion (§4.2), same review path as Role.
- A user who never opens the guided profile flow can still use the preferences page exactly as it works today, Field unset. Within the flow, Field is required to advance (see §4.1 Description).

#### FR-2: Role selection
After a Field is selected, user can select one Role from the options the Suggestion Source generates for that Field, or choose "Other" and enter free text.

**Consequences (testable):**
- Role options shown are scoped to the currently selected Field.
- Changing Field clears any previously selected Role.
- "Other" Role submissions are recorded as a Pending Taxonomy Suggestion (§4.2).
- **Confirmed:** until the Suggestion Source is LLM-connected, Role option generation produces no curated options — "Other" free text is the practical way to set a Role in the interim, by design; no separate non-LLM interim option list is planned (resolves the assumption previously tracked here).
- Role is required to advance the guided flow (see §4.1 Description), and "Other" satisfies that requirement — the gate checks that a Role value exists, not that it came from the curated list.

#### FR-3: Experience Bucket
User can select one Experience Bucket from a small fixed set of ranges.

**Consequences (testable):**
- Experience Bucket selection is stored per user, independent of Field/Role.
- Experience Bucket never triggers or influences Topic suggestion recomputation.
- Experience Bucket is required to advance the guided flow, alongside Field and Role (see §4.1 Description) — required-to-progress and "stats-only, no suggestion influence" are independent facts, not a contradiction.

**Notes:** Experience Bucket exists for product statistics only (§7). `[NOTE FOR PM]` Confirm the exact bucket boundaries before build — this PRD assumes a small illustrative set, not a finalized list.

#### FR-4: Interest Free-Text
User can optionally enter free text describing their interests.

**Consequences (testable):**
- Interest Free-Text is optional and independent of Field/Role — a user can fill either, both, or neither.
- **Confirmed, twice:** unlike Field/Role/Experience Bucket, Interest Free-Text does NOT gate advancement in the guided flow — a "skip" affordance is always available here. This was deliberately re-examined and re-confirmed during UX discovery rather than assumed; forcing it would recreate the founding cold-start problem this feature solves (§1 Vision).
- Saving or changing Interest Free-Text can feed Topic suggestion regeneration (§4.3), subject to Suggestion Source availability.

#### FR-5: Suggested Prompts
Near the Interest Free-Text field, the system shows a small number of example prompts (generated by the Suggestion Source) to help the user compose their answer.

**Consequences (testable):**
- Suggested Prompts are illustrative text only — clicking/using one does not submit or lock in a value, the field remains freely editable.
- `[ASSUMPTION]` Suggested Prompts require a connected Suggestion Source; until then, the field is shown without prompts (or with a static illustrative example) rather than blocking the free-text field itself.

**Feature-specific NFRs:**
- The Suggestion Source (Role options, Topic suggestions, Suggested Prompts) must be implemented behind a swappable interface — connecting the eventual local LLM must not require reworking the UI, API contract, or data model. See addendum for the technical shape of this abstraction.

### 4.2 Admin: Taxonomy Curation Queue

**Description:** Gives admins visibility into "Other" Field and Role submissions and a way to promote or dismiss them, mirroring the existing source-approval pattern (#22) rather than introducing a new review paradigm. Realizes UJ-2 (resolution half).

**Functional Requirements:**

#### FR-6: View pending taxonomy suggestions
Admin can view all Pending Taxonomy Suggestions (Field or Role), with their submission text, associated Field (for Role submissions), and count of users who submitted the same normalized text.

**Consequences (testable):**
- Identical free-text submissions (case/whitespace-normalized), under the same Field for Role submissions, are grouped with a count rather than listed as separate rows.

#### FR-7: Promote or dismiss a pending taxonomy suggestion
Admin can promote a Pending Taxonomy Suggestion into the curated Field or Role list, or dismiss it.

**Consequences (testable):**
- Promoting a Field suggestion makes it selectable as a normal curated Field for all users going forward; promoting a Role suggestion makes it selectable under its Field.
- Promotion does not retroactively change the profile of users who originally submitted it as free text. `[ASSUMPTION: acceptable that early submitters don't get auto-migrated onto the newly-promoted entry — flag if that's actually wanted.]`
- Dismissing a submission removes it from the queue without adding it to the curated list.

**Notes:** **Resolved:** admin stays the sole owner of Field/Role curation indefinitely, even once the Suggestion Source is LLM-connected — no automatic LLM/DB-driven takeover of Role-list growth is planned. Future automation (LLM or DB analytics proactively flagging when a Field's Role list needs growing) is tracked separately as [news-agent#29](https://github.com/MONS-Designers/news-agent/issues/29), not built now.

### 4.3 Topic Suggestion Engine

**Description:** Produces up to 4 candidate Topics from the user's Field/Role and, when present, Interest Free-Text, and lets the user pick and swap among them. Always produces *something* — there is no dead end where a user gets zero suggestions. Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-8: Suggestion generation
The system computes candidate Topics via the Suggestion Source, asynchronously, without blocking the save request or the page.

**Consequences (testable):**
- Computation is triggered after the user has had the opportunity to provide Interest Free-Text (i.e., after the Field/Role/Experience portion of the guided flow, not immediately upon Field/Role alone) — this ordering is what lets the candidate pool be properly capped at 4 (FR-10) using the strongest available signal. Exact UI sequencing lives in the UX spec.
- The preferences save request returns successfully regardless of suggestion-generation latency or failure.
- If suggestion generation fails or times out, no Topics are changed and no error is shown for that failure — save already succeeded.

#### FR-9: Always-available fallback
If Field/Role has no meaningful match (e.g., an "Other" Role with no promoted equivalent yet) or no LLM-backed Suggestion Source is connected, the system still produces candidate Topics from a non-LLM, popularity-based default ("Topics that interest most users").

**Consequences (testable):**
- A user with no Field/Role set, or an unmatched "Other" Role, still receives non-empty candidate Topics.
- This fallback requires no LLM and is the MVP-default path for Topic suggestion until a Suggestion Source is connected.

#### FR-10: Selecting and capping Topics
User can select at most 4 Topics total, combined across all sources (popularity-based default and/or LLM-computed), and can swap which ones they keep.

**Consequences (testable):**
- The preferences UI enforces a hard maximum of 4 selected Topics at any time — this is a platform-wide cap, not scoped only to freshly-suggested Topics.
- Selecting a 5th Topic requires first deselecting one of the existing 4.
- User can swap any of their (at most 4) Topics for a different suggested candidate.

**Notes:** `[NOTE FOR PM]` This caps total Topic selection for *all* users, replacing the currently unlimited toggle grid (#21). Any existing user who already has more than 4 Topics selected needs an explicit decision on what happens at rollout (grandfathered as-is vs. trimmed to 4 vs. prompted to choose). See §8.

**Feature-specific NFRs:**
- Suggestion computation must not add perceptible latency to the profile save action (async, fire-and-forget from the caller's perspective).
- LLM-backed suggestion generation is a cost-bearing operation once connected; coordinate with news-agent-infra's LLM cost-control system (per project CLAUDE.md) as a distinct call path from the article-generation pipeline's LLM usage. `[NOTE FOR PM]`

## 5. Non-Goals (Explicit)

- This is not a self-registration flow change. Users remain admin-seeded per current MVP scope; this feature only extends what an already-provisioned user can do in their own preferences.
- This does not add a third stored taxonomy level ("specialization"). Field and Role remain the only two stored profile fields — confirmed final. The Suggestion Source may generate specific, narrow Role option text, but that's content within the existing 2-level structure, not a new field.
- This does not attempt automatic taxonomy discovery from user data (e.g., clustering to invent new Fields). Fields and Roles are admin-curated (with the Pending Taxonomy Suggestion queue as the controlled growth path); Role *option generation* per Field may be LLM-driven, but the underlying curated list and its growth stay admin-governed.
- Experience Bucket is not a personalization signal — it does not weight, filter, or influence Topic suggestions in any way.
- This does not change how Topics themselves are created or approved (existing Topic/Source model, #22, is untouched).
- Choosing and hosting the specific local LLM model is a separate infrastructure decision, not scoped here — this PRD requires the integration point to be pluggable, not which model fills it.

## 6. MVP Scope

### 6.1 In Scope

- Guided, step-gated profile flow (Field + Role + Experience required together, then optional Interest Free-Text, then Topic suggestions) per the UX spec — see §0.
- Field selection (admin-curated list + "Other") on the existing preferences page.
- Role selection scoped to Field, options from the Suggestion Source (interim: "Other"-driven until LLM-connected) + "Other" free text.
- Experience Bucket selection, stats-only.
- Interest Free-Text field with Suggested Prompts (prompts require Suggestion Source; field itself works without it).
- Admin Taxonomy Curation Queue covering both Field and Role "Other" submissions.
- Topic Suggestion Engine: always-available popularity-based fallback (live from day one, no LLM required) plus a pluggable Suggestion Source interface ready for the LLM-backed path once a local model is connected.
- Hard cap of 4 selected Topics, platform-wide.
- Initial Field/Role seed content authored generically by PM (no real dogfood-user data available yet) — see Open Questions.

### 6.2 Out of Scope for MVP

- The specific local LLM model selection, hosting, and connection itself — infra decision tracked separately (§8); this PRD ships the pluggable surface around it.
- A third taxonomy level ("specialization") — explicitly rejected, not deferred.
- Experience-weighted suggestions.
- Auto-migrating a promoted "Other" Field/Role back onto users who originally submitted it as free text.
- Any change to public self-registration (still explicitly out of MVP per project scope).

## 7. Success Metrics

**Primary**
- **SM-1**: % of active users with a Field set. Target: majority of the (small, seeded) active user base within the first review cycle. Validates FR-1.
- **SM-2**: % of users who retain at least one suggested Topic after suggestions land (didn't clear all 4). Validates FR-8, FR-9, FR-10 — signal that suggestions are relevant even under the non-LLM fallback.

**Secondary**
- **SM-3**: Number and diversity of Pending Taxonomy Suggestions submitted, as a proxy for how well the initial generic Field/Role content matches real users. Validates FR-1, FR-2, FR-6.

**Counter-metrics (do not optimize)**
- **SM-C1**: % of users whose final 4 Topics are *exactly* the first candidates shown with nothing swapped. Consistently 100% across users would suggest passive acceptance rather than genuine review — not a target to chase. Counterbalances SM-2.

[Given internal/dogfood-stage stakes, targets above are directional, not contractual — revisit once there's a real, larger active user base, and once the LLM-backed Suggestion Source is live (metrics may shift meaningfully once suggestions stop being purely popularity-based).]

## 8. Open Questions

1. Real Field/Role content: PM is authoring generic starting content since no real dogfood-user job data exists yet. Should this be validated against the two actual dogfood users' real roles before or shortly after launch?
2. Which local LLM will power the Suggestion Source, and how is it hosted/operated? Separate infra decision — and since it's explicitly independent from the article-generation LLM, does news-agent-infra's cost-control system need to account for a second, locally-hosted model as a distinct concern?
3. Existing-user migration for the new 4-Topic hard cap (FR-10): what happens to users who already have more than 4 Topics selected under the current unlimited grid?
4. Exact Experience Bucket boundaries (§4.1 FR-3 Notes) — not yet finalized.

Resolved during UX discovery (kept here for audit, not open anymore): interim Role-option behavior (§4.1 FR-2 — "Other"-only until connected, confirmed, no separate interim list); Admin Taxonomy Curation Queue permanence (§4.2 FR-7 Notes — admin stays sole owner indefinitely, automation tracked as [news-agent#29](https://github.com/MONS-Designers/news-agent/issues/29)).

## 9. Assumptions Index

- §4.1 FR-5 — Suggested Prompts require a connected Suggestion Source; field itself remains usable without them in the interim.
- §4.2 FR-7 — Promoting a Pending Taxonomy Suggestion does not retroactively migrate earlier free-text submitters onto the newly-curated entry.
