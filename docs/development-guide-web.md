# Development Guide - web

**Date:** 2026-09-10
**Part:** `web` (`frontend`)

## Prerequisites

- Node 20 or newer. Continuous integration uses Node 22, and the Docker build uses Node 20.
  Debian's apt-packaged Node is too old for `@tailwindcss/oxide`.
- A running backend, for anything beyond static rendering.

## Setup

From the `frontend` directory:

```bash
npm install
```

Use `npm ci` instead when you want the lockfile honored exactly, which is what both
continuous integration and the Docker build do.

## Running locally

```bash
npm run dev
```

The dev server listens on `http://127.0.0.1:5173/` and proxies `/api/*` to
`http://127.0.0.1:8000`, rewriting the path to strip the prefix. Run the backend in a
separate terminal to test end to end.

The proxy target is overridable through the `E2E_BACKEND_URL` environment variable, which is
how the Playwright suite points the dev server at its own isolated backend instance rather
than the real one.

## Commands

| Command | What it does |
| --- | --- |
| `npm run dev` | Vite dev server on port 5173 with the `/api` proxy |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serve the built `dist/` locally |
| `npm run type-check` | `vue-tsc --noEmit` |
| `npm run test` | `vitest run`, jsdom, single pass |
| `npm run test:e2e` | Playwright, Chromium |

## Testing

### Unit and component tests

Vitest with jsdom and `@vue/test-utils`. Specs live in a `__tests__/` folder beside what they
cover. `src/test-setup.ts` is the shared setup file, wired through `vite.config.ts`.

The vitest `exclude` list adds `e2e/**`, because the default glob would otherwise pick up the
Playwright specs and try to run them under jsdom.

### End-to-end tests

Three Playwright specs under `e2e/`, covering the admin taxonomy queue, preferences and the
profile picker. `global-setup.ts` and `fixtures.ts` prepare the run; `scripts/e2e_setup.py` at
the repository root seeds the isolated backend.

Install the browser once before the first run:

```bash
npx playwright install --with-deps chromium
```

### The copy regression guard

`src/__tests__/gendered-copy.spec.ts` is not a component test. It scans `.vue` files for
Hebrew phrasings that assume the reader's gender. Being a targeted word-boundary scan rather
than a parser, a genuinely new offending phrasing may need the denylist extended rather than
the check silenced.

## Conventions to respect

### Styling

**Tailwind is version 4.** Design tokens live in an `@theme { ... }` block inside
`src/style.css`. Do not add a `tailwind.config.js`, do not add version-3 `content` globs, and
do not introduce scoped component CSS alongside the utility-class convention.

There is no third-party UI kit. Reuse the existing tokens and the `BTN_BASE` utility string
pattern rather than hand-rolling a new button.

Every screen must be responsive at laptop, tablet and phone widths. Treat "not responsive" as
a bug, not as polish.

### The API boundary

`src/api/client.ts` is the only module that talks to the backend. Add a typed function there
rather than calling `fetch` from a component.

`API_BASE` resolves to `import.meta.env.VITE_API_BASE` and falls back to the relative `/api`.
**Never hardcode a backend hostname anywhere in this part.** Vite's dev proxy and nginx both
strip that prefix, and `Dockerfile.frontend` deliberately refuses a `VITE_API_BASE` build
argument. Baking an absolute URL freezes one environment's hostname into the image, and has
already broken OAuth login once after a deploy.

If a change touches how the frontend finds the backend, send a short message to the
infrastructure repository owner before assuming a deployment shape.

### State

There is no store library, and adding Pinia would be a new dependency rather than a refactor.
Shared state is a module-level `ref` with plain functions around it, as in `auth.ts` and
`profile-draft.ts`.

Remember that module-level refs survive single-page navigation but not a page reload, so any
cache added this way must be invalidated on sign-out. `signOut()` already calls
`clearProfileDraft()` for that reason.

### TypeScript

`strict` is on, along with `noUnusedLocals` and `noUnusedParameters`. `npm run type-check` is
a separate continuous-integration step from the tests, so a type error fails the build even
when every test passes.

### Hebrew copy

No user-facing Hebrew string may address the reader in a way that assumes their gender.
Hebrew has no gender-neutral second-person present tense, so the trap is a present-tense verb
or an imperative aimed at "you", not the pronouns themselves.

Rewrite around the problem rather than using slashed forms in prose:

- Prefer second-person **past** tense, which is spelled identically for both genders.
- Possessive and object forms are already neutral in writing.
- Replace a bare imperative with an infinitive construction or a noun phrase, or reword the
  state entirely.
- Slashed forms stay acceptable only in taxonomy role names the reader picks for themselves,
  never in body copy.

`src/newsagent/pipeline/render.py`'s welcome view is the reference example on the backend
side.

### Two constants that are contracts

`TopicsStep.vue` declares `MAX_TOPICS = 4`, which must match `services/preferences.py`. Its
polling interval and roughly 45-second budget are paced to a background computation that
makes two LLM calls; the `pending_slow` status it may observe is non-terminal and must not be
treated as a failure.

## Continuous integration

`.github/workflows/ci.yml` runs a `frontend-test` job on Node 22 that installs with `npm ci`,
runs `npm run type-check`, then `npm run test`. A third job runs the Playwright suite after
both the backend and frontend jobs pass, installing Chromium with its system dependencies
first.

## Deployment

`Dockerfile.frontend` builds on Node 20 and serves from `nginxinc/nginx-unprivileged` on port
8080. A static `dist/version.json` carrying the commit SHA is written at build time so a
deploy can be verified against what is actually running. See
[deployment-guide.md](./deployment-guide.md).

---

_Generated using BMAD Method `document-project` workflow_
