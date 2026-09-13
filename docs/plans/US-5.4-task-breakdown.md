---
artifact_type: task_breakdown
story: US-5.4
version: 2
status: DRAFT
created_at: "2026-09-13T17:45:00Z"
updated_at: "2026-09-13T17:45:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
supersedes: docs/plans/US-5.4-task-breakdown.md (v1)
---

# Task Breakdown — US-5.4 (Admin Console, Frontend)

> **Revision (v2):** `version: 1` of this artifact was sequenced against specification v1,
> impact analysis v1, and implementation plan v1 — all now `SUPERSEDED` — while OD-1–OD-4
> were still `OPEN`. `PLAN_REVIEW` returned `BLOCKED` against that v1 pairing specifically
> because T16, T19, T20, and T21 were tied directly to those four still-open items
> (`docs/reviews/plans/US-5.4-plan-review.md`, v1, Blocking Issues 1–3), and
> `story-orchestrator` redirected the story to `CLARIFICATION`
> (`docs/workflow/history.jsonl`, `2026-09-13T12:45:00Z`), where a human stakeholder
> resolved all four (`docs/decisions/US-5.4-open-decisions.md`, v2). Specification v2 and
> implementation plan v2 both incorporate the resolutions directly; impact analysis v2
> confirms the affected-file set and dependency graph are otherwise unchanged from v1 (its
> own §5 "Delta From v1"). This revision re-sequences the identical file set against that
> resolved behavior: T16, T19, T20, and T21 below state what `useAuditLogs.ts`,
> `AdminUserCreateScreen.tsx`, and `AdminUserDetailScreen.tsx`/`AdminAuditLogScreen.tsx` must
> concretely do (Resolutions OD-1–OD-4), rather than naming an Open Decision they were
> waiting on. No task is added, removed, or reordered relative to v1 beyond this — the
> dependency graph, parallel-eligible batches, and every task not named above are unchanged.
> Implementation Plan Risk numbering also shifted between v1 and v2 (v2 closes the dependency
> question as its own Risk 1 rather than Risk 2, and folds the two new OD-driven risks in as
> Risk 5/Risk 6); citations below point at v2's numbering, not v1's.

**Track:** `frontend` (`docs/stories/US-5.4-admin-console-ui.md` front matter) — the
`IMPLEMENTATION` stage runs exactly one execution skill for this Story, `frontend-builder`
(`docs/workflow/stage-map.yaml` `IMPLEMENTATION.skills_by_track.frontend`), which per that
same stage's own annotation ("frontend/ scaffold, api-client, store, routes, screens,
**tests**") writes the paired `*.test.ts(x)` file together with each production file — so
every row below names `frontend-builder` and bundles a file's test with it; there is no
separate test-writing execution skill on this track (`test-writer`'s `TEST_WRITING` stage
output is `test_strategy`/`ac_test_matrix`/`test_generation_report`, guidance documents
`frontend-builder` consumes, not test code it hands off).

**Scaffold check:** `frontend/` already exists (shipped by US-5.1/US-5.2/US-5.3) — the
frontend ordering rule's "scaffold before everything" step is already satisfied, not
skipped.

**Dependency decision made explicit (Implementation Plan Risk 1):** the JWT `scopes` claim
is decoded with a hand-rolled `atob`/base64url helper in T3, **not** a new library.
`frontend/package.json` is therefore not touched by this Story, and §7.8's new-dependency
sign-off gate is not triggered.

**Layer note:** `frontend/src/layouts/AppShell.tsx` has no dedicated row in AGENTS.md §3's
Frontend layer table — it is attributed to the `routes/ (guards + layout)` row (T17 below),
per that row's own "guards + layout" label. `frontend/src/test/test-utils.tsx` and
`frontend/src/test/mswHandlers.ts` (T6, T7) are shared test infrastructure with no §3 layer
of their own; they are sequenced as prerequisites of every hook/screen test that consumes
them.

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | frontend-builder | `api/` | — | `frontend/src/api/types.ts` | `npm run type-check` clean; `npm run lint` clean; `grep -n "roles: string\[\]" frontend/src/api/types.ts` confirms `AdminUserRead.status`/`.roles` stay plain `string`/`string[]` (never a union), per Architectural Change 6 |
| T2 | frontend-builder | `api/` | — | `frontend/src/api/httpClient.ts`, `frontend/src/api/httpClient.test.ts` | `npx vitest run src/api/httpClient.test.ts`; `npm run type-check` clean; diff review confirms `performRequest`/`parseResponse` are untouched (same shape `httpPatch` used) |
| T3 | frontend-builder | `store/` | — | `frontend/src/store/decodeTokenScopes.ts`, `frontend/src/store/decodeTokenScopes.test.ts` | `npx vitest run src/store/decodeTokenScopes.test.ts --coverage` (well-formed token, empty/absent `scopes` claim, malformed payload — must not throw), per Implementation Plan Risk 1's closed dependency decision; `grep -RniE "from ['\"](\.\./)*api/|from ['\"](\.\./)*hooks/" frontend/src/store/decodeTokenScopes.ts` returns nothing (store/ must not import `api/`/hooks) |
| T4 | frontend-builder | `store/` | T3 | `frontend/src/store/authStore.tsx` | No existing `authStore.test.tsx` suite (confirmed: no `frontend/src/store/authStore.test.*` file exists today) and neither the impact analysis nor the plan's Testing Strategy names a new one — the three new reducer branches (`scopes` set on `SET_SESSION`/`TOKEN_REFRESHED`, reset on `CLEAR_SESSION`) are exercised indirectly by T17's seeded-`scopes` assertions and held by T23's 85% coverage floor, not by a dedicated unit test invented here; `npm run type-check` clean; diff review confirms `scopes` is never persisted (Client State Notes) |
| T5 | frontend-builder | `api/` | T1, T2 | `frontend/src/api/adminApi.ts` | `npm run type-check` clean; `grep -RniE "from ['\"]react|@tanstack/react-query|store/authStore" frontend/src/api/adminApi.ts` returns nothing (api/ must not import React/TanStack Query/store); diff review confirms no `deleteUser`/`DELETE /admin/users/{id}` function exists anywhere in this file (AD-AC7, satisfied by omission — see Open Items below for the assertion's test mechanism); confirms `listAuditLogs`'s parameter object key is literally `from`, not `from_` |
| T6 | frontend-builder | test infra (`frontend/src/test/`) | T4 | `frontend/src/test/test-utils.tsx` | `npm run type-check` clean; existing consumers (`AppShell.test.tsx`, `AppRoutes.test.tsx`) still pass unmodified until T17/T22 land; diff review confirms the new `scopes` option flows into `AuthStateSeed` without changing any existing `buildAuthSeed()` default |
| T7 | frontend-builder | test infra (`frontend/src/test/`) | T1, T5 | `frontend/src/test/mswHandlers.ts` | `npm run type-check` clean; diff review confirms one handler per `adminApi.ts` operation (9 total) and that `GET /admin/users/:id` sets an `ETag` response header (same mechanism as the existing `PATCH /profile` handler) |
| T8 | frontend-builder | `hooks/` | T5, T7 | `frontend/src/hooks/useAdminUsers.ts`, `frontend/src/hooks/useAdminUsers.test.ts` | `npx vitest run src/hooks/useAdminUsers.test.ts --coverage`; `grep -RniE "from ['\"](\.\./)*screens/|from ['\"](\.\./)*components/" frontend/src/hooks/useAdminUsers.ts` returns nothing (hooks/ must not import JSX/React components) |
| T9 | frontend-builder | `hooks/` | T5, T7 | `frontend/src/hooks/useAdminUser.ts`, `frontend/src/hooks/useAdminUser.test.ts` | `npx vitest run src/hooks/useAdminUser.test.ts --coverage`, including a case asserting the `ETag` for user A is never cached/read under user B's key (Implementation Plan Risk 4); same import grep as T8 |
| T10 | frontend-builder | `hooks/` | T5, T7 | `frontend/src/hooks/useAdminRoles.ts`, `frontend/src/hooks/useAdminRoles.test.ts` | `npx vitest run src/hooks/useAdminRoles.test.ts --coverage`, including a case confirming this hook is the single shared, unconditional role-catalogue source consumed by both T19 and T20 (no fallback/optional path for either); same import grep as T8 |
| T11 | frontend-builder | `hooks/` | T5, T7 | `frontend/src/hooks/useCreateAdminUser.ts`, `frontend/src/hooks/useCreateAdminUser.test.ts` | `npx vitest run src/hooks/useCreateAdminUser.test.ts --coverage`; same import grep as T8 |
| T12 | frontend-builder | `hooks/` | T5, T7, T9 | `frontend/src/hooks/useUpdateAdminUser.ts`, `frontend/src/hooks/useUpdateAdminUser.test.ts` | `npx vitest run src/hooks/useUpdateAdminUser.test.ts --coverage`, including the `412`-conflict and `immutable-field`-detail cases; same import grep as T8 |
| T13 | frontend-builder | `hooks/` | T5, T7, T9, T10 | `frontend/src/hooks/useReplaceUserRoles.ts`, `frontend/src/hooks/useReplaceUserRoles.test.ts` | `npx vitest run src/hooks/useReplaceUserRoles.test.ts --coverage`, including a case asserting `useAdminUser.ts`'s query key is invalidated/updated after a successful `PUT` (Implementation Plan Risk 3's preferred targeted-invalidation mitigation); same import grep as T8 |
| T14 | frontend-builder | `hooks/` | T5, T7, T9 | `frontend/src/hooks/useDeactivateAdminUser.ts`, `frontend/src/hooks/useDeactivateAdminUser.test.ts` | `npx vitest run src/hooks/useDeactivateAdminUser.test.ts --coverage`, including a case asserting `useAdminUser.ts`'s cached status updates without a full refetch (Implementation Plan Risk 3); same import grep as T8 |
| T15 | frontend-builder | `hooks/` | T5, T7 | `frontend/src/hooks/useResendInvite.ts`, `frontend/src/hooks/useResendInvite.test.ts` | `npx vitest run src/hooks/useResendInvite.test.ts --coverage`, including an assertion the `202` body is never surfaced to the caller; same import grep as T8 |
| T16 | frontend-builder | `hooks/` | T5, T7 | `frontend/src/hooks/useAuditLogs.ts`, `frontend/src/hooks/useAuditLogs.test.ts` | `npx vitest run src/hooks/useAuditLogs.test.ts --coverage`, with the system clock frozen (`vi.setSystemTime`, Implementation Plan Risk 5) before asserting **Resolution OD-1**'s default window: on first mount, before any filter is chosen, `from = now − 7 days` / `to = now`, both ISO 8601 UTC, computed exactly once and returned to the caller for the screen (T21) to pre-fill — never applied silently with no value handed back; same import grep as T8 |
| T17 | frontend-builder | `routes/` (guards + layout) | T4, T6 | `frontend/src/layouts/AppShell.tsx`, `frontend/src/layouts/AppShell.test.tsx` | `npx vitest run src/layouts/AppShell.test.tsx --coverage`, asserting the two new nav entries appear/are absent per seeded `scopes`; `grep -RniE "from ['\"](\.\./)*api/" frontend/src/layouts/AppShell.tsx` returns nothing (must read `scopes` off the store only, never call `api/` directly) |
| T18 | frontend-builder | `screens/` | T6, T7, T8 | `frontend/src/screens/AdminUserListScreen.tsx`, `frontend/src/screens/AdminUserListScreen.test.tsx` | `npx vitest run src/screens/AdminUserListScreen.test.tsx --coverage`, covering AD-AC1 (filters reset cursor, "Load more" appends, no total count, unrecognized `status`/`roles` renders verbatim per Implementation Plan Risk 7) and a distinct loading state; axe a11y pass (`vitest-axe`, Enforcement Matrix names this screen); `grep -RniE "from ['\"](\.\./)*api/|fetch\(" frontend/src/screens/AdminUserListScreen.tsx` returns nothing (screens/ must not import `api/` or call `fetch` directly) |
| T19 | frontend-builder | `screens/` | T6, T7, T10, T11 | `frontend/src/screens/AdminUserCreateScreen.tsx`, `frontend/src/screens/AdminUserCreateScreen.test.tsx` | `npx vitest run src/screens/AdminUserCreateScreen.test.tsx --coverage`, covering AD-AC3 (exactly `email`/`display_name`/`roles` in the `POST` body, no password field anywhere in the DOM, navigates to the new user's detail screen on `201`) and, per **Resolution OD-4**, that the `roles` control's selectable options are sourced only from `useAdminRoles.ts` (`GET /admin/roles`) — no free-text role entry anywhere on this screen; XC-AC3 client-side validation; same import grep as T18 |
| T20 | frontend-builder | `screens/` | T6, T7, T9, T10, T12, T13, T14, T15 | `frontend/src/screens/AdminUserDetailScreen.tsx`, `frontend/src/screens/AdminUserDetailScreen.test.tsx` | `npx vitest run src/screens/AdminUserDetailScreen.test.tsx --coverage`, covering AD-AC2/AD-AC4/AD-AC5/AD-AC6/AD-AC7 (roles never in `PATCH` body — asserted on every captured `PATCH`; role save hits `PUT .../roles` with the full replacement list; role control disabled without `roles:write`; deactivate/resend behind confirmation) and XC-AC1's three scoped-token scenarios; per **Resolution OD-3**, a dedicated case seeding the current roles in a different order than `GET /admin/roles` returns them (Implementation Plan Risk 6) asserting: the role control is a target-*replacement* multi-select (not add/remove), the confirmation dialog computes and renders **Gained** (`selected − current`) and **Lost** (`current − selected`) role sets via order-insensitive set comparison, and Save stays disabled exactly while the selected set equals the current set; axe a11y pass (this is the Enforcement Matrix's "user-edit" screen); same import grep as T18 |
| T21 | frontend-builder | `screens/` | T6, T7, T16 | `frontend/src/screens/AdminAuditLogScreen.tsx`, `frontend/src/screens/AdminAuditLogScreen.test.tsx` | `npx vitest run src/screens/AdminAuditLogScreen.test.tsx --coverage`, covering AD-AC8 (all nine columns, explicit placeholder per nullable column, literal `from` query param, "Load more" with a stable synthetic row key across pages per Implementation Plan Risk 7) and the console-hygiene NFR (spied `console.*` records no `ip`/`user_agent`/`request_id`); per **Resolution OD-1**, with the system clock frozen (Implementation Plan Risk 5, same technique as T16), the `from`/`to` date-picker inputs render **visibly pre-filled** with `useAuditLogs.ts`'s computed 7-day default on first render (not applied silently); per **Resolution OD-2**, the `event` filter renders as a plain free-text `<input>` carrying an illustrative placeholder, never a `<select>`/combobox against an enumerated list; axe a11y pass (Enforcement Matrix names this screen); same import grep as T18 |
| T22 | frontend-builder | `routes/` | T6, T18, T19, T20, T21 | `frontend/src/routes/AppRoutes.tsx`, `frontend/src/routes/AppRoutes.test.tsx` | `npx vitest run src/routes/AppRoutes.test.tsx --coverage`, covering the four new routes including their unauthenticated-redirect-to-`/login` case; `grep -RniE "from ['\"](\.\./)*api/" frontend/src/routes/AppRoutes.tsx` returns nothing; `git diff --stat -- frontend/src/routes/ProtectedRoute.tsx` shows no change (Implementation Plan Risk 2 — this file stays auth-only; scope gating must live only at the presentation layer, T17/T18-T21, never added here) |
| T23 | gate-enforcer | — | T1–T22 | — | `npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:coverage` (§2's four load-bearing scripts) all green from `frontend/`; diff review against AGENTS.md §3 Frontend layer table (no `lint-imports` equivalent exists for this stack) |

**Parallel-eligible batches** (dependency-minimal, not the only valid execution order):
- T1, T2, T3 — no dependencies, fully parallel.
- T4 (needs T3) ∥ T5 (needs T1, T2).
- T6 (needs T4) ∥ T7 (needs T1, T5).
- T8, T9, T10, T11, T15, T16, T17 — all reach their dependencies once T5–T7 land; parallel to each other.
- T12, T13, T14 — parallel to each other once T9 (and, for T13, T10) lands; parallel to the T8/T11/T15/T16/T17 batch too.
- T18, T19, T20, T21 — parallel to each other once their respective hook/test-infra dependencies land.
- T22 is the sole task gating on all four screens; T23 is the sequence's sole terminal task.
- Ordering-rule note: `store/` (T3-T4) is sequenced ahead of the entire `hooks/` block (T8-T16) per the frontend ordering rule ("`api/` and `store/` before `hooks/`"), even though none of T8-T16 actually imports `authStore.tsx`/`decodeTokenScopes.ts` — the rule is applied as a sequencing floor, not skipped because no hook happens to need it yet.

## Open Items Carried Forward (not resolved by this stage)

- **OD-1, OD-2, OD-3, OD-4 are `RESOLVED`** (`docs/decisions/US-5.4-open-decisions.md`, v2)
  and no longer block any task in this sequence. T16 and T21 state Resolution OD-1's default
  audit window directly; T21 states Resolution OD-2's free-text `event` filter directly; T19
  states Resolution OD-4's catalogue-only role picker directly; T20 states Resolution OD-3's
  target-replacement multi-select and gained/lost/disable-when-unchanged logic directly. This
  closes the specific gap `docs/reviews/plans/US-5.4-plan-review.md` (v1) found `BLOCKED`
  against T16/T19/T20/T21 of the prior version of this artifact.
- **AD-AC7's static/unit assertion mechanism** (no code path issues `DELETE /admin/users/{id}`)
  is deliberately left undecided by both the impact analysis and the implementation plan
  ("exact mechanism is `test-writer`'s call, not resolved here") — unchanged from v1. This
  breakdown does not invent it: T5's verification requires the omission (no `deleteUser`
  function in `adminApi.ts`), but the dedicated assertion's file and technique (a repo-wide
  grep-style check vs. an MSW-handler-absence assertion) is left for `frontend-builder`/
  `test-writer`'s `TEST_WRITING` output to settle before T5/T20 are marked done.
