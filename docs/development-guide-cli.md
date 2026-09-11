# Development Guide - cli

**Date:** 2026-09-10
**Part:** `cli` (`src/newsagent/cli.py`, `src/newsagent/pipeline/`, `src/newsagent/scheduler.py`)

## Prerequisites

Identical to the backend: Python 3.12 or newer, the package installed editable, and a
database reachable through `NEWSAGENT_DATABASE_URL`. The command-line part adds no dependency
of its own. Follow [development-guide-backend.md](./development-guide-backend.md) for setup.

## Read this before your first local run

**A local pipeline run sends real email and spends real money.** The checked-out `.env`
carries real SMTP credentials and a real external LLM token, even though its database points
at the test Neon branch. The database being safe does not make the run safe.

Two settings neutralize that, and both default to the harmless value:

```bash
NEWSAGENT_LLM_PROVIDER=mock
```

```bash
NEWSAGENT_EMAIL_SENDER=console
```

With `NEWSAGENT_EMAIL_OUTBOX_DIR` set, the console sender also writes each email's HTML to
that directory, which is the practical way to inspect a rendered digest.

**Never point a local run at `.env.prod`.**

## Command reference

Every command is a subcommand of one `argparse` tree, and the whole run shares one database
session.

### Bootstrapping

```bash
python -m newsagent.cli add-admin you@example.com
```

```bash
python -m newsagent.cli add-user you@example.com --name "Full Name"
```

### Seeding

```bash
python -m newsagent.cli seed-sources
```

```bash
python -m newsagent.cli seed-fields
```

```bash
python -m newsagent.cli seed-roles
```

All three are get-or-create by natural key, so re-running them is idempotent and safe.

### The pipeline, in order

```bash
python -m newsagent.cli fetch
```

```bash
python -m newsagent.cli filter
```

```bash
python -m newsagent.cli extract
```

```bash
python -m newsagent.cli summarize
```

```bash
python -m newsagent.cli build-digests
```

```bash
python -m newsagent.cli send-digests
```

The first four run daily in production, the last two weekly. Each stage is independently
resumable, because progress is the article's own status columns rather than a job queue.

### Subscriptions

```bash
python -m newsagent.cli subscribe you@example.com "Topic Name"
```

Returns exit code 1 and prints the message when the email or topic does not resolve.

### Cost

```bash
python -m newsagent.cli usage-report
```

```bash
python -m newsagent.cli refresh-pricing
```

## Running the scheduler

```bash
python -m newsagent.scheduler
```

A long-lived sequential loop with a 120-second tick. It needs the database URL and the mail
settings; it does not need the OAuth or session settings the API needs.

Each tick builds for unwelcomed readers, then for cadence-due readers, then runs one send
pass. Both build passes are bounded by a query that usually returns nobody, so an idle tick
costs two selects and no LLM call.

Signal handlers finish the tick in flight and then exit, so a container stop does not kill a
send midway.

Running more than one instance is safe. The `scheduler_lease` row lets exactly one deliver at
a time and the rest skip their tick, but the extras do no useful work, so one is enough.

## Exit codes

Most commands return 0. Two do not:

| Command | Code | Meaning |
| --- | --- | --- |
| `subscribe` | 1 | The email or topic did not resolve |
| `refresh-pricing` | 0 | Rates updated |
| `refresh-pricing` | 2 | Pricing source unavailable this run; existing rates stay in effect. Not a failure. |
| `refresh-pricing` | 1 | A real failure, such as the database write itself |

**The `refresh-pricing` codes are the entire interface with the infrastructure repository's
scheduler.** Changing them is a cross-repository contract change, not a local refactor.

## Debugging a run

Every log record lands in the `log_entries` table. There is no file or stream destination.

Raise verbosity for one run, in PowerShell:

```bash
$env:NEWSAGENT_LOG_LEVEL="DEBUG"; python -m newsagent.cli summarize
```

The same in bash:

```bash
NEWSAGENT_LOG_LEVEL=DEBUG python -m newsagent.cli summarize
```

The `filter` and `summarize` commands wrap their work in `track_outbound_run_logs()` and then
patch the run id onto the log rows the run produced, so you can pull exactly the lines
belonging to one run by filtering `log_entries.outbound_run_id`.

`usage-report` reads the same run data from the other side: tokens, latency and waste per
purpose. Its duration average excludes `avoided` rows, because a cache hit's near-zero lookup
time would otherwise drag down the average of real call latency. The call count still
includes them.

## Tuning knobs

| Setting | Default | Effect |
| --- | --- | --- |
| `NEWSAGENT_RELEVANCE_THRESHOLD` | `0.7` | Verdict cutoff. Changing it re-verdicts without re-scoring, since the score is stored separately. |
| `NEWSAGENT_MAX_SUMMARIZE_ATTEMPTS` | `3` | Retries before `summary_status` becomes terminal |
| `NEWSAGENT_MAX_EXTRACTION_ATTEMPTS` | `2` | Retries before `extraction_status` becomes terminal |
| `NEWSAGENT_EXTRACTION_MAX_CHARS` | `10000` | Extracted text is truncated before it is stored |
| `NEWSAGENT_EXTRACTION_TIMEOUT_SECONDS` | `10.0` | Per-page fetch timeout |
| `NEWSAGENT_FETCH_CONCURRENCY` | `5` | Bounded worker pool per stage |
| `NEWSAGENT_FILTER_CONCURRENCY` | `5` | |
| `NEWSAGENT_SUMMARIZE_CONCURRENCY` | `5` | |
| `NEWSAGENT_EXTRACTION_CONCURRENCY` | `5` | |
| `NEWSAGENT_DIGEST_MAX_ARTICLES` | `7` | Top-N per digest |
| `NEWSAGENT_RECENCY_HALF_LIFE_HOURS` | `84.0` | Half a week, tuned to the weekly send |
| `NEWSAGENT_RELEVANCE_WEIGHT` | `0.40` | The weight trio sums to 1.0 |
| `NEWSAGENT_RECENCY_WEIGHT` | `0.25` | |
| `NEWSAGENT_INTEREST_WEIGHT` | `0.35` | |
| `NEWSAGENT_INTERESTINGNESS_WEIGHT` | `0.60` | Splits the interest term |
| `NEWSAGENT_PERSONALIZATION_WEIGHT` | `0.40` | |

Concurrency is bounded rather than unbounded on purpose: an unbounded pool would hammer many
RSS hosts at once, look like a scraper, and blow through the provider's rate limit.

## Conventions to respect when adding a stage

- **A stage is a function over a `Session` returning a report dataclass of counters.** No
  FastAPI imports, no framework of any kind.
- **Workers receive plain data, never the `Session`.** All database writes happen on the
  calling thread. This is stated in four stage docstrings and is not negotiable.
- **`contextvars` do not propagate into `ThreadPoolExecutor` workers.** Copy the telemetry
  attribution context explicitly, or every call the workers make records as
  `UNATTRIBUTED`.
- **Commit per item**, so progress survives a crash mid-run.
- **Only `pending` and `error` rows enter a stage.** Terminal states stay terminal, which is
  what stops a deterministically failing article from being paid for forever.
- **Store the provider's fact and the pipeline's policy separately**, the way relevance stores
  both score and verdict.

## Testing

`tests/pipeline/` holds nine modules, one per stage plus ranking and rendering.
`tests/test_cli.py` covers dispatch and exit codes, and `tests/test_scheduler.py` covers the
tick and the lease.

Stages are testable without patching because the provider and the sender are parameters. The
mock LLM adapter and the console email sender stand in for the real ones directly.

The two `autouse` fixtures in `tests/conftest.py` reset settings and redirect telemetry and
logging to in-memory SQLite. A test that touches the database must bring its own in-memory
engine.

## Known behavior to be aware of

**Send is at-least-once, by design.** `pipeline/send.py` sends before committing `sent_at`,
so a process killed between the two re-sends an email the reader already received. SMTP and
the database share no transaction, so the window cannot be closed, only pointed the other way
at at-most-once delivery, which risks losing a digest instead. The scheduler lease prevents
concurrent delivery, not crash recovery. See
`_bmad-output/implementation-artifacts/deferred-work.md`.

**A reader subscribed to a topic with zero approved sources gets a silent empty digest.**
Tracked as issue 48.

---

_Generated using BMAD Method `document-project` workflow_
