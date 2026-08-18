# Rubric Review - ARCHITECTURE-SPINE.md (Profile-Based Topic Suggestions)

Reviewed: `_bmad-output/planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md`
Against: `.memlog.md` (same dir), PRD (`prd-news-agent-2026-07-21/prd.md` + `addendum.md`), and the real brownfield source
(`src/newsagent/models/*.py`, `services/*.py`, `api/routers/*.py`, `llm/*.py`, `config.py`, `db.py`, plus `alembic/`, `requirements.txt`, `frontend/package.json`).

**Verdict: PASS-WITH-FIXES.** The spine is well-constructed against the memlog it was distilled from and correctly ratifies most of the brownfield codebase (thin-router/service layering, plain-string status columns, get-or-create idempotency, Vue3+Tailwind stack, Pydantic v2/FastAPI BackgroundTask availability). But it contains one factually wrong claim about the brownfield codebase (AD-4, on Alembic) that is severe enough to mis-direct implementers on every new table this feature adds, plus a couple of narrower gaps. None of these require re-deriving the spine from scratch; they're targeted fixes.

---

## Critical

### 1. AD-4 is factually wrong about the brownfield codebase - Alembic is wired in and is the established migration path (checklist #4, #5, #7)

AD-4 states: *"this spine does not prescribe a migration mechanism. Alembic is an installed-but-unwired dependency; schema setup today is `create_all`-style."* The Deferred section repeats this: *"Alembic is installed but unwired; how these new tables/columns actually get applied to a running DB is an open question, not silently assumed as 'just `create_all`.'"*

This is incorrect. Verified against the repo:

- `alembic.ini` exists at repo root, `script_location = %(here)s/alembic`.
- `alembic/env.py` imports `newsagent.models.Base` and sets `target_metadata = Base.metadata` - fully wired to the real ORM models, not a stub.
- `alembic/versions/` contains **8 real migrations**, tracking the project's actual schema history end to end: `7de791f6b76c_initial_schema.py` through `d1a2b3c4d5e6_article_image_url.py` (the latter dated 2026-07-21, four days before this spine, matching commit `95d5488 #24: Article images`).
- `alembic==1.18.5` is pinned in `requirements.txt`.
- `grep -rn "create_all" src/` returns **zero hits** - nothing in the codebase actually uses `create_all`-style setup.

So every prior schema change in this project's history - including the most recent one - went through an Alembic migration, not `create_all`. There is no open question here: the established, already-load-bearing convention is "add an Alembic revision alongside your model change," exactly like every prior feature did it.

**Why this matters at this altitude:** this feature adds 4+ new tables/columns (`fields`, `roles`, `pending_taxonomy_suggestions`, five new `User` columns) - precisely the kind of change AD-4 itself says is at risk of two people diverging on. By misdescribing the tooling as "unwired" and pushing it to Deferred as an unresolved question, the spine creates exactly the divergence risk it warns about: one builder might (correctly) write Alembic migrations per the established convention, another might read AD-4 literally and hand-roll `ALTER TABLE` or lean on some `create_all` path that doesn't actually exist in this codebase. This should be an ADOPTED AD (e.g. "every new table/column ships as an Alembic revision under `alembic/versions/`, generated the same way as the prior 8"), not a Deferred open question - the checklist's own criterion #3 flags exactly this pattern ("if something IS a real divergence risk, it shouldn't be Deferred, it should be an AD").

**Fix:** Replace AD-4 with an AD stating Alembic is the existing, wired migration mechanism (cite `alembic/env.py`'s `target_metadata = Base.metadata` and the 8 existing revisions) and that this feature's schema changes follow the same convention. Remove the corresponding Deferred bullet - there is nothing open here.

---

## High

### 2. AD-8's dedup mechanism omits the DB-level uniqueness guarantee every other get-or-create idiom in this codebase relies on (checklist #2, #3)

AD-8 says `PendingTaxonomySuggestion` is "upserted" per unique `(kind, field_id, normalized_text)`, explicitly citing `add_topic`/`add_source` in `services/sources.py` as the precedent. But every existing natural-key get-or-create in the codebase backs its uniqueness with a **DB-level `unique=True` constraint**, not just application-level check-then-insert:

- `Topic.name` - `unique=True, index=True`
- `Source.url` - `unique=True`
- `User.email` / `Admin.email` - `unique=True, index=True`

Neither AD-8's Rule nor the `PENDING_TAXONOMY_SUGGESTION` entity in the ER diagram mentions a compound unique constraint/index on `(kind, field_id, normalized_text)`. Without one, "upserted" is only as safe as the service's check-then-insert logic under concurrent submissions (two users hitting "Other" with the same text at the same moment) - a real race the existing pattern closes with a DB constraint that this Rule doesn't require. Two independently-built implementations could diverge exactly here: one adds the compound unique index (matching the actual codebase convention), the other doesn't and gets occasional duplicate rows.

**Fix:** Add to AD-8's Rule (and the structural seed / ERD) that `pending_taxonomy_suggestions` carries a compound unique constraint on `(kind, field_id, normalized_text)`, matching the DB-level-constraint convention every other get-or-create table in this codebase already uses.

### 3. Popularity fallback's data source isn't specified, and the dependency diagram implicitly forbids the only way to supply it (checklist #1, #2)

AD-3 requires `suggestions/` to mirror `llm/`'s exact shape: a **pure** provider taking typed dataclass inputs, no DB access of its own (this is how `llm/base.py`/`llm/mock.py` actually work - providers never touch `Session` or models directly; callers pass in plain data). The dependency-direction diagram reinforces this: there is no edge from `suggestions` to `models`.

But FR-9's fallback is "Topics that interest most users" - i.e., aggregate popularity computed from `UserTopicPreference` rows across all users. The `SuggestionSource` interface in the addendum (`suggest_topics(field, role, interest_text) -> [topic_id]`) has no parameter carrying that aggregate data, and no AD says who computes it or how it reaches `PopularitySuggestionSource`. This leaves a real fork for the level below: one builder might have `popularity.py` import `Session`/models directly (breaking AD-3's stated purity and the diagram's own "no cross-import" shape), another might expect `services/profile.py` to precompute popularity counts and thread them through the call - a different function signature than the addendum's interface. This is exactly the kind of "real divergence point" checklist #1 asks to be fixed and isn't.

**Fix:** State explicitly (as part of AD-3 or a new AD) whether the popularity aggregate is computed by a service and passed as a typed argument (keeping providers pure, consistent with `llm/`), or whether `suggestions/` is allowed a narrow, documented exception to reach the DB for this one adapter.

---

## Medium

### 4. Operational/deployment envelope for schema rollout is only reachable through the wrong AD (checklist #7)

Checklist item 7 asks whether the operational/environmental envelope (deployment, rollout, ops concerns) is addressed or explicitly deferred. It technically is addressed - via AD-4 - but since AD-4 is factually wrong (finding #1), the rollout story for this feature's schema changes is currently "an unresolved open question" when it should be a trivial, already-established answer ("write Alembic revisions, run `alembic upgrade head` before deploying the new API code," same as every prior feature). This is a direct downstream consequence of finding #1, not a separate defect - flagged here only so it's tracked as resolved once AD-4 is fixed, not left as a residual gap.

---

## Low

### 5. Minor: "installed-but-unwired" framing appears twice (AD-4 body and Deferred) - both need the same correction

Both the AD-4 rule text and the corresponding Deferred bullet repeat the "Alembic installed but unwired" claim. When fixing finding #1, both locations need updating - a partial fix (correcting only the AD-4 rule but leaving the Deferred bullet, or vice versa) would leave the document internally inconsistent again.

---

## What checked out (no action needed)

- **AD-1** (thin-router/service layering) - verified accurate against `api/routers/me.py`, `api/routers/admin.py`, `services/preferences.py`: routers take `Session` + schema, delegate to services, translate `ValueError` → `HTTPException(400)`. Enforceable, matches reality.
- **AD-2** (plain-string review-queue status) - verified against `models/source.py` (`STATUS_PENDING`/`STATUS_APPROVED`/`STATUS_REJECTED` as bare string constants, no enum/constraint). Accurate.
- **AD-6/AD-7** (flat columns on `User`) - verified against `models/user.py`; consistent with the existing model's shape (simple columns + relationships, no separate profile table anywhere in the codebase).
- **AD-9** (cap enforced in `set_preferences`) - verified `services/preferences.py:set_preferences` is genuinely the single existing mutation point for `UserTopicPreference`; both current callers (`me.py`'s PUT) go through it. Correctly identified as the one place to add the cap.
- **AD-10** (separate `admin_taxonomy.py`) - verified against `api/routers/admin.py`'s existing shape (`require_admin` dependency, `GET` + `PATCH` under `/admin` prefix); the proposed new router matches this exactly.
- **Stack claims** - Vue 3.5.11 + Tailwind 4.3.3 + no component library (verified in `frontend/package.json`); Pydantic v2 via `pydantic-settings==2.14.2`; FastAPI `0.139.2` (BackgroundTask has existed in FastAPI for years, no staleness concern). No version claims are stale or fabricated, aside from the Alembic mischaracterization in finding #1 (which is about wiring, not version).
- **Capability → Architecture Map** - all 10 FRs (FR-1 through FR-10) are present and each maps to a plausible AD/location. No FR silently missing.
- **AD-3 naming/factory shape** - verified `llm/base.py` (ABC + template-method retry), `llm/factory.py` (dict-keyed-by-settings-string), `llm/types.py` (frozen dataclasses) are real and match the spine's description; mirroring them for `suggestions/` is a sound, low-risk call (modulo finding #3's narrower gap).
- **No existing `Field`/`Role` model naming collision** - checked `models/__init__.py`; no pre-existing entities with these names.
