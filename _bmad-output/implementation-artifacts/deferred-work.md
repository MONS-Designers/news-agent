# Deferred Work

## Deferred from: code review of story-1.1 (2026-07-26)

- **No `GET /me/profile`; picker state dies on unmount.** `FieldStep` owns `selectedName`/`isOther`/`otherText` and is destroyed by `v-if`, and there is no read endpoint to rehydrate a saved `field_name`. A returning user sees a blank picker with no sign anything was saved; clicking Reload mid-entry silently discards typed input. Story 1.3's acceptance criterion ("Given I click Back from Step 2 … my previously selected Field/Role/Experience still show as selected") requires lifting this state into the shell plus a read path — that story owns the fix.
- **No Back navigation.** Clicking Continue advances to placeholder steps 2/3 with no way back short of a page reload. EXPERIENCE.md § Component Patterns requires Back on every step, always available and never gated, but steps 2/3 are intentional stubs in Story 1.1 — Back becomes meaningful when Story 1.4 builds Step 2.
- **Not responsive.** No media queries in either picker component; the three-item `flex: 1` stepper with `white-space: nowrap` labels overflows below ~375px, and nested 30px paddings compound on narrow viewports. Tracked as news-agent#30.
- **`add_field` TOCTOU race.** SELECT-then-INSERT against the unique `ix_fields_name`, committing once per field, so a concurrent seeder's loser raises an uncaught `IntegrityError` and aborts `seed_default_fields` mid-loop with a failed session. Pre-existing pattern: faithfully mirrors `add_topic`/`add_source` in `services/sources.py`. Worth fixing project-wide rather than in one story.
- **Editable install points at a stale worktree.** `pip show newsagent` resolves to `C:\project\news-agent\.claude\worktrees\github-issues-review-6e1f99`, so `python -m newsagent.cli` and `alembic` run another branch's code unless `PYTHONPATH=src` is set explicitly. Pre-existing environment issue, not caused by this change, but it will bite anyone running migrations from a plain shell.

## Deferred from: code review of spec-32-33-llm-provider-adapters (2026-07-28)

- source_spec: `_bmad-output/implementation-artifacts/spec-32-33-llm-provider-adapters.md`
  summary: `newsagent.suggestions` has no `Refusal`-equivalent outcome, so `LLMSuggestionSource` has no cheap way to decline degenerate input (blank `field_name`, empty `popularity`) before hitting the real network/paid endpoint.
  evidence: `suggestions/types.py` and `suggestions/base.py` were designed before any adapter made a real network call — `PopularitySuggestionSource` never needed to decline anything, so the gap was free until now. Adding it is an interface change (`SuggestionSource`/`SuggestionSuggestion` contract) out of scope for this story; a future story should decide whether to mirror `llm/`'s `Refusal` type or take a different approach.
