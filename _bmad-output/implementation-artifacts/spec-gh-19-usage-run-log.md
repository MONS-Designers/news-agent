---
title: 'Persist per-run LLM usage to the DB (GH #19 follow-up)'
type: 'feature'
created: '2026-08-09'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'a3db7f5390b989ca92c0f5e4a9be99db6d6f2810'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** GH #19 fixed token accounting, but the numbers exist only as a CLI `print()` line and (if configured) a log line - both ephemeral. There is no way to answer "how much did we spend this week" without manually collecting terminal output across runs.

**Approach:** A new `pipeline_runs` table; one row per `filter`/`summarize` CLI invocation, written immediately after the existing report is built and printed. Tokens only, no cost conversion.

## Boundaries & Constraints

**Always:**
- One row per completed `filter`/`summarize` run, written from `cli.py` right after the existing `Usage:` print line, via a new `services/pipeline_runs.py::record_run()` - matches this codebase's existing services-layer convention for persistence.
- Row columns, generic across both run types: `run_type` (`"filter"` | `"summarize"`), `created_at` (server-side default), `succeeded`, `refused`, `errors`, `usage_input_units`, `usage_output_units`. `filter` maps `succeeded = FilterReport.scored` (relevant+irrelevant); `summarize` maps `succeeded = SummarizeReport.summarized`.
- New Alembic migration off the current head `a4b5c6d7e8f9`, mirroring `b2c3d4e5f6a7`'s `op.create_table` shape (see Code Map) with a reciprocal `downgrade`.
- A row is written even when the run processed zero articles or every count is zero - the run happened and belongs in the history.

**Ask First:**
- Any change to the `succeeded` mapping beyond relevant+irrelevant (filter) / summarized (summarize).
- Adding `compose_digest_voice`/`DigestReport` tracking - it has no usage tracking today at all; that's a separate, larger gap, not this story.
- Any retention or pruning policy - MVP ships with none.

**Never:**
- No reporting UI, admin view, or read/query endpoint for this table. Schema + write path only; reading it back is a future story.
- Do not touch `pipeline/digest.py` or `DigestReport`.
- No cost/₪ conversion - tokens only, already decided.
- Do not write the row from inside `filter_pending_articles`/`summarize_relevant_articles` themselves - only from `cli.py`, keeping the pipeline functions free of persistence side effects beyond the `Article`/`db.commit()` writes they already do.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal filter run | 5 relevant, 2 irrelevant, 1 error | One row: `run_type="filter"`, `succeeded=7`, `errors=1`, usage matching `FilterReport` | N/A |
| Normal summarize run | 3 summarized, 1 refused | One row: `run_type="summarize"`, `succeeded=3`, `refused=1`, usage matching `SummarizeReport` | N/A |
| Zero-article run | No pending/error articles found | One row, all counts and usage 0 | N/A |
| Billed-but-failed (GH #19) | Every article errors, but tokens were billed | Row's `usage_input_units`/`usage_output_units` reflect the billed tokens, not 0 - proves GH #19's fix reaches persistence | N/A |

</frozen-after-approval>

## Code Map

- `src/newsagent/models/pipeline_run.py` -- NEW. `PipelineRun` model; mirrors `Digest`'s `created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())` pattern.
- `src/newsagent/models/__init__.py` -- register `PipelineRun` in the import list and `__all__`.
- `alembic/versions/<new>_pipeline_runs.py` -- NEW migration. `down_revision = "a4b5c6d7e8f9"` (current head, confirmed via `alembic heads`). Mirror `alembic/versions/b2c3d4e5f6a7_role_and_user_role_name.py`'s `op.create_table(...)` call shape for the table + `PrimaryKeyConstraint`.
- `src/newsagent/services/pipeline_runs.py` -- NEW. `record_run(db, *, run_type, succeeded, refused, errors, usage_input_units, usage_output_units) -> PipelineRun`. Follows `services/sources.py`'s style: builds the row, `db.add`, `db.commit`, returns it.
- `src/newsagent/cli.py:74-95` -- the `filter`/`summarize` branches. Add one `record_run(...)` call in each, immediately after the existing `Usage:` print.
- `src/newsagent/pipeline/relevance.py::FilterReport`, `pipeline/summarize.py::SummarizeReport` -- read-only; source of the values passed into `record_run`.

## Tasks & Acceptance

**Execution:**
- [x] `alembic/versions/<new>_pipeline_runs.py` -- Create `pipeline_runs` (`id`, `run_type` String, `created_at` DateTime server_default now, `succeeded`/`refused`/`errors`/`usage_input_units`/`usage_output_units` Integer default 0); `down_revision="a4b5c6d7e8f9"`; reciprocal `downgrade()` drops the table.
- [x] `src/newsagent/models/pipeline_run.py` -- `PipelineRun` model matching the migration exactly.
- [x] `src/newsagent/models/__init__.py` -- register `PipelineRun`.
- [x] `src/newsagent/services/pipeline_runs.py` -- `record_run()`.
- [x] `src/newsagent/cli.py` -- call `record_run(db, run_type="filter", succeeded=filter_report.scored, refused=filter_report.refused, errors=filter_report.errors, usage_input_units=filter_report.usage_input_units, usage_output_units=filter_report.usage_output_units)` in the `filter` branch; the mirrored call (`run_type="summarize"`, `succeeded=summary_report.summarized`) in the `summarize` branch.
- [x] `tests/services/test_pipeline_runs.py` -- `record_run()` persists a row with every given field readable back via a fresh query.
- [x] `tests/models/test_models_smoke.py` -- add `PipelineRun` to the smoke-instantiation import/set.

**Acceptance Criteria:**
- Given a filter run with 5 relevant, 2 irrelevant, 1 error, when the CLI command finishes, then a `pipeline_runs` row exists with `run_type="filter"`, `succeeded=7`, `errors=1`.
- Given a summarize run where every article's LLM call bills tokens but fails, when the CLI command finishes, then the row's usage columns reflect the billed tokens, not zero.
- Given `alembic upgrade head` from the current head, when run, then it succeeds and `pipeline_runs` exists; `alembic downgrade -1` cleanly drops it with no leftover state.

## Spec Change Log

## Design Notes

**Why `succeeded` is one generic column, not per-type splits.** This table is for coarse spend/volume trend reporting across weeks - not a replacement for the CLI's detailed per-run printout (which still shows relevant/irrelevant/borderline separately). Splitting columns per run type would mean nullable, type-specific fields unused by the other row kind, for no reporting benefit at MVP scale (2 dogfood users, weekly cadence).

**Why the write lives in `cli.py`, not inside the pipeline functions.** Keeps `filter_pending_articles`/`summarize_relevant_articles` free of a persistence side effect beyond what they already do (per-article `Article` writes) - they stay callable from tests and any future caller without silently writing history rows. The tradeoff, accepted explicitly: a future non-CLI caller of these functions (e.g. a scheduler invoking them directly) won't get a `pipeline_runs` row unless it also calls `record_run()`.

## Verification

**Commands:**
- `python -m pytest tests/ -q` -- expected: all pass, including the two new test files, no new failures beyond the 5 known `.env`-sensitive ones.
- `python -m ruff check src tests` -- expected: clean.
- `python -m mypy` -- expected: no new errors.
- `python -m alembic upgrade head` then `python -m alembic downgrade -1` then `python -m alembic upgrade head` again -- expected: all three succeed with no error, `pipeline_runs` present after the final upgrade.

## Suggested Review Order

**Schema**

- New table: one row per completed CLI run, generic columns shared by both run types.
  [`pipeline_run.py:13`](../../src/newsagent/models/pipeline_run.py#L13)

- Migration mirrors `b2c3d4e5f6a7`'s shape; head is `a4b5c6d7e8f9`, reciprocal `downgrade` drops the table.
  [`7fe4f7681621_pipeline_runs.py:19`](../../alembic/versions/7fe4f7681621_pipeline_runs.py#L19)

**Write path**

- `record_run()`: build row, `db.add`, `db.commit`, return - matches `services/sources.py` style.
  [`pipeline_runs.py:9`](../../src/newsagent/services/pipeline_runs.py#L9)

- CLI wiring: `record_run` called right after the existing `Usage:` print, in both branches; `run_type` uses shared constants (not bare strings) to avoid typo drift.
  [`cli.py:87`](../../src/newsagent/cli.py#L87)

- Mirrored call for `summarize`, mapping `summary_report` fields the same way.
  [`cli.py:106`](../../src/newsagent/cli.py#L106)

**Peripherals**

- Model registration for import/`__all__`.
  [`__init__.py:8`](../../src/newsagent/models/__init__.py#L8)

- Persists every given field, readable back via a fresh query; includes the zero-article-run case.
  [`test_pipeline_runs.py:1`](../../tests/services/test_pipeline_runs.py#L1)

- Smoke-instantiation coverage for the new model alongside all others.
  [`test_models_smoke.py:15`](../../tests/models/test_models_smoke.py#L15)
