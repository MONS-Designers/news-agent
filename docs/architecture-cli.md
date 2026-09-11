# Architecture - cli

**Date:** 2026-09-10
**Part:** `cli`
**Root:** `src/newsagent/cli.py`, `src/newsagent/pipeline/`, `src/newsagent/scheduler.py`
**Project type:** command-line application
**Architecture pattern:** pipeline of stages over a shared database, plus a long-lived
delivery loop

## Executive Summary

Two entry points, one package. `python -m newsagent.cli <command>` is the operator
interface: fifteen subcommands covering seeding, user management, the six content stages,
and cost reporting. `python -m newsagent.scheduler` is a long-lived loop that owns the send
schedule in code rather than in an external cron.

Neither is a client of the API. Both import the same `services/` and `pipeline/` modules the
API uses and open their own session from the same `SessionLocal`. That is the payoff of the
domain layer's no-web-framework rule.

## Technology Stack

| Category | Technology | Version | Justification |
| --- | --- | --- | --- |
| Language | Python | >= 3.12 | Same package as the backend |
| Argument parsing | argparse | stdlib | No third-party CLI framework; the surface is small and stable |
| Feeds | feedparser | 6.0.12 | RSS and Atom parsing |
| Page fetching | httpx | 0.28.1 | Used directly rather than trafilatura's downloader, so timeout and user agent stay configurable |
| Extraction | trafilatura | 2.2.0 | Article body, not navigation and advertising |
| Templating | Jinja2 | 3.1.6 | The digest email |
| SMTP | smtplib | stdlib | Real delivery with no vendor SDK |
| Concurrency | `concurrent.futures` | stdlib | Bounded `ThreadPoolExecutor` per network-bound stage |

The command-line part adds no dependency of its own. Everything it needs is already a
backend dependency.

## Architecture Pattern

### The six stages

Each stage is a plain function taking a `Session` and returning a small report dataclass of
counters. None of them import from `api/`. They run in dependency order but as independent
invocations, so a failure in one does not roll back the others.

```text
fetch ──► filter ──► extract ──► summarize ──► build-digests ──► send-digests
  │         │          │            │               │                │
  │         │          │            │               │                └─ mail adapter
  │         │          │            └─ LLM adapter  └─ LLM adapter (voice) + ranking
  │         │          └─ httpx + trafilatura
  │         └─ LLM adapter
  └─ feedparser
```

| Stage | Module | Reads | Writes |
| --- | --- | --- | --- |
| `fetch` | `pipeline/fetcher.py` | approved `sources` | new `articles`, deduped by URL |
| `filter` | `pipeline/relevance.py` | pending and errored `articles` | `relevance_score`, `relevance_status` |
| `extract` | `pipeline/extract.py` | relevant `articles` | `full_text`, `extraction_status`, `extraction_attempts` |
| `summarize` | `pipeline/summarize.py` | relevant `articles` | the five summary columns, `summary_status`, `summarize_attempts` |
| `build-digests` | `pipeline/digest.py` | summarized, undelivered `articles` | `digests`, `digest_articles`, editorial voice |
| `send-digests` | `pipeline/send.py` | unsent `digests` | rendered email out, `sent_at` |

### Cadence: the stages do not all run together

The digest is weekly, but the pipeline is not. The collection stages run **daily** so
nothing scrolls off an RSS feed unseen, since feeds hold only the latest twenty to fifty
items. Only the last two stages run **weekly**.

| Stages | Cadence |
| --- | --- |
| `fetch`, `filter`, `extract`, `summarize` | daily |
| `build-digests`, `send-digests` | weekly |

That means two scheduled jobs, not one. Ranking is tuned to match:
`digest_max_articles` is 7 and `recency_half_life_hours` is 84, half a week, so an article
from Monday still competes with one from Sunday rather than being buried by decay.

### State machines, not job queues

There is no queue and no job table. Progress is the article's own status columns, so a run
is resumable by construction: only `pending` and `error` articles enter a stage, and each is
committed individually so progress survives a crash mid-run.

Retries are bounded by counters on the row. Once `summarize_attempts` reaches
`NEWSAGENT_MAX_SUMMARIZE_ATTEMPTS`, or `extraction_attempts` reaches its own cap, the status
becomes terminal `failed`. A deterministically broken article or source stops being fetched
and billed for forever.

### Score versus verdict

`pipeline/relevance.py` stores both the provider's score and the pipeline's verdict. The
score is the provider's fact; the verdict is policy, derived from
`NEWSAGENT_RELEVANCE_THRESHOLD`. Keeping both means a threshold change can re-verdict every
article without paying to re-score any of them.

### Bounded concurrency, and the contextvars trap

Four stages parallelize network-bound work through a bounded `ThreadPoolExecutor`:
`fetch_concurrency`, `filter_concurrency`, `summarize_concurrency` and
`extraction_concurrency`, each defaulting to 5. Bounded rather than unbounded so the system
cannot hammer many RSS hosts at once, look like a scraper, or blow through the provider's
rate limit.

**Workers receive plain data only, never the SQLAlchemy `Session`.** A URL goes in, a parse
result or a score comes back, and every database write happens on the calling thread. That
discipline is stated in the docstrings of `fetcher.py`, `extract.py`, `relevance.py` and
`summarize.py`.

The related trap is that `contextvars` do not propagate into `ThreadPoolExecutor` workers,
so the telemetry attribution context has to be copied into each worker explicitly. Missing
that would silently produce `UNATTRIBUTED` calls.

### Ranking

`pipeline/ranking.py` scores each candidate and keeps the best `digest_max_articles`.
Unselected candidates get no `digest_articles` row and stay undelivered, so they compete
again on a future run.

```text
final_score = relevance_weight * relevance
            + recency_weight   * recency
            + interest_weight  * interest

recency  = exp(-ln(2) * hours_since / recency_half_life_hours)
interest = interestingness_weight * llm_interestingness
         + personalization_weight * topic_affinity
```

| Weight | Default |
| --- | --- |
| `relevance_weight` | 0.40 |
| `recency_weight` | 0.25 |
| `interest_weight` | 0.35 |
| `interestingness_weight` | 0.60 |
| `personalization_weight` | 0.40 |

`topic_affinity` is the personalization signal: among the reader's past **sent** digests
that contained at least one article of a given topic, the fraction that were opened. A topic
with no such history, including a reader with no sent digests at all, scores a neutral 0.5.
This is the first real consumer of the open-tracking data.

**Topic-diversity floor.** Among candidates whose topic is not already represented in the
digest, one guaranteed slot goes to each such topic's single best-scoring candidate, with
topics ranked by that best score rather than by raw global score. Remaining slots are filled
by global score among whatever is left. The floor only prevents a topic from taking a
*second* guaranteed pick. With a single topic it does nothing, and the result is identical to
plain top-N by score.

### Delivery selection

`build_digests` selects on "not yet sent to this reader", not "articles from this week". The
`digest_articles` row is itself the record of delivery, so nothing repeats across runs and
nothing is lost when a week is skipped. One digest per reader per date is enforced by a
unique constraint; re-running the same date appends only newly arrived articles, and no
empty digest is ever created.

### Editorial voice, and why it is reused

Each digest carries an LLM-composed `intro_he` and `dad_joke_he`, generated from that
digest's own headlines. Composition is best-effort: a refusal or provider error leaves the
voice empty and the template renders without it, rather than failing the build.

`_reuse_recent_voice` copies the voice from a recent digest built on the **exact same article
set** instead of paying for another call. The match is on the article set rather than on
topics, because the voice is generated from the headlines; borrowing it across different
article sets would open a reader's digest by referring to stories that are not in it.

This is aimed squarely at new signups. A reader with no open history gets a neutral affinity
for every topic, so two people who just picked the same topics rank identically and land on
the same top-N. That is exactly when the provider would otherwise be asked to write the same
introduction twice.

## The scheduler

`python -m newsagent.scheduler` runs a sequential loop with a 120-second tick.

Each tick does two independent build passes, then one send pass:

1. **First email.** Anyone who finished setup and has not been welcomed yet. Ungated by
   cadence, because their clock has not started and the promise made at signup is "in a few
   minutes". This is what makes the tick interval matter at all.
2. **Regular cadence.** Whoever `services/cadence.py` says is due today, at whatever
   frequency each of them chose.
3. **One send pass.** `send_pending_digests` delivers whatever is unsent regardless of which
   pass created it, so sending between the two builds would only split one mailing in half.

Both build passes are bounded by a query that usually returns nobody, so an idle tick costs
two selects and no LLM call. That, not the interval, is what makes a two-minute loop
affordable.

**Fetching, filtering and summarizing are deliberately not in this loop.** They stay in the
daily pipeline run. The loop only selects from already-summarized articles and delivers,
which is why it is cheap enough to run continuously.

### Cadence rules

`services/cadence.py` is the single place that turns a reader's chosen frequency into a
yes-or-no for today. It is kept apart from `pipeline/digest.py` on purpose: the build stage
decides *what* goes in a digest, cadence decides *whether* one is owed at all, and the
scheduler is the only thing that needs both.

| Frequency key | Minimum days between sends |
| --- | --- |
| `daily` | 1 |
| `twice_weekly` | 3 |
| `weekly` | 7 |

Cadence is a minimum gap rather than fixed weekdays, which keeps "twice a week" an
approximation, every third day, rather than a standing slot. Exact weekdays would need a
real schedule model naming which days in whose timezone; nothing outside this module should
learn about days.

An unknown frequency value falls back to the default rather than raising, so a row written
by an older or newer version of the application cannot stop that reader's mail.

Due-ness is measured from the last **sent** digest's date, not the last built one: a digest
that was built but never delivered has not started the reader's clock. A reader who has never
been sent one is due immediately. The whole answer is one grouped query with no per-user
work, because the scheduler asks on every tick and the answer is usually "nobody".

### Concurrency and shutdown

Two kinds of overlap could cause duplicate mail, and both are handled:

- **Within the process**, none by construction. The loop is sequential and sleeps *after*
  the tick returns, so a slow tick delays the next one rather than running alongside it. The
  interval is a minimum gap, not a wall-clock schedule. A real cron would not give this for
  free.
- **Across processes**, the `scheduler_lease` row lets exactly one instance deliver at a
  time; the rest skip their tick. Extra replicas are harmless but do no useful work, so one
  is enough. A killed holder's lease expires and delivery resumes with no intervention.

Signal handlers set a stop flag rather than aborting, so a container stop finishes the tick
in flight and then exits.

## Command surface

Fifteen subcommands under one `argparse` tree. The whole run shares one session opened by
`main()`.

| Group | Commands |
| --- | --- |
| Bootstrapping | `add-admin <email>`, `add-user <email> [--name]` |
| Seeding | `seed-sources`, `seed-fields`, `seed-roles` |
| Pipeline | `fetch`, `filter`, `extract`, `summarize`, `build-digests`, `send-digests` |
| Subscriptions | `subscribe <email> <topic>` |
| Cost | `usage-report`, `refresh-pricing` |

All seeding is get-or-create by natural key, so re-running it is idempotent.

`filter` and `summarize` wrap their work in `track_outbound_run_logs()` and then patch the
run id onto the log rows the run produced, so a debugging session can pull exactly the log
lines belonging to one run.

### Exit codes

`main()` returns 0 in almost every case. Two commands are exceptions:

- `subscribe` returns 1 on a `ValueError`, printing the message.
- **`refresh-pricing` has a three-value contract**, and the exit code is the entire interface
  with the infrastructure repository's scheduler:

| Code | Meaning |
| --- | --- |
| 0 | Rates updated |
| 2 | Pricing source unavailable this run; existing rates stay in effect. Not a failure. |
| 1 | A real failure, such as the database write itself |

### `usage-report`

Aggregates `outbound_calls` by purpose: call count, tokens in and out, and average duration.
The duration average **excludes `avoided` rows**, because a cache hit's near-zero lookup time
would otherwise drag down the average of real call latency for the same purpose. The call
count still includes them.

It then prints a waste line: retried attempts, avoided cache-hit calls, and malformed calls,
which were billed but unusable.

No dollar figures appear yet, since pricing lookup is only partly wired; see
`_bmad-output/implementation-artifacts/deferred-work.md`.

## Data Architecture

The command-line part owns no tables of its own. It reads and writes the same schema the API
does. See [data-models-backend.md](./data-models-backend.md), and the shared-state ownership
table in [integration-architecture.md](./integration-architecture.md).

## Testing Strategy

`tests/pipeline/` holds nine modules, one per stage plus ranking and rendering.
`tests/test_cli.py` covers the command dispatch and exit codes, and `tests/test_scheduler.py`
covers the tick and the lease.

Stages are testable because each takes a `Session` and returns counters, with the provider
and the sender injected as parameters. The mock LLM adapter and the console email sender
stand in for the real ones without any patching.

## Known Constraints

- **The send window is open by design.** Sending happens before the `sent_at` commit, so a
  process killed between the two re-sends an email the reader already received. SMTP and the
  database share no transaction, so the window cannot be closed, only pointed the other way
  at at-most-once delivery, which risks losing a digest instead. The lease does not help
  here; it prevents concurrent delivery, not crash recovery.
- **A local run sends real mail and spends real money.** The checked-out `.env` carries real
  SMTP credentials and a real LLM token, even though its database points at the test branch.
- **A reader subscribed to a topic with zero approved sources gets a silent empty digest**,
  tracked as issue 48.

---

_Generated using BMAD Method `document-project` workflow_
