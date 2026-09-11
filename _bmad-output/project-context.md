---
project_name: 'news-agent'
user_name: 'NomiM'
date: '2026-09-11'
status: 'complete'
optimized_for_llm: true
---

# Project Context for AI Agents

_Every rule here earns its place one way: breaking it is **silent**. CI will not catch it, and
reading a neighbouring file will not teach it. Conventions you can infer by pattern-matching the
surrounding code are deliberately absent, and so is anything already in the global `CLAUDE.md`._

---

## Approval gates

**Dependencies.** Adding one needs NomiM's approval, asked for before the code that needs it is
written. "Adding" means a new entry in `requirements.txt`, `requirements-dev.txt` or
`frontend/package.json`, or importing a package not already declared there. Installing what is
already declared (`pip install -r`, `pip install -e .`, `npm ci`) is setup, not adding. This
codebase reaches for the standard library first on purpose: stdlib `smtplib` over an email SDK,
a thin `httpx` transport over a model-provider SDK, a module-level `ref` because Pinia is not
installed. Say why the stdlib will not do.

**Git.** Read-only git is expected: `status`, `diff`, `log`, `show`. Check `git status` before
writing code, so a parallel session's work is not overwritten. Everything that changes state
needs explicit approval every single time: `commit`, `add`, `push`, `checkout`, `branch`,
`merge`, `rebase`, `reset`, `restore`, `stash`, `tag`. Approval is per-action, never carried
over. If staged files hold changes that are not yours, say so and stop.

## Comments

Default to no comments. A comment that restates what the line already says is noise.

The test: **delete it mentally. If nothing is lost, it should not exist. If a decision, a trap,
or a reference is lost, it is not a comment, it is part of the code, and it stays.** What
survives here: why a non-obvious choice was made, a trap the next reader walks into, or a
pointer that is not derivable from code (an `AD-11`, a GitHub issue number).

The existing backend is heavily commented and mostly passes that test. **This rule governs code
you write. It is not a license to strip comments from existing files** - that is a task NomiM
asks for explicitly, never a side effect.

## Things that fail silently

**`contextvars` do not propagate into `ThreadPoolExecutor` workers.** Every submit in a pipeline
stage goes through `contextvars.copy_context().run`, or telemetry loses attribution and nothing
reports an error.

**Per-item commit depends on a flag in another file.** Pipeline stages commit inside the
`as_completed` loop so a crash loses only unlanded work. That works only because `db.py` builds
`SessionLocal` with `expire_on_commit=False`. Remove it and every processed object silently
expires and re-queries. Every test `sessionmaker` copies the flag for the same reason.

**Write ownership is invisible from the calling side.** Each table has exactly one module
allowed to mutate it, stated in that module's docstring: `services/preferences.py` is the single
mutation point for `UserTopicPreference` (where the 4-topic cap is enforced),
`services/telemetry.py` is the sole writer of `OutboundRun` / `OutboundCall`, and `api/auth.py`'s
`resolve_identity` is the only place a `User` row is created from an as-yet-unauthenticated
request. Writing to one of these from a new module passes tests and drops the invariant in
production.

**A paid LLM stage filters to subscribed topics first** (`summarize.py`, GH #45). A new paid
stage that skips the filter spends money on work nobody asked for, and nothing fails.

**Jinja templates ship as package data**, declared in `pyproject.toml` under
`[tool.setuptools.package-data]`. A template or asset not listed there is missing from the
installed package and fails only at runtime.

**`mypy` covers `packages = ["newsagent"]` only.** `tests/` and the frontend are outside it.

**A model column change without a migration in the same change is incomplete work.** The suite
never runs migrations, so nothing will tell you.

## Things an agent would "fix" and break

**Never widen the ruff rule set.** `pyproject.toml` pins `select = ["E4", "E7", "E9", "F"]`
because ruff 0.16.0 widened its own default and turned a linter release into red CI on untouched
files.

**Tailwind is v4.** Tokens live in `@theme` inside `frontend/src/style.css`. Do not add a
`tailwind.config.js` or v3-era `content` globs.

**Migrations use `op.batch_alter_table`** even though production is Postgres. Eight of them rely
on it. Do not simplify it away.

**`enum.Enum` appears nowhere.** Status values are module-level string constants beside the
model or stage that owns them, on plain `String` columns. Do not introduce enums.

**Pinia is not installed.** Shared frontend state is a module-level `ref` plus plain functions
(`auth.ts`, `profile-draft.ts`). Those refs survive SPA navigation, so any cache holding
user-specific data needs invalidation wired into `signOut()`.

**Wire fields keep the backend's `snake_case` verbatim** in `client.ts` (`topic_id`,
`is_admin`). Only a shape the frontend defines itself is camelCase, mapped explicitly.

**There is no i18n library and no message catalogue.** Hebrew user-facing strings are inline
literals, in the Vue components and the digest templates. Do not introduce one. Identifiers,
file names, commit messages and documents stay in English.

**`LOCAL_LLM_*` is not on-premise hardware.** It is a second remote endpoint, distinguished from
`EXTERNAL_LLM_*` only by config name (AD-3). `suggestion_provider` is deliberately independent
of `llm_provider`; do not collapse them.

## Layer boundaries

**`HTTPException` is raised only in `api/`.** A service raises its own domain error carrying a
stable `detail` payload; the router catches it and translates. See `routers/me.py` and
`preferences.TopicCapExceededError`.

**All frontend HTTP goes through `request<T>()`** in `frontend/src/api/client.ts`. No `fetch` in
components or views; failures arrive as `ApiError` carrying `status`.

**Return the object, let `response_model` serialize it.** A router returns an ORM row
(`-> list[Source]`) or a service dataclass (`-> list[preferences.TopicChoice]`) while the
decorator names the schema. Build a schema by hand only when there is no object to return, as
`get_my_subscription` does for a computed boolean.

**The pipeline is a separate process.** It reaches the database directly, never the API over
HTTP.

## Testing

**Tests may use sqlite. Nothing else may.** Anything that is not a test - the API, the pipeline,
a manual CLI run - uses the database `.env` resolves to.

**Tests run on sqlite; production is Postgres**, and each test calls `create_all` rather than
running migrations. Backend-specific behaviour is not caught here.

**Threads need `poolclass=StaticPool` and `connect_args={"check_same_thread": False}`.** Plain
`sqlite:///:memory:` gives each connection its own empty database, so a worker thread's write
lands in a different, tableless DB and the test fails with no visible cause.

**Override auth through `app.dependency_overrides`** using `tests/api/conftest.py`'s `as_admin` /
`as_user` / `as_user_with_db`. Never build a session cookie or drive OAuth in a test. A test
adding its own override must not leak it.

**`tests/conftest.py`'s `autouse` fixtures cover settings isolation and telemetry/logging only.**
A test touching any other table brings its own engine.

**`frontend/src/test-setup.ts` stubs `matchMedia` and `IntersectionObserver`**, which jsdom does
not implement and several components call in `onMounted`. A component that starts using another
missing browser API gets its stub added there, not mocked per spec. Mock the API module
(`vi.mock("@/api/client", ...)`), never `fetch`.

---

## Rules you must not miss

### No images of women in the digest. No exceptions.

V1 satisfies this by shipping **no images at all** (GH #57). `fetcher.extract_image_url` still
stores `Article.image_url` so future classifier work is not blocked, but `render.py`'s
`ArticleView` does not carry it and `digest.html.j2` renders no lead image.

**Do not re-add image rendering.** A classifier cannot guarantee zero exceptions, so the rule is
satisfied by absence, not by filtering. V2 is an open decision in `CLAUDE.md` and needs NomiM
first, not a pull request.

### Gender-neutral Hebrew

No user-facing Hebrew may address the reader in a way that assumes their gender. Hebrew has no
gender-neutral second-person present tense, so the trap is a present-tense verb or an imperative
aimed at "you", not the pronoun itself. Rewrite around it: second-person **past** tense is
spelled identically for both genders, `אליך` / `אותך` / `שלך` / `לך` are already neutral, and a
bare imperative becomes `יש ל` + infinitive or a noun phrase (`אישור`, never `אשר`). Slashed
forms are acceptable only in taxonomy role names the reader picks for themselves, never in body
copy. `render.py`'s `_welcome_view` is the reference.

Two regression guards scan for this: `frontend/src/__tests__/gendered-copy.spec.ts` and
`tests/test_gendered_digest_copy.py`. They are word-boundary denylist scans, not parsers, so they
miss new phrasings and can false-positive. **When one fails, fix the copy.** If it is genuinely a
false positive, narrow the pattern or add an exemption beside it. Never delete or skip the check,
and never satisfy it with a slashed form.

### Secrets and the environment

`.env` points at the **TEST** Neon branch; `.env.prod` holds the **PRODUCTION**
`NEWSAGENT_DATABASE_URL` and nothing else. Both are gitignored. `.env` also carries **real** SMTP
credentials and a real `EXTERNAL_LLM_AUTH_TOKEN`, so a careless local pipeline run sends real
email and spends real money even though its database is the test branch.

`db.py` builds `engine`/`SessionLocal` at **import time** from `settings.database_url`, so any
code opening its own `SessionLocal()` talks to whatever `.env` resolved to. Config is read only
through `newsagent.config.Settings`, never `os.environ`. Never print, log, or commit either file,
never echo a connection string or token, and never point a local run at `.env.prod`.

`NEWSAGENT_DEV_AUTH_EMAIL` gates `GET /auth/dev-login`, which signs a user in with no Google
verification. When empty the route **is never registered at all**, and startup warns whenever it
is set. Preserve both. Do not turn it into a registered route that checks a flag and 404s.

### Deployment shape is not this repo's to assume

**Never hardcode a backend hostname.** `client.ts` falls back to the relative `/api`,
`Dockerfile.frontend` deliberately refuses a `VITE_API_BASE` build arg, and
`nginx.frontend.conf.template` strips the prefix at runtime via one `BACKEND_HOST` per
environment. A hardcoded API base once broke OAuth login after a deploy. CORS origins come from
`settings.frontend_url` and the cookie domain from `settings.session_cookie_domain`; both stay
configuration.

Anything touching how the frontend finds the backend, the cookie domain, or CORS gets a message
to Moshe (`news-agent-infra`) before it is assumed. The GitHub Environments `stage` and `prod`
are orphaned - `deploy.yml` never reads them. Terraform plus Azure Key Vault is what production
runs on, so setting a GitHub secret changes nothing.

### Two schedules, not one

`fetch`, `filter`, `extract`, `summarize` run **daily**, because an RSS feed holds only the
latest few dozen items. `build-digests` and `send-digests` run **weekly**, one email per user.
Ranking is tuned to match (`recency_half_life_hours=84`). Do not collapse them or assume a daily
digest.

### Outbound fetching stays bounded

Per-request timeout, bounded worker pool, and a user agent naming the repository. `full_text` is
truncated to `extraction_max_chars` **before it is stored**, so it is bounded before it can reach
a prompt. Do not unbound any of these, and do not remove the user agent.

### Accessibility does not regress

Every chip, pill and segment is a real `<button type="button">` with `aria-pressed`; the
experience picker is a real radio group hidden with `sr-only`; gating uses the real `disabled`
attribute, never a CSS-only class; `focus-visible:outline` is on every interactive element;
motion is gated on `prefers-reduced-motion` and hover on `(hover: hover) and (pointer: fine)`.
Colour tokens were measured against WCAG 2.1 AA and three were darkened to pass, so changing an
ink or background token means re-measuring, not eyeballing. Every screen is responsive at laptop,
tablet and phone widths; not-responsive is a bug, not missing polish.

---

Versions are not listed here. `requirements.txt`, `requirements-dev.txt` and
`frontend/package.json` are the source of truth, and a copy would only drift.

**Where this file and the code disagree, the code is the fact and this file is the bug.** Say so
rather than following it.

Last updated: 2026-09-11
