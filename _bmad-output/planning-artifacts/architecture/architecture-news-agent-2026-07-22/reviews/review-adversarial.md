---
title: Adversarial Review - Profile-Based Topic Suggestions Architecture Spine
reviewed_document: ../ARCHITECTURE-SPINE.md
method: 'Two-units-one-level-down construction - for each pair, find two independent builders who each satisfy every AD literally, yet produce incompatible artifacts'
created: '2026-07-25'
---

# Adversarial Review - ARCHITECTURE-SPINE.md (Profile-Based Topic Suggestions)

**Verdict:** The spine is well-formed at the layering/pattern level (AD-1, AD-3, AD-10 are tight and leave little room for divergence), but it is silent or ambiguous at exactly the seams where two independently-built units must agree on a runtime *sequence* or a *data shape not yet fully specified* - concurrency ownership (AD-5/AD-7), the actual call path from "confirm suggestions" into the cap (AD-9), a missing symmetric column (Field's "Other" text vs. AD-6's `role_other_text`), and post-promotion collision handling in the taxonomy queue (AD-2/AD-8). Each is a genuine hole: both builders can point to the spine text and be right.

---

## Finding 1 (Severity: High) - No owner for the `suggestion_status`/`suggested_topic_ids` write race (AD-5 + AD-7)

**Units:** Developer A implementing the `profile.py` BackgroundTask body; Developer B implementing the `PUT /me/profile` request handler that fires it.

**What they'd build differently:**
- Dev B assumes the *handler* is responsible for flipping `User.suggestion_status` to `pending` synchronously, before the response returns - reasoning: the frontend starts polling `GET /me/topic-suggestions` immediately after the save response per AD-7, so if nothing sets `pending` before the response goes out, the very first poll can observe a **stale `ready`/`failed` from a previous save** and briefly render last time's suggestions as if they're new.
- Dev A assumes the *BackgroundTask itself* sets `pending` at task start (simpler: one place owns the whole status lifecycle, matching "written by the BackgroundTask" in AD-7's own wording). Under this reading there's a window - between response-sent and task-scheduled - where the frontend's first poll(s) see the old status.
- Both readings are literal, defensible readings of AD-5 ("fired after the profile-save response") + AD-7 ("written by the BackgroundTask") - the spine states *what* writes the columns eventually, never *when the transition to `pending` must be visible relative to the response*.

**The sharper race:** neither AD-5 nor AD-7 says who wins when two BackgroundTasks are in flight for the same user (double-submit, network retry, or an edit-then-resave inside the flow before the first task finishes). AD-5 only fixes the *execution model* (in-process BackgroundTask, no queue); it does not fix a version token, request id, or "ignore a stale write" rule. Concretely: request 1 (interest text A) fires task 1; user edits to text B and resaves before task 1 finishes, firing task 2. If task 1 is slower (e.g. its provider call happens to take longer) and completes *after* task 2, task 1's stale, A-based result silently overwrites task 2's B-based `ready` state - last-writer-by-completion-order, not last-writer-by-request-order. One builder might defend against this by adding an ad hoc guard ("only write if a newer request hasn't superseded me"); another won't think to, since the spine gives no shared field (timestamp, request id, version counter) to check against. This is a correctness bug waiting to happen, not just a style disagreement, and the spine doesn't foreclose it.

**Fix direction:** AD-7 (or a new AD) should name the owner of the `pending` transition (handler vs. task) and specify a race-resolution rule - e.g. a monotonic `suggestion_request_seq` column, or "each new save always supersedes: BackgroundTask captures the seq/version at fire time and no-ops its write if the row has moved on."

---

## Finding 2 (Severity: High) - Dependency diagram doesn't show who calls `set_preferences` for the guided-flow's topic confirmation (AD-9 vs. the spine's own Mermaid graph)

**Units:** Developer building `services/profile.py` (owns the guided flow, per the Structural Seed); Developer building the frontend's Topic-suggestion-confirmation step (or a second backend dev wiring its endpoint).

AD-9 explicitly says the cap must be enforced for "every caller... including the new suggestion-confirmation flow," which confirms a confirmation flow exists that ends up calling `services/preferences.py:set_preferences`. But the spine's own "Dependency direction" Mermaid graph draws no edge from `profile` (or any new confirmation call site) to `preferences` - only `preferences --> models` and `me --> preferences` / `me --> profile` are drawn, both as siblings under `me`, never touching each other.

**What they'd build differently:**
- Dev A (backend) reads AD-1 + the diagram literally: no `profile --> preferences` edge is allowed, so the confirmation step must be the frontend calling the pre-existing `PUT /me/preferences` endpoint directly with the confirmed topic ids - a second, separate HTTP round trip after `PUT /me/profile` / polling `GET /me/topic-suggestions`, with no transaction or ordering tie between "profile saved" and "topics confirmed."
- Dev B, taking AD-9's "new suggestion-confirmation flow" wording at face value, builds a new call site *inside* `services/profile.py` (or a new endpoint) that imports and calls `set_preferences` directly - which is exactly the edge the diagram omits, and arguably violates AD-1's "no new layer" framing only by accident (it's still service→service, but the diagram was supposed to be the source of truth for allowed edges and doesn't show it).

Both are internally consistent with some part of the spine and inconsistent with another part of it. The practical fallout: if Dev A's reading ships, the frontend must sequence two independent PUT calls itself with no server-side atomicity - a save-profile-succeeds/save-topics-fails split state is possible and unaddressed by any AD.

**Fix direction:** Add the missing edge (or explicitly say there is none and the frontend performs the second call), and state whether the two saves need to be atomic or are allowed to fail independently.

---

## Finding 3 (Severity: Medium-High) - AD-9's cap violation surfaces differently on the two save paths, even though both call the same service

**Units:** Developer maintaining the existing raw toggle-grid `PUT /me/preferences` path (unchanged per AD-9's own framing); Developer building the new guided-flow's topic-confirmation UI.

AD-9 fixes *where* the cap is checked (one service function) but not the **error contract** consumers must honor. `me.py`'s existing handler is `except ValueError as error: raise HTTPException(400, detail=str(error))` - a raw, un-typed string, with no error code distinguishing "cap exceeded" from "unknown topic id" (both currently raise plain `ValueError` with different free-text messages).

**What they'd build differently:**
- The old toggle-grid frontend (unchanged, per the spine) either doesn't handle this 400 specially at all (it was never designed to hit the cap, since it previously had no cap), or a maintainer bolts on a naive `detail.includes("exceed")` string-sniff to show a "pick fewer" message - a fragile, undocumented parsing contract against the service's exact wording.
- The new guided-flow's frontend author, building fresh, has full freedom to invent a friendlier contract - e.g. client-side pre-validation that keeps the cap from ever being hit server-side in the guided flow, meaning that flow's 400 handler is effectively untested and may just show a generic "something went wrong."

Both builders are fully AD-9-compliant (same service, same enforcement point, same `ValueError → HTTPException(400)` shape per the Consistency Conventions table) yet ship two different user-facing experiences for the identical failure, one of them string-sniffing internal exception text as an implicit API contract. The spine's "no new error envelope shape" convention prevents a *structural* split (both are still `{detail: string}`) but explicitly permits this *semantic/UX* split, since it never requires a stable, parseable error code.

**Fix direction:** Either a distinguishable error code (not just message text) in the 400 body, or an explicit convention that the guided flow must pre-validate client-side and treat the 400 as unreachable/generic.

---

## Finding 4 (Severity: Medium) - AD-6 defines `role_other_text` but no `field_other_text`; two builders will store/round-trip Field's free text differently

**Units:** Developer building `services/profile.py`'s save path (writes `User` columns); developer building the profile-picker frontend's "reopen and edit" case (reads `GET /me/profile`-equivalent output to pre-fill the form).

FR-1 requires Field to support "Other + free text" exactly like FR-2 requires for Role. AD-6 and the ERD list `field_id`, `role_id`, `role_other_text`, `experience_bucket`, `interest_free_text` as the flat columns on `User` - there is no `field_other_text`. So when a user picks "Other" for Field, `field_id` is presumably `NULL`, and FR-1 says the free text goes to `PendingTaxonomySuggestion` - but nothing says the raw text is *also* persisted on `User` for the "what should I show pre-filled when this user reopens their profile" case (exactly how `role_other_text` is persisted for Role, per AD-6).

**What they'd build differently:**
- Backend Dev A, mirroring AD-6's Role handling by analogy, adds an undocumented `field_other_text` column (a reasonable, but silent, spine violation - AD-4 also flags that any new column is exactly the kind of thing that needs the deferred migration story, and this one wasn't even planned for).
- Backend Dev B takes AD-6 literally - no such column exists - and simply doesn't persist Field's free text on `User` at all; on reopen, the profile picker shows Field as unset (`field_id = NULL`) with no memory of what the user actually typed, silently discarding data FR-1's Role-equivalent (`role_other_text`) explicitly preserves.
- Frontend Dev C, building the "edit profile" reopen path, needs *some* shape to pre-fill the Other-Field textbox and will code against whichever backend it happened to be paired with, producing a schema (`schemas/profile.py`) that either has or lacks `field_other_text` - an API contract the two backend readings don't agree on, discovered only at integration.

This is a genuine spine gap (an asymmetry between Field and Role handling that the spine doesn't call out or justify), not just an implementation-detail disagreement.

**Fix direction:** Either add `field_other_text` to AD-6/the ERD explicitly (symmetric with `role_other_text`), or explicitly state Field's "Other" text is not persisted on `User` and the picker always shows Field as unset on reopen (a real UX regression worth calling out if intentional).

---

## Finding 5 (Severity: Medium) - AD-2/AD-8 don't scope the upsert key by status, so a post-promotion duplicate submission silently vanishes from admin's view

**Units:** Developer building the "Other" submission write path in `services/taxonomy.py` (called from `profile.py` on FR-1/FR-2 submissions); developer building `admin_taxonomy.py`'s list-pending endpoint (FR-6).

AD-8's upsert key is `(kind, field_id, normalized_text)` with an incrementing `submission_count` "on repeat submissions" - it says nothing about scoping that key by `status`. AD-2 separately defines `status` transitions (`pending`/`approved`/`rejected`) but doesn't say whether a *new* submission matching an *already-approved* row's natural key should reopen it, no-op, or blindly bump its counter.

**What they'd build differently:**
- Taxonomy-write Dev A does a blind get-or-create on the natural key regardless of status: a submission arriving after promotion (e.g., a second dogfood user picks "Other" → "Developer Relations" moments after an admin promotes that exact text) matches the already-`approved` row and increments its `submission_count` in place.
- Admin-queue Dev B implements FR-6's list endpoint as `WHERE status = 'pending'` (the natural reading of "view pending taxonomy suggestions") - so that incremented count is invisible in the admin UI forever; FR-6's "count of users who submitted the same normalized text" silently undercounts, and the row can never be re-surfaced for review even though a real duplicate submission just occurred against a resolved item.

Both readings are literal, valid implementations of AD-2 and AD-8 as written; the spine simply never states what a post-approval collision should do (create a fresh pending row, no-op, or reopen to pending), which is exactly the kind of "two owners disagree on one entity's lifecycle" gap this review is designed to surface.

**Fix direction:** AD-8 should state the natural key is scoped to `status='pending'` (i.e., a match against an approved/rejected row always creates a new pending row) or explicitly define the reopen behavior.

---

## Summary table

| # | Severity | AD(s) | The two units | The clash |
| - | -------- | ----- | -------------- | --------- |
| 1 | High | AD-5, AD-7 | BackgroundTask author vs. save-handler author | No owner for the `pending` transition timing, and no race-resolution rule when two saves overlap - stale writes can win |
| 2 | High | AD-9, dependency diagram | `services/profile.py` author vs. frontend/confirmation-endpoint author | Diagram omits the call edge AD-9 requires to exist; two valid-but-incompatible readings of who calls `set_preferences` for confirmed suggestions, with no atomicity guarantee either way |
| 3 | Medium-High | AD-9, Consistency Conventions | toggle-grid maintainer vs. guided-flow frontend author | Same service, same `ValueError→400` shape, but no stable error code - two different (and fragile) UX treatments of the identical failure |
| 4 | Medium | AD-6, ERD | profile-save backend author vs. profile-reopen frontend author | Missing `field_other_text` column (asymmetric with `role_other_text`) - one builder invents it silently, another discards the data |
| 5 | Medium | AD-2, AD-8 | taxonomy-submission author vs. admin-queue-list author | Upsert key isn't scoped by status; a post-promotion duplicate submission bumps an invisible, already-approved row instead of surfacing for review |
