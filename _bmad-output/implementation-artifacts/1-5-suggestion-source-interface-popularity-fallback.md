---
baseline_commit: 352409a
---

# Story 1.5: Suggestion Source interface + always-available popularity fallback

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to always receive topic suggestions, even if my Role doesn't match anything curated yet,
so that I'm never left with an empty starting point.

*Realizes FR9, NFR1 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.3, §4.1).*

## Acceptance Criteria

1. **Given** the `newsagent/suggestions/` package does not yet exist, **when** this story is implemented, **then** it contains an ABC (`SuggestionSource`) with template-method retry mirroring `llm/base.py`'s shape, frozen-dataclass typed contracts (`types.py`), and a factory (`factory.py`) keyed by a new `NEWSAGENT_SUGGESTION_PROVIDER` setting.
2. **Given** the MVP configuration, **when** the factory resolves a provider, **then** it returns a `PopularitySuggestionSource` implementing only `suggest_topics` - `suggest_roles` and `suggest_prompts` return empty results.
3. **Given** a user has no Field/Role set, or an "Other" Role with no promoted match, **when** `suggest_topics` is called for them, **then** it returns a non-empty candidate list drawn from cross-user Topic-selection popularity, queried by the calling service and passed in as plain data - the provider itself makes no DB queries.
4. **Given** two different users with no profile match, **when** they each request suggestions, **then** they may receive the same generally-popular candidate set - expected and correct for a fallback.

## Tasks / Subtasks

- [x] Task 1: `newsagent/suggestions/errors.py` (AC: #1)
  - [x] 1.1 Mirrors `llm/errors.py` exactly: `SuggestionError(Exception)` base with a class-level `transient: bool = False`; `SuggestionInputError(SuggestionError)`; `SuggestionProviderError(SuggestionError)`; `SuggestionTransportError(SuggestionError)` with `transient = True`.

- [x] Task 2: `newsagent/suggestions/types.py` (AC: #1)
  - [x] 2.1 Frozen-dataclass domain contracts, mirroring `llm/types.py`'s style: `RoleOption(name: str)`, `PromptText(text: str)`, `TopicPopularity(topic_id: int, selection_count: int)`, `TopicSuggestion(topic_id: int)`.
  - [x] 2.2 No `Usage` field - no analog applies to a popularity lookup or (eventually) role/prompt generation.

- [x] Task 3: `newsagent/suggestions/base.py` - `SuggestionSource` ABC (AC: #1)
  - [x] 3.1 Same `__init__`/`_run` retry loop as `llm/base.py:LLMProvider`, importing from `newsagent.suggestions.errors`/`types` instead.
  - [x] 3.2 Public template methods: `suggest_roles`, `suggest_prompts`, `suggest_topics(*, field_name, role_name, interest_free_text, popularity)` - all three profile fields accepted now so the interface is already shaped for a future `LLMSuggestionSource` (NFR1); `PopularitySuggestionSource` ignores them.
  - [x] 3.3 Matching `@abstractmethod` adapter-surface methods.

- [x] Task 4: `newsagent/suggestions/popularity.py` - `PopularitySuggestionSource` (AC: #2, #3, #4)
  - [x] 4.1 `_suggest_roles`/`_suggest_prompts` return `[]`.
  - [x] 4.2 `_suggest_topics` ignores `field_name`/`role_name`/`interest_free_text`; stable-sorts `popularity` by `selection_count` descending; returns `[TopicSuggestion(topic_id=p.topic_id) for p in ranked]`.
  - [x] 4.3 No 4-cap here (that's Story 1.7/AD-9); zero-`selection_count` entries are kept, not filtered.

- [x] Task 5: `newsagent/suggestions/factory.py` + `config.py` (AC: #1, #2)
  - [x] 5.1 `config.py`: `suggestion_provider: str = "popularity"` added next to `llm_provider`, same `NEWSAGENT_` prefix.
  - [x] 5.2 `factory.py`: `get_suggestion_source()` resolves `settings.suggestion_provider`, `ValueError` with known-providers list on unrecognized value - same shape as `llm/factory.py`.

- [x] Task 6: `newsagent/suggestions/__init__.py` (AC: #1)
  - [x] 6.1 Flat `__all__` export of all types/errors/`SuggestionSource`/`PopularitySuggestionSource`/`get_suggestion_source`, mirroring `llm/__init__.py`.

- [x] Task 7: Tests (AC: all)
  - [x] 7.1 `tests/suggestions/__init__.py` (empty package marker).
  - [x] 7.2 `tests/suggestions/test_factory.py` - default provider is `PopularitySuggestionSource`; unknown value raises `ValueError` matching the bad value.
  - [x] 7.3 `tests/suggestions/test_popularity.py` - empty roles/prompts; non-empty ranked `suggest_topics` result from representative `TopicPopularity` fixtures; profile-agnostic (same result regardless of field/role/interest text - AC #4); zero-`selection_count` candidates kept; empty `popularity` input returns empty (not this provider's job to manufacture non-emptiness); retry mechanics via a minimal local `_FlakySource` test double exercising `base.py`'s shared `_run` loop.
  - [x] 7.4 Full suite green: 207 passed (12 new on top of the 195 baseline); `mypy` and `ruff` clean.

## Dev Notes

### Read these before writing code

- [`src/newsagent/llm/base.py`](../../src/newsagent/llm/base.py), [`types.py`](../../src/newsagent/llm/types.py), [`errors.py`](../../src/newsagent/llm/errors.py), [`factory.py`](../../src/newsagent/llm/factory.py), [`mock.py`](../../src/newsagent/llm/mock.py), [`__init__.py`](../../src/newsagent/llm/__init__.py) - the shape `newsagent/suggestions/` mirrors, file-for-file.
- [`src/newsagent/config.py`](../../src/newsagent/config.py) - `llm_provider`'s placement and the `NEWSAGENT_` env-prefix convention.
- [`tests/llm/provider_contract.py`](../../tests/llm/provider_contract.py), [`test_factory.py`](../../tests/llm/test_factory.py), [`test_mock_contract.py`](../../tests/llm/test_mock_contract.py) - the test shape mirrored (without building a reusable cross-adapter contract-suite class - premature with only one real adapter today).
- [`src/newsagent/models/topic.py`](../../src/newsagent/models/topic.py), [`user_topic_preference.py`](../../src/newsagent/models/user_topic_preference.py) - for context only, not touched. `TopicPopularity` is shaped for a future `SELECT topic_id, COUNT(*) FROM user_topic_preferences GROUP BY topic_id` (Story 1.6's job).

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-3** - `suggestions/` is a sibling package to `llm/`; neither imports the other. Selected by `NEWSAGENT_SUGGESTION_PROVIDER`. Providers never touch the DB - `TopicPopularity` is the "plain arguments" shape AD-3 requires.
- **NFR1** - the ABC's three-method shape exists now so a future `LLMSuggestionSource` swap requires no UI/API/data-model rework.
- **No AD-1 implications** - no router, no service function added; `services/profile.py` doesn't call `get_suggestion_source()` yet (Story 1.6).
- **No AD-4 implications** - no schema change.

### Explicit scope boundary

- `services/profile.py` untouched - no `BackgroundTask`, no `GET /me/topic-suggestions`, no `User.suggestion_status`/`suggested_topic_ids`/`suggestion_request_seq` (Story 1.6, AD-5/AD-7).
- No query against `user_topic_preferences` written here - `TopicPopularity` instances in tests are hand-built fixtures.
- No admin/API surface reachable from any endpoint yet.
- No reusable cross-adapter contract-suite test class built (premature for one real adapter).

### Project Structure Notes

- New backend files: `src/newsagent/suggestions/__init__.py`, `base.py`, `types.py`, `errors.py`, `factory.py`, `popularity.py`; `tests/suggestions/__init__.py`, `test_factory.py`, `test_popularity.py`.
- Changed backend files: `src/newsagent/config.py` (+ `suggestion_provider`).
- No frontend changes. No migration. No new dependencies.

### References

- [Source: epics.md#Story-1.5] - acceptance criteria, verbatim.
- [Source: prd-news-agent-2026-07-21/addendum.md § "Suggestion Source: pluggable abstraction (technical shape)"] - the `suggest_roles`/`suggest_prompts`/`suggest_topics` sketch this story formalizes.
- [Source: ARCHITECTURE-SPINE.md#AD-3, #NFR1, Structural-Seed, Dependency-direction] - sibling-package rule, `llm/`-mirroring shape, `profile → suggestions` (not yet wired) edge.
- [Source: 1-4-optional-interest-free-text-step-2.md] - most recent prior story; unrelated surface, no shared files.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- No migration, no server restart, no browser needed - a pure backend package addition, fully covered by the unit-test suite. `PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q` → 207 passed; `mypy src` and `ruff check .` both clean.

### Completion Notes List

**All 7 tasks complete.** 207 backend tests pass (12 added on top of the 195 baseline); `mypy` and `ruff` clean.

- AC #1 - `newsagent/suggestions/` contains `base.py` (ABC + `_run` retry loop copied from `llm/base.py`'s mechanics), `types.py` (4 frozen dataclasses), `errors.py` (4-class hierarchy), `factory.py` (`NEWSAGENT_SUGGESTION_PROVIDER`-keyed).
- AC #2 - `get_suggestion_source()` returns `PopularitySuggestionSource` by default (`test_default_provider_is_popularity`); its `_suggest_roles`/`_suggest_prompts` return `[]` (`test_suggest_roles_returns_empty`, `test_suggest_prompts_returns_empty`).
- AC #3 - `test_suggest_topics_with_no_profile_match_returns_non_empty_ranked_list` proves a non-empty, correctly-ranked result from hand-built `TopicPopularity` fixtures passed in as plain data; `PopularitySuggestionSource` contains no DB import.
- AC #4 - `test_suggest_topics_ignores_profile_data` proves two different profile inputs against the same popularity data produce an identical candidate set.

**Deliberately not done, per Dev Notes' explicit scope boundaries:**
- No wiring into `services/profile.py`, no endpoint, no BackgroundTask (Story 1.6).
- No real `user_topic_preferences` popularity query (Story 1.6).
- No reusable contract-suite test abstraction.

### File List

**New:**
- `src/newsagent/suggestions/__init__.py`
- `src/newsagent/suggestions/base.py`
- `src/newsagent/suggestions/types.py`
- `src/newsagent/suggestions/errors.py`
- `src/newsagent/suggestions/factory.py`
- `src/newsagent/suggestions/popularity.py`
- `tests/suggestions/__init__.py`
- `tests/suggestions/test_factory.py`
- `tests/suggestions/test_popularity.py`

**Changed:**
- `src/newsagent/config.py` (+ `suggestion_provider`)

## Change Log

- 2026-07-27: Story 1.5 implemented end-to-end - `newsagent/suggestions/` sibling package (ABC + retry, typed contracts, errors, factory, `PopularitySuggestionSource`), `NEWSAGENT_SUGGESTION_PROVIDER` config. 12 new tests (207 total). No migration, no frontend, no live-verification needed (pure backend unit-tested package, unreachable from any endpoint yet).
- 2026-07-27: Story 1.5 drafted. Purely backend, purely additive (new sibling package + one config field) - no migration, no router, no frontend, no wiring into `services/profile.py` (that's Story 1.6). Key design call: `TopicPopularity`/`TopicSuggestion` as typed contracts wrapping plain ints, matching `llm/types.py`'s domain-language convention rather than passing bare `int`/`tuple` through the interface.
