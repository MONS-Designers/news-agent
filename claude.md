# NewsAgent - project overview

One product, two sibling repos, developed by two people. This file is shared context for
Claude Code sessions opened in either repo - Claude Code reads CLAUDE.md files from parent
directories automatically.

**news-agent/** - Nomi (dev). The content engine + user-facing app: fetch, filter,
  summarize/translate, build digest, send. Backend FastAPI + SQLAlchemy (Postgres, via Neon),
  frontend Vue (admin source-approval + user preferences), auth via Google OAuth. Pipeline is a
  separate scheduled process from the API, reads/writes the DB directly. Repo:
  github.com/MONS-Designers/news-agent
**news-agent-infra/** - Moshe (DevOps). Server, daily scheduler, email delivery, default
  source list, secrets, LLM cost control. Planned using the BMad method - see
  news-agent-infra/_bmad-output/ for the full planning trail (forged idea, market research).
  Repo: github.com/MONS-Designers/news-agent-infra

## What NewsAgent is

A news digest agent for Hebrew-speaking readers: pulls articles from RSS/web sources (any
source language), summarizes and translates to Hebrew, categorizes by topic, and delivers as a
weekly email. Output language is Hebrew; source language is irrelevant.

## Current scope (superseded 2026-08-07 per launch-readiness decision; see
news-agent/_bmad-output/planning-artifacts/epics-launch-readiness.md)

**Weekly** email digest, delivered via a real email provider (SMTP adapter shipped)
Self-registration via Google OAuth is **in**: a new visitor gets an account automatically,
  hard-capped at a configurable max (10 at launch); overflow visitors are captured to a waitlist
Admin still curates RSS sources and the Field/Role taxonomy; users set their own preferences via
  a guided profile picker (Field/Role/Experience/Interests -> suggested Topics)
WhatsApp delivery remains out of scope for this stage

## Locked product decisions (per BMad forge-idea, 2026-07-14)

Sources: RSS preferred, free/web search not excluded, English sources fine
"In Hebrew" = output language only; agent translates + summarizes into Hebrew
Architecture: fetching happens server-side, on the user's behalf - client stays thin
  (registration touchpoint + mailbox only)
Delivery: daily email for MVP; WhatsApp is phase 2; a pull-model website was rejected
  - **superseded 2026-08-07: the MVP cadence is weekly, not daily.** WhatsApp-as-phase-2
  and the rejection of a pull-model website still stand.
Open technical risk (unresolved, carried to build): how the agent judges source quality when
  discovering sources from a user's stated interests (vs. picking a random low-quality blog)

## Content policy: digest images (documented 2026-08-16, V1 decision implemented 2026-08-31)

Rule: the digest must never include images of women. No exceptions.

Status: **V1 - images dropped entirely (option 1 below), per issue #57.** `extract_image_url`
in `news-agent/src/newsagent/pipeline/fetcher.py` still extracts and stores `Article.image_url`
from RSS metadata (`media:content` / `media:thumbnail` / an image enclosure) - kept as-is so V2
classifier work isn't blocked on re-adding extraction - but `render.py`'s `ArticleView` no
longer carries `image_url`/`alt_text`, and `digest.html.j2` no longer renders a lead image.
Digests are text-only regardless of what `Article.image_url` holds.

Open question, still unresolved, to pick before V2 brings images back: an ML/vision classifier
(e.g. AWS Rekognition, Google Vision) cannot guarantee zero exceptions - it will produce both
false negatives (an image of a woman slips through) and false positives (a clean image gets
blocked). Options discussed 2026-08-16:
  1. Drop images from the digest entirely - the only way to satisfy "no exceptions" without
     relying on classification accuracy. **Chosen for V1.**
  2. Automated classification with a conservative threshold, as a best-effort first line of
     defense - not a true zero-exception guarantee.
  3. Manual admin approval per image before send - reliable but not automated, adds ongoing
     editorial workload.
V2 approach (2 vs. 3) still undecided; pick one and update this section before re-adding image
rendering.

## Content policy: gender-neutral Hebrew copy (documented 2026-09-01, per issue #61)

Rule: no user-facing Hebrew string may address the reader in a way that assumes their gender.
Hebrew has no gender-neutral second-person present tense, so the trap is almost always a
present-tense verb or an imperative aimed at "you" - not the words `אתה`/`את` in isolation.

Technique - rewrite around the problem, never use slashed forms (`את/ה`) in prose:
- Second-person **past** tense is spelled identically for both genders (`הצטרפת`, `סיפרת`,
  `בחרת`) - prefer it over present tense.
- `אליך`, `אותך`, `שלך`, `לך` are already neutral in writing.
- Avoid bare imperatives (`בחר תחום קודם`, a button labeled just `אשר`) - use `יש ל` + infinitive
  (`יש לבחור תחום קודם`), a noun phrase (`אישור`), or reword the state entirely.
- Slashed forms stay acceptable only in taxonomy role names the reader picks for themselves
  (`מהנדס/ת תוכנה`, in `services/taxonomy.py`'s `DEFAULT_ROLES`) - never in body copy.
- `src/newsagent/pipeline/render.py`'s `_welcome_view` is the reference example.

A regression guard scans for the most common offenders (`אתה `, `תוכל`, bare imperatives) in
`.vue` files (`frontend/src/__tests__/gendered-copy.spec.ts`) and in the digest template
(`tests/test_gendered_digest_copy.py`) - it's a targeted word-boundary scan, not a parser, so a
genuinely new phrasing may need the denylist extended rather than the check silenced.

## Resolved drift (2026-08-07)

The self-registration question flagged below was resolved in favor of the original idea doc:
self-registration (Google OAuth, capped at 10 users, waitlist on overflow) is **in**, per the
2026-08-07 launch-readiness scope decision - see
`news-agent/_bmad-output/planning-artifacts/epics-launch-readiness.md`. Source auto-discovery
from user interests remains **out**: RSS sources stay admin-curated; only the separate
Field/Role taxonomy has a user-facing "Other" suggestion path, reviewed by admins before
promotion.

## Cross-repo integration

Before hardcoding or changing anything that assumes a particular deployment topology (API base
URL, cookie domain, CORS origins) - check with news-agent-infra on the actual deployed shape,
or make it configurable rather than assumed. `frontend/src/api/client.ts`'s `API_BASE` was a
hardcoded relative path since the original frontend scaffold commit, which silently broke
OAuth login once infra deployed the frontend and backend on split subdomains - nobody's job
was to check that assumption against the real deploy shape before it shipped. Full writeup (in
news-agent-infra): `_bmad-output/implementation-artifacts/retro-mvp-deploy-2026-08-16.md`. When
a change touches how the frontend finds the backend, a two-line message to Moshe before
assuming a deployment shape is cheaper than discovering the gap after a deploy.

## Where to look for more

Full decision log: news-agent-infra/_bmad-output/forge/daily-digest-agent/forged-idea.md
Market research: news-agent-infra/_bmad-output/planning-artifacts/research/
Informal architecture flow diagram: news-agent-infra/_bmad-output/planning-artifacts/architecture-flow-diagram-2026-07-14.md
Current scope decisions: news-agent/_bmad-output/planning-artifacts/epics-launch-readiness.md
Nomi's backlog: GitHub issues on news-agent