---
reviewer: independent rubric review (good-spine checklist, 7 criteria)
spine: ARCHITECTURE-SPINE.md (Article Topic Ownership, AD-22..AD-29, status draft)
date: 2026-09-14
code-baseline: branch dev @ b8b444e (src/newsagent/)
---

# Rubric Review — Article Topic Ownership spine

## Verdict

The split into three owners (why a feed is fetched, what an article is about, what topic a reader was shown it under) is sound, and it fits the inherited ADs. The spine is **not yet build-ready**. It leaves the `article_topics` table without identity or idempotency. Its two-release cutover has a data gap during the window when old and new code run together. Its backfill trigger is not enforceable as written. And about a quarter of its code citations are wrong or incomplete. None of this re-opens decisions the memlog records as user-decided. The fixes tighten rules those decisions imply.

## Checklist scorecard

| # | Criterion | Result |
| --- | --- | --- |
| 1 | Fixes all divergence points for the level below | Partial. Misses `article_topics` identity/idempotency, the article-selection filter in relevance.py, how the classifier result is keyed, and the "subscriber" definition |
| 2 | Every Rule enforceable and prevents its divergence | Partial. AD-27 trigger and AD-29 "all three processes run release-1 code" have no enforcement mechanism |
| 3 | Nothing Deferred lets units diverge | Partial. Setting values are deferred with no defaults |
| 4 | Named tech verified-current | Pass, minor notes. No new tech; embeddings honestly flagged unverified |
| 5 | Ratifies the brownfield codebase; file:line claims correct | Partial. Several stale or missing citations (see H-4) |
| 6 | No new AD weakens an inherited AD | Pass with one tension. AD-5 is stretched to cover pipeline work in the API process (OQ-1) |
| 7 | Every owned dimension decided/deferred/open, incl. ops envelope | Partial. Migration execution, config rollout to infra, rollback and the review gate's pass criterion are missing |

---

## Critical

### C-1 — `article_topics` has no identity and no idempotency rule, yet has three concurrent writers

- **Location:** AD-23 (table shape), AD-27 (backfill), AD-28 (sole writers), AD-29 release 1 (data backfill)
- **Finding:** AD-23 defines `article_topics(article_id, topic_id, score)` with no primary key or unique constraint on `(article_id, topic_id)`. Writes can come from four paths. The daily relevance run (CLI process), the #60 bootstrap backfill (API `BackgroundTask`, OQ-1), a second bootstrap for another topic, and the release-1 data migration. AD-28 only makes "the relevance stage" the sole writer. It says nothing about two invocations of that stage overlapping. Nor does it say what "appends" (AD-27) does when a row already exists. Concrete races:
  - An article fetched before topic C was created is still `pending` when both the daily run (its list now includes C) and C's backfill pick it up. Both classify it against C and insert duplicate rows, paying twice.
  - Two users each trigger a topic in quick succession. Two backfills overlap on the same articles.
  - A `BackgroundTask` retry, or a re-run after a crash (AD-5 accepts loss, but a user re-saving re-triggers), re-inserts.
- **Why it matters:** Duplicate rows break AD-23's top-N rule, which counts rows. They also break AD-24's resolve step, which reads "the" score. And they double backfill spend, which the spine already calls unmeasured and user-triggered. Two builders will pick different fixes: insert-or-ignore, upsert-latest-wins, or delete-then-insert. Those give different stored scores after re-classification. This is exactly the divergence a spine exists to prevent.
- **Suggested fix:** Add to AD-23: `(article_id, topic_id)` is the primary key (or unique), created in release 1. Add to AD-27/AD-28: writes are upserts and first-write-wins (`ON CONFLICT DO NOTHING`), matching the "classify once" principle. The backfill skips `(article, topic)` pairs that already have a row, before calling the LLM. Also state what happens when two stage invocations overlap: allowed, with idempotency as the only guard, or serialised via a lease like `scheduler_lease`.

---

## High

### H-1 — Expand/contract gap: rows written by old code during the overlap never become eligible

- **Location:** AD-29 release 1 and release 2
- **Finding:** Release 1 backfills `article_topics` and `DigestArticle.topic_id` once, at migration time. Old code keeps running until each process restarts (the spine's own premise). In that window:
  1. The old daily pipeline scores articles with `score_relevance`. It writes `relevance_score` and `relevance_status='relevant'` but no `article_topics` rows. Those articles now sit outside `_FILTERABLE` (`relevance.py:35`), so they are never re-classified. Under AD-23/24 new code sees zero eligible topics for them. They are silently dropped from every digest. That is starvation caused by the deploy itself.
  2. The old scheduler builds digests and inserts `DigestArticle` rows with `topic_id = NULL`. Release 2 makes that column NOT NULL. That migration fails, or those rows get arbitrary values, unless it re-runs the backfill.
- **Why it matters:** The cutover rule claims to prevent old/new overlap failures, but it only covers old code *reading* new structures. It does not cover old code *writing* data the new model depends on. The failure is silent: no error, just missing articles.
- **Suggested fix:** Release 1 is made re-runnable as a post-deploy step (a CLI command, not only the Alembic revision). It covers articles with `relevance_score IS NOT NULL` and no `article_topics` rows. Release 2's migration first re-backfills `DigestArticle.topic_id IS NULL` from `article.source.topic_id`, then checks for duplicates, then adds constraints. State both explicitly.

### H-2 — The backfill trigger "a topic enters the candidate list" is not enforceable

- **Location:** AD-27 (Backfill trigger), AD-26, memlog line 41
- **Finding:** The candidate list is computed fresh each run ("every topic with at least one subscriber"). Nothing records that a topic *entered* it. The only trigger actually wired is GH #60's bootstrap. That misses:
  - an existing topic whose subscriber count goes from 0 to 1 through the ordinary preferences page (`services/preferences.py:set_preferences`, AD-9)
  - a topic that lost its last subscriber and regained one
  - a topic an admin un-rejects

  Each is a real "entry" that gets no backfill. A builder implementing the rule literally would need persisted state (e.g. `Topic.backfilled_at`, or "has any `article_topics` row within the window"). Another builder would call it only from #60. The two diverge.
- **Why it matters:** The user's stated reason for adopting the backfill is that a sparse first week loses the reader. That bites every path that adds a subscriber, not only topic creation.
- **Suggested fix:** Define entry detectably and in one place. Two options:
  - (a) The daily relevance run computes "candidate topics with no `article_topics` rows among articles fetched in the window" and backfills them itself. That is idempotent, needs no new state, and lets #60 or preferences call it early.
  - (b) A persisted marker, reset when subscribers drop to zero.

  Name the callers (`set_preferences`, #60 bootstrap, admin status change) or state that only the daily detection counts.

### H-3 — The classifier result contract doesn't say how scores map back to candidates

- **Location:** AD-25 (Shape)
- **Finding:** "one independent, absolute 0.0–1.0 score per candidate" does not fix:
  - whether results are keyed by name or positional
  - what the adapter does when the LLM omits a candidate, adds one, or echoes a name with different whitespace or letter case (topic names are free user text, often Hebrew)
  - behaviour on an empty candidate list
  - a maximum list size relative to prompt length

  `Topic.name` is unique (`models/topic.py:25`), so keying by name is viable, but only if the contract says so and defines exact-match handling. One external adapter will treat a missing candidate as score 0.0. Another will mark it `malformed` (AD-15) and raise. The two give different costs and different eligibility.
- **Why it matters:** The spine explicitly created this contract so adapters cannot diverge (the "none of the above" suite). Result mapping is the most likely place for them to diverge.
- **Suggested fix:** State in AD-25:
  - the result is keyed by the candidate strings exactly as passed
  - a missing, extra or unparsable candidate is `malformed` (AD-15), not a default score
  - an empty list is a caller error, and the stage never calls with an empty list
  - the contract suite covers missing, extra and duplicate candidates for every adapter

### H-4 — Code citations are stale or incomplete (brownfield ratification)

- **Location:** AD-22 Rule bullet 2, memlog constraint lines 10/24
- **Finding (verified against `src/newsagent/` @ b8b444e):**
  - `render.py:151/163` is wrong. 151 is `return link` in `_get_or_create_link`. The feed-topic reads are **`render.py:159`** (`topic_name = article.source.topic.name`) and **`render.py:170-171`** (label and colour).
  - `ranking.py:93-100` is the docstring of `select_top`. The diversity-floor code that actually reads the feed topic is **`ranking.py:125`** (`topic_id = article.source.topic_id`), and it is not cited.
  - **`ranking.py:72`** (`settings.relevance_weight * article.relevance_score`) is not cited anywhere. It is the read that AD-24 ("relevance score reads the presented topic") and AD-29 (the column drop) most directly change. It is also the old-scheduler crash site AD-29 guards against.
  - **`relevance.py:120`** (`Source.topic_id.in_(subscribed_topic_ids)`, which articles enter classification) and **`relevance.py:127`** (topic ids behind AD-14 `subscriber_count`) both use `Source.topic_id`. Neither is on AD-22's move list, and neither is covered by "only `fetcher.py:154` may scope on it". A builder cannot tell whether relevance should still filter articles by feed-topic subscribers. The code does that today, and it contradicts the "only fetcher" rule. Or it could classify every article from an approved source. The spend difference is real, because a feed keeps being fetched as long as its own topic has subscribers.
  - `relevance.py:119` also gates on `Source.status == STATUS_APPROVED`. AD-23 uses "not rejected", a different predicate (a `pending` source passes one and fails the other). See M-2.
  - Verified correct: `relevance.py:143`, `ranking.py:43-49`, `ranking.py:65`, `digest.py:62`, `digest.py:185`, `summarize.py:93`, `summarize.py:100`, `extract.py:85`, `fetcher.py:154`, `_FILTERABLE` at `relevance.py:35` (= pending, error). `db.py:7` already has `expire_on_commit=False`. `relevance.py:155` and `summarize.py:127` already use `copy_context().run`.
- **Why it matters:** Criterion 5. Stories will be cut from these line lists. A missing site stays on the feed topic, which recreates the "same article, two topics" divergence AD-22 exists to prevent.
- **Suggested fix:** Correct the citations to `render.py:159/170-171` and `ranking.py:125`, and add `ranking.py:72`. Add an explicit rule for `relevance.py:120/127`. Either (a) relevance classifies every article from an approved source that was fetched (fetch scoping already bounds cost), or (b) it keeps the feed-topic subscriber filter as a declared second scoping site. Better still, replace line numbers with symbol names (`_to_view`, `select_top` by_topic loop, `score_article`, `filter_pending_articles` query), which survive edits.

### H-5 — Interestingness has two writers today, and AD-27's rule presupposes an OQ-2 answer

- **Location:** AD-27 ("written by any classification only when currently null"), AD-28 last bullet, OQ-2
- **Finding:** `summarize.py:160` sets `article.interestingness` unconditionally. AD-27 makes classification write only when it is null. Implemented as written, classification writes first (from the snippet) and summarize then overwrites (from the full text). Two ordered writers, the thing AD-28 forbids. Yet AD-28 leaves ownership open. So the "null only" rule is a decision that quietly depends on an open question, and a builder of either stage can't know whether to touch `summarize.py:160`.
- **Why it matters:** Ranking weights interestingness at 0.60 of the interest term (`config.py:52`). Whichever way it is built changes digest ordering for everyone.
- **Suggested fix:** Resolve OQ-2 before the spine is final (the memlog already frames the two options). Until then, strike the "only when currently null" sentence from AD-27, or state explicitly "summarize keeps overwriting until the select-before-summarize task; this is a declared, temporary exception to AD-28".

### H-6 — OQ-1 is open, but AD-27's execution-context rule and the deployment diagram already assume it's answered

- **Location:** AD-27 (Execution context), OQ-1, Deployment diagram, inherited AD-5
- **Finding:** AD-5 (parent) was scoped to *suggestion computation* and chose the API process explicitly to keep work off the pipeline. AD-27 reuses AD-5 so the API process runs the relevance stage: a thread pool of `filter_concurrency` (default 5) outbound LLM calls, plus fetching feeds for #60. That is the reverse of AD-5's intent. The spine correctly flags OQ-1, but it still:
  - writes rules for "whatever process calls the backfill" (implying the API)
  - draws `api -.-> ext` in the deployment diagram
  - states in the inherited table that the #60 bootstrap "is such a task"
- **Why it matters:** Criterion 6. It stretches an inherited AD beyond its bound scope. Criterion 7. Resource envelope: uvicorn worker threads and memory, multiple API replicas each firing backfills, no request timeout. The alternative (enqueue a marker, and the pipeline process backfills on its next run, which also satisfies H-2 option (a)) changes several ADs, so OQ-1 is load-bearing, not cosmetic.
- **Suggested fix:** Resolve OQ-1 before finalising. If the API runs it, add a rule binding concurrency, replicas and idempotency (C-1). If the pipeline runs it, remove the AD-5 row and the `api -.-> ext` edge, and tie it to H-2 option (a).

---

## Medium

### M-1 — "Subscribed topic" has no single definition, yet four sites depend on it

- **Location:** AD-22 bullet 3 (extract/summarize gate), AD-24 (reader's subscribed topics), AD-26 (candidate list), Telemetry conventions
- **Finding:** The code has two definitions. The GH #45 scoping sites (`fetcher.py:151`, `relevance.py:113`, `extract.py:78`, `summarize.py:86`) use any `UserTopicPreference` row. `active_subscriber_count` (`relevance.py:60`) excludes users with `unsubscribed_at`. AD-26 doesn't say which one it means, or whether candidates exclude `Topic.status == rejected`. Excluding them would avoid paying to classify topics AD-23 will discard anyway.
- **Why it matters:** The candidate list, the paid-stage gate and `subscriber_count` can drift apart. For example, classify against a topic whose only subscriber unsubscribed, then gate extract on active subscribers.
- **Suggested fix:** Add one sentence to AD-26: "subscribed topic = a topic with at least one `UserTopicPreference` from a user with `unsubscribed_at IS NULL`, and `Topic.status != rejected`; defined once in the relevance stage and imported by extract/summarize/digest". Also say what `subscriber_count` means for classification runs (per AD-13: active subscribers of any candidate) and for summarize (topics eligible for the run's articles), replacing `summarize.py:100`.

### M-2 — Source-status predicate conflicts with existing code

- **Location:** AD-23 eligibility ("source status is not rejected")
- **Finding:** Existing code gates on `Source.status == STATUS_APPROVED` (`relevance.py:119`, `fetcher.py:154`). "Not rejected" also admits `pending`, the default status for `add_source` (`models/source.py:26`). A source approved, fetched, then moved back to pending would keep its articles eligible under AD-23 but drop them under current relevance. #60's discovered feeds may land as pending.
- **Suggested fix:** Pick one predicate and cite the constant. Probably `== STATUS_APPROVED` for sources, to match the code. For topics keep `!= rejected`, since `Topic.status` defaults to approved (`models/topic.py:26`) and #60 creates pending topics that must still work.

### M-3 — Top-N cap order is ambiguous relative to the reader's subscriptions

- **Location:** AD-23 ("only the top-N by score count"), AD-24
- **Finding:** It is unclear whether the cap of `max_topics_per_article` applies globally, before intersecting with the reader's subscriptions (a reader's 4th-best topic is dropped even if it is her only match), or after. The results differ materially. The paid-stage gate (AD-22 bullet 3) also has to use the same order.
- **Suggested fix:** State the order explicitly: "top-N is computed over globally eligible topics, before any per-reader intersection; the extract/summarize gate uses the same set". Or the reverse, but decide.

### M-4 — Threshold change vs stored `relevance_status`

- **Location:** AD-23 (Prevents: "a threshold change silently requiring a paid re-classification") vs "Extract and summarize gate on [`relevance_status`] together with read-time eligibility"
- **Finding:** Lowering `relevance_threshold` makes stored-`irrelevant` articles eligible at read time. But extract and summarize also require `relevance_status == relevant`, so those articles are never summarised and never reach a digest. Raising the threshold works; lowering it silently doesn't. The "Prevents" claim holds for digest eligibility only.
- **Suggested fix:** Either gate extract/summarize on read-time eligibility alone, keeping `relevance_status` only as the classified/refused/error lifecycle marker. Or state that lowering the threshold requires a re-verdict command (no LLM cost) that recomputes `relevance_status` from `article_topics`.

### M-5 — Operational envelope: migration execution, config rollout and rollback are unstated

- **Location:** Structural Seed → Deployment & environments, AD-29
- **Finding:**
  - **Who runs migrations:** `Dockerfile.backend:76` starts uvicorn only, and nothing in the repo runs `alembic upgrade`. "Migrations run through Alembic against stage before prod" doesn't say by whom or at which deploy step, relative to the three process restarts AD-29 orders.
  - **Verifying "all three processes run release-1 code":** no mechanism. Batch hosting is open. The scheduler holds a lease (`scheduler_lease`). Nothing records a code version.
  - **New settings:** `max_topics_per_article`, `topic_presentation_margin` and `candidate_backfill_window_days` need `config.py` defaults. Per the project CLAUDE.md, prod config is sourced from Terraform `app_settings` owned by news-agent-infra, not from GH Environments. The spine doesn't name that coordination.
  - **Rollback:** Release 1 is reversible *because* `relevance_score` is still written. Worth saying so. Release 2 drops a column and is not reversible. The spine should say so, and say what "roll back release 2" means (restore from Neon branch/PITR, or accept forward-fix only).
  - **Classifier cutover:** Replacing `score_relevance` ships in the same release as the schema. There is no switch to fall back to single-topic scoring without a redeploy. Acceptable at this scale, but declare it.
- **Suggested fix:** Add an "Operations" subsection:
  - migration step and owner
  - how the overlap is confirmed (e.g. wait one full daily pipeline cycle plus a scheduler restart, checked via `outbound_runs` purpose/kind rows from new code)
  - defaults for each new setting, plus a note for Moshe to add them to Terraform only if non-default
  - rollback posture per release

### M-6 — The manual classifier gate has no pass/fail criterion or owner

- **Location:** AD-29 (Before release 1)
- **Finding:** "reviewed by eye" on about 30 articles gates a release, but nothing says what result blocks it. The Deferred section also calibrates three settings "after the AD-29 manual review". So the review is also where defaults get chosen, and that isn't stated.
- **Suggested fix:** State a minimum bar, e.g. "every deliberately unrelated article scores ≤ 0.3 on all candidates; no on-topic article is presented under a topic the reviewer judges wrong". Name the reviewer (Nomi). Record the chosen default values as the gate's output.

### M-7 — Deferred setting values with no defaults can make independent builds diverge

- **Location:** Deferred ("Values of max_topics_per_article, topic_presentation_margin, candidate_backfill_window_days")
- **Finding:** Deferring *calibration* is fine. Deferring the *value* entirely means the relevance story and the digest story may each pick a placeholder, and their tests pin behaviour to those placeholders (e.g. margin 0 disables the feed-topic tiebreak entirely).
- **Suggested fix:** Set provisional defaults in the spine (e.g. N=3, margin=0.1, window=14 days), declared "calibrate later".

### M-8 — The fetch-scoping collision still starves topics

- **Location:** AD-22, Deferred ("GH #60 spec re-derivation"), memlog line 60 ("collision now costs only fetch provenance")
- **Finding:** `Source.url` is unique (`models/source.py:24`), so a feed discovered by topics A and B has `topic_id = A`. If A loses all subscribers, `fetcher.py:154` stops fetching the feed, even though B's readers were receiving its articles through `article_topics`. So the collision costs fetch *scoping*, not just provenance. It is a quiet starvation path that the spine's own starvation log cannot tell apart from a quiet week.
- **Suggested fix:** Correct the memlog/Deferred wording, and add this as an explicit Deferred item with a revisit condition (e.g. a `source_topics` fetch-scope table, or fetch scoping by "feed produced an eligible article for a subscribed topic in the last N days"). Or accept it and name the accepted loss.

---

## Low

### L-1 — Presented-topic tiebreak on equal scores is undefined
AD-24. Two subscribed topics with identical scores, neither being the feed topic: the choice is unspecified. The value is persisted, so later reads are consistent, but tests and two builders may differ. **Fix:** "ties break by lower `topic_id`".

### L-2 — `op.batch_alter_table` rationale
AD-29 / Consistency. On PostgreSQL, Alembic's batch mode (`recreate="auto"`) is a no-op wrapper. It only recreates tables on SQLite, which the tests use (`StaticPool`, `check_same_thread=False`). The rule is harmless but reads as if Postgres needs it. **Fix:** one clause, "for SQLite test parity".

### L-3 — ERD omits cardinality constraints the ADs rely on
The Structural Seed ERD should show `ARTICLE_TOPIC` PK `(article_id, topic_id)` (C-1) and `DIGEST_ARTICLE` unique `(digest_id, article_id)` plus `topic_id` NOT NULL after release 2. That makes the constraints visible to story authors.

### L-4 — Dependency diagram omissions
- `summarize --> relevance` exists today (`summarize.py:24` imports `STATUS_RELEVANT`, `active_subscriber_count`), and `extract --> relevance` (`extract.py:30`).
- `extract` is missing from the diagram, although AD-22 binds it.
- `send --> render` is missing. Render is drawn as orphaned, reading only models, but `render.py` must now read `DigestArticle.topic_id`, which the diagram doesn't show.

**Fix:** add the missing edges and nodes.

### L-5 — Tests and docs that the replacement churns aren't listed as bound
AD-25 binds "every test and script using `score_relevance`". The repo also mentions `relevance_score`/`score_relevance` in `tests/test_scheduler.py:50`, `tests/pipeline/test_digest.py`, `tests/pipeline/test_ranking.py`, `tests/pipeline/test_relevance.py`, `alembic/versions/c41d8e2f9a03_article_filtering_columns.py` (history, leave as-is), and docs (`docs/data-models-backend.md`, `docs/architecture-cli.md`, `README.md`, `docs/v1-manual-test-plan.md`, `docs/user-management.md`, `docs/development-guide-backend.md`, `docs/index.md`, `docs/project-overview.md`). **Fix:** add "and the generated docs set" to AD-25/AD-29 binds so stale docs don't mislead later agents.

### L-6 — Starvation log granularity
Consistency → Observability. "Topics with subscribers and zero eligible articles within the window" can't distinguish "no feeds" (#60 discovery failed) from "feeds but nothing eligible". The memlog (line 18) calls that distinction out as a goal. **Fix:** log both counts per topic (own-feed articles fetched in the window, eligible articles).

---

## Criteria with no findings

- **Criterion 4 (tech currency):** No new libraries. `contextvars.copy_context().run` and `sessionmaker(expire_on_commit=False)` are standard and already in use. Alembic `batch_alter_table` is current. The embedding shortlist is correctly marked unverified.
- **Criterion 6, apart from H-6:** AD-11/13/14/15/17/18/19/20 are honoured. The separate backfill purpose and `user_id = NULL` follow AD-11/AD-14. Keeping `relevance_score` as a data column during the overlap is a legitimate reading of AD-18.
