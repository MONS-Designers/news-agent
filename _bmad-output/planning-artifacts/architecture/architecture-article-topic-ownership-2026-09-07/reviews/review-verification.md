# Verification Review — Article Topic Ownership spine

- **Reviewer lens:** was each committed decision checked against reality (the repo, pinned dependencies, live docs), or asserted from memory?
- **Reviewed:** `ARCHITECTURE-SPINE.md` (status draft, 2026-09-14) and `.memlog.md`.
- **Date:** 2026-09-14.

## Verdict

The spine is well grounded. Almost every code claim checks out against the repo, and the library claims it leans on hold for the pinned versions. There are four real gaps:

1. Two file:line references are wrong, and AD-22's list of reads to move misses two lines.
2. AD-29's expand/contract plan ignores rows written by old code during the overlap window.
3. The API background-task precedent in the repo silently breaks AD-27's session rule. The FastAPI reasoning in that precedent is also stale for the pinned version.
4. The deploy topology AD-29 depends on (a scheduler running in prod) is not confirmed by infra-as-code.

## Pinned versions (verified)

Sources: `requirements.txt`, `pip show` in the local environment, and the `Dockerfile.backend` base image.

| Package | Version | Behaviour the spine leans on |
| --- | --- | --- |
| Python | 3.12 (`python:3.12-slim`; local 3.12.10) | contextvars / executor semantics |
| FastAPI | 0.139.2 | BackgroundTasks, and when yield-dependency cleanup runs (changed across versions, see F-6) |
| Starlette / anyio | 1.3.1 / 4.14.2 | how a sync background task is run in a worker thread |
| SQLAlchemy | 2.0.51 | `sessionmaker(expire_on_commit=False)`, `StaticPool` |
| Alembic | 1.18.5 | `op.batch_alter_table` |
| psycopg | 3.3.4 | none specific |

The spine records no versions. That is acceptable at feature altitude, but F-6 shows one decision that depends on the FastAPI version. **Fix (low):** note FastAPI >= 0.118 next to AD-5/AD-27.

## Findings

### F-1 — Wrong line references in AD-22
- **Claim:** reads to move include `render.py:151/163` and `ranking.py:93-100` (the diversity floor).
- **How checked:** grepped every `source.topic` / `Source.topic_id` reference under `src/`.
- **Result: wrong.**
  - `render.py:151` is `return link`. The topic read is at `render.py:159`, and the label and colour are set at `render.py:170-171`.
  - `ranking.py:93-100` is the `select_top` docstring. The diversity-floor read is at `ranking.py:125`.
  - Correct: `ranking.py:43`, `ranking.py:65`, `digest.py:62`, `digest.py:185`, `summarize.py:93`, `summarize.py:100`, `extract.py:85`, `fetcher.py:154`, `relevance.py:143`.
- **Severity:** medium. A builder working from the list will look in the wrong place, and "every reader" is the point of AD-22.
- **Fix:** replace with `render.py:159,170-171` and `ranking.py:125`.

### F-2 — AD-22 misses two `Source.topic_id` readers in relevance.py
- **Claim:** "Only `pipeline/fetcher.py:154` may scope on it", followed by an exhaustive-looking list of reads to move.
- **How checked:** same grep as F-1.
- **Result: incomplete.**
  - `relevance.py:120` scopes articles with `Source.topic_id.in_(subscribed_topic_ids)`.
  - `relevance.py:127` derives `subscriber_count` topic ids from `article.source.topic_id`.
  - AD-26 implicitly replaces both, but neither is named. A builder could keep the line-120 filter. That would violate "only fetcher may scope", and it would also stop backfill and classification from ever seeing articles from feeds whose own topic has no subscriber.
- **Severity:** medium.
- **Fix:** add both lines to AD-22's list. State that line 120 is replaced by AD-26's candidate list, and that line 127 is recomputed from the candidate list.

### F-3 — AD-29 overlap window leaves old-code rows unbackfilled
- **Claim:** release 1 backfills `article_topics` and `DigestArticle.topic_id` from existing data. Release 2 later makes `topic_id` NOT NULL and adds a unique constraint.
- **How checked:** reasoned through the three independently restarted processes. The scheduler loop (`scheduler.py:122`) imports `pipeline.digest`; the pipeline runs via CLI. Old code paths were read in `relevance.py` and `digest.py`.
- **Result: gap (not asserted wrong, but unaddressed).**
  - Between the release-1 migration and the restart of each process, old code keeps running.
  - The old pipeline writes `relevance_score` only and no `article_topics` rows. New readers treat those articles as ineligible, so they silently never reach a digest.
  - The old scheduler inserts `DigestArticle` rows with `topic_id = NULL`. New affinity and rerun reads get NULLs, and release 2's `SET NOT NULL` fails on them.
  - A one-time backfill inside the release-1 migration cannot cover rows written after it ran.
- **Severity:** high. Articles disappear silently, and the release-2 migration can fail in prod.
- **Fix:** make the backfill idempotent and re-run it at the start of release 2, before the duplicate check, the unique constraint and NOT NULL. Alternatively, run it as an explicit step once all three processes are confirmed on release-1 code. Also state how "all three run release-1 code" is verified.

### F-4 — Release-2 DDL locking on Postgres (not considered)
- **Claim:** release 2 adds `UNIQUE(digest_id, article_id)` and `SET NOT NULL` via `batch_alter_table`.
- **How checked:** PostgreSQL docs, `ALTER TABLE` (postgresql.org/docs/current/sql-altertable.html).
- **Result: confirmed workable, with a caveat.**
  - Both statements take `ACCESS EXCLUSIVE` and scan the table.
  - `digest_articles` is small at tens of users, so this is acceptable.
  - The lock-free alternatives are `CREATE UNIQUE INDEX CONCURRENTLY` followed by `ADD CONSTRAINT ... UNIQUE USING INDEX`, and a valid `CHECK (topic_id IS NOT NULL)` so that `SET NOT NULL` skips the scan. Neither is needed now.
- **Severity:** low.
- **Fix:** one line in AD-29 stating the lock is accepted because of table size.

### F-5 — `op.batch_alter_table` on Postgres
- **Claim:** both releases use `op.batch_alter_table`.
- **How checked:**
  - Alembic batch docs (alembic.sqlalchemy.org/en/latest/batch.html): with the default `recreate="auto"`, the move-and-copy recreate happens only on SQLite. Postgres receives ordinary `ALTER` statements.
  - Repo precedent: `f9c2d7e0b118_drop_digest_article_summary.py:21,26` plus three other revisions.
  - `alembic/env.py` has no `render_as_batch`.
  - No test runs migrations. A local `newsagent.db` (SQLite) exists, which is where batch mode matters.
- **Result: confirmed.**
- **Caveat:** `models/base.py` defines no `MetaData(naming_convention=...)`. On the SQLite recreate path, an unnamed unique constraint cannot be dropped or referred to later.
- **Severity:** low.
- **Fix:** AD-29 should require an explicit constraint name, e.g. `uq_digest_articles_digest_id_article_id`.

### F-6 — Existing API background-task precedent contradicts AD-27's session rule; its FastAPI reasoning is stale
- **Claim (AD-27):** whatever process calls the backfill uses a session factory with `expire_on_commit=False`. **Claim (AD-5):** BackgroundTasks run in-process after the response.
- **How checked:**
  - `db.py:7`: `SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)`.
  - `api/deps.py:8-10`: `get_db` yields a `SessionLocal()`.
  - `api/routers/me.py:122-125`: the background task gets `db.get_bind()`.
  - `services/profile.py:502`: `with Session(engine) as db:`, a bare `Session`, so SQLAlchemy's default `expire_on_commit=True` applies.
  - FastAPI docs (advanced-dependencies, version history):
    - 0.106.0 moved yield-dependency cleanup before the response.
    - 0.118.0 moved it back to after the response.
    - 0.121.0 added `Depends(scope=...)`, whose default `"request"` runs cleanup after the response and background tasks.
    - The pinned version is 0.139.2.
- **Result:**
  - AD-5 is confirmed.
  - The spine's `expire_on_commit=False` requirement is justified, and the only existing API background-task pattern violates it. A #60 builder copying `run_suggestion_computation` gets expired ORM objects after each per-item commit.
  - The `me.py` comment "the request-scoped session is already closed by the time this BackgroundTask runs" is **wrong for FastAPI 0.139.2**. It was true only for 0.106–0.117. Passing the bind is still the right pattern, for a different reason: the request session stays open until the background task finishes.
- **Severity:** medium.
- **Fix:** in AD-27, name the trap explicitly: build the session from `SessionLocal` (or a `sessionmaker(..., expire_on_commit=False)`), not a bare `Session(engine)` as in `profile.py:502`, and never reuse the request session. Flag the stale `me.py` comment separately; it is out of scope for the spine.

### F-7 — contextvars do not propagate into ThreadPoolExecutor; `copy_context().run`
- **Claim:** worker calls must go through `contextvars.copy_context().run`.
- **How checked:**
  - Python 3.12 docs: `concurrent.futures` says nothing about context propagation, so `submit` does not copy context. `contextvars` states `Context.run` raises `RuntimeError` if the same Context is entered from more than one OS thread.
  - Repo: `telemetry/context.py:15-17`, `relevance.py:151-155` and `summarize.py:123-127` copy per submit. `services/profile.py:386-403` does the same.
- **Result: confirmed.**
- **Two nuances:**
  - The copy must be **per submit**. One shared `ctx` reused across workers raises `RuntimeError`.
  - When the backfill runs as a sync FastAPI BackgroundTask, Starlette runs it through `anyio.to_thread.run_sync`, which does copy the caller's context (anyio 4.x docs). The backfill therefore inherits the request's contextvars. This is harmless only because AD-27 opens its own run.
- **Severity:** low.
- **Fix:** write "a fresh `copy_context()` per submitted call" in AD-27.

### F-8 — Scheduler is a separate long-lived process
- **Claim:** three independently restarted readers: API, `python -m newsagent.scheduler`, and the daily CLI pipeline.
- **How checked:**
  - `scheduler.py`: a `while not _stopping` loop at line 122, a lease row via `services/scheduler_lease`, and imports of `pipeline.digest` and `pipeline.send`.
  - `Dockerfile.backend:76`: CMD is uvicorn only.
  - `news-agent-infra/deploy/for-naomi/Dockerfile.backend:78-90` documents running the scheduler as a second container.
  - Grep for "scheduler" in `news-agent-infra/terraform/` and `.github/workflows/`: no hits.
- **Result:** the code shape is confirmed; **prod deployment is unverifiable** from infra-as-code. Batch-pipeline hosting is also still open, as the spine says.
- **Severity:** medium. AD-29's gate "only after all three processes run release-1 code" has no verifiable way to confirm a process is on new code.
- **Fix:** add to OQ or Deferred: confirm with Moshe where the scheduler and pipeline actually run, and how their code version is observed during a deploy.

### F-9 — `_FILTERABLE`
- **Claim:** `_FILTERABLE` is `pending`, `error`.
- **How checked:** `relevance.py:35`, used at `:118`.
- **Result:** confirmed. **Severity:** none.

### F-10 — `score_relevance` callers
- **Claim:** exactly one production caller; `score_relevance_many` has none; about 15 tests plus `llm/demo.py:35` use it.
- **How checked:** grep.
  - Production: `relevance.py:95`.
  - `score_relevance_many` is defined at `base.py:59` and called only at `tests/llm/provider_contract.py:96`.
  - Tests: `test_call_recording.py` has 6 calls, `test_external_provider.py` 8, `test_mock_contract.py` 1 line with 2 calls, and `provider_contract.py` 4 more. `demo.py:35` also calls it.
- **Result:** confirmed. The count is slightly higher once the contract suite's own 4 calls are included.
- **Severity:** none.

### F-11 — Fetcher stores every entry with no age cutoff
- **How checked:** `fetcher.py:112-135`. `_write_feed_to_db` dedupes by `Article.url` only and applies no date filter.
- **Result:** confirmed. **Severity:** none. The backlog-spend note under Deferred is accurate.

### F-12 — No `services/` module imports `pipeline/` (OQ-1)
- **How checked:** grep for pipeline imports in `src/newsagent/services/*.py` and `src/newsagent/api` found none. `topic_sourcing.py` does not exist yet.
- **Result:** confirmed. **Severity:** none. OQ-1 is correctly framed.

### F-13 — Models and settings
- **How checked:**
  - `models/digest_article.py`: `id`, `digest_id`, `article_id`, `created_at`. No unique constraint, no `topic_id`.
  - `models/source.py`: `topic_id` is non-optional `Mapped[int]`, i.e. NOT NULL. Status values are plain string constants.
  - `models/article.py:27`: `relevance_score` is a nullable Float.
  - `config.py:6`: `env_prefix="NEWSAGENT_"`. `EXTERNAL_LLM_*` use unprefixed aliases (`:107-109`). `relevance_threshold = 0.7` (`:18`).
- **Result:** confirmed. **Severity:** none.

### F-14 — Adapter conventions (AD-15, AD-25)
- **How checked:**
  - `external.py:27,140`: `mark_malformed()` before raising.
  - The "data, not instructions" preamble is at `external.py:246`.
  - `mock.py:68` defines `_maybe_fail`, called first at `:86/99/135`. `mock.py:123/144` derive values deterministically with `hashlib.sha1`; `random` is not used.
- **Result:** confirmed. **Severity:** none.

### F-15 — `interestingness` produced by summarize
- **How checked:** `external.py:234,265` and `summarize.py:160`.
- **Result:** confirmed. **Severity:** none. OQ-2 is correctly grounded.

### F-16 — Telemetry and testing conventions
- **How checked:**
  - `telemetry/types.py:19` defines `PURPOSE_FILTERING`.
  - `telemetry/__init__.py:19-26,43-50` exports purposes alphabetically.
  - `tests/conftest.py:24-48` and `tests/api/conftest.py:46-47` use `StaticPool` with `check_same_thread=False`.
- **Result:** confirmed. **Severity:** none.

### F-17 — Digest behaviour when a reader has no articles
- **How checked:** `digest.py:163`: `if not articles: continue`, so no Digest row. `ranking.py` docstring: a topic with zero candidates costs no slot.
- **Result:** confirmed. **Severity:** none.

### F-18 — Deferred: embedding similarity / vector search on Neon
- **Claim:** the candidate technology is not verified against the project's Neon plan.
- **How checked:** web search, and Neon docs (neon.com/docs/extensions/pgvector).
- **Result:** confirmed available. pgvector is supported on every Neon plan, including Free, enabled per database with `CREATE EXTENSION vector`. The spine's explicit "unverified" label is an **acceptable deferral**: nothing in AD-22 to AD-29 depends on it, and AD-26 isolates it behind the candidate-list builder.
- **Severity:** low.
- **Fix (optional):** replace "not verified" with "pgvector available on all Neon plans (checked 2026-09-14); cost and latency at our scale unmeasured".

### F-19 — Dependency diagram edges
- **How checked:** `scheduler.py:56-57` imports `pipeline.digest` and `pipeline.send`; `digest.py:30` imports `ranking.select_top`.
- **Result:** confirmed. The scheduler → send edge is omitted, which is fine since it is out of scope. **Severity:** none.

## Summary table

| # | Severity | Result | One line |
| --- | --- | --- | --- |
| F-3 | high | gap | Overlap-window rows (no `article_topics`, NULL `DigestArticle.topic_id`) are not re-backfilled before release 2 |
| F-1 | medium | wrong | `render.py:151/163` → `159,170-171`; `ranking.py:93-100` → `125` |
| F-2 | medium | incomplete | `relevance.py:120` (scoping) and `:127` missing from AD-22 |
| F-6 | medium | confirmed + trap | `profile.py:502`'s bare `Session(engine)` violates `expire_on_commit=False`; `me.py` comment stale for FastAPI 0.139.2 |
| F-8 | medium | unverifiable | Scheduler's prod deployment absent from Terraform and workflows; AD-29 gate cannot be checked |
| F-4 | low | confirmed | ACCESS EXCLUSIVE + scan for UNIQUE / SET NOT NULL; fine at this table size |
| F-5 | low | confirmed | batch mode emits plain ALTER on Postgres; name the constraint (no naming convention) |
| F-7 | low | confirmed | Per-submit `copy_context()`; background task inherits request context via anyio |
| F-18 | low | confirmed | pgvector on all Neon plans; deferral acceptable |
| F-9–F-17, F-19 | none | confirmed | Code and convention claims hold |

## Sources
- Alembic batch migrations: https://alembic.sqlalchemy.org/en/latest/batch.html
- FastAPI dependencies with yield (version history): https://fastapi.tiangolo.com/advanced/advanced-dependencies/
- FastAPI dependencies with yield (tutorial): https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- Python contextvars: https://docs.python.org/3.12/library/contextvars.html
- Python concurrent.futures: https://docs.python.org/3.12/library/concurrent.futures.html
- AnyIO threads: https://anyio.readthedocs.io/en/stable/threads.html
- Starlette thread pool: https://starlette.dev/threadpool/
- PostgreSQL ALTER TABLE: https://www.postgresql.org/docs/current/sql-altertable.html
- Neon pgvector: https://neon.com/docs/extensions/pgvector
