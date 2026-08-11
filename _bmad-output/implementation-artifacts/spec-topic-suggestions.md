---
title: 'Real Topic suggestions in Step 3 (existing + LLM-invented new topics)'
type: 'feature'
created: '2026-07-30'
status: 'done'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/specs/spec-topic-suggestions/SPEC.md', '{project-root}/_bmad-output/specs/spec-topic-suggestions/topic-status-flow.md']
baseline_commit: 'dbedd46459457650437fe42157d372d9d15846bf'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Step 3 (`TopicsStep.vue`) falls back to "topics the user already subscribes to" whenever the suggestion result isn't ready/non-empty, and with only 3 seeded Topics against a 4-topic cap, that fallback is the only outcome anyone ever sees — Step 3 never reflects the Field/Role/Interests the user just entered, unlike Role and Prompt suggestions which already do.

**Approach:** Extend `suggest_topics` with a second adapter method for LLM-invented new Topic names; the existing async BackgroundTask/polling computation (AD-5/AD-7) merges ranked-existing-approved candidates with invented names into the stored suggestion result. Picking a not-yet-existing Topic and hitting "Save preferences" creates a real `Topic` row (`status='pending'`, get-or-create by exact name) plus a `UserTopicPreference` — usable by that user immediately. Only `status='approved'` Topics are ever suggested to *other* users. **Admin approve/reject UI is a separate, deferred follow-up spec** (`deferred-work.md`, 2026-07-30 entry) — pending Topics simply accumulate safely (never leaking to other users) until that ships.

## Boundaries & Constraints

**Always:**
- Topic selection stays a hard FK (`UserTopicPreference.topic_id`) — a new name becomes a real `Topic` row before anything references it (no free-text "Other" mechanism like Role/Field).
- New-Topic row + `UserTopicPreference` creation happens only at "Save preferences" time (batch), never eagerly at chip-click — confirmed directly with the user.
- `MAX_TOPICS = 4` (`services/preferences.py`) stays the single enforcement point and applies to the combined set of existing-id picks + new-name picks.
- `_topic_popularity`'s candidate list (`services/profile.py`) filters to `status='approved'` only and carries `Topic.name` (today: `topic_id` + `selection_count` only).
- `suggestions/` stays DB-free (AD-3) — `services/profile.py` queries popularity + approved-topic names and passes plain data in; the adapter never touches the DB.
- New-Topic creation reuses `add_topic`'s existing get-or-create-by-exact-name idempotency unchanged (whitespace-strip only) — no fuzzy matching.
- Merged suggestion-grid display cap (existing + new candidates) is 10, matching `ROLE_SUGGESTION_CAP`'s convention.
- Schema change ships as a new Alembic revision (down_revision = current head `e5f6a7b8c9d0`), following the project's existing convention — not `create_all`.
- A newly-created Topic's `status` defaults to `pending` (`add_topic`'s existing default param stays `STATUS_APPROVED` for the admin/seed path; the new-topic-suggestion call site passes `STATUS_PENDING` explicitly) — it is invisible to every other user's candidate list by construction (the `status='approved'` filter), with no further gating logic needed in this spec.
- A user's own `GET /me/preferences` keeps showing any `pending` Topic they are personally subscribed to, by name — status only gates visibility to *other* users.

**Ask First:** none identified — design fully confirmed with the user via `bmad-spec` (SPEC.md, zero open questions remaining) and this token-budget split.

**Never:** build the admin approve/reject endpoint or UI (deferred, separate spec); un-reject a rejected Topic (no rejection path exists yet either — out of scope here); fuzzy/near-duplicate Topic-name merging; change the `MAX_TOPICS` cap value; change Role/Field/`PendingTaxonomySuggestion` flow (untouched, separate mechanism).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Existing Topic + invented new names, both under cap | LLM ranks 2 approved Topics relevant, invents 3 new names | Step 3 shows 5 suggestion pills (2 existing + 3 new), merged | N/A |
| Suggested new name duplicates an approved Topic (case/whitespace) | LLM invents "ai" when "AI" (approved) exists | Deduped — only the existing "AI" pill shown, not a duplicate | N/A |
| User picks a new-name pill and saves | `new_topic_names: ["Quantum Computing"]` in save payload | `Topic(name="Quantum Computing", status="pending")` created (get-or-create), `UserTopicPreference` created for that user | N/A |
| Save would exceed cap once new-name picks resolve to ids | 3 existing ids + 2 new names, all distinct | 400 `TopicCapExceededError`, same as today's over-cap save | Existing `TopicCapExceededError` path, unchanged shape |
| Suggestion computation fails (LLM unreachable) | `SuggestionError` from either adapter method | `suggestion_status='failed'`; Step 3 falls back to current-subscriptions-first (today's existing fallback), unchanged | Caught in `_compute_and_store_suggestions`, same as today |
| Another user's candidate list, Topic still pending | User B's suggestion computation runs while User A's invented Topic is still `pending` | User B's candidates never include it | N/A |
| Migration runs against existing data | 3 seeded Topics, no `status` column yet | All 3 default to `approved`; zero behavior change for existing users | N/A |

</frozen-after-approval>

## Code Map

- `src/newsagent/models/topic.py` -- add `status: Mapped[str]` column (mirrors `Source.status` shape); add `STATUS_PENDING`/`STATUS_APPROVED`/`STATUS_REJECTED` constants (rejected unused by this spec, defined now so the follow-up admin spec doesn't need another migration)
- `alembic/versions/<new>.py` -- add `topics.status` column (`nullable=False, server_default="approved"`) and `users.suggested_new_topic_names` JSON column (nullable), down_revision=`e5f6a7b8c9d0` (current head)
- `src/newsagent/services/sources.py` -- `add_topic` gains `status: str = STATUS_APPROVED` param (admin/seed path unaffected; new-topic-suggestion path passes `STATUS_PENDING` explicitly)
- `src/newsagent/suggestions/types.py` -- new `TopicOption(name: str)` frozen dataclass (mirrors `RoleOption`) for invented new-topic proposals; `TopicPopularity` gains a `name: str` field (today: `topic_id` + `selection_count` only) so both adapter methods can see topic names
- `src/newsagent/suggestions/base.py`, `llm.py`, `popularity.py` -- new abstract method `suggest_new_topics(*, field_name, role_name, interest_free_text, existing_topic_names) -> list[TopicOption]`; `popularity.py` returns `[]` (signature-only, mirrors its `suggest_roles`/`suggest_prompts` stance); `llm.py` prompts for names not duplicating `existing_topic_names`
- `src/newsagent/services/profile.py` -- `_topic_popularity` filters `Topic.status == STATUS_APPROVED` and returns `(topic_id, name, selection_count)`; `_compute_and_store_suggestions` also calls `suggest_new_topics(...)`, dedupes new names against approved names (case/whitespace-insensitive), caps merged total at 10, stores into two columns; `suggest_prompts_for_user` untouched
- `src/newsagent/models/user.py` -- new `suggested_new_topic_names: Mapped[list[str] | None]` (JSON) column, alongside existing `suggested_topic_ids`
- `src/newsagent/services/preferences.py` -- `set_preferences` gains `new_topic_names: list[str] = ()` param: resolves each via `sources.add_topic(db, name, status=STATUS_PENDING)`, folds resulting ids into `desired` before the existing cap/known-id checks (so cap counts the combined set correctly)
- `src/newsagent/api/schemas/preference.py` -- `PreferenceUpdateIn` gains `new_topic_names: list[str] = []`
- `src/newsagent/api/schemas/profile.py` -- `TopicSuggestionsOut` gains `suggested_new_topic_names: list[str] | None`
- `src/newsagent/api/routers/me.py` -- `update_my_preferences` passes `body.new_topic_names` through to `set_preferences`
- `frontend/src/api/client.ts` -- `TopicSuggestions` type gains `suggestedNewTopicNames: string[] | null`; save payload gains `newTopicNames: string[]`
- `frontend/src/components/profile-picker/TopicsStep.vue` -- render merged existing+new pills; track picks as a small tagged union (`{kind:'existing', topicId} | {kind:'new', name}`) instead of `number[]`; FIFO-swap logic and cap counter operate over the combined array; save call sends both `topicIds` and `newTopicNames`

## Tasks & Acceptance

**Execution:**
- [x] `models/topic.py`, `models/user.py` + new Alembic revision -- add `Topic.status` (default `approved`) + `STATUS_*` constants + `User.suggested_new_topic_names` JSON column
- [x] `services/sources.py` -- `add_topic` gains `status` param -- reuse idempotent get-or-create
- [x] `suggestions/types.py`, `base.py`, `llm.py`, `popularity.py` -- `TopicOption` + `suggest_new_topics` across the contract
- [x] `services/profile.py` -- filter `_topic_popularity` to approved+name, merge+dedupe+cap new proposals in `_compute_and_store_suggestions`
- [x] `services/preferences.py` -- `set_preferences` resolves `new_topic_names` to real ids before cap check
- [x] `api/schemas/preference.py`, `profile.py` -- wire new fields
- [x] `api/routers/me.py` -- pass `new_topic_names` through
- [x] `frontend/src/api/client.ts`, `TopicsStep.vue` -- merged pill rendering, tagged-union picks, save payload
- [x] Tests: `services/preferences.py` (new-name resolution + cap), `services/profile.py` (approved-only filter, merge/dedupe/cap of new proposals), `services/sources.py` (`add_topic` status param), `suggestions/llm.py` contract test for `suggest_new_topics`, `api/routers/test_me.py` (save with new names)

**Acceptance Criteria:**
- Given a Field/Role/Interest profile with 2 approved Topics ranked relevant and 3 new names invented, when the user reaches Step 3, then up to 10 merged pills show (existing shown by real id, new by name only).
- Given the user picks a new-name pill and clicks Save preferences, then a `Topic(status='pending')` row and a `UserTopicPreference` exist for that user, and `GET /me/preferences` reflects it.
- Given a Topic is `pending`, when a different user's suggestions are computed, then that Topic never appears in their candidate list.
- Given the local LLM is unreachable, then Step 3 behaves exactly as it does today (current-subscriptions-first fallback) — no error surfaced.
- Given the migration runs, then all 3 existing seeded Topics have `status='approved'` and every existing preferences/suggestion behavior is unchanged.

## Spec Change Log

- `frontend/src/api/client.ts`'s `TopicSuggestions.suggested_new_topic_names` field was named in snake_case, not the Code Map's `suggestedNewTopicNames`. `TopicSuggestions` is a raw pass-through type for `GET /me/topic-suggestions`'s JSON body (unlike `RoleOption`, which has a manual snake->camel mapper in `listRoles()`) — the existing `suggestion_status`/`suggested_topic_ids` fields on this same interface are already snake_case for the same reason. Using the Code Map's literal camelCase name would have silently never matched the real response key. `updateMyPreferences`'s new `newTopicNames` parameter is camelCase as specified, since that's just a TS parameter name serialized into a `new_topic_names` JSON key in the request body, consistent with `topicIds`/`topic_ids`.
- `services/preferences.py`'s `set_preferences` types `new_topic_names` as `Sequence[str] = ()` rather than the Code Map's literal `list[str] = ()` — `list[str]` can't default to a tuple under mypy. The router still passes a `list[str]` (from Pydantic), which satisfies `Sequence[str]`.
- Fixed during review, outside the original Code Map's file list: `services/preferences.py:list_topic_choices` (used by `GET /me/preferences`) listed every `Topic` row regardless of `status`. Before this spec that was harmless (every Topic was implicitly approved); this feature made it a real leak — a `pending` Topic created by one user was included in the raw list returned to *every* user, and `TopicsStep.vue`'s failed-suggestion fallback grid renders exactly that raw list as pickable chips, so another user's still-pending Topic could appear there — violating the "pending Topic stays invisible to everyone except its creator" boundary (CAP-3). Fixed by filtering `list_topic_choices` to `status == STATUS_APPROVED` topics plus any topic the requesting user is already subscribed to (their own pending/rejected pick stays visible, per the spec's explicit boundary). Added `test_list_topic_choices_hides_other_users_pending_topic` and `test_list_topic_choices_shows_own_pending_topic` to `tests/services/test_preferences.py`.
- **Review loop (step-04, 2026-07-31): 2 patch findings, both `patch`-triaged and auto-fixed (no `intent_gap`/`bad_spec` — no loopback needed).**
  - `services/preferences.py::set_preferences` created and committed new `Topic(status='pending')` rows *before* checking the `MAX_TOPICS` cap — a rejected over-cap save left orphan pending rows in the DB, and an unbounded `new_topic_names` list was an unbounded-row-creation vector. Fixed: the cap (on deduped, pre-resolution counts) and a new per-name `MAX_NAME_LENGTH = 100` check (mirroring `services/profile.py`'s existing convention) now run before any `Topic` row is created. Added `test_set_preferences_over_cap_new_names_create_no_orphan_topics`, `test_set_preferences_oversized_new_name_list_creates_no_topics`, `test_set_preferences_new_name_too_long_raises`, `test_set_preferences_duplicate_ids_in_topic_ids_not_double_counted`.
  - `TopicsStep.vue`'s "ready" branch was gated on pre-filter suggestion-list lengths, but chips were then filtered by local name resolution — a suggested id that didn't resolve locally could pass the non-empty check and still render an empty grid, breaking the FR-9 non-empty guarantee. Fixed: the ready/fallback branch now checks the post-filter chip count.
  - KEEP: the approved-only filtering in `_topic_popularity`/`list_topic_choices`, the merge/dedupe/cap logic in `_compute_and_store_suggestions`, and the `suggest_new_topics` adapter contract all reviewed clean — preserve as-is on any future re-derivation.
  - 3 findings triaged `defer` (pre-existing patterns/spec-endorsed tradeoffs, not this story's fix) logged to `deferred-work.md`'s 2026-07-31 entry: cross-user near-duplicate pending Topic names, `add_topic`'s TOCTOU race now reachable from concurrent user saves, and no de-dup on `suggested_topic_ids` before truncation.
- **Post-completion fix (2026-07-31), found via the spec's own "Manual" verification step run live by the human:** the dogfood user saw only their 3 existing subscriptions with no new invented topics. Root cause: this story added a second sequential LLM call (`suggest_new_topics`, after `suggest_topics`) to the same background computation `TopicsStep.vue` polls for, but `MAX_POLL_ATTEMPTS`'s ~8s budget was never widened to match — measured ~25s combined against the real configured OpenRouter model. A too-short poll budget doesn't error, it silently falls back to the current-subscriptions view, indistinguishable from the feature not working. Fixed: `TopicsStep.vue`'s poll budget raised to ~45s. Verified: backend computation itself confirmed correct by manually re-running `_compute_and_store_suggestions` against the live dev DB and LLM (produced 6 relevant invented Design-adjacent topic names for the reporting user); `npm run type-check` clean after the fix.
  - Full spec verification suite re-run after both patches: `alembic upgrade head` clean, `pytest` 155 passed, `mypy`/`ruff` clean, frontend `type-check` clean.

## Design Notes

**Why a second adapter method (`suggest_new_topics`) instead of overloading `suggest_topics`'s return type:** mirrors the Role/Prompt story's established pattern exactly — Role has `suggest_roles` (LLM-invented names only) merged with curated DB data by the *service* layer (`taxonomy.py:suggest_roles_for_field`), not by the adapter. Applying the same split here means `TopicSuggestion(topic_id: int)` never needs an optional/nullable id, and the two result kinds (existing pick vs. new proposal) are distinguished by which list they came from, not by a runtime flag.

**Why `suggested_new_topic_names` is a new column, not a reshaped `suggested_topic_ids`:** `suggested_topic_ids` is an established AD-7 column (`JSON`, `list[int]`) already read by other code paths; splitting instead of reshaping keeps that contract stable and additive.

**Why `STATUS_REJECTED` is defined now even though nothing sets it yet:** the column and constant are one-time schema/model cost; defining all three states now means the deferred admin-approval follow-up needs no further migration, only new endpoints.

## Verification

**Commands:**
- `alembic upgrade head` -- expected: migration applies cleanly against the existing dev DB (3 Topics -> `approved`)
- `pytest tests/services/test_preferences.py tests/services/test_profile.py tests/services/test_profile_suggestions.py tests/services/test_sources.py tests/suggestions tests/api/routers/test_me.py` -- expected: all pass
- `mypy` / `ruff check` -- expected: clean on all changed files
- Frontend: `npm run type-check` -- expected: clean
- Manual: run the wizard as two differently-profiled users with `NEWSAGENT_SUGGESTION_PROVIDER=llm`; confirm Step 3 suggestions differ between them and aren't just an echo of current subscriptions; pick a new topic, save, confirm it persists via `GET /me/preferences`.

## Suggested Review Order

**Status model & migration**

- Entry point: the `status` column + `STATUS_*` constants everything else keys off.
  [`topic.py:16`](../../src/newsagent/models/topic.py#L16)

- New Alembic revision -- `topics.status` default `approved`, `users.suggested_new_topic_names` column.
  [`a4b5c6d7e8f9_topic_status_and_new_topic_suggestions.py`](../../alembic/versions/a4b5c6d7e8f9_topic_status_and_new_topic_suggestions.py#L1)

- `add_topic` now takes a `status` param -- admin/seed path stays `approved`, new call site passes `pending`.
  [`sources.py:33`](../../src/newsagent/services/sources.py#L33)

**Suggestion contract (adapter surface)**

- New result types: `TopicOption` for invented names, `TopicPopularity` gains `name` so adapters can reason about topics.
  [`types.py:27`](../../src/newsagent/suggestions/types.py#L27)

- New abstract method mirrors `suggest_roles`'s existing split-contract shape.
  [`base.py:77`](../../src/newsagent/suggestions/base.py#L77)

- The real adapter: prompts for names not duplicating `existing_topic_names`, no output-length validation (deferred finding).
  [`llm.py:189`](../../src/newsagent/suggestions/llm.py#L189)

- Fallback adapter returns `[]` -- no invention without a real LLM, matches `suggest_roles`/`suggest_prompts`'s existing stance.
  [`popularity.py:52`](../../src/newsagent/suggestions/popularity.py#L52)

**Merge, dedupe, and cap (the computation this whole feature hinges on)**

- Filters to `approved` only and carries `name` -- the fix that lets the LLM reason about candidates it previously saw only as opaque ids.
  [`profile.py:235`](../../src/newsagent/services/profile.py#L235)

- Calls both adapter methods, dedupes invented names against approved names case/whitespace-insensitively, caps the merged total at 10.
  [`profile.py:263`](../../src/newsagent/services/profile.py#L263)

**Save-time creation, cap enforcement, and the two review-loop fixes**

- Own-user-visibility fix: `pending`/`rejected` Topics only show to their creator, closing a leak the original diff missed.
  [`preferences.py:47`](../../src/newsagent/services/preferences.py#L47)

- Review-loop fix: cap and name-length checks now run before any Topic row is created -- a rejected save no longer leaves orphan rows, and an oversized name list can no longer spam the table.
  [`preferences.py:61`](../../src/newsagent/services/preferences.py#L61)

**API wiring**

- Request/response shape for the new `new_topic_names` field.
  [`preference.py:12`](../../src/newsagent/api/schemas/preference.py#L12)

- Suggestion polling response gains `suggested_new_topic_names`.
  [`profile.py:22`](../../src/newsagent/api/schemas/profile.py#L22)

- Passes `body.new_topic_names` through -- the one-line router change everything else supports.
  [`me.py:29`](../../src/newsagent/api/routers/me.py#L29)

**Frontend**

- Raw pass-through type -- deliberately snake_case to match the real JSON key (a Code Map deviation, logged above).
  [`client.ts:57`](../../frontend/src/api/client.ts#L57)

- Save now sends `newTopicNames` alongside `topicIds`.
  [`client.ts:123`](../../frontend/src/api/client.ts#L123)

- Tagged-union pick type replaces `number[]` -- a "new" pick has no id until save resolves it.
  [`TopicsStep.vue:75`](../../frontend/src/components/profile-picker/TopicsStep.vue#L75)

- Review-loop fix: ready/fallback branch now checks post-filter chip count, not pre-filter suggestion-list length.
  [`TopicsStep.vue:153`](../../frontend/src/components/profile-picker/TopicsStep.vue#L153)

- FIFO-swap toggle logic now operates over the merged existing+new chip array.
  [`TopicsStep.vue:119`](../../frontend/src/components/profile-picker/TopicsStep.vue#L119)

**Tests**

- Leak-prevention and cap-ordering regression tests added during review.
  [`test_preferences.py:65`](../../tests/services/test_preferences.py#L65)

**Post-completion fix: polling budget vs. two sequential LLM calls**

- Poll budget widened ~8s -> ~45s to match this story's new second sequential LLM call, found via live manual testing.
  [`TopicsStep.vue:63`](../../frontend/src/components/profile-picker/TopicsStep.vue#L63)
