---
title: 'GH #36 - Concurrent topic-suggestion calls + extended-wait notice'
type: 'bugfix'
created: '2026-08-07'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '6cc330b4e334685eb42c1242a409d2e725310c12'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** `_compute_and_store_suggestions` calls `source.suggest_topics(...)` then
`source.suggest_new_topics(...)` back-to-back - measured at ~11.4s and ~14.0s (~25.4s combined)
against `z-ai/glm-5.2` via OpenRouter - so Step 3 of the profile wizard shows
"Finding suggestions for you…" for ~25s on a first run. The calls are independent: both consume
only plain data from the `_topic_popularity` query that already ran, and neither reads the
other's result.

**Approach:** Run them concurrently in a `concurrent.futures.ThreadPoolExecutor`, so wall time
becomes the slower call (~14s) instead of the sum. When one call fails while the other is still
running, keep waiting for the survivor (including its existing retries) rather than aborting -
and tell the user the wait is running long, via a new `pending_slow` status the wizard renders
as a different loading message.

## Boundaries & Constraints

**Always:**
- The parallel region must not touch the SQLAlchemy `Session`. `_topic_popularity(db)` has
  already completed; both workers receive only dataclasses and strings. Two threads sharing one
  `Session` is unsafe and fails silently. Every DB write stays on the calling thread.
- A `SuggestionError` from *either* call still yields `SUGGESTION_STATUS_FAILED` with
  `suggested_topic_ids` / `suggested_new_topic_names` untouched.
- `pending_slow` is never terminal: the run always finishes by writing `ready` or `failed` over
  it. The frontend keeps polling through it, exactly as it does through `pending`.
- The interim `pending_slow` write obeys the same `suggestion_request_seq` guard as the final
  write - a superseded computation must not stamp a status onto a newer request.
- The merge/dedup/cap block, and the `db.refresh(user)` + seq guard immediately before the
  final write, stay exactly as they are.

**Ask First:**
- Widening `MAX_POLL_ATTEMPTS` in `TopicsStep.vue` beyond its current ~45s. See Design Notes:
  the extended-wait path can outlive that budget, which caps how useful the new notice is.
- Any change to `SuggestionSource` (`suggestions/base.py`) or its implementations.
- Making the executor size, or the retry/backoff values, configurable via `Settings`.

**Never:**
- No async `SuggestionSource` contract (`asyncio.gather`) - that touches three implementations
  and two in-request synchronous call sites. Out of scope.
- No sub-2s work (faster model, caching, precompute). Parallelization floors at the slower call.
- Do not cancel the surviving call when its sibling fails - the user chose to wait it out.
- Do not parallelize `suggest_roles_for_field` or `suggest_prompts_for_user`.
- No DB migration. `User.suggestion_status` is a plain `String` with no enum or constraint, so
  a new value needs no schema change.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Both succeed | Source returns ids + names | Same stored result as today; calls overlap in time; status goes `pending` → `ready`, never `pending_slow` | N/A |
| Ranking fails, invent still running | `suggest_topics` raises first | `pending_slow` written, wait continues, final status `failed`, stored values untouched | Exception surfaces from `.result()` into the existing `except SuggestionError` |
| Invent fails, ranking still running | `suggest_new_topics` raises first | Same, symmetric | Same |
| One fails after the other already finished | Second call raises with nothing left to wait for | No `pending_slow` (nothing to wait for); status `failed` | Same |
| Both fail | Both raise | Status `failed`; exactly one exception handled | Second exception discarded, never surfaces unhandled |
| Stale seq at the interim write | Newer save advanced the seq before the `pending_slow` write | No `pending_slow` write; run continues and its final result is discarded as today | N/A |
| Stale seq at the final write | Newer save advanced the seq mid-flight | Result discarded, nothing written | N/A |
| Deleted user | `user_id` gone | No-op, no executor started | N/A |
| Wizard polls during extended wait | `GET /me/topic-suggestions` returns `pending_slow` | Step 3 swaps its loading copy to the extended-wait message and keeps polling | N/A |

</frozen-after-approval>

## Code Map

- `src/newsagent/models/user.py` - status constants (`SUGGESTION_STATUS_NONE/PENDING/READY/
  FAILED`); add `SUGGESTION_STATUS_PENDING_SLOW = "pending_slow"`. The column is a plain
  `String`, so no migration.
- `src/newsagent/services/profile.py` - `_compute_and_store_suggestions`, the main change.
  `_topic_popularity` runs before the parallel region and stays there.
- `src/newsagent/suggestions/base.py` - `SuggestionSource._run`'s retry loop (3 attempts,
  exponential backoff, `time.sleep`) uses only local state, so one instance is safe to share
  across both threads. Unchanged.
- `src/newsagent/suggestions/llm.py` - `LLMSuggestionSource` holds immutable config plus an
  optional injected `httpx.Client` (thread-safe); no per-call mutable state. Unchanged.
- `src/newsagent/api/schemas/profile.py` - `suggestion_status: str`, passes the new value
  through with no change.
- `frontend/src/api/client.ts` - `TopicSuggestions.suggestion_status` is a literal union and
  **must** gain `"pending_slow"` or TypeScript rejects the comparison.
- `frontend/src/components/profile-picker/TopicsStep.vue` - `pollForSuggestions` already treats
  any non-`ready`/`failed` status as "keep polling", so only the displayed copy changes.
- `tests/services/test_profile_suggestions.py` - existing ready/failed/stale-seq and
  merge/dedup/cap coverage; all new backend tests land here.

## Tasks & Acceptance

**Execution:**
- [x] `src/newsagent/models/user.py` - add `SUGGESTION_STATUS_PENDING_SLOW`, following the
  existing constant convention and comment style.
- [x] `src/newsagent/services/profile.py` - submit both calls to a
  `ThreadPoolExecutor(max_workers=2)` inside the existing `try`; use
  `wait(..., return_when=FIRST_EXCEPTION)` to detect "one raised while the other is still
  running" and write `pending_slow` (seq-guarded) in that case; then read both `.result()`
  values as before. Add a comment stating the no-`Session`-in-workers rule.
- [x] `frontend/src/api/client.ts` - add `"pending_slow"` to the `TopicSuggestions` status union.
- [x] `frontend/src/components/profile-picker/TopicsStep.vue` - track the interim status during
  polling and swap the `.placeholder` copy to an extended-wait message while it is
  `pending_slow`. No change to `MAX_POLL_ATTEMPTS`, the terminal conditions, or the fallback.
- [x] `tests/services/test_profile_suggestions.py` - cover every I/O Matrix row. Concurrency
  proof: a stub source whose two adapter methods rendezvous on a `threading.Barrier(2,
  timeout=5)` - a sequential implementation cannot reach it and raises `BrokenBarrierError`.
  Extended-wait proof: a stub where one method raises immediately and the other blocks on an
  event, asserting `pending_slow` is observed before the run settles on `failed`.

**Acceptance Criteria:**
- Given a source whose two adapter methods each block until the other has started, when
  `_compute_and_store_suggestions` runs, then both complete and the normal ready result is
  stored - proving concurrent, not sequential, execution.
- Given a run that wrote `pending_slow`, when the run finishes, then the stored status is
  `ready` or `failed` - never left at `pending_slow`.
- Given the existing suite, when `pytest` runs, then every previously passing test still passes
  with no change to its assertions.
- Given the live OpenRouter provider, when the wizard reaches Step 3, then the wait is roughly
  the slower single call (~14s), not the sum (~25s).

## Spec Change Log

- **2026-08-07 - human edit at CHECKPOINT 1.** Original scope was backend-only with an explicit
  "no frontend change" lock. The user chose to keep the wait-for-the-survivor behavior *and*
  notify the end user, which cannot be done without a UI path. Added the `pending_slow` status
  across model → service → schema → client type → component copy, and expanded the test task to
  the full matrix. The "no UI change" boundary is deliberately retired, not overlooked.

## Design Notes

`wait(..., return_when=FIRST_EXCEPTION)` returns as soon as one future raises *or* when both
finish. The extended-wait notice fires only when a raised future coexists with a still-running
one - that is the case where the user is now waiting on a run already doomed to `failed`.

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    topics_future = pool.submit(source.suggest_topics, ...)
    new_topics_future = pool.submit(source.suggest_new_topics, ...)
    done, not_done = wait([topics_future, new_topics_future], return_when=FIRST_EXCEPTION)
    if not_done and any(f.exception() for f in done):
        _mark_pending_slow(db, user, expected_seq)
    suggestions = topics_future.result()
    new_options = new_topics_future.result()
```

`with ThreadPoolExecutor(...)` calls `shutdown(wait=True)` on exit, so the survivor is always
allowed to finish before the exception reaches `except SuggestionError` - which is exactly the
"keep the retries" behavior asked for, and costs nothing in the happy path.

`source` is fetched once and shared by both workers (see Code Map for why that is safe).
Threads, not processes: both calls block on network I/O and release the GIL while waiting.

**Known limit of the notice.** `MAX_POLL_ATTEMPTS = 112 × 400ms ≈ 45s`, while the extended-wait
path is bounded by `_run`'s 3 attempts × 30s HTTP timeout + backoff ≈ 91s. So a worst-case
extended wait still exhausts the poll budget and falls back to "current subscriptions" - the
user sees the notice, then the fallback. Widening the budget is listed under **Ask First**
rather than done here, because a longer budget also lengthens every genuine failure.

## Verification

**Commands:**
- `python -m pytest tests/services/test_profile_suggestions.py -q` - all pass, including the
  barrier and extended-wait tests.
- `python -m pytest -q` - no new failures vs. the pre-change baseline (capture it first: a local
  `.env` already fails some settings-default tests).
- `python -m ruff check src tests` - clean.
- `python -m mypy` - no new errors.
- `cd frontend && npx vue-tsc --noEmit` - clean; catches a missed `"pending_slow"` in the union.

**Manual checks (no CLI):**
- The repo has no frontend test infrastructure (tracked as GH #42), so the Step 3 copy swap is
  verified by hand: run the wizard against a source where one call fails fast, and confirm the
  loading line changes to the extended-wait message and then resolves to the fallback grid.

## Suggested Review Order

**The concurrency change itself**

- The whole point of GH #36: two independent calls, submitted instead of sequenced.
  [`profile.py:321`](../../src/newsagent/services/profile.py#L321)

- Detects "one failed, the other is still going" - narrowed to SuggestionError deliberately.
  [`profile.py:345`](../../src/newsagent/services/profile.py#L345)

**Keeping the non-terminal status honest**

- Guarantees a run that wrote pending_slow still settles, even on an unmapped error.
  [`profile.py:382`](../../src/newsagent/services/profile.py#L382)

- Best-effort by design: a locked SQLite file must not abort an otherwise-fine run.
  [`profile.py:267`](../../src/newsagent/services/profile.py#L267)

- The new status; plain String column, so no migration.
  [`user.py:24`](../../src/newsagent/models/user.py#L24)

**What the user actually sees**

- Copy swap plus the aria-live announcement the status change needs.
  [`TopicsStep.vue:13`](../../frontend/src/components/profile-picker/TopicsStep.vue#L13)

- The only polling-loop change: record the interim status, terminal conditions untouched.
  [`TopicsStep.vue:124`](../../frontend/src/components/profile-picker/TopicsStep.vue#L124)

- Literal union; without the new member TypeScript rejects the comparison.
  [`client.ts:61`](../../frontend/src/api/client.ts#L61)

**Tests**

- Concurrency proof: a sequential implementation cannot clear this barrier.
  [`test_profile_suggestions.py:321`](../../tests/services/test_profile_suggestions.py#L321)

- Observes the interim write without sharing the Session across threads.
  [`test_profile_suggestions.py:303`](../../tests/services/test_profile_suggestions.py#L303)

- Proves pending_slow appears mid-run and is never left as the final state.
  [`test_profile_suggestions.py:364`](../../tests/services/test_profile_suggestions.py#L364)

- Guards the API contract the frontend union was changed for.
  [`test_me.py:455`](../../tests/api/routers/test_me.py#L455)
