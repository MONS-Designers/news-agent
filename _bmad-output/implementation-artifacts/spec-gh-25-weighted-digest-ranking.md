---
title: 'Per-user weighted ranking + top-5 digest selection (GH #25)'
type: 'feature'
created: '2026-07-31'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
baseline_revision: 'c5a147b0dbf78d8b383b5ae090919edef49f88d0'
final_revision: '4620b6a6fb01702d770c4f7f6ce6627f177d385c'
---

<intent-contract>

## Intent

**Problem:** `build_digests` (digest.py) attaches *every* undelivered, summarized, relevant article to a user's digest, marking each one delivered — but `render_digest_html`'s `_select_diverse` then silently truncates to 5 for display. Articles beyond the cap are marked delivered and never shown, and selection is a placeholder round-robin, not the weighted score GH issue #25 specifies.

**Approach:** Add a ranking stage that scores each undelivered candidate with `final_score = 0.40*relevance + 0.25*recency + 0.35*interest` and selects only the top N (default 5, config `digest_max_articles`) at **build time** — only selected articles get a `DigestArticle` row; the rest stay undelivered for a future run. Remove the render-time cap/selection since `digest.articles` is already the final set.

## Boundaries & Constraints

**Always:**
- Rank per user, over that user's undelivered articles in subscribed topics (reuse `_undelivered_articles`'s existing filter: `summary_status == SUMMARY_DONE`, `Source.topic_id` in the user's subscribed topics, not already in any `DigestArticle` for that user).
- `recency = exp(-ln(2) * hours_since_reference / recency_half_life_hours)` (default half-life 24h); reference timestamp is `published_at`, falling back to `scraped_at` when `published_at` is `None`.
- `interest = interestingness_weight*llm_interestingness + personalization_weight*personalization_affinity` (defaults 0.60 / 0.40). `llm_interestingness` = `Article.interestingness`, defaulting to 0.5 if `None`.
- `personalization_affinity` is per (user, topic): among the user's past **sent** digests (`sent_at is not None`, excluding the digest being built now) that contained ≥1 article of that topic, the fraction that were opened (`opened_at is not None`). Default 0.5 for any topic with zero such past digests, and 0.5 for every topic when the user has no past sent digests at all.
- All five weights + `recency_half_life_hours` + `digest_max_articles` are env-overridable settings in `config.py` (`NEWSAGENT_` prefix, matching existing `Settings` fields), defaults exactly as specified in GH #25.
- Sort candidates by `final_score` descending; take the top `digest_max_articles`. Only those get new `DigestArticle` rows this run.
- `render_digest_html` renders `digest.articles` as-is (already ≤ max, already ranked) — no re-selection, no re-capping. Topic grouping/ordering for visual layout may remain, but must not drop any entry.

**Block If:** none identified — the affinity formula above is fully determined by the existing schema (only whole-digest `opened_at` exists, no per-article click data), so there is no per-article personalization signal to defer to a human.

**Never:**
- No new schema/tracking fields (no per-article or per-topic click tracking) — out of scope; GH #25 explicitly scopes personalization to the existing `opened_at` signal.
- Do not touch relevance filtering (#10) or summarization (#11) logic — only `Article.relevance_score` / `Article.interestingness` are read here.
- No changes to email template markup/design (`digest.html.j2`, colors, layout).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| No open history | User has zero past sent digests | `personalization_affinity` = 0.5 for all topics; ranking still runs on relevance+recency+interestingness | No error |
| Fewer candidates than cap | 3 undelivered articles, cap = 5 | All 3 selected, no padding | No error |
| More candidates than cap | 8 undelivered articles across topics | Top 5 by `final_score` selected; other 3 stay undelivered (no `DigestArticle` row), eligible next run | No error |
| Missing `published_at` | Candidate article has `published_at is None` | Recency computed from `scraped_at` instead | No error |
| Missing `interestingness` | Legacy article has `interestingness is None` | Treated as 0.5 | No error |
| Repeat-opener bias | User opened 5/5 past digests containing Topic A, 0/5 containing Topic B | Topic A articles rank above equally-relevant/recent Topic B articles | No error |

</intent-contract>

## Code Map

- `src/newsagent/pipeline/ranking.py` (NEW) -- weighted score + top-N selection; owns recency decay and personalization-affinity computation
- `src/newsagent/pipeline/digest.py` -- `build_digests`/`_undelivered_articles`: call ranking, cap to `digest_max_articles` before creating `DigestArticle` rows
- `src/newsagent/pipeline/render.py` -- remove `_select_diverse` cap/placeholder (lines ~119-143); keep only display grouping over the already-final `digest.articles`
- `src/newsagent/config.py` -- add `relevance_weight`, `recency_weight`, `interest_weight`, `interestingness_weight`, `personalization_weight`, `recency_half_life_hours`, `digest_max_articles`
- `src/newsagent/models/digest.py` -- reference only (`opened_at`, `sent_at` are the affinity signal)
- `src/newsagent/models/article.py` -- reference only (`relevance_score`, `interestingness`, `published_at`, `scraped_at`)
- `tests/pipeline/test_digest.py` -- extend with cap/ranking/affinity cases per the I/O matrix
- `tests/pipeline/test_render.py` -- `test_selection_is_topic_diverse` (line ~162) asserted render-time selection; remove/replace since selection now happens in `digest.py`, not render
- `tests/pipeline/test_ranking.py` (NEW) -- unit tests for score computation per the I/O matrix

## Tasks & Acceptance

**Execution:**
- [x] `src/newsagent/config.py` -- add the 7 ranking settings with GH #25 defaults -- makes weights/cap env-overridable per Always
- [x] `src/newsagent/pipeline/ranking.py` -- implement `score_article`, `topic_affinity(db, user, before_date)`, and `select_top(db, user, candidates, for_date) -> list[Article]` -- isolates scoring/selection so digest.py stays orchestration-only
- [x] `src/newsagent/pipeline/digest.py` -- replace "attach all undelivered" with "attach `select_top(...)` result" -- stops silently dropping unselected articles
- [x] `src/newsagent/pipeline/render.py` -- delete `_select_diverse`/`_MAX_ARTICLES`, render `digest.articles` directly (grouped for display only) -- selection is no longer render's job
- [x] `tests/pipeline/test_ranking.py` -- cover all 6 I/O matrix rows -- verifies scoring/affinity logic in isolation
- [x] `tests/pipeline/test_digest.py` -- add cap test (8 candidates → 5 attached, 3 remain undelivered next run) -- verifies build-time selection end-to-end
- [x] `tests/pipeline/test_render.py` -- remove/replace `test_selection_is_topic_diverse` -- render no longer selects

**Acceptance Criteria:**
- Given a user with 8 undelivered relevant/summarized articles across topics, when `build_digests` runs, then exactly `digest_max_articles` `DigestArticle` rows are created, chosen by descending `final_score`, and the rest remain undelivered for the next run.
- Given a user with no past sent digests, when ranked, then personalization is neutral (0.5) and ranking still completes without error.
- Given a user who opened every past digest containing Topic A and none containing Topic B, when ranked, then an equally relevant/recent Topic A article outranks a Topic B one.

## Spec Change Log

(empty — no bad_spec loopback triggered in this run)

## Review Triage Log

### 2026-07-31 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3 (high 1, medium 1, low 1)
- defer: 3 (medium 1, low 2)
- reject: 8
- addressed_findings:
  - `[high]` `[patch]` Same-day rerun could exceed `digest_max_articles`: `select_top` capped only the current call's candidates, not the digest's cumulative total, so a second same-day run (an already-tested product behavior) could push a digest past the cap. Fixed by counting already-attached `DigestArticle` rows via a direct query (not the `digest.articles` relationship, which would cache stale) and passing the remaining slots as `select_top`'s new `limit` param. Added regression test `test_same_day_rerun_never_exceeds_cap`.
  - `[medium]` `[patch]` `ranking.select_top` used `datetime.now()` (naive local server time) against `published_at`/`scraped_at`, which are naive UTC — systematic recency skew on any non-UTC server. Fixed to `datetime.now(timezone.utc).replace(tzinfo=None)`.
  - `[low]` `[patch]` `render.py`'s module docstring still said "Groups the top articles by topic" after selection moved out of render entirely. Corrected.
  - `[medium]` `[defer]` Unbounded undelivered backlog with no staleness cutoff — new consequence of the cap (previously every undelivered article was attached and left the backlog each run); GH #25 is silent on pruning policy. Logged in deferred-work.md.
  - `[low]` `[defer]` No startup validation that the 5 ranking weights sum to 1.0 as the config comment claims. Logged in deferred-work.md.
  - `[low]` `[defer]` N+1 query pattern in `topic_affinity` (no eager-loading); harmless at current 2-user MVP scale. Logged in deferred-work.md.
  - Rejected as noise/unreachable/out-of-scope-per-spec (not actioned): `Article.relevance_score` None-guard (unreachable — every summarized article has relevance_status=relevant, which always sets a score, matching project convention against defensive coding for impossible states); removal of round-robin topic diversity (faithful to GH #25's literal "select top-5 by final_score" text, which has no diversity term — the removed code was explicitly a placeholder pending this exact story); `interest_weight`/`interestingness_weight` naming (mirrors GH #25's own formula terminology verbatim); `for_date`/`before_date` internal param naming inconsistency (zero consumer-facing consequence); non-deterministic tie-breaking on exact score ties (cosmetic, no real-world harm for a news digest); `digest_max_articles` set to 0/negative (config misuse — no other `Settings` field is validated either); `published_at`+`scraped_at` both `None` (unreachable — `scraped_at` has a DB `server_default`); naive/aware datetime `TypeError` (unreachable — no code path in this repo ever attaches `tzinfo`).

## Design Notes

`topic_affinity` scope: iterate the user's past `Digest` rows with `sent_at is not None` (excluding the in-progress one for `for_date`), join through `DigestArticle`→`Article`→`Source` to get each past digest's distinct topic set, then per topic: `opened_count / seen_count` (both 0 → 0.5). This is the only signal available from the current schema (`Digest.opened_at` is whole-digest, not per-article), matching GH #25's "first real consumer of #13's open-tracking data."

## Verification

**Commands:**
- `python -m pytest tests/pipeline/ -q` -- expected: all pass, including new ranking/cap tests
- `python -m pytest tests/ -q` -- expected: full suite green (no regression in render/digest tests)
- `ruff check src/newsagent/pipeline/ranking.py src/newsagent/pipeline/digest.py src/newsagent/pipeline/render.py` -- expected: no lint errors
