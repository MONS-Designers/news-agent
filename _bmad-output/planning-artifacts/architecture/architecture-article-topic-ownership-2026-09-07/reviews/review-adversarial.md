---
reviewer: adversarial (pairwise-incompatibility lens)
target: ARCHITECTURE-SPINE.md (AD-22..AD-29, status draft, 2026-09-14)
date: 2026-09-14
method: for each hole, two units one level down that each obey every AD to the letter, yet build incompatibly
code verified against: pipeline/relevance.py, digest.py, ranking.py, render.py, summarize.py, extract.py, fetcher.py; llm/base.py, llm/types.py; models/article.py, digest_article.py, topic.py, user_topic_preference.py, feedback.py; services/preferences.py; scheduler.py; cli.py
---

# Adversarial Review: Article Topic Ownership Spine

## Verdict

The ownership split (Source / article_topics / DigestArticle) is sound. But the spine defines **who writes** and says almost nothing about **how writes combine**. It has no key on `article_topics`, no definition of the event that triggers backfill, no serialisation between backfill and the daily run, and no rule for rows written by old code during the AD-29 overlap. Two builders who follow every AD exactly can still ship duplicate scores, lose an eligible article to a status overwrite, or break the release-2 migration. Five holes are Critical or High and should close before the spine is marked final and GH #60 is re-derived.

Severity scale: **Critical** means silent data corruption or loss of the core promise (a new topic gets articles). **High** means two compliant stories produce behaviour that differs in a way readers can see, or wasted spend. **Medium** means a contradiction or gap that a careful builder would probably catch, but the spine does not force it. **Low** means cosmetic or already tracked.

---

## H1 — CRITICAL: `article_topics` has no key, so "append" plus re-entry creates duplicate scores

**Unit A: the relevance daily-run story.** It follows AD-23 and AD-26. Pending articles are classified against every subscribed topic, and each result becomes an `INSERT` of one row per candidate.

**Unit B: the candidate-entry backfill story.** It follows AD-27 word for word: it "appends `article_topics` rows" for topic T over articles in the window.

**Unit C: the release-1 migration story.** It follows AD-29 and seeds one row per scored article from `source.topic_id` + `relevance_score`.

**How they clash:**
- T's feed topic is the same topic an old article was seeded with in release 1. When T's backfill runs, its window covers those seeded articles, so the same `(article_id, T)` pair gets a second row with a different score, produced by a different prompt.
- T loses its last subscriber and later gains one again. The backfill runs a second time and writes a third row.
- A crashed backfill is re-run (AD-5 accepts the crash, but nothing forbids a retry, and `discover-topic` from the CLI is a second entry point). That also writes duplicates.
- Downstream, eligibility ("score >= threshold"), the top-N cut (AD-23) and the presentation margin (AD-24) each pick among multiple rows in their own way: `max`, first row, or last row. The digest builder and the summarize filter can disagree on whether the same article is eligible.

The spine never states a uniqueness rule. AD-29 only mentions a unique constraint for `digest_articles`.

**Proposed rule (tighten AD-23 and AD-29 release 1):**
> `article_topics` has `UNIQUE(article_id, topic_id)` from its creating revision. A score is immutable once written: every writer uses insert-if-absent (`ON CONFLICT DO NOTHING`). A backfill skips any article that already has a row for the topic. Re-running any relevance entry point for the same inputs changes nothing (idempotent).

If re-scoring is ever wanted, it must be an explicit separate entry point, not a side effect of re-entry.

---

## H2 — CRITICAL: "a topic enters the candidate list" is an undefined event with no detector

**Unit A: the GH #60 bootstrap story.** It follows AD-27 and AD-28, and memlog line 41 says #60 owns *when* the event happens. It calls the backfill entry point once, for `add_topic(...) created=True`. Its frozen spec says "Discovery triggers only for ids where `add_topic` reported `created=True`, once".

**Unit B: the relevance-stage story.** It follows AD-26 and AD-27, which say the relevance stage "classifies that topic alone" *when* the topic enters. To honour that, it must detect entry. The spine stores no previous candidate list, so the builder invents something like "a subscribed topic with no `article_topics` rows in the window".

**How they clash:**
- **Gaps (only Unit A implemented).** An *existing* topic can go from 0 to 1 subscriber without `created=True`. Examples: a user picks an approved topic nobody currently follows (`set_preferences` inserts the `UserTopicPreference`); `cli subscribe`; a user returns after unsubscribing. Because of GH #45, that topic's articles from other feeds were never scored against it. The reader gets exactly the sparse first week the user called unacceptable (memlog line 40). No backfill ever runs.
- **Double runs (both implemented).** A new topic is backfilled by #60 in the API process and again by the daily run's detector, if the backfill has not yet written a row for every window article. For example, articles irrelevant to T get a row, but refused articles and window-edge articles do not, so the detector fires again. Combined with H1, this doubles the cost and doubles the rows.
- **Unit B's detector cannot tell** "never backfilled" apart from "backfilled, and a quiet week produced no rows". It would re-backfill a quiet topic every day. That is the unbounded spend AD-27's heading says it prevents.

**Proposed rule (new AD-27 clause):**
> Entry means a topic's active-subscriber count goes from 0 to ≥1. It is detected only where the preference row is written, in `services/preferences.py` (`set_preferences` and `subscribe`). That code schedules the backfill. `Topic.candidate_backfilled_at`, written only by the relevance stage, makes the backfill run at most once per entry.

(Alternative: the relevance run owns detection by diffing against a stored `Topic.candidate_since`. Either works, but exactly one component must own detection.)

---

## H3 — CRITICAL: backfill and daily run race on the same article; `relevance_status` loses an update

**Unit A: the daily relevance run** (CLI process). It follows AD-26, AD-27 "classify once" and AD-28. As `relevance.py:114` does today, it loads every `_FILTERABLE` article at run start, classifies them in a thread pool, and on each `as_completed` sets `relevance_status = relevant if max(scores) >= threshold else irrelevant`, then commits.

**Unit B: the backfill** (API process `BackgroundTask`, per OQ-1). It follows AD-27. It selects "articles fetched within `candidate_backfill_window_days`, including articles previously marked irrelevant". Nothing excludes `pending`. It classifies each against T and sets `relevance_status = relevant` if it passes.

**How they clash (the four failures sit at different levels):**
1. **Lost update.** A (a pending article, list without T) and B (T alone) are both in flight on article X. B commits `relevant` for T at 0.85. A then commits `irrelevant`, because the max over *its* list was 0.2. It overwrites the status from its stale ORM object. Result: `article_topics` says X is eligible for T, but `relevance_status = irrelevant`. AD-23 gates extract and summarize on *both*, so X is never summarised and never reaches T's reader. Nothing retries, because "classify once" excludes it.
2. **Duplicate (article, T) score.** B classifies a still-pending X against T, and later A classifies X against the full list, which now includes T. See H1.
3. **Missed articles.** A's candidate list is built at run start, before T entered. B's selection snapshot is taken before A commits X, when X is still pending. If B skips pending articles to avoid (2), X is classified by A without T and is never backfilled. T is starved of exactly the articles fetched on its creation day.
4. **"Fetched within window" is unanchored.** `scraped_at` and `published_at` are both plausible. `ranking.py:58` uses `published_at or scraped_at`. A newly discovered feed's backlog (fetcher has no age cutoff) has `scraped_at = today` but `published_at` weeks old. One builder backfills the whole backlog; the other skips it.

**Proposed rules (tighten AD-27 and AD-28):**
> `relevance_status` is always recomputed from the article's `article_topics` rows, never from the in-memory call result. Backfill may only move irrelevant to relevant.
> The daily run and backfill take one Postgres advisory lock (per run in the daily job, per topic in backfill), so they never run on the same articles at the same time.
> Backfill selects articles that are already classified and have `scraped_at` inside the window. After the daily run, it re-checks whether any topic entered the list during the run.

---

## H4 — HIGH: overlap-window writes by old code break new reads and the release-2 migration

AD-29 guards only one direction: new code reading old columns. It does not guard old code writing rows the new code needs.

**Unit A: the release-1 migration story.** It follows AD-29. It backfills `article_topics` and `DigestArticle.topic_id` once, at `alembic upgrade`.

**Unit B: the release-0 processes still running during the deploy.** They follow AD-29 by definition, because release 2 waits for them.
- The old CLI `filter` writes `relevance_score` and `relevance_status` but **no `article_topics` row**.
- The old scheduler inserts `DigestArticle(digest_id, article_id)` with **`topic_id` NULL**.

**Unit C: the release-2 migration story.** It follows AD-29: check duplicates, add the unique constraint, make `topic_id` NOT NULL.

**How they clash:**
- Articles classified by old code after the migration have a verdict but no rows. New `extract`, `summarize` and `digest` code (AD-23: eligibility from rows) treats them as ineligible, and "classify once" never revisits them. They are lost without any error.
- Digest rows written by the old scheduler during the overlap have NULL `topic_id`. New `ranking.topic_affinity` and the rerun diversity floor read NULL. Release 2's `NOT NULL` step either fails the migration or, if coerced, puts the wrong value in place.
- Also: does the backfill in release 1 update the `relevance_score` compatibility column when it raises an article's max score? AD-29 says "the relevance stage keeps writing `relevance_score` as the maximum candidate score", without saying whether that includes backfill. The old scheduler would rank a backfill-rescued article with its stale, low score.

**Proposed rule (tighten AD-29):**
> Release 2 first re-runs both release-1 data backfills, idempotently, for rows written during the overlap: articles with a score but no rows, and digest rows with NULL `topic_id`. Every writer of `article_topics` keeps `relevance_score = max(score)` until release 2.

---

## H5 — HIGH: "subscriber" and "candidate list" have three definitions in the code already

The code today has two meanings of "subscribed":
- `fetcher.py:151`, `relevance.py:113`, `extract.py:78` and `summarize.py:86` use `select(UserTopicPreference.topic_id)`. That **includes users who unsubscribed** (`User.unsubscribed_at` set).
- `relevance.active_subscriber_count` (AD-14) **excludes** them.

**Unit A: the candidate-list builder.** It follows AD-26 ("every topic with at least one subscriber") and copies the GH #45 idiom that includes unsubscribed users. It does not filter on `Topic.status`, because AD-26 does not say to.

**Unit B: the paid-stage eligibility filter.** It follows AD-22 ("eligible for at least one topic with a subscriber") and uses the AD-14 active definition, because that is the spine's only *defined* subscriber.

**How they clash:**
- A topic followed only by unsubscribed users is paid for in classification but never summarised.
- A **rejected** topic that still has subscribers is classified on every article (paid), even though AD-23 says it can never be eligible.
- A returning reader (`unsubscribed_at` cleared) counts as "entering" under Unit B's definition but not under Unit A's, so H2's trigger fires in one implementation and not the other.

**Proposed rule (new convention row):**
> One function, `candidate_topic_ids(db)` in `relevance.py`, returns non-rejected topics with at least one active subscriber. Fetch, candidate list, extract, summarize and the entry trigger all import it.

---

## H6 — HIGH: top-N cap scope is ambiguous, so extract and summarize pay for articles the digest can't use

AD-23 says: "When more topics are eligible than `max_topics_per_article`, only the top-N by score count." It does not say where N is counted.

**Unit A: the summarize and extract filter.** It follows AD-22 and AD-23. For each article, it checks whether *any* row is eligible for a subscribed topic, and applies top-N **after** filtering to subscribed topics. That is a reasonable reading: "eligible for at least one topic with a subscriber".

**Unit B: the digest resolver.** It follows AD-23 and AD-24. It applies top-N over **all** eligible topics of the article (a property of the article, reader-independent), then intersects with this reader's subscriptions.

**Worked example.** N=2. Article scores A 0.95, B 0.90, C 0.80. The only subscriber follows C, and A and B lost their subscribers after classification. Unit A summarises the article, because C is within its top-N of subscribed topics. Unit B drops it for the C reader, because C is outside the global top-2. The result is a paid summary that no one receives, and a starved C.

**Also:** ties at the N boundary resolve in SQL `ORDER BY` order in one unit and in Python's stable sort in the other.

**Proposed rule (tighten AD-23):**
> Top-N is counted per article over eligible topics, before any subscriber or reader filter. Ties break on `topic_id` ascending. Everyone uses one shared eligibility helper.

(Or explicitly the reverse. The point is that one owner and one query define it.)

---

## H7 — HIGH: the classifier result's shape is not pinned; topic names round-trip through LLM output

**Unit A: the external adapter story.** It follows AD-25: "one independent, absolute score per candidate". It asks for `{"scores": {"<topic name>": 0.8, ...}}` and returns `dict[str, float]`, with names echoed by the model.

**Unit B: the relevance-stage story.** It follows AD-26 and maps results back to `topic_id` by name. Topic names are user-typed, often Hebrew, and only whitespace-stripped (`preferences.py:84`).

**How they clash:**
- The model normalises niqqud, quotes, whitespace or letter case, or translates a name. The lookup misses, and rows are silently not written.
- The model omits a candidate or adds one. Unit A is still "compliant", since nothing says the response must have exactly as many scores as candidates.
- The mock adapter (hash-based) returns a tuple in input order. Unit A returns a dict. The contract suite passes both unless it asserts the result's shape.

A returned name never matching any candidate is also a prompt-injection vector: a user-typed topic name gets echoed back as a dictionary key.

**Proposed rule (tighten AD-25 Shape):**
> The result is a tuple of scores in the order of the candidates. Adapters fail the output as malformed on any length mismatch. Names never come back from the model.

---

## H8 — MEDIUM: AD-22 and AD-24 contradict each other on who may read `Source.topic_id`

**Unit A: an AD-22 guard story.** AD-22 says "Only `pipeline/fetcher.py:154` may scope on it". The Testing convention encourages break-by-hand guards, so a builder adds a test that greps for `Source.topic_id` or `source.topic_id` outside `fetcher.py`. (A similar denylist test already exists for gendered copy.)

**Unit B: the digest resolver story.** It follows AD-24, which requires "if the feed's own topic is among them" and therefore reads `article.source.topic_id` in `digest.py`. The GH #60 bootstrap also writes `Source.topic_id` for provenance.

**How they clash:** one of the two units fails the other's test. AD-22's list ("everything else ... moves to the new model", including `digest.py:62` and `:185`) gives no exemption for the tiebreak. "Scope on" versus "read" is left to interpretation.

**Proposed rule (tighten AD-22):**
> Allowed `Source.topic_id` uses: fetch scoping (fetcher), provenance write (sources service), and the presentation tiebreak (digest resolver). No other uses.

---

## H9 — MEDIUM: an empty candidate list turns into a terminal `refused`

**Unit A: an adapter story.** It follows AD-25 and the existing blank-input precedent (`_score_relevance` junk pre-check; #60's "Refusal on blank topic name"). It returns `Refusal("no candidates")` when `candidates == []`.

**Unit B: the relevance stage.** It follows AD-26. Once AD-22 forbids scoping relevance on `Source.topic_id`, it classifies every pending article. When no topic has an active subscriber (a fresh environment, stage DB, or every reader unsubscribed), the list is empty, and it maps `Refusal` to `STATUS_REFUSED` as `relevance.py:179` does today.

**How they clash:** every article fetched while the list is empty becomes permanently `refused`. AD-27's backfill only revisits `irrelevant`, so these articles are lost even after readers return.

**Proposed rule (tighten AD-26):**
> An empty candidate list means the stage does no work, and articles stay `pending`. Adapters may assume at least one candidate.

---

## H10 — MEDIUM: the "ready before next digest" promise straddles two processes that don't share a schedule

**Unit A: the GH #60 bootstrap.** It follows AD-5 and AD-27, and memlog line 41: fetch immediately, backfill immediately, in the API process.

**Unit B: the extract and summarize stories, unchanged.** AD-27 says "the existing extract and summarize stages pick it up unchanged". Those stages run only in the daily CLI (`scheduler.py` docstring: "Fetching, filtering and summarizing are NOT here").

**How they clash:** the backfill marks articles `relevant` in minutes, but they are not summarised until the next daily run. The newly discovered feed's articles are only `pending`, and only the daily run classifies them. Meanwhile `cadence.due_user_ids` makes a never-sent user due immediately, and the scheduler's welcome pass builds on the next 2-minute tick. The spine's Deferred entry covers only "a topic created moments before the digest while discovery is running". The real gap is up to 24 hours, and it covers every new user's first digest. Each unit meets its own ADs; the product promise that justified shipping backfill now (memlog line 40) is not delivered.

**Proposed rule (Deferred to AD-27 clause):**
> A new topic is ready only after the next daily pipeline run. Otherwise the bootstrap must also run extract and summarize for articles it touched.

This needs a product decision (John).

---

## H11 — MEDIUM: `DigestArticle` uniqueness arrives one release after the model that needs it

AD-24 states "An article appears at most once per digest" from release 1. The constraint that enforces it arrives in release 2.

**Unit A: the scheduler build path.** It follows AD-24 and the lease, so it builds sequentially.

**Unit B: CLI `build-digests`.** It follows the same ADs, but it is not under the scheduler lease (`cli.py:199` calls `build_digests` for all users).

**How they clash:** both compute `_undelivered_articles` for the same user and date concurrently, and both insert the same article. The window is not new, but release 1 widens every reader's candidate set (cross-feed eligibility) and adds per-(reader, article) resolution work, which lengthens the build and so the race window. Nothing at the DB level stops it until release 2. Release 2's "check and resolve duplicates" step then has to guess which row's `topic_id` to keep.

**Proposed rule (tighten AD-29):**
> Resolve duplicates and add `UNIQUE(digest_id, article_id)` in release 1. Old code already writes one row per article.

---

## H12 — MEDIUM: backfill telemetry fields admit two readings

**Unit A.** Backfill `subscriber_count` = active subscribers of T (usually 1). This follows AD-14: a shared stage counts the subscribers of topics it touched.

**Unit B.** Backfill `subscriber_count` = active subscribers of every candidate topic. This also follows AD-14 and mirrors the daily run's report.

**How they clash:** the new purpose constant exists precisely so user-triggered spend can be queried separately (memlog line 54). Cost per subscriber differs by 10x between implementations, and there is no way to reconcile historical runs. Concurrent backfills (two readers save preferences at once, each a `BackgroundTask` with its own thread pool) also double LLM concurrency past `filter_concurrency`, which no AD bounds.

**Proposed rule (tighten AD-27 Telemetry):**
> A backfill run's `subscriber_count` is T's active subscribers. Backfills share `filter_concurrency` through one process-wide semaphore.

---

## H13 — LOW: small undefined terms

- **"Within `topic_presentation_margin`"**: inclusive (`best - feed <= margin`) or exclusive? This matters in tests at margin 0.
- **"Best"**: best among the reader's eligible subscribed topics (AD-24's text), or best across the article's eligible topics? AD-24 implies the former; state it.
- **`interestingness` "only when currently null"** (AD-27) versus `summarize.py:160`, which always overwrites. This is the OQ-2 clash and is already tracked. It blocks writing a correct relevance-stage test until resolved.
- **Backfill on `refused` articles**: AD-27 names only `irrelevant`. State that `refused` and `error` are excluded (error belongs to the daily run).
- **Starvation log**: "zero eligible articles" should say whether top-N (H6) applies.

**Proposed rule:**
> The margin is inclusive, "best" means among the reader's eligible subscribed topics, and backfill targets only `irrelevant` and `relevant`.

---

## Summary table

| # | Severity | Pair | Closing rule (short) |
|---|---|---|---|
| H1 | Critical | daily run / backfill / R1 migration | `UNIQUE(article_id, topic_id)`; insert-if-absent; scores immutable |
| H2 | Critical | #60 bootstrap / relevance detector | entry = 0 to ≥1 active subscribers, detected at the preference write; once per entry |
| H3 | Critical | daily run / backfill (two processes) | status derived from rows; advisory lock; window on `scraped_at`; backfill only classified articles |
| H4 | High | release-0 processes / R1 and R2 migrations | R2 re-runs R1 backfills; all writers maintain `relevance_score` until R2 |
| H5 | High | candidate builder / paid-stage filter | single `candidate_topic_ids`: non-rejected, active subscribers |
| H6 | High | summarize filter / digest resolver | top-N per article before subscriber filter; tiebreak `topic_id` |
| H7 | High | external adapter / relevance stage | result positional, length-validated; names never round-trip |
| H8 | Medium | AD-22 guard / AD-24 tiebreak | enumerate allowed `Source.topic_id` reads |
| H9 | Medium | adapter / stage on empty list | empty list: no work, articles stay pending |
| H10 | Medium | #60 bootstrap / daily summarize | define readiness SLA or bootstrap runs extract+summarize |
| H11 | Medium | scheduler build / CLI build | digest unique constraint in release 1 |
| H12 | Medium | backfill telemetry readings | `subscriber_count` = T's; shared concurrency bound |
| H13 | Low | assorted terms | inclusive margin; "best" among the reader's topics; backfill status set |
