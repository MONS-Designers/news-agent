# Code Map

Implementation prescription for SPEC.md's capabilities. Grouped by layer; each row names the file, the kind of change, and what it does.

## LLM layer

| File | Change | What |
|---|---|---|
| `src/newsagent/llm/types.py` | edit | New `SourceCandidate` type (name + feed URL) - the finder's output shape |
| `src/newsagent/llm/base.py` | edit | New public `discover_sources(topic_name, criteria, *, limit)` returning `list[SourceCandidate] \| Refusal` + abstract `_discover_sources` - same template-method shape as `score_relevance`/`summarize` (public wrapper owns retry, adapter implements the raw call). `limit` is asked higher than the cap the caller keeps, so collisions and dead URLs don't empty the topic |
| `src/newsagent/llm/external.py` | edit | Real adapter: one "finder" LLM call using the four criteria (authoritative, global-scale, free, on-topic). No second/judge call |
| `src/newsagent/llm/mock.py`, `src/newsagent/llm/demo.py` | edit | Deterministic/offline doubles for `discover_sources`, matching the existing pattern for the other two methods |

## New service

| File | Change | What |
|---|---|---|
| `src/newsagent/services/topic_sourcing.py` | new | `run_topic_bootstrap(engine, topic_id)`: the single entry point the background task schedules. Opens its own `Session` from the engine, re-loads the Topic by id (returns early if gone), runs `assign_topic_color` **first and unconditionally**, then `discover_sources_for_topic`. Catches `LLMError` so a finder failure never costs the color |
| ⤷ `discover_sources_for_topic(db, topic)` | | Calls the finder; returns early on `Refusal` (logged). Dedupes candidates by normalized URL, drops any whose scheme isn't `http`/`https` (feedparser accepts local paths - `file:///` would read server files), truncates to the keep-cap. Per survivor: fetch with an explicit timeout, reject on exception, on `bozo` with no entries, or on zero entries; then `services.sources.add_source(..., status=STATUS_PENDING)` and **branch on the returned `created` flag** - `False` means the URL is already owned by another Topic (`Source.url` is globally unique), logged as a collision, not counted as success. Logs a per-candidate reason for every rejection so a zero-source topic is never silent |
| ⤷ `assign_topic_color(db, topic)` | | Generates a candidate hex, rejects it if it collides with any existing non-null `Topic.color` or fails 4.5:1 contrast against `#0b1020`, retries up to a fixed attempt cap, then commits. On `IntegrityError` from the unique constraint (concurrent topic creation) retries; on exhausting the cap, logs giving up and leaves the column NULL so `render.py`'s fallback applies |

## Trigger wiring

| File | Change | What |
|---|---|---|
| `src/newsagent/services/preferences.py` | edit | `set_preferences` returns which topic ids were newly created (today the info - `resolved_new_ids` - is computed internally and discarded). Only ids where `add_topic` reported `created=True` - re-saving preferences that name an already-existing pending Topic must not re-trigger discovery |
| `src/newsagent/api/routers/me.py` | edit | Add a `BackgroundTasks` parameter to `update_my_preferences`; for each newly-created topic id schedule `topic_sourcing.run_topic_bootstrap(db.get_bind(), topic_id)`. **Pass the engine, not `db`** - `update_my_profile` in this same file already does exactly this, with a comment recording that the request-scoped session is closed by the time the task runs (AD-5). Passing `db` or a live `Topic` instance reintroduces that bug |

## Pipeline query scope

| File | Change | What |
|---|---|---|
| `src/newsagent/pipeline/fetcher.py` (`fetch_approved_sources`, ~line 154) | edit | `Source.status == STATUS_APPROVED` → `Source.status.in_((STATUS_APPROVED, STATUS_PENDING))`, plus a join to `Topic` excluding `Topic.status == STATUS_REJECTED` |
| `src/newsagent/pipeline/relevance.py` (`filter_pending_articles`, ~line 119) | edit | Same widening and the same rejected-Topic exclusion - otherwise a pending source's articles are never fetched or scored regardless of digest-time logic |

## Model + migration

| File | Change | What |
|---|---|---|
| `src/newsagent/models/topic.py` | edit | New nullable `color: Mapped[str \| None]` column |
| `alembic/versions/<new>.py` | new | Add the nullable column **with a unique constraint** (the read-then-write uniqueness check alone loses a concurrent-creation race); backfill the 3 pre-existing approved Topics with their current hardcoded colors (`בינה מלאכותית`→`#4ade80`, `סייבר`→`#f87171`, `חלל`→`#818cf8`) by resolving each name to an id first, so a renamed Topic surfaces instead of silently no-opping; include a `downgrade()` that drops the column. Follows the single-column-addition convention of `f3b9d2a71c5e_user_unsubscribed_at.py`. **Show for review before running - standing project rule** |
| `src/newsagent/pipeline/render.py` | edit | Remove the hardcoded `_TOPIC_COLORS` dict; read `topic.color`, falling back to the existing `_DEFAULT_TOPIC_COLOR`. Note this turns an in-memory dict lookup into an attribute access on the lazily-loaded `article.source.topic` chain inside `_to_view`, once per article - eager-load the chain where the digest's articles are queried rather than paying an N+1 |

## Removal

| File | Change | What |
|---|---|---|
| `src/newsagent/services/sources.py` | edit (partial removal) | Remove `DEFAULT_SOURCES`, `seed_default_sources()`, and **this module's** `SeedReport`. `services/taxonomy.py` defines its own unrelated `SeedReport` and mentions `seed_default_sources` in a docstring - leave that class alone, fix only the stale docstring reference. Keep `add_topic`/`add_source`/`set_source_status` - still used by `topic_sourcing.py` |
| `src/newsagent/cli.py` | edit (replacement) | Remove the `seed-sources` subcommand and its dispatch branch; add `discover-topic "<name>"` in its place - `add_topic` then `run_topic_bootstrap`, following the existing `subscribe` subparser+dispatch shape. This is the bootstrap path for an empty database, and it runs through the same discovery code as production rather than a second hardcoded list. With `NEWSAGENT_LLM_PROVIDER=mock` it works offline against the `discover_sources` double |

## Tests and docs the removal breaks

| File | Change | What |
|---|---|---|
| `tests/services/test_sources.py` | edit (removal) | Imports `DEFAULT_SOURCES` and `seed_default_sources` at module level and asserts on them - a module-level `ImportError` would fail every test in the file, not just the seeding ones. Delete or rewrite the seeding tests in the same change |
| `docs/v1-manual-test-plan.md` (~line 41) | edit | Replace the `python -m newsagent.cli seed-sources` setup step with the `discover-topic` equivalent |

## Documentation

| File | Change | What |
|---|---|---|
| `CLAUDE.md` | edit | "Locked product decisions": reverse "Source auto-discovery from user interests remains out: RSS sources stay admin-curated." "Open technical risk": note V1 ships with deterministic feed validation only (no LLM judge), full judge chain deferred to the future pipeline overhaul |
