---
artifact_type: plan_review
story: US-5.4
version: 2
status: DRAFT
created_at: "2026-09-13T18:30:00Z"
updated_at: "2026-09-13T18:30:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.4-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.4-task-breakdown.md
    version: 2
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
supersedes: docs/reviews/plans/US-5.4-plan-review.md (v1)
---

# Plan Review: Admin Console (Frontend)

**Story ID:** US-5.4
**Plan Reviewed:** docs/plans/US-5.4-implementation-plan.md (v2)
**Task Breakdown Reviewed:** docs/plans/US-5.4-task-breakdown.md (v2)
**Reviewed:** 2026-09-13
**Overall Verdict:** PASS

## Summary

This is a re-review of implementation plan v2 and task breakdown v2, following v1's `BLOCKED`
verdict (`docs/reviews/plans/US-5.4-plan-review.md`, v1) against a specification that still
carried OD-1–OD-4 as unresolved Open Questions while the task breakdown tied them directly to
T16/T19/T20/T21. This review independently re-verified the framing given, rather than taking it
on faith — see "Closing v1's Blocking Issues" below. Confirmed directly: specification v2's Open
Questions section reads "None," `docs/decisions/US-5.4-open-decisions.md` v2 records OD-1–OD-4 as
`RESOLVED` with an explicit `Source: human decision, 2026-09-13` on each, specification-review v2
independently re-verified the code/contract citations behind each resolution and returned `PASS`,
and task breakdown v2's T16, T19, T20, T21 now state the resolved behavior directly (e.g. T16's
"asserting **Resolution OD-1**'s default window... computed exactly once") with no remaining
"Blocked on OD-X" language anywhere in the document. No mandatory input is missing or stale: every
input this review consumed is the current, non-superseded version, and every artifact's own
`inputs` block records the matching v2 versions of its own upstream dependencies. Full
impact-analysis coverage holds (the affected-file set is unchanged from v1 per impact analysis
v2 §5 "Delta From v1: No file added or removed"), no task-breakdown layering violation was found,
the plan's Risks section is concrete and specifically addresses the new OD-driven testability
hazards (clock-dependence, set-order-insensitivity), and the Testing Strategy names per-AC
assertions concretely. One non-blocking gap (an `authStore.tsx` unit-test coverage choice)
carries forward unchanged from v1. Verdict: **PASS**.

## Closing v1's Blocking Issues

| v1 Blocking Issue | v2 status, with evidence |
|---|---|
| #1 Unresolved Open Decisions in an `APPROVED` input | Specification v2's Open Questions section: "None. All four Open Decisions raised by `us-clarifier`... have been resolved by explicit human decision on 2026-09-13." `docs/decisions/US-5.4-open-decisions.md` v2 marks OD-1 through OD-4 each `RESOLVED`, each with its own `Source: human decision, 2026-09-13` line. Closed. |
| #2 Task breakdown itself named the block (T16/T19/T20/T21 "Blocked on OD-X") | Re-read directly: none of T16, T19, T20, T21 in task breakdown v2 contains "Blocked on OD" anywhere. T16 states "asserting **Resolution OD-1**'s default window... computed exactly once"; T19 states "per **Resolution OD-4**, that the `roles` control's selectable options are sourced only from `useAdminRoles.ts`"; T20 states "per **Resolution OD-3**, a dedicated case... asserting: the role control is a target-*replacement* multi-select..."; T21 states "per **Resolution OD-1**... render **visibly pre-filled**... per **Resolution OD-2**, the `event` filter renders as a plain free-text `<input>`." Each names the resolved requirement, not an open question. Closed. |
| #3 OD-1 is a hard functional blocker (`422 range-too-wide` without both bounds) | Resolution OD-1 (`docs/decisions/US-5.4-open-decisions.md` v2): default window `from = now − 7 days`, `to = now`, both visibly pre-filled — satisfies the backend's both-bounds requirement on the very first render. Specification v2 FR-8 and implementation plan v2 (Files To Create, `useAuditLogs.ts`; Risk 5) both carry this default explicitly, and task breakdown T16/T21 test it with the system clock frozen. Closed. |
| #4 Root-cause inconsistency (spec `APPROVED` while decisions doc still `DRAFT`/`OPEN`) | Confirmed resolved, not merely asserted: specification v2's own revision note states `HUMAN_SPEC_APPROVAL` was re-run for this version (consistent with `docs/reviews/specifications/US-5.4-spec-review.md` v2's `status: APPROVED`, `verdict: PASS`), and `docs/decisions/US-5.4-open-decisions.md` v2 (`status: DRAFT` — expected, since `open_decisions` is never a target of any `human_gate`'s `required_artifacts` in `stage-map.yaml`) carries the actual resolution content with citations independently re-verified by spec-review v2. No inconsistency remains. Closed. |

A mechanical `TODO`/`TBD`/`FIXME`/`???` sweep of specification v2 and specification-review v2
(the two `APPROVED` inputs this stage's harness precondition names) found no matches.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `frontend/src/api/types.ts` (modify) | Covered | Files To Modify | New DTOs for all nine endpoints listed 1:1 with impact analysis; `AdminUserRead.status`/`.roles` stay plain `string`/`string[]` per Architectural Change 6. |
| `frontend/src/api/adminApi.ts` (new) | Covered | Files To Create | Nine typed functions named explicitly; `listAuditLogs`'s parameter key confirmed literally `from` (T5's verification command). |
| `frontend/src/api/httpClient.ts` (modify) | Covered | Files To Modify | `httpPut<T>()` addition, same shape as `httpPatch`. |
| `frontend/src/api/errorNormalization.ts` (checked, not modified) | Covered | "Files To Modify" closing note | Plan explicitly concurs with impact analysis's "no change needed." |
| `frontend/src/store/authStore.tsx` (modify) | Covered | Files To Modify; Architectural Change 1 | `scopes` field, decode-on-`SET_SESSION`/`TOKEN_REFRESHED`, reset on `CLEAR_SESSION`. |
| `frontend/src/store/decodeTokenScopes.ts` (new) | Covered | Files To Create; Architectural Change 1 | Pure decode-only helper, matches impact analysis's naming caveat. |
| `frontend/package.json` (flagged, not necessarily modified) | Covered | Files To Modify (closing note); Risk 1 | Risk 1 closes this decision explicitly in favor of a hand-rolled decoder (no dependency added); task breakdown T3 confirms the choice was implemented, so the file is untouched. |
| `frontend/src/routes/AppRoutes.tsx` (modify) | Covered | Files To Modify | Four new routes inside the existing `<ProtectedRoute>` group. |
| `frontend/src/routes/ProtectedRoute.tsx` (checked, not modified) | Covered | "Files To Modify" closing note; Architectural Change 4; Risk 2 | Plan explicitly keeps this file auth-only, matching XC-AC1's second `Given`; T22's `git diff --stat` verification command enforces it stays untouched. |
| `frontend/src/layouts/AppShell.tsx` (modify) | Covered | Files To Modify | Two conditionally-rendered nav links gated on `scopes`. |
| `frontend/src/hooks/useAdminUsers.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useAdminUser.ts` (new) | Covered | Files To Create; Risk 4 | Per-user-id `ETag` key generalization named explicitly; T9's user-A-vs-user-B test enforces it. |
| `frontend/src/hooks/useCreateAdminUser.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useUpdateAdminUser.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useAdminRoles.ts` (new) | Covered | Files To Create | Shared, unconditional catalogue query (Resolutions OD-3/OD-4); T10 asserts it is the single unconditional source for both T19 and T20. |
| `frontend/src/hooks/useReplaceUserRoles.ts` (new) | Covered | Files To Create; Architectural Change 3 | |
| `frontend/src/hooks/useDeactivateAdminUser.ts` (new) | Covered | Files To Create; Architectural Change 3 | |
| `frontend/src/hooks/useResendInvite.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useAuditLogs.ts` (new) | Covered | Files To Create; Risk 5 | **Resolution OD-1 now stated directly**: computes the default 7-day window once, hands it to the screen for visible pre-fill; T16 tests it with the clock frozen. |
| `frontend/src/screens/AdminUserListScreen.tsx` (new) | Covered | Files To Create; Risk 7 | Unrecognized `status`/`roles` verbatim-render rule named explicitly; T18 tests it. |
| `frontend/src/screens/AdminUserCreateScreen.tsx` (new) | Covered | Files To Create | **Resolution OD-4 now stated directly**: `roles` sourced only from `useAdminRoles.ts`, no free text; T19 tests it. |
| `frontend/src/screens/AdminUserDetailScreen.tsx` (new) | Covered | Files To Create; Risk 6 | **Resolution OD-3 now stated directly**: target-replacement multi-select, Gained/Lost diff via order-insensitive set comparison, Save disabled when unchanged; T20 tests it, including a case with the catalogue and current-role orders deliberately mismatched. |
| `frontend/src/screens/AdminAuditLogScreen.tsx` (new) | Covered | Files To Create; Risk 5, Risk 7 | **Resolutions OD-1 and OD-2 now stated directly**: visible 7-day pre-fill (clock frozen for the test) and a free-text `event` input; stable synthetic row-key rule also named; T21 tests all of it. |
| `frontend/src/layouts/AppShell.test.tsx` (modify) | Covered | Files To Modify | |
| `frontend/src/routes/AppRoutes.test.tsx` (modify) | Covered | Files To Modify | |
| `frontend/src/test/test-utils.tsx` (modify) | Covered | Files To Modify | New `scopes` seeding option. |
| `frontend/src/test/mswHandlers.ts` (modify) | Covered | Files To Modify | Nine new handlers, including `ETag` on `GET /admin/users/:id`. |
| `frontend/src/api/httpClient.test.ts` (modify) | Covered | Files To Modify | |
| New test files (screens/hooks/`decodeTokenScopes.test.ts`) | Covered | "Test files paired 1:1..." row; Testing Strategy | |
| a11y pass (axe) on 3 named screens | Covered | Testing Strategy, final bullet; Risk 8 | |
| AD-AC7 no-`DELETE` static/unit assertion | Covered (mechanism deferred) | Testing Strategy; task breakdown "Open Items Carried Forward" | Unchanged from v1: the impact analysis itself left the exact mechanism to `test-writer`, and the plan/task-breakdown do not silently drop it — both explicitly name it still-open as to mechanism only, not as to whether it happens. |

No impact-analysis item is Missing or Partially Covered. Impact analysis v2 §5 ("Delta From v1")
confirms the affected-file set itself is unchanged from v1 — the only deltas are the four
resolved behaviors now landing as concrete requirements within files v1 already identified, which
this table's updated Notes column reflects.

## Layering Order (Task Breakdown)

No violation found. T1–T3 (`api/types.ts`, `api/httpClient.ts`, `store/decodeTokenScopes.ts`)
have no dependencies and run first; T4 (`store/authStore.tsx`) correctly depends on T3; T5
(`api/adminApi.ts`) correctly depends on T1/T2; the entire `hooks/` block (T8–T16) depends on
T5/T7 (`api/` + test infra), never the reverse; `screens/` (T18–T21) depend only on their
specific hooks and test infra, and never import `api/` directly (enforced by each task's own
`grep` verification command); `routes/AppRoutes.tsx` (T22) is sequenced last, after all four
screens it registers, and its verification command confirms `routes/ProtectedRoute.tsx` stays
untouched. This sequencing is unchanged from v1's already-correct ordering — the task
breakdown's own revision note states "No task is added, removed, or reordered relative to v1
beyond [T16/T19/T20/T21's content]," independently confirmed by re-reading the `Depends On`
column, which matches v1's dependency graph exactly.

The task breakdown's own note that `store/` (T3–T4) is sequenced ahead of the `hooks/` block as
"a sequencing floor, not skipped because no hook happens to need it yet" is a correct,
conservative reading of the ordering rule, not a violation. T17 (`AppShell.tsx`, mapped to the
`routes/` guards+layout row) depending only on T4/T6 rather than any hook is consistent with the
layer table — `AppShell.tsx` reads `scopes` directly off the store and never calls a hook. See
Non-Blocking Findings for a note on this same ordering-floor principle being applied only in one
direction.

## Risk Realism

The plan's Risks section (8 items, renumbered from v1's 7 — v1's single "four Open Decisions"
risk item is gone, replaced by two OD-specific testability risks) is concrete and specific, not a
placeholder:
- Risk 1 (dependency choice) is now **closed**, not merely flagged: a hand-rolled decoder is
  chosen explicitly, with the `package.json`/§7.8 sign-off consequence stated and confirmed by
  T3/the Protected-File Check section.
- Risk 2 (client-decoded scopes must never become a real authorization boundary) identifies a
  specific, plausible implementation-drift failure mode (an implementer "helpfully" adding scope
  checks to `ProtectedRoute.tsx`) and names the concrete mitigation (that file stays unmodified,
  enforced by T22's `git diff --stat` verification command).
- Risk 4 (`ETag` key generalization from a fixed key to a per-user-id key) correctly identifies
  this as "the direct frontend analogue of a migration hazard" and is backed by a named test
  (T9's user-A-vs-user-B assertion).
- Risk 5 (Resolution OD-1's `now`-dependent default window) and Risk 6 (Resolution OD-3's
  order-insensitive set-comparison requirement) are new in this revision, each traced directly to
  one of the two resolutions the task breakdown's own T16/T21 and T20 now implement, and each
  names a concrete test technique (frozen system clock; sorted-array/`Set` equality with a
  deliberately reordered seed) rather than a generic "will be tested" placeholder.
- Risk 7 folds together the two "binding via Client State Notes but not literally required by any
  AC" behaviors (unrecognized `status`/`roles` rendering; synthetic audit row-key stability) with
  a newly-resolved ambiguity from spec-review v2 (FR-4's dead-ending "(see FR-5)" pointer for
  `immutable-field`) — the plan resolves that pointer directly rather than carrying it forward as
  an open ambiguity, citing the story's own Assumption #5.
- Risk 8 (a11y/responsive bar against no existing styling layer) is honestly scoped as inherited,
  not introduced, by this Story.

No gap found against this skill's frontend checklist item (the concurrent-401/single-in-flight-
refresh race): this Story introduces no new token-refresh logic — `scopes` derivation piggybacks
on the `SET_SESSION`/`TOKEN_REFRESHED` actions US-5.1/5.2 already established — so the race is out
of this Story's blast radius, unchanged from v1's conclusion (FR-9 did not change between spec v1
and v2).

## Test-Strategy Realism

The Testing Strategy concretely splits Unit (Vitest, no network) from Integration (RTL + MSW),
names the specific hook/screen files in each bucket, and maps every AC to a specific assertion —
including the two now-resolved-OD assertions added in this revision: "`useAuditLogs.test.ts`
freezes the system clock (Risk 5) before asserting the computed default `from`/`to` values" and
the Gained/Lost role-set assertion "using seed data whose current-role order differs from the
catalogue's order (Risk 6)." This is not vague.

One non-blocking gap (see Non-Blocking Findings below, carried forward unchanged from v1): T4
(`authStore.tsx`) still has no dedicated unit test for its three new reducer branches.

## Scope Creep

None found. Every file in the plan's Files To Create/Modify traces to the impact analysis; no
task in the breakdown lacks a `Files Touched` entry the impact analysis didn't already name.
FR-3's catalogue-driven role picker, FR-5's multi-select/gained-lost-diff/disable-if-unchanged
logic, and FR-8's default window/free-text filter — all newly concrete in this revision — are
each traced to a human-supplied Resolution recorded in `docs/decisions/US-5.4-open-decisions.md`
v2, the sanctioned mechanism for closing an Open Decision, not an invented requirement.

## Non-Blocking Findings

- **[Medium] `authStore.tsx`'s new reducer branches have no dedicated unit test.** Carried
  forward unchanged from v1. Task breakdown T4 explicitly relies on T17's seeded-`scopes`
  assertions (`AppShell.test.tsx`) plus the 85% coverage floor to exercise the three new branches
  (`scopes` set on `SET_SESSION`/`TOKEN_REFRESHED`, reset to `[]` on `CLEAR_SESSION`) rather than
  a dedicated `authStore.test.tsx`. The `CLEAR_SESSION` → `scopes: []` reset is the branch least
  likely to be exercised incidentally by a nav-rendering test. Worth a direct assertion, not
  required to block this stage.
- **[Low] The `store/`-before-`hooks/` ordering floor is applied asymmetrically to the
  `hooks/`-before-`routes/` boundary.** The task breakdown states explicitly that `store/`
  (T3–T4) is sequenced ahead of the entire `hooks/` block "as a sequencing floor, not skipped
  because no hook happens to need it yet," but T17 (`AppShell.tsx`, the `routes/` guards+layout
  row) is scheduled in the same parallel-eligible batch as the `hooks/` block (T8–T11, T15–T17)
  rather than strictly after it, because `AppShell.tsx` reads `scopes` directly off the store and
  happens not to need any hook. This is not a violation — no task depends on a layer built after
  it, since T17's actual dependencies (T4, T6) are satisfied — but the "floor, not skipped"
  principle applied consistently would put `routes/` (guards+layout) strictly after `hooks/` too,
  the same conservative stance taken for `store/`. Not required to block this stage.

## Verdict Rationale

Full impact-analysis coverage holds (the affected-file set is unchanged from v1, now carrying
concrete resolved behavior instead of Open-Decision placeholders in T16/T19/T20/T21), the task
breakdown's ordering is unchanged from v1's already-correct sequencing, the plan's Risks section
concretely addresses the two new OD-driven testability hazards this revision introduces, and the
Testing Strategy names specific per-AC assertions rather than vague coverage claims. No scope
creep was found. All four of v1's Blocking Issues are independently confirmed closed with
citations (see "Closing v1's Blocking Issues" above), and no unresolved blocking Open Decision
remains in any `APPROVED` input this stage consumed. One Medium and one Low non-blocking finding
are carried/noted but neither reflects missing impact-analysis coverage nor a layering violation,
so neither forces anything other than `PASS`.
