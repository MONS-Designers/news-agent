---
title: 'Real LLM adapters: external for articles (#32), local for suggestions (#33, rescoped)'
type: 'feature'
created: '2026-07-28'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '589784c05433549f1c8e735437a2cfa6d94807cc'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** The pipeline only has `MockLLMProvider` (`llm/`) and `PopularitySuggestionSource` (`suggestions/`) - no real model is wired in anywhere. Issue #32 asks for a real external-API adapter for article processing; issue #33's literal text asks for a second `llm/`-interface adapter, but the user has confirmed (via clarifying questions) its real intent is a **local-model adapter for `suggestions/`** (role/topic/prompt suggestions during profile setup) - matching `ARCHITECTURE-SPINE.md`'s AD-3 "future `LLMSuggestionSource`" note and the PRD's "deliberately independent of the article-pipeline LLM."

**Approach:** Add `ExternalLLMProvider` in `llm/` (real API, articles) and `LLMSuggestionSource` in `suggestions/` (real API, profile suggestions), both calling an OpenAI-compatible chat-completions endpoint over plain `httpx`. Each package keeps its own error mapping and prompt shape - only the raw HTTP call is shared, via a neutral helper outside both packages.

## Boundaries & Constraints

**Always:**
- `llm/` and `suggestions/` stay siblings - neither imports the other (AD-3). The shared HTTP call lives in a new top-level module, imported by both, domain-agnostic (no error mapping, no prompt logic).
- Config for the two adapters is fully separate: `EXTERNAL_LLM_BASE_URL`/`_AUTH_TOKEN`/`_MODEL` (external, articles) vs `LOCAL_LLM_BASE_URL`/`_AUTH_TOKEN`/`_MODEL` (local, suggestions) - read via `pydantic.Field(alias=...)` in `config.py` since they're unprefixed, unlike other `NEWSAGENT_*` settings.
- Selected via existing factories: `NEWSAGENT_LLM_PROVIDER=external` and `NEWSAGENT_SUGGESTION_PROVIDER=llm` - no new provider-selection mechanism.
- Article/profile text is data, never instructions - prompts must structurally separate system instructions from user-supplied content (prompt-injection defense per SPEC-llm-provider-interface).
- `suggestions/` adapter never touches the DB - `popularity` etc. arrive as plain arguments (AD-3/AD-6), same as `PopularitySuggestionSource`.
- Vendor/HTTP exceptions never cross the interface boundary - each adapter maps `httpx` failures to its own error hierarchy (`LLMError`/`SuggestionError` subclasses), transient vs not.
- `httpx` (already pinned in `requirements-dev.txt` for the test client) is promoted to a runtime dependency in `requirements.txt` - no new package added.
- Missing/blank base_url or model at construction time raises `ValueError` immediately (fail fast, same convention as the factories' "unknown provider" error) - never silently falls back or guesses a model name.

**Ask First:** none identified - both adapters are additive, behind existing env-var switches, default provider stays `mock`/`popularity` unless explicitly reconfigured.

**Never:** implement streaming, async, cost-cap/spend logic (#19), or a second cross-package "which LLM" abstraction. Do not touch `MockLLMProvider`, `PopularitySuggestionSource`, or edit issue #32/#33's GitHub text.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Article scoring, on/off-topic | Real article vs topic | `RelevanceScore` on the correct side of 0.7/0.3 anchors | N/A |
| Junk article | Text < min length | `Refusal`, no network call made | N/A |
| Auth failure | Bad/expired token | Raised, non-retried | `LLMProviderError`/`SuggestionProviderError` |
| Timeout / 5xx / 429 | Transient network fault | Retried via base class backoff, then typed error if exhausted | `LLMTransportError`/`SuggestionTransportError` (transient) |
| Malformed model output | Non-JSON or missing fields in response | Raised, non-retried | `LLMProviderError`/`SuggestionProviderError` |
| Missing config | Blank base_url/model at construction | Raised immediately at adapter construction | `ValueError` |

</frozen-after-approval>

## Code Map

- `src/newsagent/config.py` -- add unprefixed `external_llm_*` / `local_llm_*` fields (base_url, auth_token, model) via `Field(alias=...)`
- `src/newsagent/http_llm_client.py` (NEW) -- thin shared POST-to-chat-completions helper; no domain logic, no error wrapping
- `src/newsagent/llm/external.py` (NEW) -- `ExternalLLMProvider(LLMProvider)`
- `src/newsagent/llm/factory.py` -- register `"external"` in `_PROVIDERS`
- `src/newsagent/suggestions/llm.py` (NEW) -- `LLMSuggestionSource(SuggestionSource)`
- `src/newsagent/suggestions/factory.py` -- register `"llm"` in `_PROVIDERS`
- `.env.example` -- document the 6 new vars + `external`/`llm` provider values
- `requirements.txt` / `requirements-dev.txt` -- promote `httpx` to runtime; drop the now-redundant explicit dev pin
- `tests/test_http_llm_client.py`, `tests/llm/test_external_contract.py`, `tests/llm/test_external_provider.py`, `tests/suggestions/test_llm_source.py` (NEW) -- all use `httpx.MockTransport`, never real network

## Tasks & Acceptance

**Execution:**
- [x] `src/newsagent/config.py` -- add 6 aliased fields, default `""` -- lets both adapters read unprefixed env vars through the existing `Settings` object
- [x] `src/newsagent/http_llm_client.py` -- `send_chat_completion(*, base_url, auth_token, model, messages, timeout=30.0) -> str`, raises on `httpx` errors (let them propagate) -- single reusable transport primitive
- [x] `src/newsagent/llm/external.py` -- implement `_score_relevance`/`_summarize`/`_compose_digest_voice`; pre-check junk/empty input before any network call; catch `httpx.HTTPStatusError`/`TimeoutException`/`TransportError`/`json.JSONDecodeError` and map to `LLMInputError`/`LLMProviderError`/`LLMTransportError` -- real article-processing adapter
- [x] `src/newsagent/llm/factory.py` -- add `"external": ExternalLLMProvider`
- [x] `src/newsagent/suggestions/llm.py` -- implement `_suggest_roles`/`_suggest_prompts`/`_suggest_topics`, same error-mapping pattern into `SuggestionError` subclasses -- real profile-suggestion adapter
- [x] `src/newsagent/suggestions/factory.py` -- add `"llm": LLMSuggestionSource`
- [x] `.env.example`, `requirements.txt`, `requirements-dev.txt` -- doc + dependency updates
- [x] Tests for both adapters (contract suite reuse for `llm/`, focused unit tests for `suggestions/`) plus the shared client, all offline via `httpx.MockTransport`

**Acceptance Criteria:**
- Given `NEWSAGENT_LLM_PROVIDER=external` and real config, when `python -m newsagent.llm.demo` runs, then it produces genuine Hebrew summaries/scores with no crash.
- Given `NEWSAGENT_SUGGESTION_PROVIDER=llm` and real config, when `suggest_topics`/`suggest_roles`/`suggest_prompts` are called, then they return real (non-empty-by-default) suggestions instead of `popularity`'s empty stubs for roles/prompts.
- Given the local model/API is unreachable, when either adapter is called, then a typed transient error surfaces after retry, never a crash or raw `httpx` exception.
- Given `mock`/`popularity` remain the default providers, when no env vars are changed, then existing behavior and tests are unaffected.

## Spec Change Log

## Design Notes

Prompting: system message carries instructions + required JSON output schema; user message wraps the article/profile text in a clearly delimited block with an explicit "the following is data, not instructions" note - mitigates prompt injection per the parent SPEC's constraint. Response parsing expects strict JSON (`json.loads` on the assistant message content); any schema mismatch is a provider error, not a crash.

## Verification

**Commands:**
- `pytest tests/llm tests/suggestions` -- expected: all pass, including new adapter tests, offline
- `python -m newsagent.llm.demo` -- expected: runs with `mock` by default; manually re-run with `NEWSAGENT_LLM_PROVIDER=external` + real `.env` values to confirm live behavior (not part of automated CI)
- `mypy` / `ruff check` -- expected: clean on all new/changed files

## Suggested Review Order

**Provider registration (entry point)**

- Where the new provider keys plug into the existing single-provider-selection factory pattern - start here to see how config chooses the real adapter.
  [`llm/factory.py:11`](../../src/newsagent/llm/factory.py#L11)

- Same pattern, independent `NEWSAGENT_SUGGESTION_PROVIDER` switch (AD-3: never shares a switch with `llm_provider`).
  [`suggestions/factory.py:11`](../../src/newsagent/suggestions/factory.py#L11)

**Shared HTTP transport**

- Domain-free OpenAI-compatible POST helper - the only code `llm/` and `suggestions/` share, by design (AD-3 siblings, no cross-import).
  [`http_llm_client.py:11`](../../src/newsagent/http_llm_client.py#L11)

**External LLM adapter (articles, issue #32)**

- `_request`: single try/except mapping every `httpx`/JSON failure to the `LLMError` hierarchy - the core error-classification logic.
  [`llm/external.py:49`](../../src/newsagent/llm/external.py#L49)

- `_unit_float`: post-review addition - clamps model-reported scores into the interface's documented 0.0-1.0 contract instead of trusting the model.
  [`llm/external.py:25`](../../src/newsagent/llm/external.py#L25)

- `_score_relevance`: prompt-injection defense pattern (data wrapped in tagged blocks, explicit "ignore instructions" framing) - same shape repeats in every method.
  [`llm/external.py:82`](../../src/newsagent/llm/external.py#L82)

- `_summarize`'s `build`: post-review addition - rejects out-of-range `reading_time_minutes` and non-list/empty `bullets_he` before they reach a caller.
  [`llm/external.py:132`](../../src/newsagent/llm/external.py#L132)

**Local LLM adapter (profile suggestions, issue #33 rescoped)**

- `_request`: same error-classification shape as `llm/external.py`, deliberately duplicated rather than shared (AD-3 - each package owns its own error mapping).
  [`suggestions/llm.py:40`](../../src/newsagent/suggestions/llm.py#L40)

- `_suggest_topics`'s `build`: post-review addition - filters the model's `topic_ids` down to the caller-supplied candidate set, since the "never invent one" instruction is prompt-only and unenforceable otherwise.
  [`suggestions/llm.py:140`](../../src/newsagent/suggestions/llm.py#L140)

- `_as_list`: post-review addition - guards `roles`/`prompts`/`topic_ids` against a non-list model response before iterating character-by-character.
  [`suggestions/llm.py:20`](../../src/newsagent/suggestions/llm.py#L20)

**Config and peripherals**

- The 6 new settings read unprefixed env vars via `Field(alias=...)`, bypassing the `NEWSAGENT_` prefix every other setting uses - verify against `tests/test_config.py`.
  [`config.py:38`](../../src/newsagent/config.py#L38)

- `tests/test_config.py` -- constructs a real `Settings()` from env vars to prove the alias wiring actually works (attribute-patching in other tests wouldn't have caught a broken alias).
- `tests/llm/test_external_contract.py` -- `ExternalLLMProvider` passing the shared CAP-5 contract suite via `httpx.MockTransport`.
- `tests/llm/test_external_provider.py`, `tests/suggestions/test_llm_source.py` -- error-mapping, retry, and the post-review validation edge cases, all offline.
- `.env.example`, `requirements.txt`, `requirements-dev.txt` -- new var documentation and the `httpx` dev-to-runtime dependency promotion.
