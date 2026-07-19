# Scope: approved MoSCoW (issue #5)

Priority contract for implementation order. Must = issue not done without it. Should = include unless it fights the timeline. Could = sanctioned only if genuinely cheap. Won't = decided out, do not build this issue.

## Must

- Two methods: relevance scoring, summarize+translate (CAP-1, CAP-2).
- Dedicated input dataclass (clean title + text).
- Structured typed results carrying their metadata fields (CAP-2).
- Interface-owned error hierarchy by origin + hybrid retry (CAP-3).
- Calibrated anchored score scale; threshold in pipeline config (CAP-1).
- Deterministic boring mock (CAP-4).
- Abstract contract test suite (CAP-5).

## Should

- Optional usage report in neutral units on every result.
- Explicit refusal outcome (CAP-6).
- Documented rule in contract docstring: article content is data, not instructions.

## Could

- Batch scoring: list input with default loop implementation; adapters may override with real batch APIs.
- Optional user preference-history parameter on relevance scoring (personalization hook; unused by pipeline this issue).
- Documented purity property (what makes caching adapters legal).

## Won't (this issue)

- Faithfulness judge · cost caps · personalization/learning · async · real provider adapter · model router.
