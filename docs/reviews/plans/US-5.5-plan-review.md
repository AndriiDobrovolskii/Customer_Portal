---
artifact_type: plan_review
story: US-5.5
version: 2
status: DRAFT
created_at: "2026-09-14T07:30:00Z"
updated_at: "2026-09-14T07:30:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.5-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.5-task-breakdown.md
    version: 2
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
supersedes: docs/reviews/plans/US-5.5-plan-review.md (v1)
---

# Plan Review: Agent Console (Frontend)

**Story ID:** US-5.5
**Plan Reviewed:** docs/plans/US-5.5-implementation-plan.md (v2)
**Task Breakdown Reviewed:** docs/plans/US-5.5-task-breakdown.md (v2)
**Reviewed:** 2026-09-14
**Overall Verdict:** PASS

## Summary

This is a re-review of implementation plan v2 and task breakdown v2, following
this stage's own v1 `BLOCKED` verdict (`docs/reviews/plans/US-5.5-plan-review.md`,
v1), which held on specification v1 still carrying OD-1 through OD-5 as
unresolved Open Questions deferred to `HUMAN_SPEC_APPROVAL` — an approval that
never carried a resolution back into the spec text. This review does not take
the v2 chain's own version bump as proof the defect is fixed; it re-verifies
directly against current spec text (see "Closing v1's Block" below) that no
Open Question or unresolved decision survives, then separately audits the plan
and task breakdown against the impact analysis, `AGENTS.md` §3's Frontend
layering table, and §5's Frontend testing split. Confirmed directly: the
specification's Open Questions section reads "None," `docs/decisions/US-5.5-open-decisions.md`
v2 records all five OD items `RESOLVED` with an explicit `Source: human
decision, 2026-09-14` on each, spec review v2 independently verified each
resolution appears as concrete, testable requirement text in FR-1, FR-2, FR-3,
FR-6, FR-7, and new FR-11 (not merely echoed in a citation table) and returned
`PASS`, and the task breakdown's own "Resolved Decisions Consumed by This
Sequence" section cites FR numbers, not "OD-n interim default" phrasing,
against every task. Full impact-analysis coverage holds — every `api/`,
`hooks/`, `store/`, `routes/`, `layouts/`, and `screens/` item from impact
analysis v2 §1/§1a, plus every §4 test-surface item, is Covered in the plan's
Files To Create/Modify and in a task breakdown row. No task-breakdown layering
violation was found. The plan's one load-bearing external claim — that
`app/modules/support/service.py::list_agent_queue` resolves the `"me"`/`"none"`
`assignee_id` literals server-side, so the frontend sends them verbatim with no
client-side substitution — was independently checked against
`app/modules/support/service.py` (lines 462-471) and `router.py` (response
models at lines 108, 136, 190) this pass and holds. The Risks section is
concrete and specific, not a placeholder, and explicitly does not need to
(and does not) cover the concurrent-401/single-in-flight-refresh race, since
`httpClient.ts` is unmodified by this Story and no Open Decision was flagged
blast-radius-altering on that axis. The Testing Strategy names per-AC,
per-file assertions. No scope creep was found. One Low layering-note and
several Low/Medium non-blocking findings are recorded below; none forces
anything other than `PASS`.

## Closing v1's Block

| v1 Blocking Issue | v2 status, with evidence |
|---|---|
| Specification v1 (`APPROVED`) itself deferred OD-1–OD-5 to `HUMAN_SPEC_APPROVAL`, and that approval carried no resolution back into the spec text (`docs/workflow/history.jsonl`, `HUMAN_SPEC_APPROVAL` at `2026-09-14T01:20:00Z`, `comment: null`). | Specification v2's Open Questions section reads: "None. All five Open Decisions raised by `us-clarifier`... have been resolved by explicit human decision on 2026-09-14." Read directly (not inferred from the revision banner): FR-1, FR-2, FR-3, FR-6, FR-7 each embed the resolution as operative requirement text (e.g. FR-1: "the assignee column renders the assigned agent's identity as a shortened/truncated `assignee_id` UUID — no backend-provided display name exists, and no name-resolution call is made opportunistically... (Resolution OD-1)"; FR-3: the navigation-state-handoff mechanism stated in full, not referenced), and new FR-11 states the shared-app-shell nav requirement directly. `docs/decisions/US-5.5-open-decisions.md` v2 marks all five `RESOLVED`, each with `**Source:** human decision, 2026-09-14`. Spec review v2 independently re-verified this clause-by-clause and returned `PASS`. Closed. |
| Task breakdown v1 phrased task content as "the plan's concrete interim default pending resolution of OD-1 through OD-5." | Task breakdown v2's "Resolved Decisions Consumed by This Sequence" section cites each task by FR number against the settled resolution (e.g. "OD-3 ... implemented in T5, T6 ... T11 ... T12"), and its own revision banner states every "interim default"/"OD-n" phrasing was replaced with a citation to settled FR text. Re-read directly: T4/T5/T6/T11/T12's Verification Command cells cite "FR-1," "FR-6," "Architectural Change 8" — no "Blocked on OD-X" or "pending resolution" language appears anywhere in the document. Closed. |
| Implementation plan v1 carried a "Dependencies on Unresolved Open Decisions" section. | That section is removed in v2; the plan's own revision banner states why ("nothing remains open for it to carry"), and the "Open Decisions Status" closing section states all five are `RESOLVED` and implemented as stated spec behavior, not an interim default. Closed. |

A mechanical `TODO`/`TBD`/`FIXME` sweep of specification v2 and specification
review v2 (the two `APPROVED` inputs this stage's harness precondition names)
found no matches. Design review v2 (`NOT_APPLICABLE`, re-derived against spec
v2, independently re-confirmed by this review against `stage-map.yaml`'s
`DESIGN_REVIEW.optional_when` clause) confirms none of the five resolutions
touches API or persistence design — consistent with the story's own
Assumption #7 and this Story's `track: frontend` designation, so `api_design`/
`openapi`/`database_design`/`entity_model` are correctly absent as inputs to
this stage.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `frontend/src/api/types.ts` (modify) | Covered | Architectural Change 1; Files To Modify | `AgentTicketRead`, `AgentTicketListResponse`, `AssignTicketRequest`, `AgentTicketStateRead`, `ResolveTicketRequest` added; `ReplyRead.visibility` closes the carried-forward Non-Blocking Finding as a required field; `CreateReplyRequest.visibility` optional. |
| `frontend/src/api/supportApi.ts` (modify) | Covered | Architectural Change 1; Files To Modify | `listAgentTickets`, `assignTicket`, `unassignTicket`, `resolveTicket` added; no existing signature changes. |
| `frontend/src/api/httpClient.ts` (no change) | Covered | Plan's closing "No change" paragraph | Plan explicitly concurs: `httpDelete<T>` and `Retry-After` parsing already generic. |
| `frontend/src/hooks/useAgentTickets.ts` (new) | Covered | Architectural Change 3; Files To Create | Cursor query, `me`/`none`/raw-UUID sent verbatim (independently re-verified against `service.py::list_agent_queue`, see Risk Realism). |
| `frontend/src/hooks/useAssignTicket.ts` (new) | Covered | Architectural Changes 3, 7, 8; Files To Create | |
| `frontend/src/hooks/useUnassignTicket.ts` (new) | Covered | Architectural Changes 3, 7, 8; Files To Create | |
| `frontend/src/hooks/useResolveTicket.ts` (new) | Covered | Architectural Change 3; Files To Create | |
| `frontend/src/hooks/useTicketDetail.ts` (no change) | Covered | Architectural Change 3 ("reused as-is") | Consistent — no Files To Modify entry. |
| `frontend/src/hooks/useReplyToTicket.ts` (modify) | Covered | Architectural Change 2; Files To Modify | Additive optional `visibility` field, not a signature change; customer path payload unaffected. |
| `frontend/src/hooks/useCloseTicket.ts`, `useReopenTicket.ts` (no change) | Covered | Dependency on Prior Stories ("reused unmodified") | Consistent with Resolution OD-5 (Architectural Change omits a `reason` field, matching these hooks' existing shape). |
| `frontend/src/store/authStore.tsx`, `decodeTokenScopes.ts` (no change) | Covered | Plan's closing "No change" paragraph | |
| `frontend/src/routes/AppRoutes.tsx` (modify) | Covered | Architectural Change 4; Files To Modify | |
| `frontend/src/layouts/AppShell.tsx` (modify) | Covered | Architectural Change 4; Files To Modify | |
| `frontend/src/screens/AgentTicketQueueScreen.tsx` (new) | Covered | Architectural Changes 5, 7, 8; Files To Create | |
| `frontend/src/screens/AgentTicketDetailScreen.tsx` (new) | Covered | Architectural Changes 5, 6, 7, 8; Files To Create | Component-extraction question (impact analysis §1 Note) explicitly resolved (Change 6: no extraction). |
| §1a `TicketDetailScreen.tsx`, `TicketListScreen.tsx`, `NewTicketScreen.tsx` (checked, not affected) | Covered | Architectural Change 6; no plan action | Plan confirms `TicketDetailScreen.tsx` stays untouched (T10 verifies zero diff); the other two are not mentioned, consistent with "not affected." |
| §1a `ErrorState.tsx`, `FieldError.tsx`, `apiErrorHelpers.ts` (checked, not affected) | Covered | Plan's closing "No change" paragraph | |
| §1a `useRetryAfterCountdown.ts` (checked, not affected) | Covered | Plan's closing "No change" paragraph; Testing Strategy | Reused unchanged for FR-9. |
| §1a `ProtectedRoute.tsx`, `GuestOnlyRoute.tsx` (checked, not affected) | Covered | Plan's closing "No change" paragraph; Architectural Change 4 | T13's verification command additionally asserts `ProtectedRoute.tsx` has zero diff. |
| §1a `test-utils.tsx` (checked, not affected) | Covered | Plan's closing "No change" paragraph | `scopes` seeding already exists (US-5.4). |
| §1a any `app/modules/support/` backend file (not applicable) | Covered | Goal statement; Out of Scope alignment | Plan makes no backend change, consistent with spec v2 and design review v2. |
| `frontend/src/hooks/useReplyToTicket.test.ts` (modify) | Covered | Files To Modify | |
| `frontend/src/screens/TicketDetailScreen.test.tsx` (modify) | Covered | Files To Modify | Fixture-only; T10 confirms zero production diff. |
| `frontend/src/hooks/useTicketDetail.test.ts` (modify) | Covered | Files To Modify | Fixture-only; T9 confirms zero production diff. |
| `frontend/src/test/mswHandlers.ts` (modify) | Covered | Files To Modify | New default handlers for assign/unassign/resolve; baseline-vs-`server.use()` convention for the agent-branch queue shape stated explicitly. |
| `frontend/src/routes/AppRoutes.test.tsx` (modify) | Covered | Files To Modify | |
| `frontend/src/layouts/AppShell.test.tsx` (modify) | Covered | Files To Modify | |
| New: `useAgentTickets.test.ts`, `useAssignTicket.test.ts`, `useUnassignTicket.test.ts`, `useResolveTicket.test.ts` | Covered | Files To Create; Testing Strategy | |
| New: `AgentTicketQueueScreen.test.tsx`, `AgentTicketDetailScreen.test.tsx` | Covered | Files To Create; Testing Strategy | |

No impact-analysis item is Missing or Partially Covered.

## Layering Order (Task Breakdown)

No violation found. `api/` (T1–T2) → test infra (T3) → `hooks/` (T4–T8) →
`screens/` (T11–T12) → `routes/` (T13–T14), each task's `Depends On` column
consistent with `AGENTS.md` §3's Frontend layer table (T9, T10 are
fixture-only tasks floating on T1 alone — see the Low finding immediately
below for the one place this floor is inconsistently stated). T4 correctly
gates on T2/T3; T5/T6 correctly add T4 (the queue query key they invalidate);
T11 correctly gates on T3–T6; T12 correctly gates on T3, T5–T8; T13 (routes)
correctly gates on both new screens (T11, T12).

**[Low] The task breakdown's own stated ordering-floor policy contradicts
itself on T10.** The "Ordering-rule floor" paragraph states the general rule
as "no `routes/`- or `screens/`-layer task below is sequenced ahead of the
`hooks/` block, even where its own file has no code-level import that
requires it" and then, in the very next clause, names T10
(`TicketDetailScreen.test.tsx`, attributed to the `screens/` layer) as
depending only on T1 — which is in the `api/` layer, strictly *before* the
`hooks/` block, not after it. The stated policy and T10's actual floor
disagree. This is not a functional layering violation under this skill's own
test ("flag any task that depends on a layer built after it"): T10 is
fixture-only, makes zero production change (its own Verification Command
requires `git diff --stat -- frontend/src/screens/TicketDetailScreen.tsx`
to be empty), and the Parallel-eligible-batches section places it correctly
alongside T2, which is consistent with its real (non-floor) dependency. This
mirrors the same asymmetric-floor pattern `docs/reviews/plans/US-5.4-plan-review.md`
(v2) flagged as a non-blocking Low finding for that Story's T17 — noted for
`implementation-planner` to tighten the stated policy's wording, not a defect
in the sequence itself.

## Risk Realism

The plan's four Risks are concrete, each naming a specific hazard and a
concrete mitigation/test, not a placeholder:

- **Risk 1** (`ReplyRead.visibility` becoming a required field breaks two
  existing untyped fixture files) is closed by naming the exact fixture
  updates as Files To Modify (and task breakdown T9/T10 as their own tasks),
  not left as a latent inconsistency.
- **Risk 2** (React Hook Form `defaultValues` caching could leak a prior
  "internal" choice into the next composer open, violating both FR-4 and the
  NFR) names the exact mitigation (`reset({ body: "", visibility: "public" })`
  on mutation success) and requires it be asserted by a direct test
  (`AgentTicketDetailScreen.test.tsx`), not assumed from the default value —
  task breakdown T12 carries this forward as its own named test case.
- **Risk 3** (`AgentTicketStateRead` vs. `AgentTicketRead` field-shape
  confusion — both carry `assignee_id`, only one carries `subject`/`category`)
  is enforced as an explicit diff-review constraint on T1/T5/T6 ("never
  spread the response over a full `AgentTicketRead`-typed object"), not a
  generic caveat.
- **Risk 4** (the queue's `assignee_id` free-text filter has no client-side
  UUID validation, by design, per `service.py::list_agent_queue`'s own
  server-side validation) correctly frames this as required behavior, not a
  gap, and names the concrete test surface (422-renders-inline, not a
  client-side block) — folded into T4's and T11's Verification Command.

**Independently checked this pass** (the plan's one load-bearing claim about
backend behavior, per this stage's "verify, don't just trust the version
bump" mandate): `app/modules/support/service.py::list_agent_queue` (lines
462–471) does resolve `assignee_id == "me"` to the calling agent's id and
`assignee_id == "none"` to a passthrough sentinel server-side, and raises a
field-level `422` for anything that doesn't parse as a UUID — confirming
Architectural Change 3's and Risk 4's stated behavior exactly.
`app/modules/support/router.py` confirms `response_model=AgentTicketStateRead`
on both the assign (line 108) and unassign (line 136) routes and a single
`response_model=TicketDetailRead` on the detail GET (line 190) — confirming
Risk 3's and Architectural Change 7's stated shapes exactly. Neither claim
was taken on the plan's word alone.

**No gap found against this skill's frontend checklist item** (the
concurrent-401/single-in-flight-refresh race): this Story introduces no new
token-refresh logic and makes no change to `frontend/src/api/httpClient.ts`
or `frontend/src/store/authStore.tsx` (both confirmed "no change" by impact
analysis v2 and this plan), and no Open Decision (OD-1 through OD-5) touches
token refresh or concurrent-401 handling — the race is out of this Story's
blast radius, not merely unaddressed.

## Test-Strategy Realism

Concrete. The Testing Strategy names the exact Vitest-unit vs.
RTL+MSW-integration split per `AGENTS.md` §5 Frontend subsection, lists the
specific new/modified files in each bucket, and maps every FR/AC to a named
assertion (e.g., "FR-4 (visibility default always `"public"` including after
a prior internal submission — the concrete test for Risk 2 above...)"). The
task breakdown's own per-task Verification Command column repeats these
assertions at the file level (e.g. T12's cell enumerates FR-3 through FR-10
by name against specific rendering/behavior assertions), not a vague
"integration tests will cover this" placeholder.

## Scope Creep

None found on the file/task boundary: every Files To Create/Modify entry
traces to an impact-analysis item, and no task lacks a named origin.

Three items are worth recording as narrowing/addition beyond literal FR text,
though each traces to a specification-review v2 finding or story-level intent
rather than an invented requirement — see Non-Blocking Findings.

## Non-Blocking Findings

- **[Low] Empty-queue-result state goes beyond FR-1's literal text.** FR-1
  states only what the queue renders when tickets exist; the NFR list names
  an explicit loading state and an explicit error state, not an empty-result
  state. The plan's Files To Create for `AgentTicketQueueScreen.tsx` adds
  `"No tickets match these filters."` anyway. This closes spec review v2's
  carried-forward Low finding on the same gap and is a reasonable UX
  completion, not scope creep against the spec's *intent* — but it is not
  literally required by FR-1 or the NFRs, so it is recorded rather than
  silently endorsed.
- **[Low] Whitespace-only `resolution_note` block goes beyond FR-5's literal
  text.** FR-5 and AG-AC5 both say only "an empty note blocks submission";
  the plan's client-side check is post-`trim()`, blocking a whitespace-only
  note too. This closes spec review v2's carried-forward Low finding on the
  same ambiguity and is the more defensible reading, but is the plan's own
  concrete choice, not a resolved FR requirement — recorded for the same
  reason as above.
- **[Low] Three literal placeholder strings are the plan's own choice, not
  FR text.** Architectural Change 8 states this itself: the `"—"`
  unknown/stale-assignee placeholder (with `aria-label="Assignee unknown"`)
  and the `"Unassigned"` null-assignee placeholder resolve spec review v2's
  Medium/Low ambiguities about *what* renders in those states, but neither
  string appears in FR-1 or FR-3. This is exactly what this stage expects a
  plan to do with a non-blocking specification ambiguity — resolve it as
  concrete implementation detail — so it is not a defect; recorded so
  `test-writer`/`reconciliation-reviewer` know these exact strings are a plan
  decision, not a spec requirement, should either need to be revisited.
- **[Low] Task breakdown's ordering-floor policy statement is internally
  inconsistent for T10** (see Layering Order above; not a functional
  violation).

## Verdict Rationale

Full impact-analysis coverage holds (every `api/`/`hooks/`/`store/`/`routes/`/
`layouts/`/`screens/` item and every test-surface item from impact analysis
v2 §1/§1a/§4 is Covered), no task-breakdown layering violation was found (one
Low, non-functional inconsistency in the ordering-floor policy's own wording
is noted, not a violation), the plan's Risks section is concrete and its one
load-bearing external claim about backend behavior was independently
re-verified against `service.py`/`router.py` this pass rather than trusted on
citation, and the Testing Strategy names specific per-FR/AC assertions. No
scope creep was found; three items narrow or add beyond literal FR text but
each closes a named, non-blocking specification-review ambiguity as the
concrete implementation detail this stage expects a plan to supply. Most
importantly, this stage's specific historical failure mode — an `APPROVED`
specification quietly still resting on unresolved Open Decisions that the
plan/task breakdown built defaults around — does not recur: Open Questions
reads "None" in spec v2, all five OD items carry an explicit human
`Source:` line, and every FR/task citation in the plan and task breakdown
points at settled requirement text, verified directly against the spec
rather than inferred from version numbers alone.
