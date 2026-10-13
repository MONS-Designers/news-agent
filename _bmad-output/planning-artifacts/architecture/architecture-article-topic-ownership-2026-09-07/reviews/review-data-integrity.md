# Data-Integrity Review: Article Topic Ownership spine

- **Reviewer lens:** data model and migration integrity for a production cutover (Neon Postgres prod, sqlite tests)
- **Scope:** AD-23, AD-24, AD-27, AD-28, AD-29 and the ER diagram of `ARCHITECTURE-SPINE.md` (2026-09-14 draft)
- **Evidence read:** spine, `.memlog.md`, `project-context.md`, `models/{article,topic,source,digest,digest_article,digest_link,feedback,user_topic_preference,base}.py`, `pipeline/{relevance,digest,ranking}.py`, `alembic/env.py`, migrations `7de791f6b76c`, `a3f6c9d1e442`, `a06a39402215`, `d7f3a4b91e28`, `f9c2d7e0b118`, repo-wide grep for `relevance_score`
- **Date:** 2026-09-14. No database was touched, and nothing was edited except this file.

## Verdict

The expand/contract direction is right. The spine is **not yet safe as a build substrate for the data layer**, for two reasons:

- It never defines `article_topics`' key, conflict behaviour or concurrent-writer semantics, and AD-27 literally says "appends".
- The two-release plan leaves three data gaps open during the overlap window:
  - articles scored by old code get no `article_topics` rows
  - digest rows are written with a NULL `topic_id`
  - old ranking code reads a max score with different meaning

  These gaps cause silent article loss, a failed release-2 migration, or exactly the "stretched" delivery the spine is meant to prevent.

All of them can be fixed inside the spine with a few added rules. None needs a redesign.

---

## Critical

### C1. `article_topics` has no key, and AD-27 says "append". Duplicates are guaranteed.

**Where:** AD-23 names the table as `article_topics(article_id, topic_id, score)`. AD-27 says "appends `article_topics` rows". The ER diagram has no key. AD-29 plans duplicate cleanup only for `digest_articles`.

**Why it breaks:**

- **Topics re-enter the candidate list.** "A topic enters the candidate list" is not a one-time event. A topic whose last subscriber leaves drops out of the list (AD-26: "at least one subscriber"), and re-enters when anyone subscribes again. That fires a second backfill over the same window, and the backfill includes articles that already have a row for that topic.
- **Two writers race.** The GH #60 bootstrap backfill (API process, `BackgroundTask`) and the daily filter run (CLI process) can both classify the same pair concurrently. A `pending` article inside the window is picked up by the daily run against the full list, which now includes the new topic. The backfill scores the same article against that topic at the same moment.
- **A re-run migration duplicates everything.** Release 1's backfill has no stated guard, so re-running it after a partial failure, or on the stage branch and then again, duplicates every row.

**Impact:** a duplicate (article, topic) row breaks the read-time model.

- "Top-N by score among eligible" counts the same topic twice, which can push a genuinely eligible second topic out of the top N.
- The presentation margin compares a topic against itself.
- The planned dedupe step doesn't cover this table, so the damage is permanent.

**Fix (add to AD-23 and AD-27):**

1. **Composite key.** Make the primary key `PRIMARY KEY (article_id, topic_id)`, with no surrogate `id`. Declare it in the model (`primary_key=True` on both columns) *and* in the migration, so `create_all` in tests and Alembic in prod agree.
2. **Conflict semantics: first score wins.** Write with `INSERT … ON CONFLICT (article_id, topic_id) DO NOTHING`. That matches "classify once" and makes the backfill idempotent. If re-scoring is ever wanted, it is a separate, explicit `DO UPDATE` path, never the default.
   - SQLAlchemy has no portable upsert, so the relevance stage needs a tiny dialect switch: `sqlalchemy.dialects.postgresql.insert` vs `sqlalchemy.dialects.sqlite.insert`, both of which support `on_conflict_do_nothing`. Alternatively, catch `IntegrityError` per article and commit per article, as the stage already does.
   - State which option in the spine, so two builders don't pick differently.
3. **Skip already-scored pairs.** The backfill's article query excludes pairs that already exist (`NOT EXISTS (SELECT 1 FROM article_topics WHERE article_id = a.id AND topic_id = :t)`), so re-entry costs zero LLM calls for articles already scored.
4. **Replace "appends" with "inserts if absent".**

### C2. Articles scored by old code during the overlap never become eligible (silent loss)

**Where:** AD-29 release 1 backfills `article_topics` "for already-scored articles" inside the migration. AD-27 keeps `_FILTERABLE = (pending, error)`.

**Sequence:**

1. The migration runs and backfills.
2. The daily pipeline, still on old code until restarted, runs `filter`.
3. Old code writes `relevance_score` and sets `relevance_status` to `relevant` or `irrelevant`, but writes **no `article_topics` row**.
4. New code starts. These articles are no longer `pending` or `error`, so they are never re-classified.
5. Under AD-23 they have no eligible topic, so they never reach any digest. Paid summarize output for them is wasted.

No error is raised and no count reveals it. It isn't limited to the daily run: any manual `newsagent filter` run in the window does the same thing.

**Fix (add to AD-29):**

- Write the release-1 backfill as an **idempotent, re-runnable data step**. A set-based `INSERT … SELECT … WHERE a.relevance_score IS NOT NULL AND NOT EXISTS (…)`, with ON CONFLICT DO NOTHING per C1.
- **Run it twice.** Once inside the release-1 migration, and again as a mandatory step after all three processes run release-1 code. The second pass can be a small CLI subcommand, or the first statement of the release-2 migration.
- **Verification gate before release 2:** `SELECT count(*) FROM articles a WHERE a.relevance_score IS NOT NULL AND NOT EXISTS (SELECT 1 FROM article_topics t WHERE t.article_id = a.id)` must be 0.

---

## High

### H1. Release 2 as written ("drop the column and stop writing it") takes down every release-1 process

**Where:** AD-29 release 2.

**Mechanism:**

- SQLAlchemy selects every mapped column on every `select(Article)`. Release-1 code maps `relevance_score`, because it dual-writes it.
- Migrations here are applied by hand (`alembic upgrade head`; `Dockerfile.backend` only copies `alembic/`, and nothing runs it at start-up).
- If the drop migration runs before all three processes are on code that no longer maps the column, every article query in the scheduler, pipeline and API fails with `column articles.relevance_score does not exist`.
- The spine's ordering sentence ("only after all three processes run release-1 code") guards the wrong boundary. What must be true is that all three run **release-2 code**, which no longer maps the column, before the drop.

**Fix:** split release 2 into two ordered steps and say so in AD-29.

- **2a (code only):** remove `relevance_score` from `models/article.py` and stop writing it. Deploy all three processes. No migration yet. The column stays in Postgres, unused and harmless.
- **2b (migration):** first check the C2 gate and resolve duplicates (H3). Then drop the column, add the unique constraint, and set `topic_id` NOT NULL.

State explicitly that code comes first for a contract step and migration first for an expand step.

### H2. Digest rows written by the old scheduler during the overlap have NULL `topic_id`, so release 2's NOT NULL fails, and new reads must tolerate NULL

**Where:** AD-29 backfills `DigestArticle.topic_id` inside the release-1 migration only. AD-24 says every single-topic read uses the presented topic.

**Mechanism:**

- The delivery scheduler runs every ~2 minutes. After the migration and before its restart, it inserts `DigestArticle(digest_id, article_id)` with `topic_id` NULL. The old model doesn't map the column.
- **Release 2 fails.** `SET NOT NULL` will fail on those rows. The failure is transactional on Postgres, so no data is lost, but the rollout is blocked.
- **New reads mis-attribute in the meantime.** Release-1 new code reading `DigestArticle.topic_id` for affinity (`ranking.py:43`) and for the same-day rerun diversity floor (`digest.py:185`) will see NULL for those rows. If it skips them, the affinity is wrong. If it groups them under a `None` key, a same-day rerun thinks topic `None` is represented. Neither case is specified.

**Fix:**

- Make the `DigestArticle.topic_id` backfill idempotent (`UPDATE digest_articles SET topic_id = (SELECT s.topic_id FROM articles a JOIN sources s ON s.id = a.source_id WHERE a.id = digest_articles.article_id) WHERE topic_id IS NULL`), and re-run it as the first statement of the release-2b migration, right before `SET NOT NULL`.
- **Add a rule to AD-24.** Historical digest rows with NULL `topic_id` are read as the feed topic, *for history only* (affinity, rerun floor). This does not contradict "no fallback": that rule governs eligibility of new candidates, not attribution of already-delivered rows. Say so explicitly, so a builder doesn't "fix" it by excluding the rows.
- **Operational alternative:** stop the scheduler (it has a lease and tolerates a gap) from migration until its restart on release 1. This closes H2 and H4 at once. Record it as the preferred deploy order.

### H3. The duplicate-resolution policy for `digest_articles` is unspecified, and the unique constraint has no concurrent-insert handling

**Where:** AD-29 says "check for existing duplicate `(digest_id, article_id)` rows and resolve them".

**Findings:**

- **Duplicates are possible today.** `_undelivered_articles` excludes already-sent articles per build, but two concurrent builds for the same user and date can each insert the same pair. For example, the CLI `digest` command running while the scheduler holds its lease; the lease only guards scheduler replicas.
- **What can be deleted.** Nothing references `digest_articles.id`. `digest_links` and `feedback` key on `(digest_id, article_id)`, not the row id. So deleting the extra rows loses no links or feedback. It *does* change historical "how many articles did this digest have" counts, and it is a production data deletion that needs explicit user approval (standing rule).
- **Build failure after the constraint lands.** A racing builder hits `IntegrityError` at `db.flush()` (`digest.py:203`), which aborts that user's whole build transaction, including voice composition.

**Fix:**

- **Resolution rule:** keep `MIN(id)` per `(digest_id, article_id)` and delete the rest. The migration first prints the count and aborts if it is nonzero, so the delete is a separate, reviewed, user-approved step rather than silently embedded.
- **Explicit name:** name the constraint `uq_digest_articles_digest_id_article_id` in both the model's `__table_args__` and the migration. The house precedent is `uq_digests_tracking_token`. `Base` has no naming convention, and an unnamed model constraint would get Postgres's auto name. That breaks a later `batch.drop_constraint` and makes sqlite batch mode unable to reference it.
- **AD-24 rule:** the builder skips an article already attached to this digest, re-checking inside the transaction. The alternative is to treat `IntegrityError` on this constraint as "already attached" and continue.

### H4. During the overlap, old ranking code reads `relevance_score = max candidate score`, which delivers exactly the "stretched" article AD-24 forbids

**Where:** AD-29 dual-writes `relevance_score` as the maximum candidate score, and new `relevance_status` means "at least one candidate passed".

**Mechanism with an old scheduler still running:**

1. Feed F belongs to topic X. The new classifier scores article A: X = 0.1, Y = 0.9.
2. The new filter sets `relevant` and `relevance_score = 0.9`.
3. New summarize pays for A, correctly, because it is eligible for Y.
4. The old `_undelivered_articles` scopes by `Source.topic_id IN (X subscribers)` and checks only `summary_status`.
5. So the old builder delivers A to an X-only reader. It ranks it at 0.9 (`ranking.py:72`) and labels it X.
6. The `DigestArticle` row marks A as delivered to that reader forever. It will never be shown to them under Y.

This is harmful, not cosmetic: it is the user's stated fear, and it persists in delivery history. Dual-writing prevents the `None * float` crash, but not this semantic disagreement.

**Fix (pick one and write it into AD-29):**

- **(a) Preferred:** pause the scheduler from migration until it restarts on release-1 code, so no old digest build overlaps new classification. The filter/summarize stages write only per-article data and are safe to overlap.
- **(b)** Dual-write the **feed topic's** score, not the max. Fall back to the max only if the feed topic isn't a candidate, which old digest code can't select anyway, since it scopes to subscribed feed topics. Keep in mind the old builder will still deliver articles eligible only for another topic. (b) reduces the damage but doesn't remove it, which is why (a) is preferred.

### H5. Candidate-list entry detection is not persisted, so the first run after cutover can backfill every topic

**Where:** AD-27 is triggered by "when a topic enters the candidate list", but no column or table records which topics were already candidates or already backfilled.

**Why:**

- The release-1 backfill seeds only the feed-topic score for each article.
- If "entered" is derived from data, such as "topic has no `article_topics` rows in window" or "topic not in last run's list" (in-memory, lost on restart), then every subscribed topic looks new on the first release-1 run.
- That triggers a window-sized paid backfill of every topic against every article. That is the quadratic spend AD-26/27 try to avoid, and it happens on the first deploy.
- The same ambiguity makes "did the backfill already run for topic T" unanswerable after an AD-5 crash.

**Fix:** persist the fact.

- Add a nullable `topics.candidate_backfilled_at` (or `candidate_since`) column in the release-1 migration.
- **Backfill** it to `now()` for every topic that currently has a subscriber, so the cutover is not "entry".
- **Clear it** when the topic's last subscriber leaves, if re-entry should backfill again. Otherwise leave it and rely on C1's NOT EXISTS to keep re-entry cheap.
- **Set it** only when the backfill run closes successfully. A crashed backfill (AD-5) is then detectable and can be retried by the daily run.
- The relevance stage is its sole writer (extend AD-28).

---

## Medium

### M1. Concurrent `relevance_status` writes are a lost update

AD-28 names one *component* as sole writer, but that component runs in two processes (the daily CLI and the API `BackgroundTask`).

- The daily run computes `relevant`/`irrelevant` from its candidate list, which may predate topic T.
- The backfill for T sets `relevant`.
- Whichever commits last wins. If the daily run commits `irrelevant` after the backfill set `relevant`, an article that is eligible for T is never extracted or summarized.

**Fix:** have both writers only *promote* the verdict, never demote it, with `UPDATE articles SET relevance_status='relevant' WHERE id=:id AND summary_status <> 'summarized'`. The daily run may set `irrelevant` only with `WHERE relevance_status IN ('pending','error')`. A cheaper equivalent: after each insert, recompute the status from `article_topics` in the same transaction.

State this conditional-update rule in AD-28.

### M2. The stored verdict drifts from read-time eligibility, and AD-23 gates paid stages on both

`relevance_status` is the verdict against the *threshold at classification time*. After a threshold change (the reason the spine stores every score), an article can be `irrelevant` yet have a candidate ≥ the new threshold, or `relevant` with none.

- Lowering the threshold never promotes old articles, so extract and summarize ignore them.
- Raising it is harmless, because read-time eligibility filters.

**Fix:** one of two options, either way explicit in AD-23.

- Document that a threshold change re-verdicts via a relevance-stage entry point: a set-based `UPDATE`, no LLM calls, with the relevance stage as sole writer.
- Or make extract/summarize gate on read-time eligibility alone and treat `relevance_status` purely as the classification-attempt state (`pending`/`classified`/`refused`/`error`).

### M3. The release-1 backfill must be set-based, not the row loop of prior migrations

The only precedent that writes computed data via a Python loop, `a3f6c9d1e442`, runs one `UPDATE` per row. Against Neon over the network, that is thousands of round-trips inside one migration transaction, and `env.py` wraps the whole run in a single `begin_transaction`, which holds locks throughout.

**Fix:** a single `INSERT INTO article_topics (article_id, topic_id, score) SELECT a.id, s.topic_id, a.relevance_score FROM articles a JOIN sources s ON s.id = a.source_id WHERE a.relevance_score IS NOT NULL AND NOT EXISTS (…)`, via `op.execute(sa.text(...))`, like `d7f3a4b91e28`.

- It is portable to sqlite and Postgres.
- At the stated scale (tens of users, likely at most tens of thousands of articles), one transaction is fine and gives atomic rollback on Postgres, which has transactional DDL.
- Run the data SQL **outside** the `batch_alter_table` block, following the note in `a06a39402215` (sqlite batch mode rebuilds the table by copy).
- Also add a pre-migration count query to the plan shown to the user. It must include articles with `relevance_status='relevant' AND relevance_score IS NULL`, which should be 0; any such rows would silently lose eligibility.

### M4. Backfill scope decisions that should be written down

These are recommendations to *state*; they are not defects.

| Case | Recommended rule | Reason |
| --- | --- | --- |
| `relevance_score IS NULL` (pending, error, refused) | no row | pending/error are classified by new code; refused is terminal |
| `refused` with a non-NULL score (not produced by current code, but check) | no row | refusal means no trustworthy score |
| scored `irrelevant` | **row inserted** (below-threshold score) | AD-23 stores every candidate score |
| source or topic later `rejected` | **row inserted** | rejection is applied at read time (AD-23); filtering here would make un-rejecting lose data |
| topic with no subscribers now | row inserted | same reason; a fact is not a policy |
| historical articles vs other topics | never scored | accepted gap: only AD-27 backfills cross-topic, and only inside the window. Note it in Deferred |

### M5. FK ON DELETE behaviour is unspecified

Nothing in `src/` deletes articles, topics or sources today (grep for `delete(`: only `UserTopicPreference`). Admin rejection is a status change. Existing FKs have no `ondelete`.

**Recommendation:**

- **`article_topics.article_id`:** `ON DELETE CASCADE`, since the rows are derived facts about the article.
- **`article_topics.topic_id`:** `ON DELETE CASCADE`. Topic deletion is blocked anyway by `sources`, `user_topic_preferences` and `digest_articles`.
- **`digest_articles.topic_id`:** default `NO ACTION`/RESTRICT, since delivery history must never silently lose its presented topic.

Write this into the model and migration explicitly. Also note that sqlite enforces none of it (see T2).

### M6. Read-time top-N must be deterministic and computed in a defined order

"When more topics are eligible than `max_topics_per_article`, only the top-N by score count" has two unstated details.

- **Filter vs cap order.** Is the cap applied after the status filters (rejected topic or source) and before the reader's subscription filter? If a builder caps before excluding rejected topics, a rejected topic occupies a slot. If a builder caps after the subscription filter, the cap becomes per-reader, which contradicts "eligible for a topic" being reader-independent.
- **Ties.** Equal float scores (the mock adapter hashes to repeated values) make `ORDER BY score DESC` non-deterministic across Postgres and sqlite.

**Fix:** define it as `ROW_NUMBER() OVER (PARTITION BY article_id ORDER BY score DESC, topic_id ASC)` over rows that already passed threshold and both status checks, then `rn <= N`, then join to subscriptions. Window functions work on Postgres and sqlite ≥ 3.25.

---

## Low

### L1. Indexes

At tens of users these tables are small. Add only what the known queries use.

- **`article_topics`:** the PK `(article_id, topic_id)` covers per-article lookup and the conflict target. Add `ix_article_topics_topic_id_score` on `(topic_id, score)` for the per-topic backfill `NOT EXISTS`, the starvation log ("topics with zero eligible articles in window") and the eligibility join driven from subscribed topics.
- **`articles.scraped_at`:** the backfill window filter `scraped_at >= now() - window` otherwise scans `articles`. It is cheap to add in release 1.
- **`digest_articles`:** the release-2 unique constraint also gives a `(digest_id, article_id)` index for the rerun and voice-reuse queries.
- **`articles.source_id`:** no index today (Postgres doesn't auto-index FKs). It is pre-existing and not required by this spine, so mention it but don't bundle it.

### L2. Downgrade paths

**Release 1 downgrade** (drop `article_topics`, drop `digest_articles.topic_id`):

- It is mechanically safe, since `relevance_score` is still dual-written.
- It is **lossy**: every cross-topic score and every presented topic written since cutover is lost, and articles that are `relevant` only for a non-feed topic are then treated by old code as relevant to their feed topic (the H4 effect, permanently).
- Document this in the migration docstring, like `a06a39402215` does.

**Release 2b downgrade:**

- **Constraints:** drop the unique constraint and make `topic_id` nullable.
- **Score column:** re-add `relevance_score` nullable, and backfill it from `article_topics`, preferring the feed-topic score, else `MAX(score)`. Release-1 code would otherwise crash on `relevance_weight * None` (`ranking.py:72`) for articles classified after 2b.
- **Unrecoverable deletions:** duplicates deleted in H3 cannot be restored. Say so.

### L3. Release-2 read-site inventory (grep, 2026-09-14)

Production readers and writers of `Article.relevance_score` are limited to:

- `pipeline/ranking.py:72` (read; release-1 new code must already read the presented topic's score from `article_topics`)
- `pipeline/relevance.py:183` (write)

**No admin endpoint, CLI report, schema or frontend reads it.** The following must move before 2a:

- `tests/test_scheduler.py:50`
- `tests/pipeline/test_relevance.py:68-69, 84`
- `tests/pipeline/test_ranking.py:41, 54, 88, 93, 171-173, 191-193, 206, 220-221` (the `add_article` helper takes `relevance_score`)
- `tests/pipeline/test_digest.py:38, 46`
- `FilterReport.scores` (`relevance.py:44`) is one float per article. Decide whether it becomes the max per article or all candidate scores, because the "borderline" log line changes meaning.
- Docs: `docs/architecture-cli.md:58` and `docs/data-models-backend.md:122`.

The fixtures above should move in **release 1**, since new ranking no longer reads the column. Release 2 then deletes only the model attribute and the write.

---

## Test implications (sqlite vs Postgres)

- **T1. Migrations are never exercised.** `project-context.md` says the suite uses `create_all`, and the upgrade path is untested. The backfill SQL, the NOT EXISTS idempotency, `SET NOT NULL`, the unique constraint over existing duplicates, and both downgrades exist only in migrations.
  - **Fix:** a one-off verification run of `alembic upgrade head`, then `downgrade -1`, then `upgrade` again, against a **Neon stage branch** seeded from a prod snapshot, with the C2 and H3 gate queries run before and after. Show it to the user first (standing rule). Optionally add a test that runs Alembic against a temp-file sqlite DB seeded with scored articles and a duplicate digest row; batch mode makes that feasible.
- **T2. sqlite doesn't enforce FKs.** No `PRAGMA foreign_keys=ON` exists anywhere in the repo, so M5's CASCADE/RESTRICT behaviour and bad `topic_id` values are invisible in tests. Either add the pragma via an `event.listen(engine, "connect")` in the article-topic tests, or accept this and cover it in the T1 run.
- **T3. Upsert is dialect-specific.** `on_conflict_do_nothing` exists on both dialect `insert` constructs, with different import paths. Test the helper on sqlite, and make sure the Postgres branch is exercised at least once in the T1 run.
- **T4. Races can't be reproduced on sqlite.** The C1 and M1 races need real concurrent transactions. The shared `StaticPool` connection serialises everything. Test the *logic* deterministically instead: insert a row for (article, T) first, then run the backfill and assert no error and one row; and a promote-only status update. Per the spine's testing convention, break the conflict clause by hand and confirm the test fails.
- **T5. Constraint names matter under batch mode.** On sqlite, batch mode rebuilds the table from reflected metadata; an unnamed unique constraint can't be dropped later. Name every new constraint and index explicitly (H3).
- **T6. Float boundaries.** `score >= threshold` behaves the same on Postgres `double precision` and sqlite `REAL`, but the mock adapter should include a score exactly equal to the threshold in one test, to pin `>=` vs `>`.

---

## Suggested spine edits (summary)

1. **AD-23:** `article_topics` PK `(article_id, topic_id)`; FK ON DELETE rules; `(topic_id, score)` index; deterministic top-N order and filter-before-cap (C1, M5, M6, L1).
2. **AD-27:** "insert if absent" plus NOT EXISTS skip; persisted `topics.candidate_backfilled_at` as the entry marker, set on successful close (C1, H5).
3. **AD-28:** relevance status is promote-only under concurrent writers; the entry marker has a sole writer (M1, H5).
4. **AD-24:** historical NULL `topic_id` is read as the feed topic for history only; skip or handle an already-attached pair (H2, H3).
5. **AD-29:**
   - scheduler paused from the release-1 migration until its restart
   - idempotent backfills re-run before release 2, with gate queries
   - release 2 split into 2a (code) and 2b (migration)
   - named constraint, and a duplicate policy that aborts rather than auto-deletes
   - set-based SQL
   - documented lossy downgrades
   - a stage-branch upgrade/downgrade rehearsal

   (C2, H1–H4, M3, L2, T1)
6. **ER diagram:** mark `ARTICLE_TOPIC` with its composite key and `score`, and `DIGEST_ARTICLE` with `topic_id` (NOT NULL after release 2) and the unique `(digest_id, article_id)`.
