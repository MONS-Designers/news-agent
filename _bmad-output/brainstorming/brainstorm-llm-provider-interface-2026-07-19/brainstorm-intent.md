# Intent: LLM Provider Interface (issue #5)

## Context
A swappable provider abstraction for the news-agent pipeline: one uniform contract over any LLM (or non-LLM) backend, with a deterministic mock as a first-class implementation. Three "employers" hire it: the pipeline hires it as a trustworthy editor (editorial judgment in Hebrew), developers hire it to decouple dev velocity from LLM dependency (the mock is the product), and tests hire it for determinism (identical results every run).

## Decisions

Winning shape (morphological combo A-B-B-C-C):
- Two methods: `summarize` and `score_relevance`.
- Dedicated input dataclass (not loose args).
- Structured typed result dataclasses, each carrying a usage report.
- Sync interface with a door left open for async later.
- Hybrid retry: adapter retries transient errors internally with backoff, then raises a typed error; pipeline sees uniform success / failure / retry outcomes.

MoSCoW (approved):
- **Must**
  - Two methods (summarize, score_relevance).
  - Dedicated input dataclass.
  - Structured result dataclasses (e.g., SummaryResult: summary_he, source language, reading time, translated title).
  - Error hierarchy classified by origin (context/input vs LLM/provider vs transport/infra).
  - Hybrid retry (internal transient retry with backoff, then typed error).
  - One calibrated relevance score scale with semantic anchor points.
  - Deliberately boring, fully deterministic mock provider (same input, same output).
  - Abstract contract test suite every adapter (including mock) must pass.
- **Should**
  - Optional usage report in neutral units (token counts are an LLM assumption).
  - Explicit refusal channel, distinct from failure.
  - Documented rule: article content is data, not instructions.
- **Could**
  - Batch scoring (with a default loop implementation).
  - Optional user preference-history parameter on score_relevance (personalization hook).
  - Documented purity property enabling caching adapters.
- **Won't** (this issue)
  - Faithfulness/hallucination judge; per-run cost cap enforcement; personalization/learning; async implementation; real provider adapter; smart cost-based model router (solved via per-task model config, not the contract).

## Contract principles
- Contract speaks domain language, not LLM language; no LLM assumptions may leak in (a non-LLM impostor implementation must be able to comply).
- Article content is data, not instructions: adapters must structurally separate instructions from content (prompt-injection defense).
- Input is clean plain text only; media/broken-content handling is out of provider scope.
- Relevance scores share one calibrated scale with semantic anchors defined by the contract; the threshold lives in pipeline config, not the contract.
- Purity is a contract property: same input yields same output class of behavior, making caching adapters legal.
- Explicit refusal (provider declines to summarize/score bad content) is a distinct outcome, not a failure.
- Errors are classified by origin (context/input, LLM/provider, transport/infra), each with its own handling policy; callers always see a uniform outcome: success / failure / retry. End users are never exposed to raw provider errors.
- Usage is reported in neutral, optional units - never mandated token counts.
- Provider output parsing is adapter-internal; the contract only exposes typed results.

## Open questions deferred
- Faithfulness verification of summaries: a future optional pipeline stage (cheap heuristic / LLM judge on sample / human review) - the contract must not block it, but it is not a provider obligation.
- Cost cap enforcement and spend reporting policy: issue #19 (usage field here is the enabler only).
- Personalization/learning beyond the optional preference-history hook on score_relevance.
- Async variant of the interface.
- First real provider adapter (mock only in this issue).
