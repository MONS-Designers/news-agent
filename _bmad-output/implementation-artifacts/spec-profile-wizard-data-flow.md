---
title: 'Profile wizard: pass known data down instead of each step re-fetching it'
type: 'feature'
created: '2026-09-09'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'e5e347ee036b112d465608e2e28950080121c5ce'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `PreferencesView.vue` already fetches `profile` and `preferences` once before the wizard even mounts, but `AboutYouStep`/`InterestsStep`/`TopicsStep` each independently re-fetch or re-derive their own copy instead of receiving it - live dogfooding on GH #79 surfaced three concrete symptoms: (1) `AboutYouStep` hard-blocks Continue on `rolesLoading` even when re-entering to edit an unchanged, already-known Field/Role; (2) `InterestsStep`'s Suggested Prompts pop in abruptly mid-typing with no loading indicator; (3) `TopicsStep` shows a loading state and re-derives picked chips from a fresh `listMyPreferences()` call even when the user's current subscriptions (already known to the parent) haven't changed.

**Approach:** Add a small shared store module (`frontend/src/profile-draft.ts`), mirroring the existing `frontend/src/auth.ts` pattern already used in this codebase (module-level `ref`s + plain functions, no Pinia - none is installed) - not prop-drilling. `AboutYouStep`/`InterestsStep`/`TopicsStep` import it directly, both reading it for prefill (replacing their independent `onMounted` fetches) and writing to it on save, so siblings see each other's changes without `ProfilePickerShell` relaying anything (architecture call, per consultation this session: 3 sibling components needing shared read/write access is past the "Rule of Three" threshold for a shared-module pattern over prop+emit, and this project has no state-management library installed - the module pattern matches existing convention). `PreferencesView`'s own `profile`/`preferences` refs *become* the store (import, don't copy) and are seeded once via `initProfileDraft(...)` inside `loadPreferences()` - reused as-is if the user switches to the wizard without a fresh page load. Distinguish "prefill from already-known data" from "genuine user-initiated change" in `AboutYouStep`, so only real changes trigger a blocking fetch/gate. `TopicsStep` renders already-known picked chips instantly from the store while suggestion candidates populate in the background.

## Boundaries & Constraints

**Always:** `profileDraft`/`preferencesDraft` (`frontend/src/profile-draft.ts`) stay the single source of truth for the page and wizard - steps read/write them via the store, never re-fetch independently. A step's own successful save is still the only thing that can change what's "known" (no optimistic UI beyond what already exists today). New loading placeholders use `HybridSpinner` + noun-form Hebrew text ("טעינת הצעות…"), matching this session's established `{components.spinner}`/gender-neutral-copy convention, never a bare "טוען"-style verb.

**Ask First:** none anticipated - the store-based design was confirmed with an architecture consultation this session (mirrors `frontend/src/auth.ts`'s existing pattern); each step's specific "what counts as unchanged" rule is spelled out below, not left to implementation judgment.

**Never:** Don't touch the `suggestion_request_seq`/`BackgroundTask` mechanism (AD-5) or the topic-suggestion computation itself - only the client's re-fetch/re-block behavior around already-known data changes. Don't fix Suggested Prompts' text quality (too short/not exhaustive) - that's a backend LLM-prompt concern; log it to `deferred-work.md`, don't touch `suggest_prompts_for_user`. Don't add client-side persistent caching (localStorage/IndexedDB) - explicitly rejected; the fix is eliminating redundant fetches, not caching their results.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Re-enter wizard, Field unchanged | `profileDraft` already has a saved `field_name`/`role_name` | Role shows immediately, Continue is NOT gated on `rolesLoading`; roles list still refreshes silently in the background | Background refresh failure is silent (no `loadError`) - the shown role is already valid |
| User genuinely changes Field (click a different chip) | Real user interaction, not prefill | Same hard-gate as today: Continue disabled + spinner + "טעינה…" until the new Role list resolves | Existing `loadError` message still applies |
| Re-enter Step 2, Field/Role/Experience unchanged since last fetch | `promptKey` matches `lastPromptsProfileKey` | Existing behavior unchanged (already fixed this session) - no re-fetch, no flicker | N/A |
| Step 2's prompts genuinely re-fetching (first entry, or Field/Role changed) | Fetch in flight | A small `HybridSpinner` + "טעינת הצעות…" placeholder shows in the prompts slot instead of nothing, so arrival doesn't feel like a sudden pop-in | Fetch failure -> placeholder removed, no error shown (existing FR-5 behavior) |
| Enter/re-enter Step 3 | `preferencesDraft` already has the user's current subscriptions | Picked chips render instantly from `preferencesDraft`, no loading state for them; suggestion polling runs in the background to populate/refresh unpicked candidate chips | Poll failure/timeout -> candidates area just stays empty/unchanged; picked chips (already shown) are unaffected |
| AboutYouStep saves a new Field/Role mid-session | User changes and saves Step 1, then goes to Step 2 | `InterestsStep` reads the same shared `profileDraft` - sees the new Field/Role immediately, no plumbing needed; its promptKey comparison re-fetches correctly | N/A |

</frozen-after-approval>

## Code Map

- `frontend/src/profile-draft.ts` -- new. `profileDraft`/`preferencesDraft` module-level refs + `initProfileDraft(profile, preferences)` + `patchProfileDraft(patch)`, mirroring `frontend/src/auth.ts`'s existing pattern exactly
- `frontend/src/views/PreferencesView.vue` -- replace local `profile`/`preferences` refs with the store's (import `profileDraft as profile`, `preferencesDraft as preferences`); call `initProfileDraft(...)` inside `loadPreferences()` instead of assigning fetched data to local refs; `refreshPreferencesQuietly` writes to the same store ref (no functional change to its body)
- `frontend/src/components/profile-picker/ProfilePickerShell.vue` -- no data-flow changes needed (was only relaying before; now the steps read the store directly) - confirm no dead props/emits remain
- `frontend/src/components/profile-picker/AboutYouStep.vue` -- import `profileDraft`/`patchProfileDraft`, drop its own `getMyProfile()` call; distinguish prefill vs. genuine change in the Field/Role watcher so only genuine changes gate `rolesLoading`; call `patchProfileDraft(...)` on save
- `frontend/src/components/profile-picker/InterestsStep.vue` -- import `profileDraft`/`patchProfileDraft`, drop its own `getMyProfile()` call; add `promptsLoading` + placeholder; call `patchProfileDraft(...)` on save
- `frontend/src/components/profile-picker/TopicsStep.vue` -- import `preferencesDraft`, drop its own `listMyPreferences()` call in `load()`; render picked chips from the store immediately, decouple suggestion polling from the whole-component `loading` gate
- Test files: new `profile-draft.spec.ts`, plus updates to all four touched components' specs

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/profile-draft.ts` -- new module: `export const profileDraft = ref<Profile | null>(null)`, `export const preferencesDraft = ref<TopicPreference[]>([])`, `export function initProfileDraft(profile: Profile, preferences: TopicPreference[]): void` (assigns both), `export function patchProfileDraft(patch: Partial<Profile>): void` (`Object.assign`s into `profileDraft.value` if non-null)
- [x] `frontend/src/views/PreferencesView.vue` -- replace `const profile = ref<Profile | null>(null)` and `const preferences = ref<TopicPreference[]>([])` with `import { profileDraft as profile, preferencesDraft as preferences, initProfileDraft } from "@/profile-draft"`; in `loadPreferences()`, replace `preferences.value = prefs; profile.value = prof;` with `initProfileDraft(prof, prefs);`; leave `refreshPreferencesQuietly` and the template untouched (both already just use `profile`/`preferences` by name)
- [x] `frontend/src/components/profile-picker/AboutYouStep.vue` -- import `profileDraft`, `patchProfileDraft` from `@/profile-draft`; in `onMounted`, read `profileDraft.value` directly instead of calling `getMyProfile()` (still call `listFields()`); in the `[fieldName, fieldIsOther]` watcher, when `rolePrefill !== null` (the prefill case, not a genuine user click): set `roleName.value = rolePrefill` immediately, do NOT set `rolesLoading.value = true`, let `listRoles()` update `roles.value` in the background without gating `canContinue`, and don't set `loadError` on a background-refresh failure; keep today's full hard-gate behavior (`rolesLoading = true`, clear-then-refetch) for genuine user-initiated Field changes; call `patchProfileDraft({ field_name: ..., role_name: ..., experience_bucket: ... })` right before emitting `continue`
- [x] `frontend/src/components/profile-picker/InterestsStep.vue` -- import `profileDraft`, `patchProfileDraft` from `@/profile-draft`; in `onMounted`, read `profileDraft.value` for `interestFreeText` prefill instead of calling `getMyProfile()`; use `profileDraft.value` (reactive - already reflects `AboutYouStep`'s patches with no plumbing) in the existing `profileKey()` comparison; add `const promptsLoading = ref(false)`, set `true` at the start of a genuine re-fetch (when the key differs) and `false` in both the success and catch branches; render `<HybridSpinner size="inline" /> טעינת הצעות…` in the prompts slot while `promptsLoading` is true, in place of showing nothing; call `patchProfileDraft({ interest_free_text: text })` right before emitting `continue` on the saved path (the no-op-unchanged path has nothing to patch)
- [x] `frontend/src/components/profile-picker/TopicsStep.vue` -- import `preferencesDraft` from `@/profile-draft`; in `load()`, replace the `listMyPreferences()` call with `preferencesDraft.value` directly; set `allChips`/`pickedChips` from it synchronously (before the suggestion poll resolves) so picked chips render with no loading state; keep `pollForSuggestions()` running to populate/refresh unpicked candidate chips once it resolves, no longer gating the whole component's `loading`/template on it - only gate a smaller "candidates still loading" indicator if needed for the unpicked-chips area
- [x] Log the Suggested Prompts text-quality concern (too short/not exhaustive) to `deferred-work.md` - backend LLM-prompt concern, out of scope here
- [x] Update/add tests: new `profile-draft.spec.ts` (`initProfileDraft`/`patchProfileDraft` behavior), `AboutYouStep.spec.ts` (prefill doesn't gate Continue, genuine change still does, `patchProfileDraft` called on save - mock the module), `InterestsStep.spec.ts` (store-based prefill, placeholder shown/hidden, `patchProfileDraft` called, sees `AboutYouStep`-shaped patches via the shared store), `TopicsStep.spec.ts` (picked chips render instantly from `preferencesDraft`, no loading state for them), `PreferencesView.spec.ts` (`initProfileDraft` called with fetched data)

**Acceptance Criteria:**
- Given a returning user re-enters the wizard with an unchanged Field, when Step 1 renders, then Continue is available immediately (not gated on a fresh role fetch).
- Given a user genuinely changes their Field, when the Role list is fetching, then Continue is still disabled with the spinner + "טעינה…", exactly as today.
- Given Step 2's prompts are genuinely re-fetching, when the user is looking at the textarea, then a spinner + "טעינת הצעות…" is visible in the prompts slot, not a silent gap that later pops content in.
- Given a returning user reaches Step 3 with existing subscriptions, when the step renders, then their picked topics appear instantly with no loading state, while candidate suggestions may still be arriving in the background.
- Given `AboutYouStep` saves a Field/Role change, when the user reaches Step 2, then its prompt-suggestion re-fetch logic sees the new values (not stale ones from a prop that was never updated).

## Spec Change Log

## Verification

**Commands:**
- `cd frontend && npx vue-tsc --noEmit` -- expected: no new type errors
- `cd frontend && npx vitest run` -- expected: full suite passes, including updated/new specs

**Manual checks (if no CLI):**
- Browser pane: as a seeded returning user, click "עריכת פרופיל" and confirm Continue is immediately available on Step 1 without a role-fetch wait. Type in Step 2 before prompts arrive and confirm a spinner placeholder shows, not a sudden pop-in. Reach Step 3 and confirm previously-subscribed topics appear with no loading flash. Change Field on Step 1, confirm the hard-gate still works exactly as before.
