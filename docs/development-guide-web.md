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
Hebrew phrasings that assume the reader's gender. What to do when it fails is in
[Project Context: Gender-neutral Hebrew](../_bmad-output/project-context.md#gender-neutral-hebrew).

## Conventions to respect

### Styling

Design tokens live in an `@theme { ... }` block inside `src/style.css` (Tailwind 4). There is
no third-party UI kit. Reuse the existing tokens and the `BTN_BASE` utility string pattern
rather than hand-rolling a new button. The styling, responsiveness and accessibility rules are
in [Project Context for AI Agents](../_bmad-output/project-context.md).

### The API boundary

`src/api/client.ts` is the only module that talks to the backend. Add a typed function there
rather than calling `fetch` from a component.

`API_BASE` resolves to `import.meta.env.VITE_API_BASE` and falls back to the relative `/api`.
Before changing how the frontend finds the backend, read
[Project Context: Deployment shape](../_bmad-output/project-context.md#deployment-shape-is-not-this-repos-to-assume).

### State

Shared state is a module-level `ref` with plain functions around it, as in `auth.ts` and
`profile-draft.ts`. See [architecture-web.md](./architecture-web.md#state-management) for how it
works, and [Project Context for AI Agents](../_bmad-output/project-context.md) for the rules around it.

### TypeScript

`strict` is on, along with `noUnusedLocals` and `noUnusedParameters`. `npm run type-check` is
a separate continuous-integration step from the tests, so a type error fails the build even
when every test passes.

### Hebrew copy

User-facing copy must never assume the reader's gender. The technique and the reference
example are in [Project Context: Gender-neutral Hebrew](../_bmad-output/project-context.md#gender-neutral-hebrew).

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
