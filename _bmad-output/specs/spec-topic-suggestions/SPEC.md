---
id: SPEC-topic-suggestions
companions: [topic-status-flow.md]
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only - consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Real Topic Suggestions (Step 3)

## Why

Step 3 of the profile wizard (`TopicsStep.vue`) currently falls back to "the topics the user is already subscribed to" whenever the suggestion result isn't ready or non-empty - and with only 3 seeded Topics total against a 4-topic selection cap, that fallback is effectively the only outcome anyone ever sees, so Step 3 never demonstrates the personalization the rest of the wizard (Role/Prompt suggestions) already delivers. The pain: a user who just told the wizard their Field, Role, and interests in Steps 1–2 gets no topic suggestions that reflect any of it. Unlike Role (a free string with an "Other" queue), Topic selection is a hard foreign key (`UserTopicPreference.topic_id`), so an LLM can't propose a new topic the same way it proposes a new Role - a name has to become a real, referenceable row first. This spec wires that up: an LLM-backed suggestion set that mixes ranked existing Topics with brand-new invented ones, gated by a lightweight admin-approval status so a user's own novel pick works immediately while only vetted Topics get suggested to everyone else.

## Capabilities

- **CAP-1**
  - **intent:** The Step 3 suggestion set merges Topics the LLM ranks as relevant from the existing (approved) catalog with brand-new Topic names the LLM invents from the user's Field/Role/Interest-Free-Text, so the grid is never just an echo of the user's current subscriptions.
  - **success:** Two differently-profiled users (e.g. Finance/Financial-Advisor vs Tech/Software-Engineer) produce visibly different suggestion sets; a user with zero prior subscriptions still gets a non-trivial suggestion set drawn from more than the 3-topic seed catalog once new topics exist.

- **CAP-2**
  - **intent:** Selecting a not-yet-existing suggested Topic creates a real `Topic` row (`status='pending'`, get-or-create by exact name) plus a real `UserTopicPreference` for the selecting user, so it is fully usable for them immediately with no admin gate blocking their own use.
  - **success:** After picking a brand-new topic and saving, a fresh `GET /me/preferences` for that user includes it as subscribed; `Topic.status` for that row is `pending`.

- **CAP-3**
  - **intent:** Only `status='approved'` Topics are ever offered as suggestion candidates to other users; a `pending` Topic stays invisible to everyone except the user who created it, until an admin decides it.
  - **success:** A second, differently-profiled user's suggestion candidate list never includes a still-`pending` Topic created by the first user.

- **CAP-4**
  - **intent:** An admin can approve or reject a pending Topic through a dedicated review endpoint and UI. Approving flips it to `approved` (now suggestible to everyone); rejecting flips it to `rejected` permanently - still fully functional for the original selecting user, never offered to anyone else again, with no un-reject path.
  - **success:** Approving a pending Topic makes it appear in a subsequent, differently-profiled user's candidate list; rejecting one leaves the original user's own subscription intact while it never appears for anyone else, and there is no endpoint or UI action that moves a `rejected` Topic back to `pending` or `approved`.

- **CAP-5**
  - **intent:** Existing Topics migrate with zero behavior change - every pre-existing `Topic` row defaults to `approved`.
  - **success:** After migrating, the 3 seeded Topics (and any admin-added ones) are `approved` and continue to appear in every user's preferences and candidate lists exactly as before this feature.

## Constraints

- Topic selection stays a hard FK (`UserTopicPreference.topic_id`) - no free-text "Other" mechanism like Role/Field. A new name must become a real `Topic` row before anything can reference it; this is why the flow differs from `PendingTaxonomySuggestion`'s defer-the-row-until-promotion pattern.
- `MAX_TOPICS = 4` (`services/preferences.py`) is unchanged and still enforced by the existing `set_preferences` / `TopicCapExceededError` path, including when a newly-created pending topic is among the picks.
- `suggest_topics`'s adapter contract must return two distinguishable kinds of result - existing-candidate picks by `topic_id`, and new-topic proposals by name - so the service layer can route each to the correct write path. A plain `topic_id` list can no longer represent the full contract.
- `_topic_popularity`'s candidate list (`services/profile.py`) must filter to `status='approved'` only, and must carry `Topic.name` alongside `topic_id` + `selection_count` - the LLM cannot reason about or avoid duplicating a topic it cannot see the name of.
- A user's own preferences view (`list_topic_choices` / `GET /me/preferences`) must keep showing any `pending` or `rejected` Topic they are personally already subscribed to, by name. Status only gates whether a Topic is offered as a *suggestion to others* - never whether the owning user can see or keep their own pick.
- New-Topic creation reuses `add_topic`'s existing get-or-create-by-exact-name idempotency unchanged (whitespace-strip only). No fuzzy/normalized name matching is introduced for Topics - that is new scope beyond this feature.
- `suggestions/` stays DB-free (AD-3, same rule as the Role/Prompt story): `services/profile.py` queries popularity and approved-topic names and passes plain data into `suggest_topics`; the LLM adapter never touches the DB.
- Rejected Topics stay rejected permanently - no re-review/un-reject path, mirroring how a rejected `Source` has no un-reject path either.
- Admin Topic review gets its own router file, mirroring `admin.py`'s `Source` pattern exactly (list-pending + patch-status) rather than extending `admin_taxonomy.py` - follows this codebase's existing precedent (AD-10) that source approval and taxonomy approval are independent review concerns that merely share a shape; Topic status lives on the `Topic` row itself, like `Source.status`, structurally unlike `PendingTaxonomySuggestion`.
- Suggestion-grid display cap for the merged existing+new Topic candidates is 10, matching `ROLE_SUGGESTION_CAP`'s established convention in this codebase (see Assumptions).
- New-Topic row + `UserTopicPreference` creation happens only at "Save preferences" time (batch, same as every existing topic toggle today) - never eagerly at chip-click time. No dedicated create-on-click endpoint: the existing `PUT /me/preferences` payload/service is extended to accept new-topic names alongside existing `topic_id`s and resolve/create them server-side within that single save call.

## Non-goals

- No re-review/un-reject workflow for rejected Topics.
- No fuzzy or near-duplicate Topic-name merging (e.g. "AI" vs "Artificial Intelligence" stay separate rows).
- No change to the Role/Field/`PendingTaxonomySuggestion` flow - untouched, separate mechanism.
- No change to the `MAX_TOPICS` cap value itself (stays 4).
- No bulk/batch admin actions - one Topic decided at a time, matching existing Source/Taxonomy admin UX.
- No proactive admin notification when a new pending Topic appears (it simply appears in the review queue).

## Success signal

`pytest` covers: the migration (existing Topics default to `approved`); new-topic get-or-create plus immediate `UserTopicPreference` creation; approved-only candidate filtering (a pending topic never appears in another user's suggestion set); admin approve/reject transitions, with permanently-rejected verified as terminal; and `MAX_TOPICS` cap enforcement including a newly-created topic. Manually: run the wizard as two differently-profiled users with `NEWSAGENT_SUGGESTION_PROVIDER=llm`, confirm Step 3 shows more than an exact echo of current subscriptions for each; pick a brand-new topic and save; as admin, find it in the Topic review queue and approve it; confirm a second, differently-profiled user can now also see it suggested.

## Assumptions

- Suggestion-grid display cap for merged existing+new Topic candidates set to 10, matching `ROLE_SUGGESTION_CAP`'s convention in this codebase for consistency - not explicitly stated by the user, flagged as an assumption.
