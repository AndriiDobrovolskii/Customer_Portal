---
artifact_type: plan_review
story: US-5.6
version: 1
status: APPROVED
created_at: "2026-09-15T13:00:00Z"
updated_at: "2026-09-15T14:15:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.6-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-5.6-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.6-task-breakdown.md
    version: 1
  - path: docs/decisions/US-5.6-open-decisions.md
    version: 2
supersedes: null
---

# Plan Review: Global Navigation

**Story ID:** US-5.6
**Plan Reviewed:** docs/plans/US-5.6-implementation-plan.md (version 1)
**Task Breakdown Reviewed:** docs/plans/US-5.6-task-breakdown.md (version 1)
**Reviewed:** 2026-09-15
**Overall Verdict:** PASS

## Summary

Reviewed `implementation-plan` v1 and `task-breakdown` v1 for US-5.6 (Global Navigation, `track: frontend`) against `specification` v2, `impact-analysis` v1, and `open-decisions` v2 (API/DB design and design review are both `NOT_APPLICABLE` for this Story, confirmed unchanged). Every file the impact analysis named — production and test — has a corresponding, correctly-attributed row in the plan's Files To Modify and the task breakdown's task table; the task sequence (T1 production+tests → T2 test-only floor → T3 gate) has no ordering violation against `AGENTS.md` §3's Frontend layer table; the plan's Risks and Testing Strategy sections are concrete and tied to specific hazards (the Home/Tickets active-state collision, OD-2/OD-4's edge cases, the GN-AC6 cross-check's scope-coverage requirement) rather than generic placeholders; and no planned change or task lacks a traceable FR/AC origin — the plan explicitly rejects the one place scope could have crept (a shared route-path constants module) with a cited rationale. Independent spot-checks against the actual `AppShell.tsx`, `AppRoutes.tsx`, `AppShell.test.tsx`, `AppRoutes.test.tsx`, and `mswHandlers.ts` corroborate the plan's and impact analysis's factual claims (route registrations, existing test names/lines, MSW baseline coverage). Verdict: **PASS**, no Critical or Major findings.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `frontend/src/layouts/AppShell.tsx` (Modify — FR-2, FR-4, FR-5) | Covered | Files To Modify row 1; Architectural Changes 1–3 | Four new ungated `NavLink` entries, Home as plain `Link`, `Link`→`NavLink` swap on every other entry. Verified against current `AppShell.tsx`: today all entries are plain `Link`, no `aria-current` set — consistent with the plan's Risk 4 claim. |
| `frontend/src/routes/AppRoutes.tsx` (No change — verification only) | Covered | Files To Modify note ("No change to `frontend/src/routes/AppRoutes.tsx`"); Architectural Change 5 | Independently re-verified: lines 87–111 already register `/tickets`, `/sessions`, `/settings/profile`, `/settings/security`, `/settings/deactivate` inside the `ProtectedRoute`/`AppShell` group with auth-only gating. |
| §1a Checked-Not-Affected: `LogoutControls.tsx`, `MfaEnrollmentBanner.tsx` | Covered | Files To Modify note ("No change to ... `LogoutControls.tsx`/`MfaEnrollmentBanner.tsx`") | Plan affirms these stay untouched, matching the NFR constraint. |
| §1a Checked-Not-Affected: `store/authStore.tsx`, `store/decodeTokenScopes.ts` | Covered | Files To Modify note; Architectural Changes 1/3 (`useAuthStore()` usage unchanged) | No new scope constant introduced, matching impact analysis. |
| §1a Checked-Not-Affected: `frontend/src/hooks/*`, `frontend/src/api/*` | Covered | Validation Strategy ("no new `api/` or `hooks/` import is introduced") | Task T1's Verification Command adds an explicit `grep` check for this — stronger than the plan's prose alone. |
| §1a Checked-Not-Affected: `frontend/src/test/test-utils.tsx` | Covered | Files To Modify note | No new seed option needed; plan states this explicitly. |
| §1a Checked-Not-Affected: any backend `app/` file | Covered | Goal section, Migration/Schema-equivalent statement | Plan reiterates `NOT_APPLICABLE` API/DB impact. |
| Cross-Module Ripple: None | Covered | Architectural Changes 1–3 (single-file change) | Consistent — no new cross-module import direction introduced. |
| Migration/Schema Impact: None | Covered | Goal section | Consistent. |
| Test-Surface: `frontend/src/layouts/AppShell.test.tsx` (Modify) | Covered | Files To Modify row 2; Testing Strategy | All five sub-items (a)–(g) from the impact analysis (zero-scope extension, new-entry assertions, Home click, active-state, GN-AC6 cross-check, axe, a11y-keyboard) are individually itemized in the plan and in Task T1's Verification Command. |
| Test-Surface: `frontend/src/routes/AppRoutes.test.tsx` (Modify) | Covered | Files To Modify row 3; Testing Strategy | Matches impact analysis's GN-AC1/GN-AC3 click-through requirement; independently verified this file already renders the full route tree via `renderWithProviders` (existing pattern, e.g. line 30). |
| Test-Surface: "New test files: None required" | Covered | Files To Create: "None"; Testing Strategy closing bullet | Matches exactly. |
| Non-Blocking Finding: route-path duplication is pre-existing | Covered | Architectural Change 4 | Plan explicitly rejects introducing a shared route-path constants module, with a cited rationale (§7.8 opportunistic-refactor ban, FR-6 is a verification not a production requirement, US-5.5 precedent) rather than silently ignoring the note. |
| Notes for Downstream Stages: Home's markup left open | Covered | Architectural Change 2 | Plan makes the call explicitly (plain `Link`, not `NavLink`/`<button>`) with stated rationale. |

<!-- Every item in impact-analysis.md §1, §1a, §2, §3, §4, Non-Blocking Findings, and Notes for Downstream Stages is accounted for above. -->

## Layering Order (Task Breakdown)

No ordering issue found. `AppShell.tsx` is attributed to the `routes/` (guards + layout) row of `AGENTS.md` §3's Frontend table — consistent with the same attribution used by `US-5.4`/`US-5.5`'s task breakdowns for this same file, and independently confirmed the file's only import beyond `react-router-dom` is `store/authStore` (read-only) plus two `components/` — no `hooks/`/`api/` import is added, so the layer table's "must not import `api/` directly" constraint for this row holds. T1 (production `AppShell.tsx` + its test file) precedes T2 (`AppRoutes.test.tsx`, a test-only floor dependency on T1's nav element, no production import between the two files), which precedes T3 (`gate-enforcer`). No task depends on a layer built after it; the `api/`→`store/`→`hooks/`→`routes/`/`screens/` ordering rule is vacuous here since no `api/`, `store/`, or `hooks/` file changes, exactly as the task breakdown itself states.

*(Carried forward for visibility, not a new finding: `AppShell.test.tsx`'s own header comment records that `docs/reviews/plans/US-5.1-plan-review.md` flagged which single §3 row this file's layering categorization should fall under as an open, non-blocking question — since AGENTS.md §3's Frontend table has no dedicated row for a shell that reads `store/` directly the way this one does. This Story's task breakdown repeats the same attribution prior Stories used and does not re-litigate it; it is not a layering-order violation and does not affect this Story's ordering.)*

## Risk Realism

None found requiring escalation. The plan's five Risks are concrete and each ties to a specific hazard rather than a generic placeholder: Risk 1 (Home/Tickets active-state collision from a copy-paste `Link`→`NavLink` conversion, mitigated by an explicit diff-review check plus a direct test assertion) directly addresses OD-2's resolution; Risk 2 (extend, don't rewrite, the existing zero-scope tests) heads off an `AGENTS.md` §7.7 "weakening a passing test" violation; Risk 3 (net-new `axe` wiring in this specific file) and Risk 4 (`aria-current` non-collision, independently re-verified against the current file — confirmed no existing `aria-current` usage) are both checked, not assumed; Risk 5 (the GN-AC6 cross-check must render with every scope granted or it silently skips the gated entries) is folded directly into the Verification Command. The backend-oriented risk categories this skill's process names (migration hazards, concurrency, contract-breaking changes) are correctly absent, since impact analysis, spec, and design review all confirm zero backend/API/persistence touch for this Story — there is nothing in that category to omit.

One item independently checked and found to *de-risk* the plan further than its own text states: Architectural Change 5's GN-AC6 cross-check renders `AppRoutes` at all eight collected nav `href`s inside `AppShell.test.tsx`, whose own MSW usage today is scoped only to `/auth/logout`/`/auth/logout-all`. Direct verification against `frontend/src/test/mswHandlers.ts` and the api-client modules confirms every on-mount data fetch this cross-check would trigger already has a baseline handler — `GET /support/tickets` (shared by `TicketListScreen` and `AgentTicketQueueScreen`, per `supportApi.ts`'s own comment "the agent branch of GET /support/tickets — same URL as..."), `GET /auth/sessions`, `GET /admin/users`, `GET /admin/audit-logs` — and `ProfileScreen`/`SecurityScreen`/`DeactivateAccountScreen` issue no GET on mount at all (`api/types.ts`: "no GET /profile exists yet"; `SecurityScreen`'s own MFA calls are click-triggered, not mount-triggered). So the plan's Testing Strategy phrase "MSW where a click triggers a network call" understates what this specific new case needs (it's a mount-triggered fetch across eight rendered screens, not a click), but the underlying MSW baseline this codebase already maintains covers it. Recorded as a Low, non-blocking finding below for completeness — not a gap that blocks implementation.

## Test-Strategy Realism

None found. The plan's Testing Strategy names the exact unit-vs-integration split per `AGENTS.md` §5's Frontend subsection (no new hook/API function, so no new unit-test file; both existing files stay integration-style, RTL + MSW), and lists concretely which test case covers which FR/AC/OD/Risk in each of the two files — not a vague "testing will catch issues" statement. Task T1/T2's Verification Commands name the exact `npx vitest run` invocations and the exact behavioral assertions expected, and T3 names all four `AGENTS.md` §2 load-bearing script names plus a diff-review check for the layer-table constraint.

- **[Low] Testing Strategy's MSW characterization is incomplete for the GN-AC6 cross-check.** Plan says: *"`frontend/src/layouts/AppShell.test.tsx` (integration, renders `AppShell` directly with `renderWithProviders`, MSW where a click triggers a network call)"*. This describes the file's existing pattern accurately but doesn't name that the new GN-AC6 cross-check (Files To Modify item (e)) mounts eight different screens via `AppRoutes` on render, each potentially firing its own on-mount query, rather than a click-triggered call. As verified above, this is fully covered by mswHandlers.ts's existing baseline handlers with no new handler needed — not a defect, just an incomplete restatement in the plan's own prose. Non-blocking.

## Scope Creep

None found. Every architectural change traces to a named FR (FR-2, FR-4, FR-5, FR-6) or a resolved Open Decision (OD-1 through OD-4), and every Files-To-Modify/task-breakdown row traces to a file the impact analysis already named. The one place a new file could plausibly have been introduced (a shared route-path constants module, per the impact analysis's own Notes for Downstream Stages) is explicitly considered and rejected in Architectural Change 4, with a cited rationale grounded in `AGENTS.md` §7.8's opportunistic-refactor prohibition and direct in-repo precedent (`US-5.5`'s implementation plan, Architectural Change 6) — the correct outcome given neither FR-6 nor any other FR requires a production change to how routes are declared.

## Verdict Rationale

**PASS.** Every impact-analysis item (production files, checked-not-affected files, test-surface files, and both non-blocking notes) has a corresponding Covered status in the plan and task breakdown; the task sequence introduces no layering-order violation against `AGENTS.md` §3's Frontend table; the plan's Risk and Testing Strategy sections are specific and evidence-based rather than placeholders (one Low, non-blocking completeness note recorded above, empirically checked and found not to be a real gap); and no scope creep was found — the plan's own explicit rejection of a plausible extra file demonstrates active scope discipline rather than silence. None of the conditions that force `CHANGES_REQUIRED` (missing impact-analysis coverage, a layering-order violation) are present.

## Non-Blocking Findings (carried forward / recorded for visibility)

1. **Bookkeeping mismatch in `specification_review` v1's front matter (carried forward from every prior stage this run).** `specification_review` v1 records consuming `specification`/`open_decisions` at version 1; both are now version 2. Independently assessed here, not merely deferred to: (a) this stage's own precondition is that consumed artifacts are current and non-superseded on disk — `specification_review` v1 carries `status: APPROVED` with no v2 in existence, so it is current; (b) the v1→v2 delta is exactly the write-back `specification_review` v1 itself demanded (FR-4's Boundary Condition, the `a11y-keyboard` Verification row), and `HUMAN_SPEC_APPROVAL` verified this exact pairing before approving; (c) structurally, `PLAN_REVIEW`'s only two loop-back keys (`changes_required` → `ARCHITECTURE_PLANNING`, `changes_required_sequencing` → `IMPLEMENTATION_PLANNING`) name no route back to `SPEC_REVIEW` — naming any other key would be rejected and hold this stage `BLOCKED` for a re-review no wired stage in this pipeline can trigger, over a mismatch a human gate already priced in. Recorded, not held blocking.
2. **`AppShell.tsx`'s AGENTS.md §3 layer-row categorization remains an open, non-blocking question carried from `US-5.1-plan-review.md`.** This Story's task breakdown repeats the prior Stories' attribution (`routes/` guards+layout row) without re-litigating it; it does not create or worsen a layering-order violation for this Story's own tasks.
3. **Testing Strategy's MSW description is incomplete, not incorrect, for the GN-AC6 cross-check** (detailed under Test-Strategy Realism above) — independently verified against `mswHandlers.ts` and every relevant `api/*.ts` module that the existing baseline handler set already covers all eight screens' on-mount needs, so this does not block implementation.
