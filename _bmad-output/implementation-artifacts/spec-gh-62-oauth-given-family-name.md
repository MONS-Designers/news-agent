---
title: 'Stop guessing the first name - capture given_name/family_name from Google OAuth'
type: 'bugfix'
created: '2026-08-31'
status: 'done'
review_loop_iteration: 1
context: []
baseline_commit: '0133e3944f4702f1bd92ccbb40124c96ae859fd7'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The greeting derives a reader's first name via `user.name.split()[0]` (`send.py`, `render.py`), which breaks for family-name-first cultures (Hungarian, Japanese, Chinese, Korean) even though OAuth already requests `profile` scope and Google already returns separate `given_name`/`family_name` claims - the code discards them.

**Approach:** Log userinfo keys once (verification), store `given_name`/`family_name` as new nullable `users` columns, populate them only on brand-new-user creation via Google sign-in, and prefer `given_name` for the greeting - falling back to `name.split()[0]` only when `given_name` is absent.

## Boundaries & Constraints

**Always:**
- One new Alembic revision on head `e29c47a1b6d8`, nullable `String` columns, matching `f3b9d2a71c5e_user_unsubscribed_at.py`'s pattern. No `create_all`/hand DDL (AD-4).
- `given_name`/`family_name` populated **only at row creation**, inside `register_user_if_capacity`'s existing atomic INSERT...SELECT...WHERE (never a separate UPDATE) - preserves the FR3 race guarantee.
- An **existing** user re-authenticating is never mutated - `resolve_identity`'s existing-row branch stays read-only (human decision: refresh-on-login is out of scope here).
- First-name derivation (`given_name`, else `name.split()[0]`, else none) lives in one function, used by both `send.py` and `render.py` - not duplicated.
- Log only `userinfo` *keys* (never values), once, in `routers/auth.py`'s callback.
- `dev-login` and CLI-seeded users keep `given_name`/`family_name` as `None`.

**Ask First:** none - open decisions were resolved before planning.

**Never:** Profile-picker/UI change. Backfill of existing rows. Refresh of stored name fields on repeat sign-in. Any change to the already-correct/tested "no name at all -> no greeting" path.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior |
|----------|--------------|---------------------------|
| New sign-up, family-name-first culture | `given_name="Nagy"`, `family_name="János"` | Row stores `given_name="Nagy"`; greeting uses "Nagy" |
| New sign-up, `given_name` absent | userinfo has only `name="Ariel"` | `given_name=None`; greeting falls back to `name.split()[0]` |
| Pre-existing row (predates this change) | `given_name=None`, `name="דנה לוי-כהן"` | Greeting falls back to `name.split()[0]` -> "דנה" (unchanged) |
| Existing user re-authenticates | Row already exists for the email | Row untouched; stored fields unchanged |
| No name at all | `name=None`, `given_name=None` | No greeting anywhere (existing tested behavior, untouched) |

</frozen-after-approval>

## Code Map

- `alembic/versions/<new>.py` -- new revision: `users.given_name`/`family_name`, `down_revision="e29c47a1b6d8"`
- `src/newsagent/models/user.py` -- new columns + shared `first_name(user)` helper
- `src/newsagent/services/identity.py` -- `register_user_if_capacity` gains the two fields in its atomic INSERT
- `src/newsagent/api/auth.py` -- `resolve_identity` gains the two fields, forwarded only to new-user creation
- `src/newsagent/api/routers/auth.py` -- `callback()` logs userinfo keys, extracts and forwards the two fields
- `src/newsagent/pipeline/send.py`, `render.py` -- replace each inline first-name derivation with `models.user.first_name`
- `tests/services/test_identity.py`, `tests/api/test_auth.py`, `tests/pipeline/test_send.py`, `tests/pipeline/test_render.py` -- new/updated coverage

## Tasks & Acceptance

**Execution:**
- [x] `alembic/versions/<new>.py` -- add nullable `given_name`/`family_name` String columns on `users` -- AD-4 schema-change convention
- [x] `src/newsagent/models/user.py` -- add both columns; add `first_name(user: User) -> str | None` exactly as given in Design Notes (strips a string `given_name` before returning it; falls through to `name.split()[0]` if `given_name` isn't a non-empty string; else `None`) -- single source of truth
- [x] `src/newsagent/services/identity.py` -- extend `register_user_if_capacity(db, email, name, cap, given_name=None, family_name=None)`, add both to the existing atomic INSERT -- keeps FR3 atomicity
- [x] `src/newsagent/api/auth.py` -- extend `resolve_identity(..., given_name=None, family_name=None)`; forward only into `register_user_if_capacity`, never into the existing-user branch
- [x] `src/newsagent/api/routers/auth.py` -- in `callback()`, log `sorted(userinfo.keys())`; extract `given_name`/`family_name` and pass to `resolve_identity`
- [x] `src/newsagent/pipeline/send.py`, `render.py` -- replace each's inline first-name logic with `models.user.first_name(user)`
- [x] `tests/pipeline/test_render.py`, `tests/pipeline/test_send.py` -- add given-name-verbatim and given-name-absent-fallback cases; existing tests must keep passing unmodified
- [x] `tests/services/test_identity.py` -- assert both fields land on the row `register_user_if_capacity` creates
- [x] `tests/api/test_auth.py` -- assert `resolve_identity` forwards both fields for a new row, never for an existing one
- [x] `tests/models/test_user.py` (new file, or add to an existing model test file if this repo already has one) -- unit-test `first_name()` directly for the two review-found edge cases: a whitespace-padded `given_name` (e.g. `" Nagy "`) returns the stripped value with no stray whitespace, and a non-string `given_name` (e.g. `123`) falls through to the `name.split()[0]` branch instead of raising

**Acceptance Criteria:**
- Given a new Google sign-in with `given_name="Nagy"`, when the digest is sent, then the greeting uses "Nagy".
- Given a pre-existing row (`given_name=None`, `name` set), when the digest is sent, then the greeting still uses `name.split()[0]`.
- Given an existing user signs in again, when `callback()` runs, then their stored name fields are unchanged.
- Given two callers race `register_user_if_capacity` at the cap boundary, then exactly one still succeeds (FR3 unaffected).

## Spec Change Log

- **Finding (review_loop_iteration 1, bad_spec):** Two independent review passes (adversarial + edge-case) on the first implementation both caught the same defect in the `first_name()` example this Design Notes section shipped: `if user.given_name and user.given_name.strip(): return user.given_name` checks the *stripped* string for truthiness but returns the *unstripped* value, so a `given_name` with surrounding whitespace (e.g. `" Nagy "`) leaks stray whitespace into the rendered greeting/subject. The edge-case pass also noted nothing guards against `given_name` being a non-string value (a malformed OAuth claim), which would raise `AttributeError` from `.strip()` at digest-send time - far from where the value was ingested.
- **Amended:** The target helper below now (a) strips before returning, and (b) checks `isinstance(..., str)` before calling `.strip()` on either field, so a non-string claim falls through to the `name.split()[0]` branch instead of crashing.
- **Known-bad state avoided:** Stray leading/trailing whitespace baked into a live greeting/subject line; an unhandled `AttributeError` during digest send for one user if a future/non-Google claim value is ever not a string.
- **KEEP:** Everything else from the first pass was verified correct by 65/65 + 628/628 passing tests and two independent review agents finding no other real defect - preserve unchanged: the atomic-INSERT extension in `register_user_if_capacity`, `resolve_identity` forwarding `given_name`/`family_name` only into new-row creation (never the existing-user branch), the single shared `first_name()` living in `models/user.py`, the migration's shape (nullable columns chained off `e29c47a1b6d8`), and the `given_name` → `name.split()[0]` → `None` fallback order. Only the helper's body changes.
- **Round 2 (review_loop_iteration 1, patch):** `first_name()` confirmed fixed by both review passes (71/71 + 634/634 passing). Two small patches applied directly (no further revert needed): (1) `routers/auth.py` now coerces a non-string `given_name`/`family_name` claim to `None` at extraction time, symmetric with `first_name()`'s read-side guard, so a malformed OAuth claim can never reach the raw SQL `INSERT`; (2) the `models/user.py` column comment was tightened - it previously implied `family_name` participates in the greeting, but only `given_name` does. Two out-of-scope gaps found by both reviewers independently (waitlist entries never capture given_name/family_name; the OAuth callback's extraction lines have no router-level test) were logged to `deferred-work.md` rather than actioned - both require scope beyond this issue's approved Intent.

## Design Notes

`send.py`/`render.py` duplicate the same first-name logic inline - the reason this bug needed fixing twice. One `first_name(user)` in `models/user.py` removes that risk:

```python
def first_name(user: User) -> str | None:
    if isinstance(user.given_name, str) and user.given_name.strip():
        return user.given_name.strip()
    if user.name and user.name.strip():
        return user.name.split()[0]
    return None
```

## Verification

**Commands:**
- `alembic upgrade head` -- migration applies cleanly, no manual DDL
- `pytest tests/services/test_identity.py tests/api/test_auth.py tests/api/routers/test_auth.py tests/pipeline/test_send.py tests/pipeline/test_render.py` -- all pass
- `pytest` -- full suite still green

## Suggested Review Order

**The fix itself**

- Entry point: given_name wins for the greeting, else the old `name.split()[0]` guess, else no greeting - now the one place this decision is made.
  [`user.py:105`](../../src/newsagent/models/user.py#L105)

- Both string checks use `isinstance(..., str)` before `.strip()`, and the *stripped* value is what's returned - fixes a whitespace/type bug two review passes caught in the pre-fix version.
  [`user.py:106`](../../src/newsagent/models/user.py#L106)

**Capturing the claims at the OAuth boundary**

- `given_name`/`family_name` extracted from Google's userinfo, each coerced to `None` if not a string before they can reach storage.
  [`routers/auth.py:77`](../../src/newsagent/api/routers/auth.py#L77)

- Keys-only logging (never values) to verify live what Google actually returns for this scope - the issue's own unresolved "not yet verified" gap.
  [`routers/auth.py:70`](../../src/newsagent/api/routers/auth.py#L70)

- Forwarded into `resolve_identity` alongside the existing `name`.
  [`routers/auth.py:83`](../../src/newsagent/api/routers/auth.py#L83)

**Storage: new-row-only, atomic**

- `resolve_identity` forwards the two fields only into new-user creation - the existing-row branch above this line is untouched, by design.
  [`auth.py:60`](../../src/newsagent/api/auth.py#L60)

- The two fields ride the same atomic `INSERT...SELECT...WHERE` as `email`/`name`, preserving the race-free registration-cap guarantee (FR3).
  [`identity.py:62`](../../src/newsagent/services/identity.py#L62)

**Consumers: where the greeting actually renders**

- Digest subject line now asks the shared helper instead of guessing inline.
  [`send.py:44`](../../src/newsagent/pipeline/send.py#L44)

- Welcome-email greeting, same helper - this is the second of the two places that used to duplicate the buggy logic.
  [`render.py:192`](../../src/newsagent/pipeline/render.py#L192)

**Schema and peripherals**

- New Alembic revision, nullable columns chained off the real current head.
  [`b7e4a1c9d3f2_user_given_family_name.py:19`](../../alembic/versions/b7e4a1c9d3f2_user_given_family_name.py#L19)

- Direct unit coverage of `first_name()`'s edge cases (whitespace, non-string, absent, no-name-at-all).
  [`test_user.py:1`](../../tests/models/test_user.py#L1)
