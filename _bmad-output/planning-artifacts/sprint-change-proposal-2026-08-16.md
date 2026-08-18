---
title: Sprint Change Proposal - Documentation Drift (CLAUDE.md / README.md)
date: 2026-08-16
status: approved
scopeClassification: Minor
---

# Sprint Change Proposal - Documentation Drift

## 1. Issue Summary

`CLAUDE.md` (shared cross-repo project context, auto-loaded into every Claude Code session) and
`README.md` (repo entry point) both still describe the pre-2026-08-07 MVP: seeded-only users,
no self-registration, no real email sender, and an "unresolved drift" note about
self-registration vs. auto-discovery.

In reality, the 2026-08-07 launch-readiness scope decision was made and almost entirely
implemented: `_bmad-output/planning-artifacts/epics-launch-readiness.md` (Epics E/A/B/C/D)
covers self-registration + waitlist, real SMTP email delivery, full-text extraction, digest
click/open tracking, per-run LLM usage accounting, and a responsive/touch profile picker - all
of which are present in the git history (e.g. `0bc92c1`, `06dba22`, `fb5e7bf`, `1cd6f26`,
`88acfcb`, `44c5a5e`, `0d4afe1`, `882bf96`), plus adjacent shipped work not captured in any epic
doc (Hebrew UI translation `2a9e762`, self-service unsubscribe `33e3ef1`).

`epics-launch-readiness.md` itself explicitly states it resolves the drift `CLAUDE.md` has
carried since 2026-07-17 - but `CLAUDE.md` was never updated to reflect that resolution.

Discovered via `/bmad-correct-course`, triggered by the user's own observation: "the project
doesn't reflect what I'm doing" (code ahead of docs, MVP scope changed).

## 2. Impact Analysis

**Epic Impact:** None. All epics in `epics.md` and `epics-launch-readiness.md` are already
accurate and (per commit history) shipped. No epic needed modification, addition, or removal.

**Story Impact:** None. No story-level changes required.

**Artifact Conflicts:**
- PRD (`prd-news-agent-2026-07-21/prd.md`): no conflict - explicitly scoped to Profile-Based
  Topic Suggestions only, doesn't claim to cover the launch-readiness epics.
- Architecture (`ARCHITECTURE-SPINE.md`): no conflict - same narrow scope, cross-cutting
  invariants (AD-1, AD-4) still hold.
- UX specs: no conflict - scoped to the Hybrid Depth picker, unaffected.
- **`CLAUDE.md` and `README.md`** (not formal BMad artifacts, but the two docs every session and
  every new contributor reads first): both stale, both corrected by this proposal.

**Technical Impact:** None. Documentation-only change; no code, schema, or API changes.

## 3. Recommended Approach

**Option 1: Direct Adjustment** (selected). Update `CLAUDE.md` and `README.md` text to match
already-implemented, already-approved scope. No PRD/epic/architecture changes needed since none
of those artifacts are actually wrong.

- Effort: Low
- Risk: Low
- Rollback (Option 2) and MVP Review (Option 3) were not viable/applicable - there is nothing to
  roll back and no MVP scope decision left to make; it was already made and executed.

## 4. Detailed Change Proposals

All seven edits below were presented individually (Incremental mode) and approved by the user,
then applied directly to the working tree.

### CLAUDE.md

**4.1 - "Current MVP scope" -> "Current scope"**
- OLD: "Weekly email digest only, for 2 seeded dogfood users - not self-registered..."
- NEW: Documents self-registration (Google OAuth, cap of 10, waitlist), real SMTP delivery,
  admin-curated sources/taxonomy, guided profile picker.
- Rationale: directly contradicted shipped code (`0bc92c1`, `06dba22`, SMTP adapter PR #35).

**4.2 - "Known drift to resolve" -> "Resolved drift (2026-08-07)"**
- OLD: presented self-registration vs. seeded-users as an open, unresolved question.
- NEW: states the resolution (self-registration in, source auto-discovery still out) and points
  to `epics-launch-readiness.md` as the record of that decision.
- Rationale: `epics-launch-readiness.md` already declares this resolved; `CLAUDE.md` never
  caught up.

**4.3 - "Where to look for more" - added pointer**
- Added a line pointing to `epics-launch-readiness.md` as the current scope-decision record.
- Rationale: without a signposted path from `CLAUDE.md` to the authoritative scope doc, this
  exact drift recurs.

### README.md

**4.4 - "MVP scope" -> "Scope (updated 2026-08-07 launch-readiness decision)"**
- Same substance correction as 4.1, README-side.

**4.5 - Architecture bullet + Schedule table**
- Added the `extract` pipeline stage (full-text extraction, Epic D.1) which existed in code but
  was missing from the documented pipeline flow and the daily-cadence table.

**4.6 - Pipeline command list + surrounding text**
- Added `python -m newsagent.cli extract` to the documented command list; removed the false "no
  real email sender yet" claim (SMTP adapter shipped); pointed to the Status section instead of
  duplicating the gap list.

**4.7 - "Status" section**
- OLD: claimed no real email sender, no click tracking mention, listed only infra-owned gaps
  (#15/#17/#18) plus #23.
- NEW: states what's actually built (self-registration -> profile -> digest loop, SMTP, click
  tracking, usage accounting) and lists the real currently-open gaps: #23 (never run E2E), #48
  (empty digest for under-sourced topic), #31 (accessibility remediation incomplete despite
  being scoped as baseline), #15/#17/#18 (infra), #50/#49/#42/#43 (polish/test-coverage).
- Sourced from `gh issue list --state open`, cross-checked against `epics.md`'s UX-DR14
  ("must land... not deferred") to catch the #31 gap specifically.

*(A request to add a blanket rule prohibiting user-facing images of women was declined as
out-of-scope and discriminatory; not included in this proposal.)*

## 5. Implementation Handoff

**Scope classification: Minor.** Documentation-only changes, already implemented directly in
this session (all 7 edits applied to `CLAUDE.md` and `README.md` via the Direct Adjustment
path). No further handoff to PO, PM, or Architect is needed.

**Success criteria:** `CLAUDE.md` and `README.md` accurately describe the shipped scope as of
2026-08-16, with no factual claims contradicted by the current codebase or open-issue list.

**Next steps (not part of this proposal, noted for awareness):**
- Consider whether the open gaps (#48, #31, #49, #50, #42, #43) warrant grouping into a
  lightweight "hardening" epic, or stay as standalone backlog issues (current state is
  sufficient; no action required unless desired).
- `git status` still shows unrelated in-progress work on `#34` (taxonomy commit-boundary fix) -
  untouched by this proposal, left for the user to commit separately.
