---
artifact_type: plan_review
story: US-5.3
version: 2
status: APPROVED
created_at: "2026-09-08T22:10:00Z"
updated_at: "2026-09-08T22:30:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/reviews/specifications/US-5.3-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.3-task-breakdown.md
    version: 2
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
supersedes: docs/reviews/plans/US-5.3-plan-review.md
---

# Plan Review: Support Tickets (Frontend)

**Story ID:** US-5.3
**Plan Reviewed:** docs/plans/US-5.3-implementation-plan.md (version 2)
**Task Breakdown Reviewed:** docs/plans/US-5.3-task-breakdown.md (version 2)
**Reviewed:** 2026-09-08
**Overall Verdict:** PASS

## Summary

This is a fresh review of implementation_plan v2 and task_breakdown v2, produced after `HUMAN_PLAN_APPROVAL` rejected v1 for hedging on OD-1..OD-6 instead of stating them as firm architecture. Both v2 artifacts cover every file `impact_analysis` (v1, `PASS`) named as affected, respect `AGENTS.md` §3's frontend layering direction (`api/` → `hooks/` → `routes/`/`screens/`) across all 20 tasks, name a concrete Risks section, and give a per-AC unit-vs-integration (Vitest + RTL/MSW) test split. All six binding OD resolutions are verified below as firmly incorporated as delivered architecture, not workarounds — the human's specific concern at rejection. No blocking findings.

**Precondition note (evaluated, not a defect):** `docs/decisions/US-5.3-open-decisions.md` (v1, `DRAFT`) still shows OD-1..OD-6 as `OPEN` on disk, and `docs/specifications/US-5.3-spec.md` (v1, `APPROVED`) still carries OD-1 as an unresolved Open Question in its FR-12 prose and Open Questions section. Read literally, an unresolved blocking Open Decision in an `APPROVED` input this stage depends on would force `BLOCKED`. It does not here: the human supplied binding resolutions for all six at `HUMAN_PLAN_APPROVAL` (recorded in `docs/workflow/history.jsonl`'s `2026-09-08T21:00:00Z` rejection event and echoed in `workflow-state.yaml`'s current `note`), and rewriting `open_decisions.md`/the spec's FR-12 prose belongs to `us-clarifier`/`story-spec-writer`, not to `planner`/`implementation-planner`/this stage. Plan v2 states this reconciliation debt explicitly in its own "Re-plan note." This stage is therefore not `BLOCKED`; the open-decisions/spec staleness is disclosed, not a plan defect. Story front matter's `source.issue_number: TODO` is likewise stale provenance metadata (`active-story.yaml` already records `issue_number: 26`) that this stage does not depend on and is not re-flagged here.

## OD-1 through OD-6 Firm-Incorporation Check

The human's rejection turned specifically on hedged language in v1 ("narrowest reading pending OD-1," "does not resolve OD-6," "OD-5's de facto precedent"). Each binding resolution was checked against v2's actual architecture text, not just its re-plan note:

| OD | Binding resolution | Where v2 states it | Firm or hedged? |
|---|---|---|---|
| OD-1 | `ApiError` gains a first-class `retryAfterSeconds` field, new constructor param, set by `parseResponse` on any `429` — permanent shared-client architecture, not FR-12-scoped | Architectural Change 2 (plan); T1/T3 (task breakdown) | **Firm.** Change 2 states `retryAfterSeconds` as "a permanent part of `ApiError`'s public shape," sets it via a new third constructor parameter, and states explicitly that "any future `429` reached through `performRequest`/`parseResponse` — i.e. `httpGet`, `httpPost`, or `httpDelete` ... automatically carries this field," not a mechanism scoped to this story's two endpoints. T1's verification command explicitly proves this ("not just this story's two endpoints"). The one boundary drawn — `parseResponseWithMeta` (the separate `PATCH`/`ETag` error path) is left untouched — is accurate scoping to the resolution's own wording, which names `parseResponse` specifically, not evidence of a narrowed reading: the resolution's "not narrowly scoped to FR-12 only" contrasts against *endpoint* scoping (this story's two rate-limited routes), not against *error-path* scoping, and the plan says so directly ("the human's resolution names `parseResponse` specifically"). |
| OD-2 | `category` is a firm plain-text `maxLength=50` input, no dropdown/enum seam | Architectural Change 10; Change 4; T2/T14 | **Firm.** Change 10 states "no forward-compatible dropdown seam beyond what a plain controlled `<input>` already offers ... not something this plan needs to design a seam for now." `types.ts` (Change 4) types `category` as plain `string` with no companion literal-union type. T2/T14 verification greps confirm no enum/`<select>`. |
| OD-3 | "Reopen" never proactively disabled; `409` is the sole eligibility signal | Architectural Change 6 (`TicketDetailScreen.tsx`); hook `useReopenTicket.ts` (Change 5); T11/T15 | **Firm.** Change 6: "never proactively disabled or grayed out based on any client-side date computation ... always clickable when `offeredActionsForStatus` includes it, and a `409` ... is handled entirely by the existing problem+json rendering path ... not by a pre-check." T11/T15 verification includes an explicit grep for "zero client-side reopen-eligibility date computation." |
| OD-4 | `first_response_at` renders as plain labeled text, no SLA-breach styling | Architectural Change 6; T15 | **Firm.** Change 6: labeled "First response," "rendered as a plain timestamp with no SLA-breach context or styling ... no target/deadline language, no color/urgency treatment." T15 verification asserts "no SLA-styling class/attribute/copy." |
| OD-5 | No new UI/component library — hard constraint | Goal section; Validation Strategy; "Not modified" file list; T14/T20 | **Firm.** Validation Strategy states this is "now a hard constraint on `IMPLEMENTATION`, not a default subject to reconsideration." `package.json` is listed under "Not modified." T20's verification command confirms no new dependency was added. |
| OD-6 | `useCreateTicket.ts`: edit-before-resubmit → new key; verbatim resubmit → same key | Architectural Change 8; T8 | **Firm.** Change 8 quotes the binding resolution verbatim and implements it as "a direct equality check on the three form fields ... not a 'has the user touched any field' flag," explicitly "not as a hedge against an unresolved product question." T8 requires three dedicated test cases (verbatim retry, fresh mount, edited resubmission). |

A repo-wide check for hedging language (`pending`, `provisional`, `narrowest`, `at-risk`, `contingent`, `undecided`, `subject to reconsideration`) in both v2 documents found only meta-commentary contrasting v1's retired hedges against v2's firm resolutions (e.g. "OD-1-pending shape ... is rewritten" — describing what changed, not live hedging) — no residual hedged framing of the six resolutions themselves.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `api/httpClient.ts` | Covered | Architectural Change 1, 2; Files To Modify | `Idempotency-Key` option unconditional; `Retry-After` threading now stated as permanent architecture (OD-1 firm) |
| `api/errorNormalization.ts` (contingent on OD-1 in impact_analysis) | Covered (explicit no-op, now confirmed not provisional) | Architectural Change 2; "Not modified" note | OD-1's binding resolution keeps `retryAfterSeconds` on `ApiError`'s constructor, not on `NormalizedApiError` — the plan states this file "stays unmodified ... now confirmed rather than provisional" |
| `errorNormalization.test.ts` | Covered (correctly absent from task breakdown) | Task breakdown "Field notes" | Correctly not touched — Change 2's shape never modifies this file |
| `components/apiErrorHelpers.ts` (contingent on OD-1 in impact_analysis) | Covered | Architectural Change 2; Files To Modify; T3 | Additive `getRetryAfterSeconds` getter, now unconditional (OD-1 resolved) |
| `api/types.ts` | Covered | Architectural Change 4; Files To Modify; T2 | All DTOs impact-analysis named, plus `TicketStatus` union; `category` plain `string` (OD-2); agent-only shapes correctly excluded |
| `api/supportApi.ts` (new) | Covered | Architectural Change 3; Files To Create; T4 | One function per operation, matching `authApi.ts` convention |
| `hooks/useTickets.ts` | Covered | Architectural Change 5; Files To Create; T6 | |
| `hooks/useTicketDetail.ts` | Covered | Architectural Change 5; Files To Create; T7 | Two independent, non-prefix-sharing query keys for FR-5's dual-paginator requirement |
| `hooks/useCreateTicket.ts` | Covered | Architectural Change 5/8; Files To Create; T8 | Key mint/reuse/rotate rule is OD-6's binding case, firm |
| `hooks/useReplyToTicket.ts` | Covered | Architectural Change 5; Files To Create; T9 | |
| `hooks/useCloseTicket.ts` | Covered | Architectural Change 5; Files To Create; T10 | |
| `hooks/useReopenTicket.ts` | Covered | Architectural Change 5; Files To Create; T11 | OD-3 firm: no client-side eligibility computation |
| `screens/TicketListScreen.tsx` | Covered | Architectural Change 6/11; Files To Create; T13 | |
| `screens/NewTicketScreen.tsx` | Covered | Architectural Change 6; Files To Create; T14 | OD-2/OD-5 firm constraints named in task description and verification |
| `screens/TicketDetailScreen.tsx` | Covered | Architectural Change 6/9; Files To Create; T15 | OD-3/OD-4 firm constraints named in task description and verification |
| `screens/PlaceholderHomeScreen.tsx` | Covered | Architectural Change 7; Files To Delete; T17 | Deleted with explicit §7.8 rationale, sequenced after T16 so `MfaEnrollmentBanner` is never orphaned |
| `components/MfaEnrollmentBanner.tsx` (new cross-file dependency) | Covered | Architectural Change 7; Files To Modify; T16 | Relocated to `AppShell.tsx`; unaffected by any OD resolution |
| `routes/AppRoutes.tsx` | Covered | Architectural Change 11; Files To Modify; T18 | `/` → `<Navigate to="/tickets" replace>` |
| `routes/GuestOnlyRoute.tsx` | Covered | Files To Modify; T19 | |
| `screens/LoginScreen.tsx` (routing literal) | Covered | Files To Modify; T19 | |
| `screens/MfaVerifyScreen.tsx` (routing literal) | Covered | Files To Modify; T19 | |
| `layouts/AppShell.tsx` | Covered | Architectural Change 7; Files To Modify; T16 | New nav entry plus banner relocation |
| Existing test files impact-analysis named (`AppRoutes.test.tsx`, `GuestOnlyRoute.test.tsx`, `LoginScreen.test.tsx`, `MfaVerifyScreen.test.tsx`, `PlaceholderHomeScreen.test.tsx`, `MfaEnrollmentBanner.test.tsx`, `AppShell.test.tsx`, `httpClient.test.ts`, `mswHandlers.ts`) | Covered | Testing Strategy; T1, T5, T13, T16–T19 | |
| `frontend/src/test/test-utils.tsx` | Covered (correctly not modified) | Risk 2; task breakdown "Field notes" | `TicketDetailScreen.test.tsx` (T15) wraps `ui` in a local `<Routes>` instead of changing this file's signature |
| New test files impact-analysis named (screen/hook tests, a11y pass, plain-text-rendering assertion) | Covered | Testing Strategy; T6–T15 | |

No impact-analysis item is Missing or Partially Covered.

## Layering Order (Task Breakdown)

No violation found. `T1`–`T5` (`api/` layer) all precede `T6`–`T12` (`hooks/`), which all precede `T13`–`T19` (`screens/`/`routes/`), consistent with `AGENTS.md` §3's Frontend layer table and this project's frontend ordering rule (`api/`/`store/` before `hooks/`, `hooks/` before `routes/`/`screens/`). `T20` (`gate-enforcer`) is correctly isolated as the sole final, non-`frontend-builder` task. `T3` (`components/apiErrorHelpers.ts`) sits between `T1` and `T4`/`T6` — it is classified as a `components/` shared-helper task in the table but functionally reads `ApiError`'s shape; this is unchanged, shipped precedent (the same structural-getter pattern `getErrorStatus`/`getErrorKind` already use in this codebase) rather than something v2 introduces, and the ordering verdict holds either way it is classified: it is sequenced after `T1` (which defines the field it reads) and before every screen task that consumes `getRetryAfterSeconds`. Dependency edges are internally consistent (`T13`–`T15` depend only on already-sequenced `hooks/`/`api/` tasks; `T18` depends on `T17` so `AppRoutes.tsx` never routes to the about-to-be-deleted `PlaceholderHomeScreen.tsx`; `T19` depends on `T18` since it targets the `/tickets` path `T18` registers).

## Risk Realism

No gap found. Risk 1 directly addresses this story's frontend-track equivalent of the "concurrent-401 race" check: it instructs `frontend-builder` not to touch `performRequest`'s/`parseResponse`'s existing 401→refresh→retry behavior while adding the `Idempotency-Key`/`Retry-After` extensions, preserving US-5.1's existing single-in-flight-refresh coordinator untouched, and explicitly notes this risk is "unchanged by OD-1's resolution." Risk 4 covers FR-9's fail-closed, customer-facing security surface (no `resolve` key, unrecognized status defaults to zero actions). Risk 5 covers OD-6's key-rotation logic as "the most behaviorally subtle piece of new client state ... even though OD-6 is now resolved," naming three required test cases. Risks 6/7 cover the two already-shipped-US-5.1-file ripples (`PlaceholderHomeScreen.tsx` deletion, `MfaEnrollmentBanner.tsx` relocation). Risks 2/3/8/9 (URL-param test-harness gap, first cursor-pagination precedent, pre-existing styling-layer gap, route-ranking dependency) are each concrete and file-specific, none a generic "testing will catch issues" placeholder.

## Test-Strategy Realism

No gap found. The Testing Strategy explicitly separates Unit (Vitest: `httpPost`'s new option, `parseResponse`'s 429 gate, `getRetryAfterSeconds`, `offeredActionsForStatus`, `useCreateTicket.ts`'s three-case key lifecycle) from Integration (RTL + MSW, one module per screen), per `AGENTS.md` §5's Frontend subsection. Each of TK-AC1–TK-AC14 plus the plain-text-rendering and a11y bars maps to a specific test file and assertion. The task breakdown's per-task Verification Command column repeats the same specificity (e.g. T8's three named key-lifecycle assertions, T15's table-driven `offeredActionsForStatus` test "over all five known statuses and at least one unrecognized value").

## Scope Creep

None blocking. Two Low items recorded for traceability, carried forward unchanged from the v1 review since neither is affected by the OD resolutions:

- **[Low] `hooks/useRetryAfterCountdown.ts`** is not individually named in `impact_analysis`'s `hooks/` layer table (which listed six hooks; the plan adds a seventh). It is directly traceable to FR-12/TK-AC12's requirement that both `NewTicketScreen.tsx` and `TicketDetailScreen.tsx`'s reply composer show an identical countdown — the plan states the shared-hook rationale explicitly rather than inventing new scope.
- **[Low] `frontend/src/components/apiErrorHelpers.test.ts`** is touched by `T3` but was not individually named in `impact_analysis`'s "Existing test files that must change" list (only `httpClient.test.ts` and `errorNormalization.test.ts` were named there, though `apiErrorHelpers.ts` itself was correctly flagged as affected). The plan/task breakdown correctly infer the test file must gain a case for `getRetryAfterSeconds`, per `AGENTS.md` §5's Frontend pairing rule — a minor gap in `impact_analysis`'s own enumeration that this plan closed rather than propagated.

## Verdict Rationale

PASS: every `impact_analysis` item has full coverage in the plan's Files To Create/Modify/Delete, the task breakdown's ordering has no layering violation against `AGENTS.md` §3's Frontend subsection, the Risks section concretely addresses the frontend-track equivalent of concurrency/blast-radius hazards, the Testing Strategy names a concrete unit-vs-integration split per AC, and — the specific defect that sent v1 back at `HUMAN_PLAN_APPROVAL` — all six OD-1..OD-6 resolutions are verified above as stated in v2 as firm, delivered architecture rather than hedged or provisional language. The two Low-severity scope notes are informational only and do not change the verdict.
