---
title: 'Per-call outbound telemetry'
type: 'feature'
created: '2026-08-26'
status: 'done'
review_loop_iteration: 1
baseline_commit: '2d57c29b08ecba15f9a163c85f90031e491af75f'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-llm-telemetry-2026-08-26/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** No individual LLM call is recorded anywhere. `pipeline_runs` aggregates tokens per CLI invocation only — no cost, no latency, no model, no link to the result it produced. `scheduler.py` and `services/profile.py` report nothing at all, and `compose_digest_voice` is entirely invisible. We cannot answer what a user costs, and — more importantly — how much was spent on work nobody read.

**Approach:** Replace the whole mechanism with two tables: `outbound_calls` (the atom — spend, time, result link) and `outbound_runs` (context and outcome counts). The transport measures, a `contextvars` context attributes, one service writes. See ARCHITECTURE-SPINE, AD-11 through AD-20.

## Boundaries & Constraints

**Always:**
- Identity travels **only** via `contextvars` — never as a parameter through `llm/`, `suggestions/`, or `http_llm_client` (AD-11).
- `http_llm_client` measures and reports only: no `Session`, no DB access, no domain vocabulary (AD-12).
- A call made with **no** open context is still recorded, as `purpose='UNATTRIBUTED'`.
- Two nesting levels: `open_run()` once per stage invocation, `attribute_call()` per unit of work. Never one run per article.
- Totals are never stored — always `SUM` over children.
- `cost_usd` / `rate_*` stay `NULL` when no rate is known. **Never `0`.**
- A telemetry failure never breaks the business operation — swallow, log `ERROR`, continue.
- `status` means "did this call produce usable work", **not** "did the HTTP succeed": `ok` / `error` (transport) / `malformed` (billed but unparseable) / `avoided` (AD-15).
- The row is flushed when the **attempt scope closes**, not when the transport reports — the transport cannot yet know whether the result was usable. Default `ok`; any layer that finds the result unusable marks `malformed` before raising.

**Ask First:**
- Any change to column names or their semantics versus the spine.
- If migrating `log_entries.pipeline_run_id` turns out to be impossible without data loss.

**Never:**
- Do not implement pricing: no `model_prices`, no `pricing.py`, no `refresh-pricing`. The columns are created and left empty (deferred — see `deferred-work.md`).
- Never store prompts or output text. From the output, only `output_chars` (AD-20).
- Do not leave the old mechanism running alongside — it is deleted in the same revision (AD-18).
- Do not wire `email` / `rss` targets. `target` accepts the values; the wiring is not done now.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Successful call | Summarize article 4711 inside an open context | One row: `purpose='SUMMARIZING'`, `article_id=4711`, `attempt=1`, `status='ok'`, real tokens and `duration_ms`, `cost_usd=NULL` | N/A |
| Retry | First call fails transiently, second succeeds | **Two** rows, same `run_id`+`article_id`, `attempt=1` (`status='error'`) and `attempt=2` (`status='ok'`) | Both recorded; the failed call's spend is preserved |
| Billed but unusable | HTTP 200, tokens billed, but the body fails JSON parsing or schema validation in `llm/external.py` | One row, `status='malformed'`, **real tokens and `duration_ms`** — never `ok` | The `LLMProviderError` still propagates unchanged; only the recorded status differs |
| Cache hit | `_reuse_recent_voice` returns `True` | Row with `status='avoided'`, `tokens=NULL`, `cost_usd=0`, real `duration_ms` for the cache lookup | N/A |
| Junk refusal | `_refuse_if_junk` returns before the network | **No** call row; `outbound_runs.refused` increments by 1 | N/A |
| No context | A new caller that opened no context | Row with `purpose='UNATTRIBUTED'`, no FK, but with cost and latency | N/A |
| Call from a thread | Profile suggestions via `ThreadPoolExecutor` | Rows carry the same `run_id` as the calling thread | If context did not propagate, `UNATTRIBUTED` — never a crash |
| Write failure | DB unavailable while writing telemetry | The business operation completes normally | Swallowed, logged at `ERROR` |

</frozen-after-approval>

## Code Map

- `src/newsagent/telemetry/` — **new.** `types.py` (`CallMeasurement`, `CallAttribution`, frozen), `context.py` (`contextvars` + `open_run` / `attribute_call`), `sink.py` (joins measurement with attribution, hands to the service).
- `src/newsagent/models/outbound_run.py`, `outbound_call.py` — **new.** `models/pipeline_run.py` — **deleted.**
- `src/newsagent/models/log_entry.py:24` — `pipeline_run_id` is a real FK to `pipeline_runs.id`. **Must migrate** to `outbound_run_id` → `outbound_runs.id`, or dropping the table breaks the FK.
- `src/newsagent/services/telemetry.py` — **new**, the sole writer. `services/pipeline_runs.py` — **deleted.**
- `src/newsagent/services/log_entries.py:30`, `logging_setup.py:72-88` — `attach_pipeline_run` / `track_pipeline_run_logs` rename to the new column.
- `src/newsagent/http_llm_client.py:39,75-83` — `on_usage` stays as a test injection point; add elapsed-time measurement and a default report to the sink.
- `src/newsagent/llm/base.py:41,73-88,108-117` — remove `_usage_log`/`_record_usage`/`drain_usage`; **`_run` increments the `attempt` counter in the context** — the only place that knows a call is a retry (AD-15).
- `src/newsagent/llm/types.py:19-26,35,58,69` — remove `Usage` and the `usage` fields. Also `llm/__init__.py:11,26`, `external.py:8,26,97,169-185`, `mock.py:21,97-98,128-129,152-153`.
- `src/newsagent/pipeline/relevance.py:41-42,55-60,87-117` and `summarize.py:42-43,46-51,86-117` — wrap the loop body in `attribute_call`; drop the usage fields and `_accumulate_usage`.
- `src/newsagent/pipeline/digest.py:151,198-199` — `open_run` per user; report `avoided` when `_reuse_recent_voice` returns `True`.
- `src/newsagent/services/profile.py:334,344-358` — provider calls run in a `ThreadPoolExecutor`; context does **not** propagate automatically.
- **AMENDED 2026-08-27.** `src/newsagent/services/profile.py`'s `suggest_prompts_for_user` and `src/newsagent/services/taxonomy.py:144`'s `suggest_roles_for_field` are two more real, API-reachable LLM call sites (`api/routers/me.py:89,133`) that were missed by the line ranges above — first review round found both left completely unwired, permanently recording as `UNATTRIBUTED`. Wrap each in its own `open_run('profile_suggestions', user_id=...)` / `open_run('taxonomy_suggestion', user_id=None)`, using the already-exported `PURPOSE_SUGGEST_PROMPTS` / `PURPOSE_SUGGEST_ROLES` constants from `telemetry/types.py` (defined in the first pass, never referenced anywhere — this is why).
- `src/newsagent/cli.py:16,18,47-49,84-160` — remove `record_run`; rewrite `usage-report`.
- `alembic/versions/` — new revision, `down_revision = "d4a7b2c85f16"`, matching the shape of `d4a7b2c85f16_scheduler_lease.py`.
- Tests that break: `tests/services/test_pipeline_runs.py` (delete), `tests/models/test_models_smoke.py`, `tests/pipeline/test_relevance.py`, `tests/pipeline/test_summarize.py`, `tests/llm/test_external_provider.py`, `tests/test_logging_setup.py`. Fixture pattern: `create_engine("sqlite:///:memory:")` + `Base.metadata.create_all` (there is no shared fixture).

## Tasks & Acceptance

**Execution:**
- [x] `src/newsagent/telemetry/{__init__,types,context,sink}.py` — new package: `CallMeasurement`, `CallAttribution`, `open_run`/`attribute_call` as context managers over `contextvars`, and a sink that joins and hands off. The `attempt` counter lives in the context.
- [x] `src/newsagent/models/outbound_run.py` + `outbound_call.py` + register in `models/__init__.py` — columns per the spine's ERD. `cost_usd`/`rate_*` are nullable `Numeric(12,6)`.
- [x] `alembic/versions/<rev>_outbound_call_telemetry.py` — create both tables; migrate `log_entries.pipeline_run_id` → `outbound_run_id`; `drop_table("pipeline_runs")`. Fully reciprocal `downgrade`.
- [x] `src/newsagent/services/telemetry.py` — `open_run`/`close_run`/`record_call`. Sole writer; swallows and logs exceptions.
- [x] `src/newsagent/http_llm_client.py` — `time.monotonic()` around the POST; report `CallMeasurement` to the sink on every path, including HTTP failure. `on_usage` stays.
- [x] `src/newsagent/llm/{base,types,external,mock,__init__}.py` — delete the usage mechanism; `_run` increments `attempt` in the context.
- [x] `src/newsagent/pipeline/{relevance,summarize}.py` — `attribute_call(purpose, article_id)` wraps the loop body **including the `except` path**; remove usage fields from the reports. (Also opens `open_run` per invocation, per AD-11's own example — see implementation report.)
- [x] `src/newsagent/pipeline/digest.py` — `open_run('digest_build', user_id=...)` around the per-user loop body; report `avoided` in the cache branch.
- [x] `src/newsagent/services/profile.py` — propagate context into the threads (see Design Notes) + `open_run('profile_suggestions', user_id=...)`.
- [x] `src/newsagent/services/log_entries.py` + `logging_setup.py` + `models/log_entry.py` — rename to `outbound_run_id`.
- [x] `src/newsagent/cli.py` — remove `record_run` and `RUN_TYPE_*`; rewrite `usage-report` over the new tables: tokens, latency, and waste (`attempt>1`, `status='avoided'`). No dollars.
- [x] Delete: `models/pipeline_run.py`, `services/pipeline_runs.py`, `tests/services/test_pipeline_runs.py`.
- [x] `tests/telemetry/` — new: cover every row of the I/O matrix, including the thread case and the `UNATTRIBUTED` case.
- [x] Update the broken tests listed in the Code Map.
- [x] **AMENDED 2026-08-27 — `malformed` status.** `telemetry/{context,sink}.py`: buffer the measurement and flush **once, when the attempt scope closes**, instead of at the transport's report. Default the outcome to `ok`. `llm/external.py`: all three `except` blocks (envelope / json / schema) mark the outcome `malformed` before re-raising. `llm/base.py:_run` **and** `suggestions/llm.py`'s own retry loop must each close the attempt scope — AD-3 keeps them separate, so fixing only `llm/` leaves the bug live on the suggestions path. `cli.py`: `usage-report` counts `malformed` as waste alongside `attempt>1` and `avoided`. (The retry loop actually lives in `suggestions/base.py:_run`, structurally mirroring `llm/base.py:_run` — same file relationship as `suggestions/llm.py`/`llm/external.py`; fixed there, see implementation report.)
- [x] **AMENDED 2026-08-27 — wire the two missed suggestion call sites.** `services/profile.py`'s `suggest_prompts_for_user` and `services/taxonomy.py`'s `suggest_roles_for_field` each open their own run (see Code Map) instead of running with no context.

**Patch backlog (auto-fix, no spec ambiguity — from the first review round):**
- [x] `pipeline/digest.py` — `run.close(succeeded=1)` is hardcoded regardless of `_compose_voice`'s outcome. Have `_compose_voice` return/expose whether it produced a usable voice, and pass the real `succeeded`/`errors` counts (AD-13: counts come from the stage's own report, never a placeholder).
- [x] `services/profile.py` — the `except BaseException` handler around the suggestion computation leaves `status` unset before the run closes, so a genuine crash and a no-op both read as `succeeded=0, errors=0`. Set an explicit failed/error status in that handler before it re-raises.
- [x] `telemetry/sink.py` — `current_attribution()` is called before the `try` block in `report()`, so a failure there is not swallowed, violating the frozen "a telemetry failure never breaks the business operation" rule. Move it inside the `try`.
- [x] `pipeline/relevance.py` and `pipeline/summarize.py` — the `subscriber_count` query counts every user with a `UserTopicPreference` row, including unsubscribed ones (`User.unsubscribed_at` not filtered). AD-13/AD-14 define it as *active* subscribers. Fix in both files (same query is duplicated verbatim in each — consider a shared helper).
- [x] `models/outbound_run.py` / `services/telemetry.py` — `created_at` is DB-side (`func.now()`) while `finished_at` is app-host (`datetime.now()`, naive). Use the same clock for both to avoid skewed/negative durations across hosts.
- [x] `cli.py` — `usage-report` compares `OutboundCall.status == "avoided"` as a hardcoded literal; import and use `STATUS_AVOIDED` from `newsagent.telemetry` instead, matching the project's constants-not-free-strings convention.
- [x] `http_llm_client.py` — the `on_usage` parameter/branch is now dead (no caller supplies it since `llm/external.py` was rewired); remove it, or confirm and document a real remaining caller if one exists.
- [x] `intent_summary` is fully plumbed end-to-end but no call site (`relevance.py`, `summarize.py`, `digest.py`, `profile.py`) ever passes a value, so the column is always `NULL`. Pass a short bounded description at each `open_run(...)` call site (per AD-20's own worked example, e.g. `f"profile suggestions · field={field}"`) — low priority, skip if it risks scope creep beyond a one-line value per call site.

**Patch backlog, round 2 (auto-fix, no spec ambiguity — from the second review round):**
- [x] `pipeline/relevance.py` and `pipeline/summarize.py` — the per-article loop only catches `LLMError`; any other exception escapes before `run.close()`, discarding the whole run's tally (`0/0/0`) even though earlier articles in the same loop already had their DB status committed and their `outbound_calls` rows written. Wrap the loop body so `run.close()` always fires (e.g. `try`/`finally`) with whatever counts were accumulated up to the failure point, not defaults.
- [x] `pipeline/digest.py::_compose_voice`, `services/profile.py::suggest_prompts_for_user`, `services/taxonomy.py::suggest_roles_for_field` — each is missing the `except BaseException: ...; raise` safety net that `services/profile.py::_compute_and_store_suggestions` already has from round 1. Without it, an unmapped exception (not `LLMError`/`SuggestionError`) skips the explicit error-count update and the run closes as if nothing happened. Apply the same pattern used in `_compute_and_store_suggestions` to all three.
- [x] `cli.py usage-report` — the average-duration figure (`func.avg(OutboundCall.duration_ms)` grouped by `purpose`) mixes `avoided` cache-hit rows (near-zero duration) into the same average as real LLM calls, understating latency with no indication in the output. Filter `avoided` out of the duration average, and add a test covering the report's grouping/filtering logic (currently zero coverage).
- [x] `alembic/versions/<rev>_outbound_call_telemetry.py` — the migration's own docstring/comment says human sign-off for nulling `log_entries.pipeline_run_id` was not sought. That approval **was** obtained during this implementation (see the spec's Design Notes → "Human decisions on the frozen spec's Ask First items"). Update the comment so it doesn't read as an outstanding gap.
- [x] `telemetry/context.py`'s `buffer_measurement()` — silently overwrites an existing buffered measurement with no warning if called twice within one `attempt_scope()`. Add a `logger.warning(...)` on that path (not a raise — telemetry must never break the caller) so a future double-report doesn't lose data invisibly.

**Acceptance Criteria:**
- [x] Given a `filter` run over 5 articles, when it finishes, then exactly one `outbound_runs` row and 5 `outbound_calls` rows exist with `article_id` populated.
- [x] Given code that calls `send_chat_completion` with no open context, when it runs, then a row is written with `purpose='UNATTRIBUTED'`, a `duration_ms` and a model — and no exception is raised.
- [x] Given `alembic upgrade head`, then `downgrade -1`, then `upgrade head`, when they run, then all three succeed and `log_entries` keeps a valid FK at every step.
- [x] Given `grep -rn "drain_usage\|_record_usage\|pipeline_runs\|RUN_TYPE_" src/`, when it runs, then there are zero results.
- [x] Given a provider that returns HTTP 200 with tokens billed and an unparseable body, when the call runs, then exactly one row exists with `status='malformed'` and non-null tokens — and `status` is never `ok`. Cover this on **both** the `llm/` path and the `suggestions/` path.
- [x] Given a call to `suggest_prompts_for_user` or `suggest_roles_for_field` (e.g. via `api/routers/me.py`), when it completes, then an `outbound_runs` row exists with `kind` reflecting the operation and `user_id`/`NULL` set appropriately — not `UNATTRIBUTED`.

### Review Findings

**From code review (2026-08-27), reviewing the uncommitted working-tree diff on `dev` (`db6d655`) against this spec + ARCHITECTURE-SPINE — Blind Hunter + Edge Case Hunter + Acceptance Auditor:**

- [x] [Review][Patch] Purpose granularity: `suggest_topics` vs `suggest_new_topics` both tagged `PURPOSE_SUGGEST_TOPICS` — Both are real, concurrent LLM calls in `services/profile.py::_compute_and_store_suggestions` (`services/profile.py:387,397`), tagged with the same `purpose` constant. Telemetry can never distinguish their cost, latency, or failure rate from one another, even though they are different prompts against different call sites. This matches the spine's own Consistency Conventions purpose list exactly (no separate constant exists for "new topics") — the gap is in the spec's own taxonomy, not an implementation deviation. **Resolved 2026-08-27 (decision-needed → patch):** add a new `PURPOSE_SUGGEST_NEW_TOPICS` constant to `telemetry/types.py` and use it at `services/profile.py:397`'s `attribute_call`, amending the spine's purpose list to match.
- [x] [Review][Patch] Kind granularity: `outbound_runs.kind='profile_suggestions'` shared by two different-shaped operations — `suggest_prompts_for_user` (`services/profile.py:255-259`, one cheap read-only lookup) and `_compute_and_store_suggestions` (`services/profile.py:362-366`, two concurrent LLM calls plus a DB write) both open with `kind=telemetry.KIND_PROFILE_SUGGESTIONS`. A query grouped only by `kind` cannot separate "how often did the light fetch run" from "how often did the heavy compute-and-store run." This matches the spec's own explicit instruction (Code Map: "open_run('profile_suggestions', user_id=...)" for both) — again the code follows the frozen spec as written, not a deviation. **Resolved 2026-08-27 (decision-needed → patch):** add a new `KIND_PROMPT_SUGGESTIONS` constant to `telemetry/types.py` for `suggest_prompts_for_user`'s `open_run` call (`services/profile.py:256`), leaving `_compute_and_store_suggestions` on `KIND_PROFILE_SUGGESTIONS`, amending the spine's kind list to match.
- [x] [Review][Patch] `malformed` status can land on a call that billed zero tokens [`src/newsagent/http_llm_client.py:66-80`, `src/newsagent/llm/external.py:108-122`, `src/newsagent/suggestions/llm.py:91-98`] — When the raw HTTP response body isn't JSON at all (`response.json()` raises `ValueError` before `usage` is ever parsed), the exception propagates to `llm/external.py`'s and `suggestions/llm.py`'s single "envelope" `except` clause, which calls `mark_malformed()` unconditionally — the same clause also handles the separate case of a missing `choices` key *after* usage was already parsed. Both are tagged `malformed`, but only the second case actually billed tokens. Result: a response that billed nothing at all can be recorded as `status='malformed'` with `tokens_in=NULL, tokens_out=NULL`, contradicting AD-15's own definition ("malformed... real tokens... never ok" implies tokens are always known when malformed) and leaving a `malformed` row with null tokens, which is internally inconsistent. Unexercised by the test suite. Affects both the `llm/` and `suggestions/` paths.
- [x] [Review][Patch] `services/taxonomy.py::suggest_roles_for_field` can skip `open_run()` entirely [`src/newsagent/services/taxonomy.py:162-171`] — `if len(curated) >= ROLE_SUGGESTION_CAP: return views` returns before the function ever reaches `telemetry.open_run(...)`. When a Field's curated Role catalog already fills the cap, this API-reachable function (from `api/routers/me.py`) completes with zero `outbound_runs` rows written — not even a 0/0/0 row, unlike every other "nothing to do" case in this diff. Directly contradicts AD-13's own worked example ("a run row is always created, even for role suggestions") and the spec's acceptance criterion for this exact call site. Not reachable with today's seed data (`ROLE_SUGGESTION_CAP=10`, default seed has 4 roles/field) but reachable as admins curate more Roles over time. Untested.
- [x] [Review][Patch] `intent_summary` has no enforced length bound [`src/newsagent/services/telemetry.py:21-37`] — AD-20 requires it stay "bounded," but the column is a plain `Text` and `services/telemetry.py::open_run` (the sole writer) stores whatever string it's given verbatim. Every current call site is a short hand-written f-string, so nothing is broken today, but nothing stops a future call site from interpolating something unbounded. `open_run` is the single natural enforcement point.
- [x] [Review][Patch] `telemetry/sink.py::report()`'s local import sits outside its `try` [`src/newsagent/telemetry/sink.py:43-49`] — `from newsagent.telemetry.context import buffer_measurement` (line 43) is above the `try:` on line 45. `report()` is called from `http_llm_client`'s `finally:` block on every outbound attempt; if that import ever raised, it would propagate uncaught and could mask the real HTTP/parsing exception the caller was propagating — breaking AD-12's "telemetry failure never changes what a caller here sees" guarantee. Currently safe in practice (module is fully loaded by the time `report()` runs), but cheap to close off.
- [x] [Review][Patch] `README.md:69` describes stale schema — Still reads "the id of that run's `pipeline_runs` row"; this revision renames it to `outbound_runs`/`outbound_run_id` and drops the `pipeline_runs` table entirely.
- [x] [Review][Patch] `models/outbound_call.py:38` inline comment omits `malformed` [`src/newsagent/models/outbound_call.py:38`] — `# ok / error / avoided` is missing the fourth status value this spec's own amendment added and that `record_call()` actually writes. Doc drift only.
- [x] [Review][Defer] `usage-report`'s "Waste" line has no per-purpose breakdown [`src/newsagent/cli.py:156-168`] — deferred, pre-existing pattern (CLI reporting depth explicitly deferred per ARCHITECTURE-SPINE)
- [x] [Review][Defer] `cost_usd` NULL-vs-zero conflation is a landmine for direct SQL before pricing ships [`src/newsagent/services/telemetry.py:65-69`] — deferred, already documented and guarded by AD-16; the CLI itself avoids it by omitting dollars entirely
- [x] [Review][Defer] Retry-loop `attempt` var and telemetry `increment_attempt()` counter are two hand-synced counters duplicated across `llm/base.py`/`suggestions/base.py` [`src/newsagent/llm/base.py:90-110`, `src/newsagent/suggestions/base.py:133-148`] — deferred, currently correct by construction, no active bug
- [x] [Review][Defer] `tests/test_cli.py` doesn't exercise `filter`/`summarize`'s actual `attach_outbound_run` CLI wiring or its `try/except` fallback end-to-end [`src/newsagent/cli.py:95-103,111-119`] — deferred, the underlying `attach_outbound_run` function itself is already well-covered in `tests/test_logging_setup.py`
- [x] [Review][Defer] `subscriber_count` for `filter`/`summarize` is computed once up front and goes stale if a user unsubscribes mid-run [`src/newsagent/pipeline/relevance.py:106-107`] — deferred, low-probability edge case, consistent with AD-13's own "compute counts once" philosophy
- [x] [Review][Defer] Migration's `UPDATE log_entries SET pipeline_run_id = NULL` is unbatched against the full table [`alembic/versions/a06a39402215_outbound_call_telemetry.py:85`] — deferred, harmless at current row counts; migration has since been applied to the live Neon Postgres instance (2026-08-29) with no issue

**Dismissed as noise (3):**
- `buffer_measurement()`'s double-report overwrite (Blind Hunter) — already implemented exactly as accepted in this spec's own Patch backlog item #11; not a new issue.
- `build_digests` opening a run when `select_top` selects zero articles (Blind Hunter) — re-verified against the code: a genuine error always increments `errors` via the round-2 `except BaseException` safety net (confirmed present), so `0/0/0` unambiguously means "nothing attempted," not a silently-vanished failure.
- `usage-report`'s dropped day-over-day trend view (Edge Case Hunter) — already recorded verbatim in `deferred-work.md` under "Deferred from: outbound call telemetry (2026-08-26)"; not re-added to avoid duplicating that entry.

## Spec Change Log

### 2026-08-27 — `malformed` status, and where the row is flushed

**Finding:** Two review agents independently found that a call returning HTTP 200 with billed tokens, whose body then fails JSON parsing or schema validation in `llm/external.py` (raising `LLMProviderError`), is recorded as `status='ok'` with real token counts. The transport had already reported before anything knew the result was unusable. The frozen I/O matrix did not cover this case.

**Amended:** `status` gains a fourth value, `malformed`, and is defined as "did this call produce usable work" rather than "did the HTTP succeed". The row is now flushed when the **attempt scope closes**, not at the transport's report — the transport structurally cannot know the final status. Default `ok`; the layer that discovers the result is unusable marks `malformed` before raising. AD-15 in the spine was amended to match (AD id kept stable).

**Known-bad state avoided:** pure waste — tokens spent for nothing — reading as success, and so vanishing from the waste queries that are this feature's entire point. Same failure family AD-16 guards against by forbidding `0` where `NULL` is meant.

**KEEP:** `malformed` must stay distinct from `error` — different fixes: `error` is provider availability, `malformed` is a prompt or schema problem (cf. GH #38). Do not collapse them. Also keep the existing behaviour where `_on_usage` fires before content extraction (GH #19); it is what makes the billed tokens available to record at all.

### 2026-08-27 — two suggestion call sites never wired to telemetry

**Finding:** The first review round found `services/profile.py`'s `suggest_prompts_for_user` and `services/taxonomy.py`'s `suggest_roles_for_field` — both real, synchronous LLM calls reachable from `api/routers/me.py` — were never wrapped in `open_run`, because the original Code Map's line citations for `services/profile.py` (334, 344-358) covered only the threaded topic-suggestion path. `PURPOSE_SUGGEST_ROLES`/`PURPOSE_SUGGEST_PROMPTS` constants existed since the first pass but were never referenced anywhere — a tell that this was missed, not a deliberate exclusion (unlike `suggestions/base.py` bypassing the transport entirely, which AD-11 declares out of scope by design).

**Amended:** Code Map and Tasks gained an explicit line for both call sites (above).

**Known-bad state avoided:** two real, user-triggered LLM call paths permanently invisible to the exact "who costs what" question this feature exists to answer — silently, since `UNATTRIBUTED` is valid, expected behavior elsewhere (AD-11), so nothing would ever flag this as broken.

**KEEP:** everything else about the first pass's suggestion-wiring work (the `ThreadPoolExecutor` `copy_context()` fix for the topic-suggestion path) is correct and unaffected — this amendment only adds the two missed call sites, it does not change the threaded one.

## Design Notes

**`contextvars` do not cross into `ThreadPoolExecutor`.** `services/profile.py:344-358` submits the provider calls to worker threads. Python does **not** copy context into a new thread, so a context opened on the calling thread simply does not exist there, and every suggestion call would silently record as `UNATTRIBUTED`. Nothing would fail — the mechanism would look like it works while losing attribution. Fix with `copy_context()` and `ctx.run` inside the submit:

```python
ctx = contextvars.copy_context()
pool.submit(ctx.run, source.suggest_topics, ...)
```

**`log_entries.pipeline_run_id` is a coupling the spine missed.** It is a real FK to `pipeline_runs.id`, and `cli.py` builds a chain on it (`track_pipeline_run_logs` → `attach_pipeline_run`) that ties log rows to a run. Dropping the table without migrating it breaks the schema. Moving it to `outbound_run_id` preserves that capability and gains from it — there is now a run for the scheduler and for suggestions too, not only for the CLI.

**SQLite and `Numeric`.** Tests run on SQLite, which has no real decimal type. `Numeric(12,6)` works through SQLAlchemy but returns `float` on SQLite and `Decimal` on Postgres. Any test comparing cost must compare with a tolerance, not exact equality.

**Human decisions on the frozen spec's "Ask First" items (2026-08-27), during implementation:**
- **`log_entries.pipeline_run_id` → `outbound_run_id` migration.** There is no valid mapping between old `pipeline_runs.id` values and new `outbound_runs.id` values (separate ID sequences). Decision: null out every existing `pipeline_run_id` before renaming the column. Log row content is preserved; only "which run produced this log line" is lost for pre-migration rows. Rejected alternative: copy historical `pipeline_runs` rows into `outbound_runs` to preserve FK values — rejected because it would give legacy rows flat, non-`SUM`-derived counts, a permanent inconsistency, and stretches AD-18's "old mechanism fully deleted."
- **`outbound_calls.run_id` nullability.** The spine's ERD shows `run_id` as a plain (non-nullable-annotated) FK. Decision: keep it nullable, as implemented, to support a call made with no `open_run()` anywhere in the call stack (`purpose='UNATTRIBUTED'`, no run at all — not just no result FK). Rejected alternative: enforce `NOT NULL` via a fabricated placeholder "unattributed" run, rejected as an undocumented mechanism that adds complexity the spec never described.

**Not yet applied to the real database.** Per the standing rule against running migrations against anything but a local dev database, `alembic upgrade/downgrade/upgrade` was verified against a throwaway local SQLite file only. The live Neon Postgres instance (`NEWSAGENT_DATABASE_URL`) still has `pipeline_runs` and the old `log_entries.pipeline_run_id` column untouched — applying this migration there is a separate, explicit step for later.

## Verification

**Commands:**
- `python -m pytest tests/ -q` — expected: all pass, no new failures beyond the 5 known `.env`-sensitive ones.
- `python -m ruff check src tests` — expected: clean (watch `import dataclasses` in `external.py`, which becomes unused).
- `python -m mypy` — expected: no new errors.
- `python -m alembic upgrade head && python -m alembic downgrade -1 && python -m alembic upgrade head` — expected: all three succeed.
- `grep -rn "drain_usage\|_record_usage\|pipeline_runs\|RUN_TYPE_" src/` — expected: zero results.

## Suggested Review Order

**Core mechanism — ambient context, buffering, sole writer**

- Entry point: two nesting levels a caller opens per AD-11 — read the docstring before anything else.
  [`context.py:94`](../../src/newsagent/telemetry/context.py#L94)

- Where the round-2 rework lives: the row is no longer flushed at transport-report time.
  [`context.py:128`](../../src/newsagent/telemetry/context.py#L128)

- Buffers instead of writing immediately; now warns (not silently drops) on a double-report.
  [`context.py:147`](../../src/newsagent/telemetry/context.py#L147)

- Lets a later layer override the default `ok` outcome before the scope flushes.
  [`context.py:173`](../../src/newsagent/telemetry/context.py#L173)

- Joins measurement with attribution and flushes exactly once — the only place that writes.
  [`sink.py:27`](../../src/newsagent/telemetry/sink.py#L27)

- Sole DB writer (AD-1); swallows and logs on failure so telemetry never breaks the caller.
  [`telemetry.py:40`](../../src/newsagent/services/telemetry.py#L40)

**`malformed` status — transport measures, a later layer decides usability**

- Measures and reports on every exit path, including HTTP failure — never writes to DB itself.
  [`http_llm_client.py:42`](../../src/newsagent/http_llm_client.py#L42)

- `llm/`'s retry loop closes the attempt scope; the one place that knows a call is a retry.
  [`base.py:90`](../../src/newsagent/llm/base.py#L90)

- Marks a billed-but-unparseable response before re-raising — three `except` blocks, same intent.
  [`external.py:121`](../../src/newsagent/llm/external.py#L121)

- `suggestions/`'s own, separate retry loop (siblings, no cross-import) — must close the scope too.
  [`base.py:133`](../../src/newsagent/suggestions/base.py#L133)

- Same `mark_malformed` pattern on the suggestions sibling — this file, not `suggestions/llm.py`, holds the retry loop.
  [`llm.py:97`](../../src/newsagent/suggestions/llm.py#L97)

**Schema**

- `run_id` nullable — documented deviation from the spine's ERD, for the no-context-at-all case.
  [`outbound_call.py:31`](../../src/newsagent/models/outbound_call.py#L31)

- The irreversible step: nulls historical `log_entries.pipeline_run_id` before dropping `pipeline_runs`.
  [`a06a39402215_outbound_call_telemetry.py:85`](../../alembic/versions/a06a39402215_outbound_call_telemetry.py#L85)

**Pipeline callers — counts always reflect what actually happened**

- `run.close()` now always fires with real accumulated counts, even if something escapes mid-loop.
  [`relevance.py:146`](../../src/newsagent/pipeline/relevance.py#L146)

- `_compose_voice`'s real outcome drives `run.close()` — no more hardcoded `succeeded=1`.
  [`digest.py:228`](../../src/newsagent/pipeline/digest.py#L228)

- Newly wired call site (was permanently `UNATTRIBUTED`) plus the round-2 exception safety net.
  [`profile.py:255`](../../src/newsagent/services/profile.py#L255)

- Same fix, second newly-wired call site.
  [`taxonomy.py:171`](../../src/newsagent/services/taxonomy.py#L171)

- `copy_context()`/`ctx.run` — the fix for `contextvars` not crossing into `ThreadPoolExecutor` threads.
  [`profile.py:388`](../../src/newsagent/services/profile.py#L388)

**CLI reporting**

- Excludes `avoided` cache-hit rows from the latency average so it reflects real LLM calls.
  [`cli.py:132`](../../src/newsagent/cli.py#L132)

**Peripherals**

- New test package covering every row of the frozen I/O matrix, including `malformed` on both paths.
  [`test_call_recording.py`](../../tests/telemetry/test_call_recording.py#L1)

- New coverage for `usage-report`'s grouping/filtering, previously untested.
  [`test_cli.py`](../../tests/test_cli.py#L1)
