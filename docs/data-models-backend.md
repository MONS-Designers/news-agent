# Data Models - backend

**Date:** 2026-09-10
**ORM:** SQLAlchemy 2.0.51, declarative 2.0 style only
**Migrations:** Alembic 1.18.5, 33 revisions, head `b7e4a1c9d3f2`
**Database:** PostgreSQL on Neon, driver `psycopg` 3.3.4

## Style rules that apply to every model

- `Mapped[...]` with `mapped_column(...)`, and `select()` for queries. The legacy `Query`
  API and bare `Column(...)` class attributes are never used.
- Status columns are **plain strings with no database enum or check constraint**. `Source`,
  `Topic`, `PendingTaxonomySuggestion`, `Article` and `OutboundCall` all follow this
  convention. Allowed values are module-level constants next to the model.
- "Has this happened yet, and when" is modelled as a **nullable timestamp**, never a
  boolean. `Digest.sent_at`, `Digest.opened_at`, `DigestLink.clicked_at`,
  `User.unsubscribed_at`, `User.welcomed_at` and `User.topics_stale_at` all share that
  shape, which answers both questions with one column and stays reversible.
- Every migration uses `op.batch_alter_table` even though production is Postgres. Eight
  existing migrations rely on it; it is not to be simplified away.

## Entity overview

```text
admins                                        waitlist
                                              (capacity-full sign-in attempts)
fields ──< roles
   │
   └──< pending_taxonomy_suggestions ──┐ (self-FK: parent_suggestion_id)
                                       └─┘

topics ──< sources ──< articles
   │                       │
   └──< user_topic_preferences        digest_articles >── digests
             │                                              │
users ───────┘                                              │
   ├──< digests ──< digest_links ──> articles               │
   └──< feedback >── digests, articles                      │

outbound_runs ──< outbound_calls ──> articles
      │
      └──< log_entries

model_prices        scheduler_lease (single fixed row, id = 1)
```

## Identity and access

### `admins`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | primary key |
| `email` | str | unique, indexed |
| `created_at` | datetime | server default `now()` |

An email with an `Admin` row can always sign in, even when the registration cap is full. In
that case the session carries `user_id` null.

### `users`

The largest model in the schema. Grouped by concern:

**Identity.** `id`, `email` (unique, indexed), `name`, `created_at`.

**Google claims.** `given_name`, `family_name`, both nullable and captured only at row
creation. `first_name(user)` in the same module prefers `given_name` over splitting `name`,
because `name.split()[0]` breaks for family-name-first cultures. `family_name` has no reader
today. These are null for dev-login, CLI-seeded users, and every row predating the column.

**Profile.** `field_name`, `role_name`, `experience_bucket`, `interest_free_text`, all
nullable plain strings. Field and role are deliberately **not** foreign keys: "Other" is a
user-interface concept only, and a curated pick and a typed "Other" value are stored
identically. `experience_bucket` is validated against a fixed illustrative set in
`services/profile.py` and has no "Other" concept.

**Delivery.** `digest_frequency`, not null, defaulting to `weekly`. It stores a key into
`services.cadence.INTERVAL_DAYS` rather than a number of days, so the mapping can change
without a data migration. Valid keys are `daily`, `twice_weekly`, `weekly`.
`unsubscribed_at` is the reversible opt-out. `welcomed_at` records when the one-time beta
welcome was delivered; a failed send leaves it null so the next run retries with the welcome
intact rather than silently downgrading to an ordinary digest. It lives on the user rather
than the digest because the welcome belongs to the person's lifecycle and its beta-only
variant is sent when no digest exists at all.

**Suggestions.** `suggestion_status` (not null, default `none`), `suggested_topic_ids`
(JSON), `suggested_new_topic_names` (JSON), `suggestion_request_seq` (int, default 0). The
sequence number lets a later request supersede an in-flight one. Unlike the profile columns,
`suggestion_status` is not nullable: a user who never saved a profile reads `none`, not null.

**Divergence.** `topics_stale_at`, set when a profile edit changes an input that topic
suggestions derive from while the reader already has subscriptions, and cleared when they
next save topics. Subscriptions are never touched here, because silently unsubscribing a
reader is worse than leaving a stale one.

### `waitlist`

`id`, `email` (unique, indexed), `name`, `captured_at`. A brand-new email that arrived after
the registration cap was full. Never a `User`, never signed in.

## Content

### `topics`

`id`, `name` (unique, indexed), `status` (default `approved`), `created_at`. `rejected` is
defined but unused, so the deferred admin-approval follow-up needs no further migration.

### `sources`

`id`, `topic_id` (FK to `topics`), `url` (unique), `name`, `status` (default `pending`),
`created_at`. Only `approved` sources are polled by the fetch stage.

### `articles`

The pipeline's state machine lives on this table. One row per unique URL.

| Column | Purpose |
| --- | --- |
| `id`, `source_id`, `title`, `url` (unique) | Identity, and the dedupe key |
| `published_at`, `scraped_at` | Feed timestamp and insert time |
| `rss_summary`, `full_text` | Raw text inputs |
| `relevance_score` (float), `relevance_status` | Score is the provider's fact, status is the pipeline's verdict |
| `summary_he`, `title_he`, `source_language`, `reading_time_minutes`, `paragraphs_he` (JSON) | The persisted `SummaryResult`, so rendering never recomputes |
| `interestingness` (float) | General "worth reading" signal, distinct from relevance, feeds ranking |
| `summary_status`, `summarize_attempts` | Summarization state and bounded-retry counter |
| `extraction_status`, `extraction_attempts` | Full-text extraction state and bounded-retry counter |
| `image_url` | Extracted from RSS media fields at fetch time |

Storing score and verdict separately means a threshold change can re-verdict every article
without paying to re-score them.

**State machines.** All three are plain strings.

```text
relevance_status:   pending -> relevant | irrelevant | refused (terminal) | error (retried)
summary_status:     pending -> summarized | refused (terminal) | error (retried)
extraction_status:  pending -> done | failed (terminal, after bounded retries)
```

`summarize_attempts` and `extraction_attempts` are incremented on every failed attempt.
Once they reach `NEWSAGENT_MAX_SUMMARIZE_ATTEMPTS` or `NEWSAGENT_MAX_EXTRACTION_ATTEMPTS`
the status becomes terminal, so a deterministically failing article stops being billed for
forever.

**Image policy.** `image_url` is still extracted and stored, but the digest renders no
images at all. See the content-policy section in the repository's `CLAUDE.md`.

## Subscription and delivery

### `user_topic_preferences`

`id`, `user_id`, `topic_id`, `created_at`, with a unique constraint on the pair. The
association table between readers and topics.

### `digests`

| Column | Notes |
| --- | --- |
| `id`, `user_id`, `date` | Unique constraint on `(user_id, date)` - one digest per reader per date |
| `created_at` | |
| `tracking_token` | Unique, `secrets.token_urlsafe(24)`, never the sequential id, so the public tracking endpoint cannot be walked to forge opens |
| `sent_at`, `opened_at` | Nullable timestamps |
| `opened_device_type` | Set once, alongside `opened_at` |
| `intro_he`, `dad_joke_he` | Digest-level editorial voice, composed by the LLM from the week's headlines |

### `digest_articles`

`id`, `digest_id`, `article_id`, `created_at`. The row itself is the record of delivery,
which is why the build stage selects on "not yet sent" rather than "articles from this
week". Nothing repeats across runs, and nothing is lost when a week is skipped.

### `digest_links`

One click-trackable link embedded in a sent digest.

`id`, `digest_id`, `token` (unique), `kind`, `article_id` (nullable), `target_url`,
`created_at`, `clicked_at`, `device_type`. Unique on `(digest_id, kind, article_id)`.

Link kinds: `article`, `preferences`, `unsubscribe`, `feedback_up`, `feedback_down`. The
feedback kinds carry an `article_id` for a per-article thumb, or null for the digest-level
pair in the footer.

Rows are get-or-created at render time, so a retried send reuses the same token instead of
minting a new one.

### `feedback`

`id`, `user_id` (nullable, indexed), `digest_id` (nullable), `article_id` (nullable),
`source`, `sentiment` (nullable), `text` (nullable), `created_at`.

Deliberately append-only and permissive: no unique constraint, and both `sentiment` and
`text` nullable. A reader tapping the same thumb twice leaves two rows, which is honest
data. Deduplicating would silently discard a second, later opinion. The point of this table
is that leaving feedback never fails.

`user_id` is nullable because an email thumb is authenticated by the `DigestLink` token, not
by a session, and the digest may outlive the user row.

`source` records where the reader was: `article`, `digest` or `app`. It is not derivable
from the nullable foreign keys, since a digest-level thumb and a footer note both carry a
`digest_id` and no `article_id`.

`sentiment` holds `up` or `down` from the email thumbs, or the digit `"1"` through `"5"`
from the in-app star widget. The two share a column because it is already a free-form
nullable string with no database constraint, and the in-app source is the only writer that
ever stores a rating.

## Profile taxonomy

### `fields`

`id`, `name` (unique, indexed), `created_at`.

### `roles`

`id`, `field_id` (FK, indexed), `name` (indexed), `created_at`. Unique on
`(field_id, name)`, named `uq_roles_field_name`. Names are unique per field rather than
globally, because "Researcher" legitimately exists under both Healthcare and Education.

### `pending_taxonomy_suggestions`

A free-text "Other" field or role submission, queued for admin review.

`id`, `kind` (indexed), `field_id` (nullable FK), `parent_suggestion_id` (nullable self-FK),
`normalized_text` (indexed), `raw_text` (nullable), `submission_count` (default 1), `status`
(indexed, default `pending`), `created_at`.

One row per unique combination of kind, field, normalized text and status. Resubmitting
something that matches an existing **pending** row increments its `submission_count`.
Resubmitting something that matches an already-decided row creates a fresh pending row
rather than reopening or mutating the decided one, because the same text may legitimately be
rejected, resubmitted and rejected again.

**The partial unique index `uq_pending_taxonomy_suggestions_open`** is the database backstop
for the "one pending row per normalized text" rule. It matters because the service's
select-then-insert is not atomic, so two concurrent submissions would otherwise create two
rows at count 1 instead of one at 2, corrupting the demand signal the admin queue ranks by.

Three details in that index are load-bearing:

- It uses `COALESCE(field_id, -1)` rather than a bare `field_id`. Nulls never compare equal
  in a unique index, and `kind='field'` rows always carry a null `field_id`, so a plain
  three-column index would silently protect role rows only.
- It folds in `COALESCE(parent_suggestion_id, -1)`, so two orphan role rows with identical
  text but different parent field suggestions stay distinct. Without that, a cascading
  decision could not tell them apart.
- It is partial, `WHERE status = 'pending'`, so decided rows stay outside it.

`raw_text` holds the submission as typed. `normalized_text` is the dedupe key and is
casefolded, so promoting a suggestion without `raw_text` would mint a lowercase name sitting
next to properly cased ones. It is nullable because rows written before the column existed
genuinely have no display form.

## Telemetry and operations

### `outbound_runs`

One row per stage invocation, always created exactly once by `open_run()`, even for an
invocation that never places a call.

`id`, `created_at`, `finished_at`, `kind`, `user_id` (nullable), `subscriber_count`
(nullable), `intent_summary` (nullable text), `succeeded`, `refused`, `errors`.

`user_id` is null for the shared stages, filter and summarize, and populated only when the
work was done for one reader, as in digest build and profile suggestions.
`subscriber_count` is the mirror image: meaningful only for the shared stages, null for
per-user runs.

The three counters are written once at close, from the stage's own report, never incremented
live. Token, cost and duration totals are deliberately **not** columns here. They are always
a `SUM` over this run's child calls.

`intent_summary` is bounded, and never a raw prompt or user-authored free text.

### `outbound_calls`

One row per outbound HTTP attempt. The atom of the telemetry system, and the sole source of
truth for spend, latency and result.

`id`, `run_id` (nullable, indexed), `created_at`, `purpose`, `target` (default `llm`),
`status`, `attempt` (default 1), `model`, `duration_ms`, `article_id` (nullable, indexed),
`tokens_in`, `tokens_out`, `unit`, `output_chars`, `cost_usd`, `rate_in_usd_per_mtok`,
`rate_out_usd_per_mtok`. The three money columns are `Numeric(12, 6)`.

`status` is one of `ok`, `error`, `malformed`, `avoided`. `target` is `llm`, `email` or
`rss`, though only `llm` is written in the current revision.

`run_id` is nullable. A call made with no open run is still recorded, with
`purpose='UNATTRIBUTED'`. The architecture spine's entity diagram does not mark it nullable,
but there is no run to attach to in that case, and fabricating an owning run would
misrepresent what happened.

The rate columns are copied onto each call at write time rather than held as a foreign key,
so a later pricing refresh can never change a historical call's recorded cost. For an
`avoided` row, `cost_usd = 0` is a literal written by the caller: nothing was spent, with
total certainty, so it is not a priced value.

### `model_prices`

`id`, `model` (indexed), `rate_in_usd_per_mtok`, `rate_out_usd_per_mtok`, `effective_from`,
`source`.

**Append-only.** A price change never updates or deletes a row; `refresh-pricing` only
inserts a new one with a later `effective_from`. `lookup_rate` in `telemetry/pricing.py`
reads the newest row whose `effective_from` is at or before now.

`source` is `api`, from the provider fetch, or `manual`, a human-entered correction. Not
modelled as an enum, matching the convention used for status columns.

### `log_entries`

`id`, `created_at`, `level`, `logger_name`, `message`, `version`, `outbound_run_id`
(nullable, indexed).

One row per emitted log record, and **the only log destination**. There is no file or stream
fallback. `outbound_run_id` starts null and is patched in after the fact, because the
`outbound_runs` row is only created at the end of a run. A write failure inside the log
handler itself falls back to `logging.Handler.handleError()`, which prints to stderr, rather
than raising into application code.

### `scheduler_lease`

`id` (fixed at 1), `holder`, `expires_at`.

A single fixed row, because there is one delivery loop and therefore one thing to hold.
Using a constant id rather than one row per holder is what makes claiming it a single
conditional `UPDATE`, which the database executes atomically.

It exists because sending is not idempotent across processes: two loops both reading
`Digest.sent_at IS NULL` would each render and send the same digest. `welcomed_at` already
protected the one-time welcome, but nothing protected an ordinary digest.

It is time-based rather than a held database lock, because a scheduler that is killed by a
container stop or an out-of-memory kill never gets to release anything. A lock depending on
an orderly release would block delivery until a human noticed. An expiring lease recovers on
its own once `expires_at` passes.

`holder` is an opaque per-process identity, so a holder can tell its own lease from a
rival's and renew it instead of waiting out its own expiry.

## Migration strategy

Thirty-three Alembic revisions form a single linear chain from `7de791f6b76c` (initial
schema) to head `b7e4a1c9d3f2` (Google given and family name claims). There are no branches
and no merge points.

Schema is created and upgraded with:

```bash
alembic upgrade head
```

Notable revisions beyond plain column additions:

| Revision | What it does |
| --- | --- |
| `f9c2d7e0b118` | Drops `digest_articles.summary_he` - the summary lives on `Article` |
| `f2b6d81a04c7` | Renames `articles.bullets_he` to `paragraphs_he` |
| `d7f3a4b91e28` | Data migration renaming curated Field, Role and Topic names from English to Hebrew |
| `a06a39402215` | Replaces the earlier `pipeline_runs` and `Usage` tables with `outbound_runs` plus `outbound_calls` |
| `b2c3d4e5f6a7` | Adds the partial unique index on open taxonomy suggestions |

Alembic's own configuration lives in `alembic.ini` and `alembic/env.py`; migration files sit
in `alembic/versions/`.

---

_Generated using BMAD Method `document-project` workflow_
