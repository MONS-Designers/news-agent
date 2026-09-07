---
id: SPEC-topic-source-discovery
companions: [code-map.md, discovery-flow.md, ../spec-llm-provider-interface/SPEC.md, ../spec-topic-suggestions/SPEC.md]
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only - consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Self-Managing Topic Source Discovery (issue #60)

## Why

A pain to solve, compounding into a mandate: the entire system has three admin-curated Topics (בינה מלאכותית, סייבר, חלל) because every Topic-to-Source mapping lives in a hardcoded Python dict (`DEFAULT_SOURCES`) that only a code change and redeploy can extend. Meanwhile `services/preferences.py::set_preferences` already lets a user create a brand-new pending Topic today - by typing an interest directly, or by picking an LLM-invented suggestion from the separately-specified Step 3 flow (`spec-topic-suggestions`) - and that Topic lands with zero Sources attached, a dead end for whoever picked it. This spec closes that gap by making source acquisition and topic presentation self-managing: an LLM discovers real RSS feeds for a new Topic, a deterministic check rejects anything it hallucinated, and the Topic gets a DB-assigned color instead of a hardcoded one - so growing the topic catalog stops requiring a developer.

## Capabilities

- **CAP-1**
  - **intent:** A newly created pending Topic automatically gains real, working RSS sources with no code change, seed edit, or admin action.
  - **success:** Creating a new Topic through the existing `set_preferences` flow results, without further human input, either in one or more `Source` rows under it whose feed URL is independently confirmed reachable and parseable, or - when no candidate survives - in an explicit logged reason per rejected candidate. Silent completion with zero sources and no recorded cause is a failure of this capability.

- **CAP-2**
  - **intent:** Every Topic carries a color unique across all Topics and legible against the digest's dark background, without anyone hand-assigning it.
  - **success:** For any Topic whose color assignment has run, `Topic.color` is set, no two non-null `Topic.color` values are equal (enforced by a DB unique constraint, not by the read-then-write check alone), and every one independently measures at or above 4.5:1 contrast against `#0b1020`. A Topic whose assignment has not yet run or gave up falls back to `render.py`'s existing default color; the uniqueness guarantee covers assigned colors, not that shared fallback.

- **CAP-3**
  - **intent:** A reader who just subscribed to a brand-new topic sees articles from that topic's newly-discovered sources in their own digest before any admin has reviewed those sources.
  - **success:** Subscribe a user to a new topic, let discovery complete, run fetch → relevance → digest-build; that user's digest includes articles from the new sources, while a second user not subscribed to that topic sees none of them.

- **CAP-4**
  - **intent:** Creating a Topic never makes the triggering request wait on source discovery.
  - **success:** The preferences-save request completes on its own existing timing; `Source` rows for the new topic appear afterward with no second user action required.

- **CAP-5**
  - **intent:** A source candidate that does not actually resolve to a working feed is rejected before it can become a `Source` row, regardless of how plausible the proposing LLM made it look.
  - **success:** Given a candidate list containing one genuinely reachable feed and one dead or fabricated URL, only the reachable one is persisted.

## Constraints

- Source discovery is a single LLM call (a "finder"); no second, independent "judge" LLM verifies its output in this feature - deferred to the future multi-stage pipeline overhaul already tracked as an open item in `CLAUDE.md`, noted there and as a code TODO rather than built now.
- The finder joins `llm/base.py`'s existing template-method contract, the same shape as `score_relevance`/`summarize` - domain language only (topic, source, feed), matching the LLM Provider Interface spec's existing constraint on that contract.
- Candidate validation is deterministic - an actual feed fetch + parse (`feedparser`, the library `pipeline/fetcher.py` already uses) - never LLM-judged.
- No hardcoded source list may remain as a competing source of truth: `DEFAULT_SOURCES`, `seed_default_sources()`, and `services/sources.py`'s `SeedReport` are removed, not merely unused. `services/taxonomy.py` defines an unrelated class of the same name for profile Fields/Roles - out of scope, untouched.
- `Topic.color` is computed against live DB state every time (checked against every existing non-null `Topic.color` row) - never drawn from a fixed/enumerated lookup table, since a hardcoded color map is exactly what this replaces. The read-then-write check is a fast path, not the guarantee; the DB unique constraint is.
- Pending-source article visibility relies entirely on the pre-existing `subscribed_topic_ids` scoping already enforced in `pipeline/fetcher.py` and `pipeline/relevance.py` - both must widen their `Source.status` filter from approved-only to approved-or-pending, since either shared pipeline stage still filtering to approved-only would never fetch or score a pending source's articles at all.
- The same widening must exclude Topics whose own `Topic.status` is rejected. `Topic.status` carries the same pending/approved/rejected set as `Source.status`, and widening on the source alone would let a rejected Topic's pending sources reach digests.
- Widening to approved-or-pending is deliberately indiscriminate: the pipeline queries cannot tell a discovery-created pending source from one an admin left pending on purpose, so admin review shifts from a gate to after-the-fact removal. Accepted for this feature; no per-source provenance flag is introduced to narrow it.
- Migration is additive-only: a nullable `Topic.color` column carrying a unique constraint, a reversible `downgrade()`, plus a backfill of the 3 pre-existing approved Topics with their current hardcoded render colors, so nothing changes visually for them. The backfill resolves each Topic to an id at migration time rather than matching on its Hebrew name in the UPDATE - a renamed Topic must not silently no-op into a NULL.
- Migration content, including the exact backfill values, is shown to the user for review before it is ever run - a standing project rule, not a one-off ask for this feature.
- Discovery triggers once, at Topic-creation time, from a background task - not a periodic batch sweep.
- The background task receives the engine (`db.get_bind()`), never the request-scoped `Session`. `api/routers/me.py` already establishes this for its existing suggestion task, with a comment recording that the request session is closed by the time a `BackgroundTask` runs; the task re-opens its own session and re-loads the Topic by id.
- A candidate URL is rejected before any fetch unless its scheme is `http` or `https`. `feedparser.parse` accepts a local filesystem path, so an LLM-proposed `file:///...` would read server files; the scheme check is deterministic and precedes validation.
- Every candidate fetch carries an explicit timeout, and a response that parses with feedparser's `bozo` flag set and no entries is rejected - an HTML error page or a 401 body must not persist as a `Source`.
- The candidate list is capped before validation, and the finder is asked for more candidates than that cap, so a URL collision or a failed fetch does not leave a Topic sourceless.
- `discover_sources` returns candidates or a `Refusal`, matching every other public method on `llm/base.py`. Both a `Refusal` and an exhausted-retry `LLMError` are terminal for that run and logged; neither may escape the background task uncaught.
- Color assignment is independent of source discovery and runs regardless of whether discovery succeeded, failed, or returned nothing. Its retry loop carries an explicit attempt cap and logs giving up rather than spinning.
- `Source.url` is globally unique and `add_source` is get-or-create by URL, so a candidate already owned by another Topic yields that other Topic's row rather than a new one. This is a distinct, logged outcome - never counted toward CAP-1's success and never silently discarded.
- `seed-sources` is replaced by a `discover-topic "<name>"` CLI command, not merely deleted: an empty database must retain a bootstrap path, and it must run through the same discovery code path as production rather than a second, hardcoded one.

## Non-goals

- A second/independent LLM judge for source quality.
- Making a feed shareable across Topics (a `Source`-to-`Topic` many-to-many). `Source.topic_id` is how `pipeline/relevance.py` derives the single topic an Article is scored against and how `pipeline/render.py` derives its digest label and color; splitting that ownership is a data-model overhaul outside this issue. The cost is accepted: a feed already owned by one Topic cannot be reused by another.
- Any new admin UI to review/approve a pending Topic itself - Source-level approval via the existing `admin.py` endpoint is unchanged; a pending Topic having no reviewer of its own is a pre-existing, separately tracked gap.
- Any change to how `suggest_topics`/`suggest_new_topics` rank or invent topic names - a separate mechanism; a production defect in it is tracked as GitHub issue #72.
- LLM cost/spend control policy for the new `discover_sources` calls - ownership sits with `news-agent-infra` per the project's cross-repo split.

## Success signal

Create a brand-new pending Topic through the existing preferences-save flow. Once the background job completes: the Topic has one or more `Source` rows (`status=pending`) whose feed URLs are independently verified reachable - or a logged reason per rejected candidate - and `Topic.color` is set, unique, and contrast-compliant. Running fetch → relevance → digest-build for the subscribing user's account includes articles from those sources; a second user not subscribed to that topic sees none of them. `DEFAULT_SOURCES`, `seed_default_sources()`, `SeedReport` (the one in `services/sources.py`) and the `seed-sources` CLI command no longer exist anywhere in the codebase, and `discover-topic "<name>"` populates an empty database through the same discovery path.

## Assumptions

- The finder LLM call reuses whatever provider adapter the existing `LLMProvider` factory (`llm/factory.py`) already resolves, rather than introducing a second, separate provider-selection axis for this one capability. Decided 2026-09-06: V1 runs on the already-configured EXTERNAL provider, with no feature flag of its own; a future change of finder model is a provider-config change, not a code change here.
- No automatic retry or periodic sweep for a topic whose first discovery attempt finds zero valid sources - a permanently-sourceless pending Topic is an accepted V1 edge case.
- The end-to-end check in Success signal has to account for `digest_max_articles` (default 5) and the weighted top-N ranking from GH #25: a new topic's articles compete for those slots, so the test pins the ranking inputs rather than asserting a new-source article always appears.

## Open Questions

- None blocking. LLM spend for the new `discover_sources` calls stays a `news-agent-infra` ownership item (see Non-goals) - worth a heads-up to Moshe that these calls are triggered by ordinary user activity rather than a controlled batch job, but it does not gate this build.
