# Test Automation Summary

## Pre-existing coverage found (not generated this run)

Both frontend and backend already had comprehensive test coverage before this run:

- **Frontend unit/component tests** (Vitest + `@vue/test-utils`, commit `d5bfcf7`): all 11 `.vue`
  files, 127 tests.
- **Backend API tests** (pytest): one file per router - `admin`, `admin_engagement`,
  `admin_taxonomy`, `auth`, `me`, `tracking` - 93 tests.

Neither exercises a real browser against a real running app, so this run added true end-to-end
coverage on top.

## Fixed: non-hermetic backend test suite

Found 3 failing backend tests (`test_get_roles_is_scoped_to_the_field`,
`test_get_roles_includes_is_curated_flag`, `test_prompt_suggestions_with_popularity_provider_is_empty`)
and, once investigated, 3 more with the same root cause
(`test_default_provider_is_mock`, `test_default_sender_is_console`, `test_default_provider_is_popularity`).
Root cause: the local `.env` overrides `NEWSAGENT_SUGGESTION_PROVIDER`/`NEWSAGENT_LLM_PROVIDER` for
manual QA, and the suite had no isolation from it - results depended on whose machine ran them, not
on the code. Fixed with an autouse fixture in [tests/conftest.py](../../../tests/conftest.py) that
resets `newsagent.config.settings` to its code-defined defaults before every test. No application
code changed. All 528 backend tests pass.

## Generated Tests

### E2E Tests (Playwright, new)

Real browser tests against a real, isolated instance of the app (own sqlite DB, own throwaway
session secret, own ports 5183/8010 - never touches the shared dev DB/ports). Google OAuth is
bypassed by planting the same signed session cookie the real callback would set
([scripts/e2e_setup.py](../../../scripts/e2e_setup.py)), since a real third-party login can't be
automated here.

- [x] `frontend/e2e/profile-picker.spec.ts` - a brand-new user completes onboarding (Field → Role →
      Experience → Interests → Topics), reaches the home page, and the saved profile persists on
      reload.
- [x] `frontend/e2e/preferences.spec.ts` - a returning user with a profile pauses and resumes their
      weekly digest subscription; state persists across a page reload.
- [x] `frontend/e2e/admin-taxonomy.spec.ts` - an admin promotes one pending Field/Role suggestion
      and dismisses another; the queue empties and stays empty on reload.

Run with `npm run test:e2e` from `frontend/`. Config: `frontend/playwright.config.ts`.

## Coverage

- Frontend: unit (127 tests, all components) + E2E (3 real-browser flows).
- Backend: API (93 tests, all routers) + full suite (528 tests, all hermetic now).
- New end-to-end coverage: onboarding, subscription toggle, admin taxonomy curation.

## Not covered

- Real Google OAuth itself (can't be automated / no real account here) - bypassed via cookie
  injection, so the `/auth/login` → Google → `/auth/callback` round trip is untested by this suite.
- Source approval (`AdminView`) and engagement (`EngagementView`) admin screens - no E2E flow
  written for these; unit tests exist.
- Mobile/responsive viewport behavior.

## Next Steps

- Consider an E2E flow for source approval, if that screen sees real usage soon.
- Add a real Google OAuth smoke test only if/when a staging environment with a dedicated test
  Google account exists - not safe to attempt against the real client credentials in `.env`.
