---
baseline_commit: 1d4de7b
---

# Story 2.1: View pending taxonomy suggestions

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an admin,
I want to see all pending Field/Role "Other" submissions grouped by normalized text with counts,
so that I can tell which ones real users actually need without duplicate noise.

*Realizes FR6 ([PRD](../planning-artifacts/prds/prd-news-agent-2026-07-21/prd.md) §4.2 FR-6).*

**This is the first story of Epic 2.** Epic 1 (Stories 1.1–1.7) already shipped the entire data layer this story reads — `pending_taxonomy_suggestions` rows are being written today by `services/taxonomy.py:record_pending_suggestion` whenever a user submits an "Other" Field or Role in the guided picker. **This story adds no tables, no columns, and no migration** — only a read path (service function → schema → router → admin UI). Story 2.2 adds promote/dismiss on top of it.

## Acceptance Criteria

1. **Given** there are rows in `pending_taxonomy_suggestions` with `status='pending'`, **when** I view the admin Taxonomy Curation Queue (`GET` endpoint on a new `admin_taxonomy.py` router, `require_admin`), **then** I see each pending suggestion with its kind (`field`/`role`), associated Field name (for role-kind rows), submission text, and `submission_count`.
2. **Given** multiple identical `(kind, field_id, normalized_text)` submissions were made, **when** I view the queue, **then** they appear as one row with the incremented `submission_count` (per AD-8), never as separate rows.
3. **Given** no pending submissions exist, **when** I view the queue, **then** I see an empty state consistent with the existing admin panel's conventions (`AdminView.vue`'s look, not Hybrid Depth — this surface is explicitly out of that visual spine per EXPERIENCE.md).
4. **Given** I am not an admin, **when** I try to access this endpoint or view, **then** I am denied, via the same `require_admin` dependency the existing `admin.py` source-approval router already uses.

## Tasks / Subtasks

- [x] Task 1: `services/taxonomy.py` — the read function (AC: #1, #2)
  - [x] 1.1 Add a `@dataclass(frozen=True) PendingSuggestionView` with exactly these fields: `id: int`, `kind: str`, `field_name: str | None`, `text: str`, `submission_count: int`. Mirrors `preferences.TopicChoice`'s role — the plain-data unit the router renders, so the router never touches `models/` (AD-1).
  - [x] 1.2 Add `list_pending_suggestions(db: Session) -> list[PendingSuggestionView]`. Select `PendingTaxonomySuggestion` where `status == STATUS_PENDING`. **No `GROUP BY`** — AD-8 already guarantees one row per unique `(kind, field_id, normalized_text)` among pending rows; re-aggregating at read time is the exact anti-pattern AD-8 exists to prevent.
  - [x] 1.3 `text` = `row.raw_text or row.normalized_text`. `raw_text` is `nullable=True` (rows predating that column have none) and `normalized_text` is casefolded — rendering `normalized_text` unconditionally would show every submission lowercased. Read the model's comment at [`models/pending_taxonomy_suggestion.py:60-64`](../../src/newsagent/models/pending_taxonomy_suggestion.py) before writing this.
  - [x] 1.4 `field_name` = the related `Field.name` for `kind='role'` rows, `None` for `kind='field'` rows (which always carry `field_id=NULL`). The model already declares `field: Mapped["Field | None"] = relationship()` — use it; do not hand-roll a join or a second query per row. Use `selectinload(PendingTaxonomySuggestion.field)` on the select to avoid N+1.
  - [x] 1.5 Order by `submission_count` descending, then `created_at` ascending (oldest first as tiebreak). AD-8 calls `submission_count` "the demand signal Epic 2 ranks by" — the most-requested suggestion must be the admin's first row, deterministically.

- [x] Task 2: `api/schemas/taxonomy.py` — response schema (AC: #1)
  - [x] 2.1 Add `PendingTaxonomySuggestionOut(BaseModel)` with `model_config = ConfigDict(from_attributes=True)` and fields `id: int`, `kind: str`, `field_name: str | None`, `text: str`, `submission_count: int` — one-to-one with `PendingSuggestionView`, same shape as `TopicPreferenceOut` mirrors `TopicChoice`.
  - [x] 2.2 Export it from `api/schemas/__init__.py` (add to both the import block and `__all__`, which is alphabetically sorted).

- [x] Task 3: `api/routers/admin_taxonomy.py` — new router file (AC: #1, #4)
  - [x] 3.1 New file. Copy `admin.py`'s exact shape: `router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])`. **Do not extend `admin.py`** (AD-10) and **do not touch `admin.py`** at all.
  - [x] 3.2 `@router.get("/taxonomy", response_model=list[PendingTaxonomySuggestionOut])` → `return taxonomy.list_pending_suggestions(db)`. Thin — validate + delegate only, no filtering or shaping in the router (AD-1).
  - [x] 3.3 Register in `api/main.py`: add `admin_taxonomy` to the `from newsagent.api.routers import ...` line and `app.include_router(admin_taxonomy.router)` after `admin.router`. **Easy to forget — without it the endpoint 404s and every test in Task 6.2 fails confusingly.**

- [x] Task 4: Frontend — `client.ts` additions (AC: #1)
  - [x] 4.1 `export interface PendingTaxonomySuggestion { id: number; kind: string; field_name: string | null; text: string; submission_count: number; }` — snake_case keys, matching the wire format of every other interface in this file.
  - [x] 4.2 `export async function listPendingTaxonomySuggestions(): Promise<PendingTaxonomySuggestion[]> { return request("/admin/taxonomy"); }` — placed near `listPendingSources`.

- [x] Task 5: Frontend — `TaxonomyQueueView.vue` + routing (AC: #1, #2, #3, #4)
  - [x] 5.1 New file `frontend/src/views/TaxonomyQueueView.vue`. **Structurally a copy of `AdminView.vue`** — same Tailwind classes, same header/refresh-button/loading/error/list/empty-state blocks, same `ApiError` 401/403/other message branching, same `onMounted(load)`. Reuse, do not reinvent. **Read-only in this story: no Approve/Reject buttons** — promote/dismiss is Story 2.2.
  - [x] 5.2 Per row show: the submission `text` (primary line), a kind badge (`field` / `role`), the `field_name` as secondary context on role rows only, and the `submission_count` (e.g. "3 submissions" / "1 submission"). Use `AdminView.vue`'s existing badge class (`rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700`) for the kind badge rather than inventing a new pill style.
  - [x] 5.3 Empty state: reuse `AdminView.vue`'s dashed-border block verbatim, copy `No pending taxonomy suggestions.` Header copy: `Taxonomy queue` / `Review "Other" field and role submissions from users.` Plain complete sentences, no emoji or exclamation marks (EXPERIENCE.md Voice/Tone).
  - [x] 5.4 `router/index.ts`: add `{ path: "/admin/taxonomy", name: "TaxonomyQueue", component: TaxonomyQueueView, meta: { requiresAdmin: true } }`. `meta.requiresAdmin` is what drives the existing `beforeEach` guard that redirects non-admins to `/preferences` — omitting it silently leaves the view reachable by any signed-in user (AC #4).
  - [x] 5.5 `App.vue`: add a `Taxonomy` nav `router-link` to `/admin/taxonomy` beside the existing `Admin` link, inside the same `v-if="me?.is_admin"` gating, copying the link's class list exactly. **Then change the existing `Admin` link's `active-class` to `exact-active-class`:** vue-router 4's `active-class` matches inclusively, so `/admin` would stay highlighted while the user is on `/admin/taxonomy`, showing two active nav items at once. `exact-active-class` on `Admin` fixes it; the new `Taxonomy` link keeps plain `active-class` (its path has no children).

- [x] Task 6: Tests (AC: all)
  - [x] 6.1 `tests/services/test_taxonomy.py` (extend, do not create): `list_pending_suggestions` returns `[]` on an empty DB; a `kind='field'` row yields `field_name is None`; a `kind='role'` row yields its Field's name; `approved`/`rejected` rows are excluded; two `record_pending_suggestion` calls with case/whitespace variants of the same text yield **one** view with `submission_count == 2` (AC #2); rows are ordered by `submission_count` desc; a row with `raw_text=None` falls back to `normalized_text` for `text`.
  - [x] 6.2 New `tests/api/routers/test_admin_taxonomy.py`: unauthenticated → 401; `as_user` → 403; `as_admin` on empty DB → 200 `[]`; `as_admin` with seeded pending rows → 200 with the expected JSON shape and ordering. **Copy `tests/api/routers/test_admin.py`'s local `db_session` + `client` fixture pattern verbatim** — that file defines its own `db_session`/`client` fixtures overriding `get_db`, and the shared `as_admin`/`as_user` fixtures in `tests/api/conftest.py` compose with them.
  - [x] 6.3 `npm run type-check` (vue-tsc) clean; `mypy` and `ruff` clean; full pytest suite green with no regressions against the 223-test baseline.

- [x] Task 7: Live browser verification (AC: #1, #2, #3, #4)
  - [x] 7.1 Verify against the real dev DB with an authenticated admin session: seed a couple of pending rows (one `field`-kind, one `role`-kind, one of them submitted twice so `submission_count == 2`), then confirm the queue renders them correctly, the counts are grouped, and the empty state shows when they are removed.
  - [x] 7.2 Confirm a non-admin session cannot reach `/admin/taxonomy` (router guard redirects to `/preferences`) and that the API returns 403 directly.
  - [x] 7.3 Clean up any rows added purely for verification.

## Dev Notes

### Read these before writing code

- [`src/newsagent/services/taxonomy.py`](../../src/newsagent/services/taxonomy.py) — **the file you extend.** `record_pending_suggestion` (writer side, already shipped) and `normalize_taxonomy_text` explain exactly what `normalized_text` contains and why `raw_text` exists. `list_fields`/`list_roles` show the house style for read functions.
- [`src/newsagent/models/pending_taxonomy_suggestion.py`](../../src/newsagent/models/pending_taxonomy_suggestion.py) — the full model, including the partial unique index that makes the no-`GROUP BY` decision safe, and the `raw_text` nullability comment.
- [`src/newsagent/api/routers/admin.py`](../../src/newsagent/api/routers/admin.py) — 27 lines; the template for the new router's shape, `require_admin` wiring, and `response_model` usage.
- [`src/newsagent/services/preferences.py`](../../src/newsagent/services/preferences.py) `TopicChoice` + `list_topic_choices` — the frozen-dataclass-view precedent `PendingSuggestionView` follows.
- [`frontend/src/views/AdminView.vue`](../../frontend/src/views/AdminView.vue) — 121 lines; the visual and behavioural template for `TaxonomyQueueView.vue`. Copy its structure rather than writing a new one.
- [`tests/api/routers/test_admin.py`](../../tests/api/routers/test_admin.py) — the auth-matrix test pattern (401 / 403 / 200) to mirror.

### Architecture compliance ([ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-news-agent-2026-07-22/ARCHITECTURE-SPINE.md))

- **AD-10** — `admin_taxonomy.py` is a separate router file under the same `/admin` prefix. `admin.py` stays untouched.
- **AD-8** — one pending row per `(kind, field_id, normalized_text)` is a *write-side* invariant already enforced by `record_pending_suggestion` plus the partial unique index. The read path trusts it: no `GROUP BY`, no re-normalization, no client-side merging.
- **AD-2** — filter on the plain string `status == STATUS_PENDING` (import the constant from `models/pending_taxonomy_suggestion`, never a literal `"pending"` in the service).
- **AD-1** — the router validates and delegates; the service returns plain dataclasses. No model instance crosses the router boundary.
- **Consistency Conventions → naming** — endpoint is `GET /admin/taxonomy`, matching the spine's stated `GET`/`PATCH /admin/taxonomy/{id}` pattern (the `{id}` form lands in Story 2.2). Admin endpoints keep using `require_admin`.
- **Consistency Conventions → Frontend controls** does not bite here: this surface has no chips or pills-as-controls, only a static list and real `<button>` elements for refresh.

### UX compliance

- This surface is **explicitly out of the Hybrid Depth visual spine** ([EXPERIENCE.md](../planning-artifacts/ux-designs/ux-news-agent-2026-07-21/EXPERIENCE.md) Information Architecture, and epics UX-DR16). Do **not** import anything from `components/profile-picker/`, do not reuse its dark background, orbs, animations, or tokens. It follows `AdminView.vue`'s light Tailwind conventions.
- It is a separate surface reached from admin nav, not a section appended to the source-approval page (EXPERIENCE.md: "Admin Taxonomy Curation Queue | Admin nav (separate role)").

### Explicit scope boundary — do NOT build

- **No promote/dismiss** — no `PATCH` endpoint, no `set_suggestion_status` service function, no Approve/Reject buttons. That is Story 2.2 in full.
- **No migration and no schema change.** If you find yourself writing an Alembic revision, stop — you have misread the story. Every table and column this story reads shipped in Stories 1.1/1.2.
- **No changes to the writer side** (`record_pending_suggestion`, `save_profile`) and no changes to `admin.py`.
- **No pagination, search, or filtering** of the queue — the dogfood dataset is two users.
- **No retroactive migration** of users whose free text later gets promoted (a Story 2.2 / PRD-level non-goal, listed here so it isn't "helpfully" added).
- **No frontend unit tests** — this project has no frontend test runner (established across Stories 1.1–1.7).

### Previous story intelligence (Stories 1.1–1.7)

- **Live browser verification is not skippable.** Story 1.7's two real bugs (a fetch firing at page load instead of step entry, and a refresh path that reset the whole flow) were invisible to `vue-tsc` and the backend suite, and were caught only in the browser. This story's frontend surface is far simpler, but Task 7 still stands.
- **Dev-environment gotchas that cost time in Stories 1.3/1.4/1.7, likely to recur:** the editable install can resolve to a stale worktree (`pip show newsagent`), so run backend commands with `PYTHONPATH=src` set explicitly; and the local dev DB may be behind on migrations — this story adds none, but Epic 1's must all be applied for `pending_taxonomy_suggestions` to exist at all. **Applying a migration to the dev DB requires explicit user approval before running it.**
- **Authentication for live verification** has been done in prior stories by minting a local session cookie for a seeded user. This story needs an **admin** identity specifically (`admins` table / `require_admin`), which prior stories did not exercise — expect this to need a step the earlier stories' recipe does not cover.
- Established fixture pattern: API router tests define their own in-memory `db_session` and override `get_db`; `as_admin`/`as_user` come from `tests/api/conftest.py`.

### Project Structure Notes

- New backend files: `src/newsagent/api/routers/admin_taxonomy.py`, `tests/api/routers/test_admin_taxonomy.py`.
- Changed backend files: `src/newsagent/services/taxonomy.py`, `src/newsagent/api/schemas/taxonomy.py`, `src/newsagent/api/schemas/__init__.py`, `src/newsagent/api/main.py`, `tests/services/test_taxonomy.py`.
- New frontend file: `frontend/src/views/TaxonomyQueueView.vue`.
- Changed frontend files: `frontend/src/api/client.ts`, `frontend/src/router/index.ts`, `frontend/src/App.vue`.
- No migration. No new dependencies (spine Stack section: this feature adds none).

### References

- [Source: epics.md#Story-2.1] — acceptance criteria, verbatim.
- [Source: prd.md#4.2-FR-6] — "submission text, associated Field (for Role submissions), and count of users who submitted the same normalized text"; grouping consequence.
- [Source: ARCHITECTURE-SPINE.md#AD-1, #AD-2, #AD-8, #AD-10, #Consistency-Conventions, #Traceability FR-6 row].
- [Source: EXPERIENCE.md#Information-Architecture] — admin queue is a separate admin-nav surface, styled per the existing admin panel, explicitly not Hybrid Depth.
- [Source: epics.md#UX-DR16].
- [Source: 1-7-review-swap-confirm-topics-step-3.md#Debug-Log-References] — live-verification and dev-environment learnings carried forward.

## Dev Agent Record

### Agent Model Used

Claude Opus 5

### Debug Log References

- Confirmed no migration needed: the dev DB already sits at `e5f6a7b8c9d0` (Story 1.6's revision) and `pending_taxonomy_suggestions` already held 4 real rows written by earlier stories' live verification. No schema work of any kind in this story.
- **Real-data finding not anticipated by the plan.** The dev DB contains a `kind='role'` row with `field_id=NULL` ("Reef Survey Lead") — a Role submitted as "Other" underneath a Field that was itself uncurated "Other" text, so there is no `field_id` to attach. Task 5.2's plan assumed `field_name is None` implied a field-kind row, which would have labelled that row "New field" in the queue. Fixed with a `context()` helper: field-kind rows read "New field", role rows with a Field read "Under {name}", and role rows without one read "Field not curated". The backend needed no change — `field_name: str | None` already modelled it correctly.
- Verification environment: `PYTHONPATH=src` set explicitly for every backend command (the editable install still resolves to a stale worktree, per Story 1.1's deferred-work note). The backend was restarted for this story so the new router would be registered; the Vite dev server already running on 5173 was reused via HMR and deliberately left untouched.
- Authenticated by minting a session cookie locally with `itsdangerous.TimestampSigner` and `settings.session_secret`, then setting it via `document.cookie`. This story is the first to need an **admin** identity (`nomimagnus@gmail.com`, the sole row in `admins`); prior stories only ever minted plain-user cookies.
- **Out-of-scope issue found and fixed on the user's instruction, in the same session but conceptually separate from this story:** CI had been red since Story 1.4. Cause was not the code — `ruff` was unpinned in `requirements-dev.txt`, CI installed `ruff 0.16.0`, and that release widened ruff's *default* rule selection (adding `B`, `I`, `UP`, `RUF`), producing 38 errors across 17 pre-existing untouched files (19 of them `B008` on FastAPI's own `Depends()` idiom). Fixed by pinning `ruff==0.15.22` and declaring `[tool.ruff.lint] select = ["E4","E7","E9","F"]` explicitly — the set the project had always enforced. Those two files are listed separately below.

### Completion Notes List

**All 7 tasks complete.** 233 backend tests pass (10 added on top of the 223 baseline); `mypy` (63 files), `ruff check`, and `vue-tsc` all clean. No migration, no new dependencies, no changes to `admin.py` or to the writer side.

Per acceptance criterion, live-verified in the browser against the real dev DB with an authenticated admin session:

- **AC #1** — the queue renders all four real pending rows with kind badge, resolved Field name, submission text and count. "Clinical Data Lead" correctly shows "Under Healthcare" (relationship resolved via `selectinload`, no N+1). Hebrew submission text renders correctly.
- **AC #2** — "marine biology" appears as a single row reading "2 submissions", not two rows: the two case/whitespace variants submitted in an earlier story were merged at write time by AD-8's upsert, and the read path reports that count without re-aggregating. Singular/plural wording is correct ("1 submission" vs "2 submissions").
- Ranking verified: the count-2 row sorts above the count-1 rows.
- The `raw_text or normalized_text` fallback verified on real data — "marine biology" is a pre-`raw_text` row and still renders readably rather than blank.
- **AC #3** — the empty state ("No pending taxonomy suggestions.") renders in `AdminView.vue`'s dashed-border style. Exercised by stubbing `window.fetch` to return `[]` for that one endpoint rather than deleting real queue rows, then restoring it.
- **AC #4** — verified both layers with a non-admin session cookie: `GET /api/admin/taxonomy` returns **403**, and navigating to `/admin/taxonomy` redirects to `/preferences` with both admin nav links hidden. With the admin cookie, the endpoint returns 200.
- Nav highlighting verified in both directions after the `exact-active-class` change: on `/admin/taxonomy` only "Taxonomy" is active; on `/admin` only "Admin" is. Without that change both would have lit up at once.
- No browser console errors and no server errors in the backend log throughout.

No test data was added or removed — verification ran entirely against rows that already existed, so there was nothing to clean up.

### File List

**New**
- `src/newsagent/api/routers/admin_taxonomy.py`
- `tests/api/routers/test_admin_taxonomy.py`
- `frontend/src/views/TaxonomyQueueView.vue`

**Modified**
- `src/newsagent/services/taxonomy.py`
- `src/newsagent/api/schemas/taxonomy.py`
- `src/newsagent/api/schemas/__init__.py`
- `src/newsagent/api/main.py`
- `tests/services/test_taxonomy.py`
- `frontend/src/api/client.ts`
- `frontend/src/router/index.ts`
- `frontend/src/App.vue`

**Modified — CI repair, separate concern from this story (see Debug Log)**
- `pyproject.toml`
- `requirements-dev.txt`

## Change Log

- 2026-07-27 — Story 2.1 implemented: admin Taxonomy Curation Queue read path (`GET /admin/taxonomy`, `services/taxonomy.py:list_pending_suggestions`, `TaxonomyQueueView.vue` at `/admin/taxonomy`). 10 tests added. No schema change.
- 2026-07-27 — CI repaired independently of this story: `ruff` pinned and its rule selection declared explicitly, after `ruff 0.16.0`'s widened defaults turned an unrelated linter release into a red build.
