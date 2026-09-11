# Architecture - web

**Date:** 2026-09-10
**Part:** `web`
**Root:** `frontend`
**Project type:** web single-page application
**Architecture pattern:** component-based single-page app with module-level reactive stores

## Executive Summary

A Vue 3 single-page app with five routes and two audiences. Admins approve RSS sources,
curate the Field and Role taxonomy, and read an engagement report. Readers work through a
three-step guided profile picker and manage topic subscriptions. Output copy is Hebrew,
right to left.

The app is deliberately thin. It holds no business logic, no derived domain state and no
client-side cache beyond two module-level refs. All fetching happens server-side on the
reader's behalf; the client is a registration touchpoint and a preferences surface.

## Technology Stack

| Category | Technology | Version | Justification |
| --- | --- | --- | --- |
| Framework | Vue | ^3.5.11 | Composition API, `<script setup lang="ts">` throughout |
| Routing | vue-router | ^4.4.0 | History mode, with a single global guard |
| Language | TypeScript | ^5.6.3 | `strict`, plus `noUnusedLocals` and `noUnusedParameters` |
| Styling | Tailwind CSS | ^4.3.3 | Version 4, CSS-first configuration via `@tailwindcss/vite` |
| Build | Vite | ^5.4.10 | Dev server with the `/api` proxy, and the production build |
| Unit tests | Vitest | ^4.1.10 | jsdom environment |
| Component tests | @vue/test-utils | ^2.4.11 | |
| End-to-end | Playwright | ^1.62.1 | Chromium, against a real seeded backend |
| Type check | vue-tsc | ^2.0.0 | `npm run type-check` |

Frontend dependencies use caret ranges while backend dependencies are pinned exactly. That
inconsistency is a known fact, not a task.

**Tailwind is version 4.** Design tokens live in an `@theme { ... }` block inside
`frontend/src/style.css`. There is no `tailwind.config.js` and no version-3 `content` globs,
and scoped component CSS is not used alongside the utility-class convention.

There is no state-management library. Pinia and Vuex are not installed, and adding one would
be a new dependency rather than a refactor.

## Architecture Pattern

```text
main.ts ──► App.vue (shell: header, nav, FeedbackWidget gate)
              │
              ▼
         router/index.ts ──guard──► auth.ts (ensureMe)
              │
              ├─► HomeView          /
              ├─► PreferencesView   /preferences      requiresAuth
              ├─► AdminView         /admin            requiresAdmin
              ├─► TaxonomyQueueView /admin/taxonomy   requiresAdmin
              └─► EngagementView    /admin/engagement requiresAdmin
                        │
                        ▼
                 api/client.ts ──► backend
```

### Routing and guards

Five routes, three of them admin-only. One global `beforeEach` guard handles both meta
flags:

- `requiresAdmin`: calls `ensureMe()` and redirects to `/preferences` when the identity is
  absent or not an admin.
- `requiresAuth`: calls `ensureMe()` and redirects an anonymous visitor to
  `/?signin=required`.

The query flag on that second redirect is load-bearing. Without it the guard silently
swallows the navigation and the click reads as broken; the flag is what lets the home view
explain why the visitor ended up there.

### State management

No store library. Two module-level `ref` objects, each with plain functions around them,
following the same pattern.

**`auth.ts`** is the single owner of "who is signed in". It exports a `me` ref, an
`ensureMe()` that fetches once and memoizes behind a `loaded` flag, and a `signOut()`. Views
and the router guard read from it rather than calling `/auth/me` themselves.

**`profile-draft.ts`** holds the profile and preferences draft shared by the preferences
view and the three wizard steps. The view seeds it once through `initProfileDraft()`; the
steps read it directly for prefill and patch it on save, so siblings see each other's
changes without the shell relaying anything.

**The lifetime trap, and its fix.** Module-level refs survive single-page navigation, since
there is no page reload. The preferences view relies on that to skip re-fetching data it
already has. But it also means they survive a sign-out with no reload, so a second user
signing in in the same tab could briefly see the first user's cached profile. `signOut()`
calls `clearProfileDraft()` for exactly that reason.

### The API boundary

`api/client.ts` is the only module that knows the backend exists. Every view and component
imports typed functions from it rather than calling `fetch`.

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
```

The relative fallback is the intended production behavior. Vite's dev proxy and nginx both
strip the `/api` prefix before forwarding, and `Dockerfile.frontend` deliberately refuses a
`VITE_API_BASE` build argument. Baking an absolute backend hostname anywhere freezes one
environment into the image, and has already broken OAuth login once after a deploy. See
[integration-architecture.md](./integration-architecture.md).

One private `request<T>()` helper wraps every call and throws a typed `ApiError` carrying the
HTTP status. `getMe()` is the only caller that catches it, turning a 401 into `null` because
"not signed in" is a normal state rather than a failure.

TypeScript interfaces in the same file mirror the backend's Pydantic schemas field for
field, in snake case, so a rename on either side surfaces as a type error rather than a
runtime `undefined`.

### Suggestion polling

`getTopicSuggestions()` returns a `suggestion_status` union that includes `pending_slow`.
That value is **non-terminal**, like `pending`: the backend is still working, but one of its
two concurrent calls has already failed and it is waiting out the other's retries. Clients
must keep polling through it. The type in `client.ts` carries a comment saying so, because
treating it as a failure state would abandon a run that is about to succeed.

## Component Overview

See [component-inventory-web.md](./component-inventory-web.md) for the full catalogue.

Two visual systems coexist deliberately:

- **The default surface** is light: neutral greys, a white sticky header, an amber accent in
  the wordmark. Used by the shell, both admin views and the topic grid.
- **Hybrid Depth** is the profile picker's dark identity, expressed as `--color-hd-*` theme
  tokens in `style.css`. It is scoped in usage to the picker and its companions, but declared
  as Tailwind theme tokens so the picker uses the same utility-class convention as the rest
  of the app rather than hand-rolled scoped CSS.

The Hybrid Depth muted, label and body tokens were darkened on 2026-09-09 to pass WCAG AA
contrast at 4.5 to 1 against the void background. The previous values measured 3.04 and 4.05
and failed.

## Content Rules

Two project-wide content policies land almost entirely in this part.

**Gender-neutral Hebrew.** No user-facing Hebrew string may address the reader in a way that
assumes their gender. Hebrew has no gender-neutral second-person present tense, so the trap
is a present-tense verb or an imperative aimed at "you", not the pronouns in isolation. The
technique is to rewrite around the problem rather than use slashed forms in prose: prefer
second-person past tense, which is spelled identically for both genders; use possessive and
object forms, which are already neutral in writing; replace bare imperatives with an
infinitive construction or a noun phrase. Slashed forms remain acceptable only in taxonomy
role names the reader picks for themselves.

A regression guard scans `.vue` files for the most common offenders in
`frontend/src/__tests__/gendered-copy.spec.ts`. It is a targeted word-boundary scan rather
than a parser, so a genuinely new phrasing may need the denylist extended rather than the
check silenced.

**No images of women in the digest.** Currently satisfied by dropping images from the digest
entirely, which is a backend rendering decision. It constrains this part only in that the
frontend must not reintroduce them.

## Testing Strategy

**Unit and component**: Vitest with jsdom, specs colocated in a `__tests__/` folder beside
what they cover. `src/test-setup.ts` is the shared setup file. Every view and every
profile-picker component has a spec, plus the copy regression guard and the draft store.

**End to end**: three Playwright specs under `frontend/e2e/`, covering the admin taxonomy
queue, preferences, and the profile picker. `global-setup.ts` and `fixtures.ts` prepare the
run, and `scripts/e2e_setup.py` at the repository root seeds an isolated backend. The Vite
proxy target is overridable through `E2E_BACKEND_URL` so the suite points at that isolated
instance rather than the developer's real one.

Vitest's `exclude` list adds `e2e/**`, because its default glob would otherwise pick up the
Playwright specs and try to run them.

**Type checking** runs as its own npm script, `type-check`, using `vue-tsc --noEmit`. It is a
separate CI step from the tests.

## Deployment Architecture

`Dockerfile.frontend` has two stages. The build stage runs on Node 20, installs with
`npm ci`, runs `npm run build`, and writes a static `dist/version.json` carrying the commit
SHA so a deploy can be verified against what is actually running. The serve stage is
`nginxinc/nginx-unprivileged`, listening on 8080 as a non-root user, with the built `dist`
copied in and `nginx.frontend.conf.template` placed where nginx's bundled envsubst entrypoint
will substitute `BACKEND_HOST` at container start.

See [deployment-guide.md](./deployment-guide.md).

## Known Constraints and Gaps

- **Accessibility remediation is incomplete on the profile picker**, despite being scoped as
  a baseline requirement. Tracked as issue 31. The contrast fix on 2026-09-09 addressed part
  of it.
- **`request()` sends no explicit `credentials` option**, so it relies on the default
  same-origin cookie behavior. That is correct under the nginx-proxy topology, where the
  browser sees a same-origin request, and is the reason the split-subdomain deploy needed a
  cookie-domain setting rather than a client change.
- **The design tokens are documented outside this repository** in `DESIGN.md` and
  `EXPERIENCE.md`, referenced from `style.css` comments.

---

_Generated using BMAD Method `document-project` workflow_
