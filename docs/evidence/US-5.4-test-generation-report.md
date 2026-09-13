---
artifact_type: test_generation_report
story: US-5.4
version: 1
status: DRAFT
created_at: "2026-09-13T20:00:00Z"
updated_at: "2026-09-13T20:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.4-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.4-plan-review.md
    version: 2
supersedes: null
---

# Test Generation Report: Admin Console — Frontend (US-5.4)

## Headline: zero test source files written by this pass, by design

Unlike `US-5.1`/`US-5.2`/`US-5.3`, **this pass writes no file under
`frontend/src/`.** `docs/plans/US-5.4-task-breakdown.md` v2's own header
states, for this Story specifically, that `IMPLEMENTATION` runs exactly one
execution skill (`frontend-builder`), which "writes the paired `*.test.ts(x)`
file together with each production file," and that this stage's output is
"guidance documents `frontend-builder` consumes, not test code it hands off."
The task's own explicit constraint for this run is consistent: only the three
documents this stage owns (`test_strategy`, `ac_test_matrix`,
`test_generation_report`) were produced or touched. No file under
`docs/specifications/`, `docs/plans/`, `docs/impact-analysis/`,
`docs/reviews/`, `docs/workflow/`, or `docs/catalog/` was read-then-modified;
those were read only as inputs.

What was generated instead: two guidance documents naming every test
`frontend-builder` must write, plus this report.

## What was generated

| File | Status | Content |
|---|---|---|
| `docs/tests/US-5.4-test-strategy.md` | New (v1) | Unit/integration split, 15 collaborator-shape decisions (including the AD-AC7 static-assertion mechanism this stage was explicitly asked to settle), statement-count-ceiling equivalent, coverage floor, one non-blocking-finding closure, three recorded known gaps. |
| `docs/tests/US-5.4-ac-test-matrix.md` | New (v1) | 12 AC rows (AD-AC1–8, XC-AC1–4), each with ≥1 prescribed test function; plus five non-AC sections (`httpPut` wrapper, `decodeTokenScopes`, routing, per-screen loading state, console hygiene) and the a11y `[gate]` row for the three named screens. |
| `docs/evidence/US-5.4-test-generation-report.md` | New (v1, this file) | This report. |

### Prescribed test-function count (by file `frontend-builder` will create/edit)

| File | New/Additive | Prescribed test functions |
|---|---|---|
| `frontend/src/hooks/useAdminUsers.test.ts` | New | 4 |
| `frontend/src/hooks/useAdminUser.test.ts` | New | 3 |
| `frontend/src/hooks/useCreateAdminUser.test.ts` | New | 3 |
| `frontend/src/hooks/useUpdateAdminUser.test.ts` | New | 4 |
| `frontend/src/hooks/useAdminRoles.test.ts` | New | 2 |
| `frontend/src/hooks/useReplaceUserRoles.test.ts` | New | 2 |
| `frontend/src/hooks/useDeactivateAdminUser.test.ts` | New | 2 |
| `frontend/src/hooks/useResendInvite.test.ts` | New | 1 |
| `frontend/src/hooks/useAuditLogs.test.ts` | New | 4 |
| `frontend/src/store/decodeTokenScopes.test.ts` | New | 3 |
| `frontend/src/api/adminApi.test.ts` | New | 3 |
| `frontend/src/api/httpClient.test.ts` | Additive | 1 |
| `frontend/src/screens/AdminUserListScreen.test.tsx` | New | 12 |
| `frontend/src/screens/AdminUserCreateScreen.test.tsx` | New | 9 |
| `frontend/src/screens/AdminUserDetailScreen.test.tsx` | New | 21 |
| `frontend/src/screens/AdminAuditLogScreen.test.tsx` | New | 13 |
| `frontend/src/layouts/AppShell.test.tsx` | Additive | 3 |
| `frontend/src/routes/AppRoutes.test.tsx` | Additive | 8 |
| **Total** | 15 new files, 3 additive | **98** |

`frontend/src/test/test-utils.tsx` and `frontend/src/test/mswHandlers.ts` are
Tasks T6/T7's own deliverables on this Story (`frontend-builder`'s territory,
per `task_breakdown` v2 — unlike the US-5.1 precedent, where `test-writer`
wrote them). This pass specifies their required shape
(`docs/tests/US-5.4-test-strategy.md`'s collaborator-shape items 10/14 and the
"Unit vs. integration split" section's handler-shape note) without writing
either file.

## AD-AC7's deferred mechanism — settled by this pass, not re-deferred

`task_breakdown` v2's "Open Items Carried Forward" and
`docs/workflow/workflow-state.yaml`'s non-blocking finding both name this as
an explicit, intentional deferral to this stage: "the exact mechanism is
`test-writer`'s call, not resolved here." This pass resolves it:

- **Primary proof, static and source-wide:** `api/adminApi.test.ts::test_no_frontend_source_file_calls_http_delete_against_the_admin_users_path`,
  using Vite's `import.meta.glob("/src/**/*.{ts,tsx}", { eager: true, query:
  "?raw", import: "default" })` against the raw source text of every file
  under `frontend/src`. This is a build-time source-text map (resolved by
  Vite's transform pipeline), not a `node:fs` read, so it executes correctly
  under this project's `jsdom` Vitest environment
  (`frontend/vite.config.ts`, `test.environment: "jsdom"`) where a plain
  `fs.readFileSync` would not resolve relative source paths the way a Node
  test runner's would. This is the only mechanism among the three that can
  actually prove the AC's literal "anywhere" — an MSW-handler-absence check
  or a per-screen render assertion can only prove absence in the paths a
  given test happens to exercise.
- **Structural backstop:** `api/adminApi.test.ts::test_admin_api_ts_does_not_export_a_delete_user_function`.
- **Screen-level backstop (regression guard, not an "anywhere" proof):**
  `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_never_renders_a_delete_control`.

`frontend-builder` must create `frontend/src/api/adminApi.test.ts` as part of
Task T5 (`adminApi.ts`) even though `task_breakdown` v2's own "Files Touched"
column for T5 does not list a paired test file — this pass adds that pairing
explicitly, the same kind of collaborator-shape gap-fill `US-5.3`'s test
strategy recorded for `offeredActionsForStatus`'s required named export.

## Self-check performed (skill Completion Criteria, adapted to this stage's guidance-only output)

- **Every AC has ≥1 row:** confirmed by direct count against
  `docs/tests/US-5.4-ac-test-matrix.md` — AD-AC1 through AD-AC8 (8 rows) and
  XC-AC1 through XC-AC4 (4 rows), 12 of 12, each with at least one prescribed
  test function. 0 gaps.
- **No forbidden mock prescribed:** every hook-level assertion in
  `docs/tests/US-5.4-test-strategy.md`'s Collaborator-shape section and every
  test name in the matrix routes network behavior through MSW; no
  `vi.mock()` on a unit-under-test is named or implied anywhere in either
  document.
- **No artifact this stage does not own was modified:** confirmed by this
  run touching exactly three paths, all under `docs/tests/` and
  `docs/evidence/`, matching `docs/workflow/artifact-paths.yaml`'s owner
  entries for `test_strategy`/`ac_test_matrix`/`test_generation_report`.
  `docs/workflow/workflow-state.yaml`, `docs/workflow/active-story.yaml`,
  `docs/workflow/history.jsonl`, and `docs/catalog/US-5.4-pipeline-status.md`
  were not written.
- **Active-story / workflow-state agreement (harness precondition):**
  `docs/workflow/active-story.yaml` (`active_story: US-5.4`) and
  `docs/workflow/workflow-state.yaml` (`story: US-5.4`,
  `current_stage: TEST_WRITING`) agree. Checked directly, not assumed.
- **Input currency:** every input this stage's `inputs` block records
  (`specification` v2, `impact_analysis` v2, `implementation_plan` v2,
  `task_breakdown` v2, `plan_review` v2) matches the version actually on disk
  at read time and none is `SUPERSEDED`/`ARCHIVED`. `plan_review` v2's own
  verdict is `PASS` with no blocking issues. `api_design`/`openapi`/
  `database_design`/`entity_model` are correctly omitted — both design
  stages recorded `NOT_APPLICABLE`.
- **No `TODO`/`TBD`/`FIXME`/unresolved blocking Open Decision:** a sweep of
  specification v2 (this stage's `APPROVED`-status input) found none;
  OD-1–OD-4 are `RESOLVED` in `docs/decisions/US-5.4-open-decisions.md` v2 and
  incorporated into the spec directly.
- **Matrix-vs-strategy consistency:** every collaborator-shape decision in
  the strategy document that implies a named test (the `ETag` per-user-id
  key, the Gained/Lost reordered-seed case, the frozen-clock default window,
  the verbatim-render case, the stable synthetic row key, the AD-AC7
  three-part mechanism) has a corresponding row in the matrix; none was
  named in one document and silently dropped from the other.

## Known limitation this pass records rather than obscures

Every test function name in `docs/tests/US-5.4-ac-test-matrix.md` is a
**specification for `frontend-builder`**, not evidence a test exists, passes,
or was even parsed by a test runner. No `npx vitest run`, no lint, no
type-check, no coverage number is reported here — there is no test source and
no implementation source for either to run against. This is the correct
state for this stage under this Story's approved division of labor (unlike
`US-5.1`/`US-5.2`/`US-5.3`'s RED-state-but-collected-by-the-runner reports),
not an omission. The runnable-and-green proof moves to `QUALITY_GATE`
(`task_breakdown` v2 Task T23) once `frontend-builder` has created the files
this report names.

## Gaps Not Covered

None at the AC level (see `docs/tests/US-5.4-ac-test-matrix.md`'s own "Gaps
Not Covered" section, which is empty). Three items are recorded as
deliberately out of Vitest's reach rather than silently dropped
(`docs/tests/US-5.4-test-strategy.md`'s "Known gaps" section): the
production-build-specific half of the console-hygiene NFR, the
responsive/viewport NFR, and `AdminUserCreateScreen`'s exclusion from the
a11y `[gate]` (the Enforcement Matrix names only three screens for that
check, not four).
