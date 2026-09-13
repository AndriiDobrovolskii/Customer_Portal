---
artifact_type: test_strategy
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

# Test Strategy: Admin Console — Frontend (US-5.4)

## Track and binding context

`track: frontend` (`docs/stories/US-5.4-admin-console-ui.md` front matter).
`API_DESIGN`/`DB_DESIGN` are `NOT_APPLICABLE` for this Story (re-confirmed by
`docs/reviews/designs/US-5.4-design-review.md` v2) — the spec's own API
Contract table, cross-checked against the already-shipped US-3.1/US-3.2/US-3.3
backend, is the reference contract, per this skill's Required Context for
this track.

OD-1 through OD-4 are `RESOLVED` (`docs/decisions/US-5.4-open-decisions.md`
v2) and are incorporated directly into specification v2's FR-3/FR-5/FR-8 and
into `implementation_plan` v2 / `task_breakdown` v2 as concrete, binding
behavior (default 7-day audit window; free-text `event` filter; catalogue-only
role pickers for both create and replace; target-replacement multi-select with
a Gained/Lost confirmation diff). This pass treats all four as firm
requirements, not open questions.

## This stage's division of labor on this Story (read before the rest of this document)

**No test source file is written by this pass.** `docs/plans/US-5.4-task-breakdown.md`
v2's own header states this explicitly for this Story: `IMPLEMENTATION` runs
exactly one execution skill, `frontend-builder`, which "writes the paired
`*.test.ts(x)` file together with each production file," and `TEST_WRITING`'s
output here is "guidance documents `frontend-builder` consumes, not test code
it hands off." This is a deliberate divergence from the US-5.1/US-5.2/US-5.3
precedent (where `test-writer` did write `frontend/src/**/*.test.ts(x)` files
directly) — an approved planning decision for this Story specifically, not an
omission by this pass. Every test function name in this document and in
`docs/tests/US-5.4-ac-test-matrix.md` is therefore **prescriptive**: a binding
name and assertion `frontend-builder` must create verbatim under the file
mapping below, not a claim that the function already exists in the working
tree. `docs/evidence/US-5.4-test-generation-report.md` states this in its own
terms so no downstream reader mistakes the matrix for as-built evidence.

Reconciliation-reviewer's later check ("the referenced test function exists
and actually asserts the AC's stated behavior") is satisfiable under this
model only if `frontend-builder` adopts these names unchanged; a renamed or
reshaped test at `IMPLEMENTATION` is drift to flag at `RECONCILIATION`, not
silently accepted as equivalent.

## Unit vs. integration split (`AGENTS.md` §5 Frontend subsection)

- **Unit** (`frontend/src/hooks/*.test.ts`, `frontend/src/store/decodeTokenScopes.test.ts`,
  `frontend/src/api/httpClient.test.ts`, `frontend/src/api/adminApi.test.ts`):
  a hook or pure function in isolation, MSW as the network boundary for any
  hook that performs I/O (never a hand-mocked `fetch`), no DOM beyond what a
  bare `renderHook`/`renderHookWithProviders` needs.
- **Integration** (`frontend/src/screens/*.test.tsx`, additive cases in
  `frontend/src/layouts/AppShell.test.tsx` and `frontend/src/routes/AppRoutes.test.tsx`):
  React Testing Library renders the real screen + hooks + store tree; MSW
  intercepts every network call with a handler shaped like the real backend
  contract (status, body, `ETag` response header on `GET /admin/users/{id}`,
  `application/problem+json` content type on every 4xx, including the `412`
  conflict and `immutable-field` shapes named by the spec).

**No `vi.mock()` on the unit under test anywhere in this pass's prescriptions**
— `frontend-builder` mocks the network (MSW) only, never the
component/hook/store being tested, per `AGENTS.md` §5's explicit prohibition.
`frontend/src/test/test-utils.tsx` and `frontend/src/test/mswHandlers.ts` are
`task_breakdown` v2 Tasks T6/T7's own deliverables (`frontend-builder`'s
territory on this Story, unlike the US-5.1 precedent) — this pass specifies
what they must expose (the `scopes` seeding option; nine baseline handlers)
without writing them.

## Collaborator-shape decisions this pass fixes

No design doc exists on this track to fix an internal hook signature, a query
key, or a component's accessible name beyond `implementation_plan` v2's prose.
To write concrete, executable-when-implemented assertions, this pass fixes the
following — flagged, per the `US-5.2`/`US-5.3` precedent, as decisions for
`frontend-builder`/`reconciliation-reviewer` to check the shipped shape
against, not resolved Open Decisions:

1. **`api/adminApi.ts`'s nine function names** are taken verbatim from
   `implementation_plan` v2's Files To Create row: `listUsers`, `getUser`,
   `createUser`, `updateUser`, `deactivateUser`, `resendInvite`, `listRoles`,
   `replaceUserRoles`, `listAuditLogs`. `listAuditLogs`'s parameter object key
   for the start-of-window bound must be the literal `from` (not `from_`).
2. **`useAdminUsers.ts`** returns a bare `useInfiniteQuery` result (same shape
   as `useTickets.ts`), `queryKey: ["admin-users", q, status, role]`,
   `getNextPageParam` reading `next_cursor`.
3. **`useAdminUser.ts`** captures the `ETag` response header into a
   **per-user-id** TanStack Query cache key — `adminUserEtagQueryKey(id)` (a
   named, exported helper, not an inline literal repeated at each call site) —
   generalizing `useProfileUpdate.ts`'s single fixed `ETAG_QUERY_KEY` constant.
   `useUpdateAdminUser.ts` reads the outgoing `If-Match` from this same helper,
   never a fixed key, so Implementation Plan Risk 4's "user A's `ETag` never
   sent as `If-Match` for user B" is a namable, testable property.
4. **`useUpdateAdminUser.ts`** mirrors `useProfileUpdate.ts`'s `conflict`
   boolean state on a `412`, and additionally exposes the parsed
   `immutable-field` problem's `detail` string when present, since FR-4/FR-5
   require rendering it.
5. **`useAdminRoles.ts`** is a single unconditional `useQuery(["admin-roles"], ...)`
   with no pagination (the API Contract table's `GET /admin/roles` has no
   cursor) — the same query key is read by both `AdminUserCreateScreen.tsx`
   and `AdminUserDetailScreen.tsx`'s role control, never a per-screen copy.
6. **`useReplaceUserRoles.ts`** invalidates `useAdminUser.ts`'s query key
   (not the `ETag` cache key) for the same user id on success — targeted
   invalidation, per Implementation Plan Risk 3's preferred mitigation, not a
   hand-merged cache patch.
7. **`useDeactivateAdminUser.ts`** updates `useAdminUser.ts`'s cached
   `AdminUserRead.status` via `setQueryData` on success (not a full
   invalidate+refetch), per Risk 3 and FR-6's "the returned status is
   reflected."
8. **`useAuditLogs.ts`** computes its default `from`/`to` window (`now − 7
   days` / `now`, ISO 8601 UTC) exactly once per mount and **returns both
   values to the caller** (e.g. `{ query, defaultFrom, defaultTo }`) rather
   than only threading them silently into the query — `AdminAuditLogScreen.tsx`
   needs them to pre-fill the date-picker inputs *visibly* (Resolution OD-1).
   Every test asserting this default freezes the system clock
   (`vi.setSystemTime`) before mount, per Implementation Plan Risk 5.
9. **The Gained/Lost role diff (Resolution OD-3)** is computed via
   order-insensitive set comparison (sorted-array or `Set` equality) against
   the user's roles *as currently loaded* — `AdminUserDetailScreen.test.tsx`'s
   dedicated case seeds the current roles in a different array order than
   `GET /admin/roles` returns the catalogue, per Implementation Plan Risk 6,
   to catch a naive stringify-and-compare bug. Save is disabled exactly when
   the selected set equals the current set under this same comparison.
10. **Accessible names / control labels** (no design doc fixes UI copy;
    matchers below are case-insensitive regexes loose enough to tolerate
    minor copy differences while still pinning presence and accessible-name
    pattern, per the `US-5.2`/`US-5.3` documented matcher policy):
    - "Reason" — the required-reason field on both the field-edit and
      deactivate forms.
    - "Roles" — the multi-select on both the create-user and role-replacement
      controls.
    - "Gained roles" / "Lost roles" — the two headings the confirmation
      dialog renders.
    - "From" / "To" — the audit log's date-picker inputs.
    - "Event" — the audit log's free-text filter, placeholder matching
      `/e\.g\.|user_created|authz_denied/i`.
    - "Status" — the user list's fixed `invited`/`active`/`deactivated`
      `<select>`.
    - "Load more" — both cursor-paginated screens' pagination control (same
      label, matching `useTickets.ts`-family precedent).
    - "Save role changes" / "Deactivate" / "Resend invite" — the three
      user-detail mutation triggers.
11. **`AdminUserRead.status`/`.roles` stay plain `string`/`string[]`** (never
    a union) in `api/types.ts`; `AdminUserListScreen.test.tsx` and
    `AdminUserDetailScreen.test.tsx` each include a case seeding a value
    outside the known set and asserting it renders verbatim rather than
    being coerced or hidden (Implementation Plan Risk 7).
12. **`AuditLogEntry` has no `id`.** `AdminAuditLogScreen.tsx` must synthesize
    a stable per-row key (e.g. `occurred_at` + `request_id` + index within
    page) so a "Load more" append does not duplicate or destabilize row
    identity across pages — asserted directly (Implementation Plan Risk 7),
    not inferred from absence of a visible defect.
13. **`AppShell.tsx`'s new nav entries** read `scopes` off `useAuthStore()`
    directly (no hook call) and are gated independently per entry: "Users"
    on `users:read`, "Audit Log" on `audit:read`.
14. **XC-AC1's three seeded-token scenarios** all depend on `task_breakdown`
    v2 Task T6 landing a `scopes` option on `test-utils.tsx`'s
    `RenderWithProvidersOptions`/`buildAuthSeed()` before any test below that
    seeds `scopes` can run — named here so `frontend-builder` sequences T6
    ahead of T17–T22 exactly as the task breakdown's own dependency graph
    already requires, not merely as a lint of this pass.
15. **AD-AC7's "no control anywhere issues `DELETE /admin/users/{id}`"
    assertion mechanism** — the one item `task_breakdown` v2 left this stage
    to settle (its own "Open Items Carried Forward" and non-blocking finding
    in `docs/workflow/workflow-state.yaml`). Resolved here, not re-deferred:

    - **Primary (static, source-wide):** a new unit test file,
      `frontend/src/api/adminApi.test.ts`, uses Vite's native
      `import.meta.glob("/src/**/*.{ts,tsx}", { eager: true, query: "?raw",
      import: "default" })` (works synchronously under the project's `jsdom`
      Vitest environment — this is a build-time source-text map, not a
      runtime `node:fs` read, which would not resolve in `jsdom`) to load
      every source file's raw text and assert that no file (excluding this
      test file's own source) matches
      `/httpDelete\s*\(\s*[`'"][^`'"]*\/admin\/users[^`'"]*[`'"]/`. This is
      the only mechanism that can prove **"anywhere"** — a per-screen render
      test can only prove the absence of a control in the screens it happens
      to render, not the whole codebase.
    - **Structural backstop:** the same file asserts, via
      `import * as adminApi from "./adminApi"`, that the module never exports
      a `deleteUser` (or equivalently named) function — narrower than the
      scan above, but catches the single most likely reintroduction point
      directly by name.
    - **Screen-level backstop (not a proof of "anywhere," a regression guard
      for the one screen a delete control would plausibly appear on):**
      `AdminUserDetailScreen.test.tsx` asserts no button/link with an
      accessible name matching `/delete/i` is present anywhere in that
      screen's rendered output.

## Statement-count ceiling

Not applicable in the backend sense (`AGENTS.md` §5's SQL statement-count
ceiling is a real-database concern). This track's analogous pagination
regression guard: every cursor-paginated screen/hook test
(`AdminUserListScreen`, `AdminAuditLogScreen`, `useAdminUsers`, `useAuditLogs`)
asserts the exact MSW-observed request count and the `cursor` value carried on
each request — "Load more" issues exactly one additional request carrying the
previous page's `next_cursor` — so an accidental per-render refetch regresses
a test, not only latency.

## Coverage floor

85% via `test:coverage`, CI-enforced (`AGENTS.md` §5/§6 Frontend subsection).
Not measured by this stage — no implementation exists yet, and this stage
writes no test source either; enforced at `QUALITY_GATE` per `task_breakdown`
v2 Task T23.

## Non-blocking finding this pass closes within its remit

`docs/reviews/plans/US-5.4-plan-review.md` v2 carries forward (Medium,
unchanged from v1) that `authStore.tsx`'s three new reducer branches (`scopes`
set on `SET_SESSION`/`TOKEN_REFRESHED`, reset to `[]` on `CLEAR_SESSION`) have
no dedicated unit test, relying instead on `AppShell.test.tsx` (Task T17) plus
the 85% coverage floor. The approved plan declined a new `authStore.test.tsx`
file; this pass does not reopen that decision. It does close the specific gap
the finding names — the `CLEAR_SESSION` branch being "the branch least likely
to be exercised incidentally" — by naming a concrete `AppShell.test.tsx` case
in `docs/tests/US-5.4-ac-test-matrix.md`
(`test_app_shell_clears_admin_nav_entries_after_a_clear_session_dispatch`):
seed an authenticated admin with admin scopes, trigger the existing logout
control (which dispatches `CLEAR_SESSION`), and assert the admin nav entries
are gone before the resulting redirect completes. This exercises the reset
branch directly through an assertion `frontend-builder` must write, rather
than leaving it to incidental coverage-floor credit.

## Known gaps this pass records rather than papers over

- **NFR "no audit-log row content (`ip`, `user_agent`, `request_id`) in the
  browser console in production builds"** — asserted as a spied
  `console.log`/`console.warn`/`console.error` recording no matching call
  during `AdminAuditLogScreen.test.tsx`'s own test run (a dev-mode proxy for
  the production-build guarantee); the production-build-specific claim itself
  is a build/grep check (`frontend-builder`'s self-check + `SECURITY_REVIEW`),
  not fully provable by a Vitest spy alone.
- **NFR "responsive ~375px through desktop; audit table scrolls horizontally
  within its own container"** — not Vitest-testable without a
  visual/viewport-emulation tool this project does not use; not asserted here,
  consistent with `US-5.3`'s identical recorded gap.
- **a11y bar** — asserted via the existing `vitest-axe` devDependency on
  exactly the three screens the Enforcement Matrix names
  (`AdminUserListScreen`, `AdminUserDetailScreen`, `AdminAuditLogScreen`);
  `AdminUserCreateScreen` is not named by the Enforcement Matrix and is not
  given an axe assertion here, matching the story's own scoping rather than
  inventing a fourth.
