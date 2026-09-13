---
artifact_type: implementation_report
story: US-5.4
version: 2
status: DRAFT
created_at: "2026-09-13T20:20:00Z"
updated_at: "2026-09-13T21:15:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.4-task-breakdown.md
    version: 2
  - path: docs/tests/US-5.4-ac-test-matrix.md
    version: 1
supersedes: docs/evidence/US-5.4-implementation-report.md (v1)
---

# Implementation Report — US-5.4 (Admin Console — Frontend)

**Track:** frontend. **Scope:** admin user list/create/detail/roles and audit-log screens
consuming the already-delivered EPIC-3 backend contract (US-3.1/US-3.2/US-3.3); no backend,
API, or DB change (`api_design`/`database_design` both `NOT_APPLICABLE` per the story's own
Assumption #8 and confirmed by `docs/reviews/designs/US-5.4-design-review.md`, v2).
Aggregated from the single `IMPLEMENTATION` sub-step (`frontend-builder`), which reported
`PASS` on its first dispatch (`docs/catalog/US-5.4-pipeline-status.md`), per
`docs/plans/US-5.4-task-breakdown.md` v2 (T1–T22; T23 is this stage).

## What was built

- **`api/` layer:** `types.ts` gained the admin DTOs (`AdminUserRead`, its list response,
  `AdminRoleRead`, `AuditLogEntry`/list response, request bodies) with `status`/`roles` kept
  plain `string`/`string[]` — never a union — per Architectural Change 6 (verified: `grep
  "roles: string\[\]"` on `types.ts` matches). `httpClient.ts` was extended (additive) with
  two new exports, `httpPut` (mirrors `httpPost`'s shape, for `PUT .../roles`) and
  `httpGetWithMeta` (the GET-verb analogue of `httpPatch`, for capturing the `ETag`
  response header) — `httpPatch` itself pre-existed from a prior story and is reused as-is
  for the `If-Match` `PATCH`, unchanged (verified directly: `httpPut`/`httpGetWithMeta` are
  new exports at lines 238/248, `httpPatch` at line 198 carries no diff-relevant change).
  `adminApi.ts` (new) adds all nine
  endpoints (`listUsers`, `getUser`, `createUser`, `updateUser`, `deactivateUser`,
  `resendInvite`, `listRoles`, `replaceUserRoles`, `listAuditLogs`) — imports only
  `httpClient`/`types`, zero React/TanStack imports (confirmed); no `deleteUser`/`DELETE
  /admin/users/{id}` function exists anywhere in the file (AD-AC7, satisfied by omission and
  independently re-verified — see quality gate report item 9); `listAuditLogs`'s
  start-of-window parameter key is literally `from`.
- **`store/` layer:** `decodeTokenScopes.ts` (new) — a hand-rolled base64url JWT-claim
  decoder (no new dependency, per Implementation Plan Risk 1's closed decision), returning
  `[]` for any malformed token rather than throwing. `authStore.tsx` gained a `scopes` field
  set on `SET_SESSION`/`TOKEN_REFRESHED` and cleared on `CLEAR_SESSION`; never persisted to
  `localStorage`/`sessionStorage`.
- **Test infrastructure:** `test/mswHandlers.ts` gained one handler per `adminApi.ts`
  operation (verified: nine `http.*` handlers for `admin/users`, `admin/users/:id`,
  `admin/users/:id/deactivate`, `admin/users/:id/resend-invite`, `admin/roles`,
  `admin/users/:id/roles`, `admin/audit-logs`), with the `GET`/`POST`/`PATCH`
  `admin/users/:id` handlers each setting an `ETag` response header.
  `test/test-utils.tsx` gained a `scopes` seeding option on `buildAuthSeed()`/
  `AuthStateSeed` without changing any existing default.
- **`hooks/` layer (nine new hooks, all new files with paired tests):**
  `useAdminUsers.ts` (list, cursor pagination), `useAdminUser.ts` (detail, capturing and
  caching the `ETag` per-user-id — verified the ETag for one user is never read under
  another user's key), `useAdminRoles.ts` (the single shared role-catalogue source consumed
  by both create and detail/roles screens), `useCreateAdminUser.ts`, `useUpdateAdminUser.ts`
  (`PATCH` with `If-Match`, surfacing `412`/`immutable-field` cases), `useReplaceUserRoles.ts`
  (`PUT .../roles`; `onSuccess` calls `queryClient.invalidateQueries(adminUserQueryKey(id))`),
  `useDeactivateAdminUser.ts` (`onSuccess` calls `queryClient.setQueryData(adminUserQueryKey(id),
  data)` — a direct cache patch, no refetch), `useResendInvite.ts`
  (the `202` body is never surfaced to the caller), `useAuditLogs.ts` (computes the default
  7-day `from`/`to` window once, ISO 8601 UTC, per Resolution OD-1, and returns it to the
  caller rather than applying it silently). None import a screen/component (confirmed by
  grep on all nine).
- **`screens/` layer (four new screens, all new files with paired tests):**
  `AdminUserListScreen.tsx` (AD-AC1: filters reset the cursor, "Load more" appends, no total
  count anywhere, unrecognized `status`/`roles` render verbatim), `AdminUserCreateScreen.tsx`
  (AD-AC3: exactly `email`/`display_name`/`roles` in the `POST` body, no password field in
  the DOM, navigates to the new user's detail screen on `201`; per Resolution OD-4 the roles
  control is sourced only from `useAdminRoles.ts`, no free-text entry), `AdminUserDetailScreen.tsx`
  (AD-AC2/4/5/6/7 and XC-AC1: `ETag`→`If-Match` round-trip, roles never in the `PATCH` body,
  role replacement as a confirmed target-replacement multi-select computing Gained/Lost sets
  per Resolution OD-3, deactivate/resend behind confirmation, read/write scopes gated
  independently), `AdminAuditLogScreen.tsx` (AD-AC8: all nine columns, explicit placeholder
  per nullable column, literal `from` query parameter, stable synthetic row key across
  pages, `from`/`to` visibly pre-filled with the computed 7-day default per Resolution OD-1,
  `event` as plain free-text per Resolution OD-2). None imports `api/` directly or calls
  `fetch` (confirmed by grep on all four — only `*Query.refetch()` matches).
- **Routing / shell:** `layouts/AppShell.tsx` gained two scope-gated nav entries
  (`users:read` → user list, `audit:read` → audit log), reading `scopes` off
  `useAuthStore()` read-only — no `api/` import. `routes/AppRoutes.tsx` registers the four
  new routes inside the existing `ProtectedRoute`+`AppShell` group; `ProtectedRoute.tsx`
  itself is unchanged (`git status` confirms no diff), keeping scope gating at the
  presentation layer only, per Implementation Plan Risk 2.
- **No backend/API/DB change.** No new dependency added — `frontend/package.json` and
  `package-lock.json` show no diff in `git status`, consistent with Implementation Plan
  Risk 1's closed dependency decision.

## Per-task status against `task_breakdown` v2 (T1–T23)

| Task | Files | Status | Evidence |
|---|---|---|---|
| T1 | `api/types.ts` | Done | Present, modified; `type-check` clean; `roles: string[]` grep confirms plain types |
| T2 | `api/httpClient.ts`, `.test.ts` | Done | Present, modified; `type-check` clean |
| T3 | `store/decodeTokenScopes.ts`, `.test.ts` (new) | Done | Files present; grep confirms no `api/`/`hooks/` import |
| T4 | `store/authStore.tsx` | Done | Present, modified; `type-check` clean; `scopes` never persisted (grep) |
| T5 | `api/adminApi.ts` (new) | Done | Present; grep confirms no React/TanStack/store import; no `deleteUser` |
| T6 | `test/test-utils.tsx` | Done | Present, modified |
| T7 | `test/mswHandlers.ts` | Done | Present, modified; verified nine `admin/*` handlers, `ETag` header on the GET/POST/PATCH user-detail handlers |
| T8 | `hooks/useAdminUsers.ts`, `.test.ts` (new) | Done | Files present; no screens/components import |
| T9 | `hooks/useAdminUser.ts`, `.test.ts` (new) | Done | Files present |
| T10 | `hooks/useAdminRoles.ts`, `.test.ts` (new) | Done | Files present |
| T11 | `hooks/useCreateAdminUser.ts`, `.test.ts` (new) | Done | Files present |
| T12 | `hooks/useUpdateAdminUser.ts`, `.test.ts` (new) | Done | Files present |
| T13 | `hooks/useReplaceUserRoles.ts`, `.test.ts` (new) | Done | Files present; verified `onSuccess` calls `queryClient.invalidateQueries(adminUserQueryKey(id))`, not a store action |
| T14 | `hooks/useDeactivateAdminUser.ts`, `.test.ts` (new) | Done | Files present; verified `onSuccess` calls `queryClient.setQueryData(adminUserQueryKey(id), data)` — cache patch, no refetch, no store action |
| T15 | `hooks/useResendInvite.ts`, `.test.ts` (new) | Done | Files present |
| T16 | `hooks/useAuditLogs.ts`, `.test.ts` (new) | Done | Files present |
| T17 | `layouts/AppShell.tsx`, `.test.tsx` | Done | Present, modified; grep confirms no `api/` import; scopes read-only (verified) |
| T18 | `screens/AdminUserListScreen.tsx`, `.test.tsx` (new) | Done | Files present; no `api/`/`fetch` import |
| T19 | `screens/AdminUserCreateScreen.tsx`, `.test.tsx` (new) | Done | Files present |
| T20 | `screens/AdminUserDetailScreen.tsx`, `.test.tsx` (new) | Done | Files present |
| T21 | `screens/AdminAuditLogScreen.tsx`, `.test.tsx` (new) | Done | Files present; no `console.*` of `ip`/`user_agent`/`request_id` (verified) |
| T22 | `routes/AppRoutes.tsx`, `.test.tsx` | Done | Present, modified; `ProtectedRoute.tsx` unchanged (verified via `git status`) |
| T23 | gate-enforcer (this stage) | Done | This report + `docs/evidence/US-5.4-quality-gate-report.md`; verdict `PASS` (re-run) — see that report |

All T1–T22 files named in `task_breakdown` v2 were independently confirmed present on the
filesystem (not merely transcribed from `pipeline_status`), matching the plan's file set
exactly; `git status --porcelain` shows no extra file outside that set beyond
`frontend/tsconfig.app.tsbuildinfo`, a build artifact, not implementation code.

## Test evidence (re-captured this session, after the CRLF/LF fix)

```
 Test Files  68 passed (68)
      Tests  395 passed (395)

Statements   : 97.48% ( 8319/8534 )
Branches     : 94.83% ( 1654/1744 )
Functions    : 86.58% ( 271/313 )
Lines        : 97.48% ( 8319/8534 )
```
All four clear the story's 85% floor; identical test counts to the prior run (only the
statement/line denominators shifted slightly, from the 31 pre-existing files' LF
renormalization changing what v8's coverage instrumentation counts, not from any test being
added, removed, or weakened). Full detail, including the `npm run lint`, `npm run
format:check`, and `npm run type-check` re-runs, is in
`docs/evidence/US-5.4-quality-gate-report.md`.

## Migrations / runtime rules (§6.6)

N/A — frontend track. No ORM, cache, or migration exists in this stack (`AGENTS.md` §6's
Frontend note).

## Resolved item from the prior `QUALITY_GATE` run

The prior run (v1, 2026-09-13T20:20:00Z) returned `BLOCKED` solely because `npm run
format:check` failed on 31 pre-existing files (none touched by this Story) due to a
CRLF/Prettier-LF mismatch on this Windows checkout (`core.autocrlf=true`). With human
authorization, `frontend/.gitattributes` (`* text=auto eol=lf`) was added and the 31 files
were renormalized to LF on disk. This re-run independently re-executed `format:check` (and
every other Definition-of-Done check) fresh against the current working tree and confirmed
`exit code 0` — "All matched files use Prettier code style!" — rather than trusting that
summary. `docs/evidence/US-5.4-quality-gate-report.md` (v2) now records verdict `PASS`.
