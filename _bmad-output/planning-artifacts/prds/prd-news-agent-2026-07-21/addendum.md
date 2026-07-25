# Addendum: Profile-Based Topic Suggestions

Depth that doesn't belong in the PRD's main narrative but is useful for downstream UX/architecture work. Captured from the design roundtable (party mode: Amelia/dev, Sally/UX, John/PM) preceding this PRD.

## Rejected alternative: hand-maintained Field × Role → Topic weight matrix

Early framing was "update Topic categories for every job type" — a matrix mapping each (Field, Role) combination directly to a fixed set of Topics, maintained by hand. Rejected because:
- Grows unboundedly as Roles are added — every new Role needs its own hand-authored Topic mapping.
- No graceful handling of near-duplicate Roles ("Product Manager" vs "Product Owner" needing different defaults).
- Duplicates a decision the project already flagged as an open, unresolved risk in the original forge doc (source-quality judgment from stated user interests) — same shape of problem, one layer up.

Chosen alternative instead: LLM does the (Field, Role) → Topic mapping live/async at suggestion time (§4.3 in the PRD), rather than a maintained lookup table. Tradeoff accepted: introduces LLM latency/failure handling (see FR-6 consequences) in exchange for removing an ongoing content-ops burden.

## Rejected alternative: 3-level taxonomy (Field → Role → Specialization)

A third, optional "specialization" level beneath Role was proposed (sharper signal for suggestions, e.g. "Tech → Engineering → Backend") and discussed as *optional/skippable* to avoid onboarding friction. User explicitly decided to drop it entirely in favor of the simpler 2-level Field → Role structure. If suggestion relevance turns out to be too coarse with just (Field, Role), this is the documented fallback to revisit — not a dead idea, just not v1.

Reconfirmed on a later pass, when an LLM-driven Role-suggestion mechanism was introduced (see below): the LLM enriches *what Role options look like* for a given Field, it does not add a third stored profile field. Two stored levels stays final.

## Suggestion Source: pluggable abstraction (technical shape)

The PRD's FR-2, FR-5, FR-8/FR-9 require the suggestion mechanism to be swappable without UI/data-model rework once a specific LLM is chosen. Shape discussed:

- A single `SuggestionSource` interface/port with roughly three capabilities: `suggest_roles(field) -> [role_option]`, `suggest_prompts() -> [prompt_text]`, `suggest_topics(field, role, interest_text) -> [topic_id]`.
- **MVP implementation**: a non-LLM `PopularitySuggestionSource` that only implements `suggest_topics` (returns the globally-popular-Topics fallback, FR-9) — `suggest_roles` and `suggest_prompts` return empty/no-op until a real backend is wired in, per the FR-2/FR-5 assumptions.
- **Future implementation**: an `LLMSuggestionSource` backed by a locally-hosted model, implementing all three. Swapped in via configuration, not a code change to the API or preferences UI.
- The local LLM used here is explicitly a separate model/deployment from the LLM already in use for article summarization/translation in the content pipeline — different concern, different cost profile, likely different sizing (this one needs to be fast/cheap enough to run per-profile-save, not per-article). Coordinate model choice and hosting with news-agent-infra, since they own LLM cost control (per project CLAUDE.md), but treat it as a second, distinct call path rather than folding it into the existing pipeline's model budget.
- Not yet decided: whether "local" means self-hosted on the app server, a separate inference service news-agent-infra stands up, or something else. Flagged to architecture, not resolved here.

## Suggested data-model shape (non-binding, for architecture's reference)

Raised during the roundtable, not a commitment:
- `field` and `role` as small admin-owned tables (role FK'd to field), not free columns on the user/preferences table.
- `years_experience` stored as a bucket value (enum-like), not a raw integer — cleaner for group-by/stats than a raw number.
- Suggestion computation as `(field, role) → LLM → topic_ids[]`, cached/stored as the suggestion result rather than recomputed on every page load.
- "Other" Role submissions: a nullable free-text column plus a lightweight "pending roles" review surface for admins, explicitly parallel to the existing Source `pending/approved/rejected` status pattern rather than a new mechanism.

## UX tone notes (for the UX spec workflow)

- Explicit design reaction against a plain form: "a blank textarea is always homework." The Field/Role/Experience picker should read as a short interactive quiz, not a profile form — chips/illustrated selects for Field and Role, a segmented control or slider for Experience Bucket rather than a numeric input.
- Analogy used in the room: "RPG class-select screen" — pick a world (Field), then it reveals your class options (Role) within it. Useful framing for the UX spec's interaction design, not a literal visual direction requirement.
- Hard constraint carried from Sally's opening objection: whatever ships must remain permanently editable in the preferences page — never a one-shot registration wizard step that disappears after first fill-in.

## Admin ownership condition (John)

Role list per Field should start small and admin-seeded — explicitly not an "enumerate every possible job title" exercise. Mirrors the existing discipline in the admin source-approval panel (#22): curated and grown deliberately via the Pending Role Suggestion queue (PRD §4.2), not crowdsourced open-ended from day one.
