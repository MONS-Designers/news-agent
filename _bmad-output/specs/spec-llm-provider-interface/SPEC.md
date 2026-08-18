---
id: SPEC-llm-provider-interface
companions: [scope.md]
sources: [../../brainstorming/brainstorm-llm-provider-interface-2026-07-19/brainstorm-intent.md]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only - consult them only if you need narrative rationale or prose color this contract intentionally omits.

# LLM Provider Interface (issue #5)

## Why

A mandate from the project backlog plus a pain to prevent: every content-pipeline stage (relevance filtering, Hebrew summarization) needs LLM judgment, and hardcoding a vendor would couple pipeline velocity, cost, and correctness to one provider. Three "employers" hire this interface: the pipeline hires an *editor* (trustworthy editorial judgment in Hebrew), developers hire *independence* (build the whole pipeline with no API key, cost, or network - the mock is the product), and tests hire *determinism* (identical results every run). The contract must serve all three at once.

## Capabilities

- **CAP-1**
  - **intent:** Pipeline can score an article's relevance to a topic through the provider contract, on one calibrated 0.0–1.0 scale with contract-defined semantic anchors (≥0.7 clearly on-topic, ≤0.3 clearly off-topic).
  - **success:** Contract tests feed a clearly on-topic and a clearly off-topic article; every adapter returns scores on the correct side of the anchors. Filtering threshold lives in pipeline config, not in any adapter.

- **CAP-2**
  - **intent:** Pipeline can request a Hebrew summary of an article and receive a structured result: Hebrew summary, source language, estimated reading time, translated title.
  - **success:** Result is a typed object with those fields populated; no caller ever parses free-form provider text.

- **CAP-3**
  - **intent:** Callers get uniform error behavior regardless of provider: errors are classified by origin (input/context, provider, transport/infra); adapters internally retry transient errors with backoff, then raise a typed error from the interface's own hierarchy.
  - **success:** Contract tests simulate a transient and a permanent failure; the adapter retries the former and surfaces the latter as the correct typed error. No vendor exception type ever crosses the interface boundary.

- **CAP-4**
  - **intent:** A deterministic mock provider implements the full contract offline - same input yields identical output on every call, with no API key or network.
  - **success:** Calling each method twice with identical input returns equal results; the full pipeline can run end-to-end against the mock offline.

- **CAP-5**
  - **intent:** One abstract contract test suite runs against any adapter; a new adapter earns trust by passing it, not by review.
  - **success:** The suite runs against the mock and passes; wiring a future adapter into the suite requires only providing an instance.

- **CAP-6**
  - **intent:** A provider can explicitly refuse to process bad input (broken, empty, junk content) as a distinct outcome - a legitimate answer, not a failure.
  - **success:** Contract tests submit refusal-worthy input; callers can branch on refusal separately from error handling.

## Constraints

- The contract speaks domain language (article, topic, score, summary) - never LLM language (prompt, tokens, model). Litmus test: a non-LLM impostor (translation API + keyword classifier, or a cache of stored results) must be able to comply.
- Article content is data, not instructions: adapters must structurally separate their instructions from article text (prompt-injection defense).
- Input is clean plain text only (dedicated input dataclass); media and broken-HTML handling are out of provider scope.
- Methods are pure: same input may legally return the same output - caching adapters are valid implementations.
- Usage reporting on results is optional and in neutral units; mandated token counts are an LLM assumption and forbidden.
- Provider output parsing is adapter-internal; the contract exposes only typed results.
- Interface is sync, designed not to preclude a later async variant.

## Non-goals

- Faithfulness/hallucination judging of summaries (future optional pipeline stage; contract must not block it).
- Cost-cap enforcement or spend policy (issue #19; the usage field is only the enabler).
- Personalization or learning beyond an optional preference-history hook.
- Async implementation.
- Any real provider adapter (mock only in this issue).
- Smart cost-based model routing (solved later via per-task model config, not the contract).

## Success signal

`pytest` passes the contract suite against the mock, and a demo script runs score→summarize on sample articles offline, printing structured Hebrew results - no API key present anywhere in the environment.
