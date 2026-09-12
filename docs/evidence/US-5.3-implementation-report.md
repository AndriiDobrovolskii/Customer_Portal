---
artifact_type: implementation_report
story: US-5.3
version: 2
status: DRAFT
created_at: "2026-09-12T00:00:00Z"
updated_at: "2026-09-12T00:50:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.3-task-breakdown.md
    version: 2
  - path: docs/tests/US-5.3-ac-test-matrix.md
    version: 1
supersedes: null
---

# Implementation Report — US-5.3 (Support Tickets — Frontend)

**Track:** frontend. **Scope:** customer-facing ticket list/create/detail/reply/close/
reopen screens consuming the already-delivered EPIC-4 backend contract; no backend, API,
or DB change (`api_design`/`database_design` both `NOT_APPLICABLE` per the story's own
Assumption #8). Aggregated from all `IMPLEMENTATION` sub-steps executed by
`frontend-builder` (two `CHANGES_REQUIRED` loops through `TEST_WRITING` — three
test-file defects after attempt 1, one more after the eslintrc sign-off — plus one
`BLOCKED` resolved by human sign-off on an enforcement-config override, then `PASS`), per
`docs/plans/US-5.3-task-breakdown.md` v2 (T1–T20).

## What was built

- **`api/` layer:** `httpClient.ts` gained an additive `idempotencyKey` option on
  `httpPost` and a first-class `ApiError.retryAfterSeconds?: number`, set by
  `parseResponse` on any `429` (not scoped to this story's two endpoints). `types.ts`
  gained the ticket DTOs (`TicketRead`, `TicketListResponse`, `CreateTicketRequest`,
  `TicketDetailRead`, `ReplyRead`, `ReplyThreadPage`, `CreateReplyRequest`,
  `TicketStateRead`, `CloseTicketRequest`, `ReopenTicketRequest`, `TicketStatus`), with
  `category` typed plain `string` (OD-2) rather than an enum. `supportApi.ts` (new) adds
  `listTickets`, `createTicket`, `getTicketDetail`, `replyToTicket`, `closeTicket`,
  `reopenTicket` — imports only `httpClient`/`types`, zero React/TanStack imports.
- **`components/` layer:** `apiErrorHelpers.ts` gained `getRetryAfterSeconds(error)`
  alongside the existing `getErrorKind`/`getErrorMessage`/`getErrorStatus`.
- **Test infrastructure:** `test/mswHandlers.ts` gained one handler per the six new
  endpoints.
- **`hooks/` layer (six new hooks, all new files with paired tests):** `useTickets.ts`
  (`useInfiniteQuery`, keyed `["tickets", status]`), `useTicketDetail.ts` (`useQuery` +
  sibling `useInfiniteQuery` for replies, exporting `ticketDetailQueryKey`/
  `ticketRepliesQueryKey`), `useCreateTicket.ts` (OD-6: lazily-minted
  `crypto.randomUUID()` idempotency key, reused verbatim on an unchanged resubmission,
  rotated when subject/body/category differ), `useReplyToTicket.ts` (invalidates both
  detail and replies keys on success), `useCloseTicket.ts` (invalidates detail key only),
  `useReopenTicket.ts` (OD-3: no client-side eligibility computation — the backend's `409`
  is the sole source of truth), `useRetryAfterCountdown.ts` (local-state countdown off
  `retryAfterSeconds`, no network).
- **`screens/` layer (three new screens, all new files with paired tests):**
  `TicketListScreen.tsx` (five-status filter, cursor "Load more", empty/error states),
  `NewTicketScreen.tsx` (plain `<input maxLength={50}>` free-text `category` per OD-2, no
  new UI dependency per OD-5), `TicketDetailScreen.tsx` (reply thread, close/reopen
  affordances gated by the pure exported `offeredActionsForStatus(status)` — `resolved` →
  all three actions, `closed` → none, every other listed status → reply+close only,
  unrecognized status → none (fail closed); `first_response_at` rendered as plain labeled
  text with no SLA styling per OD-4; "Reopen" never proactively disabled per OD-3).
- **App shell / routing (US-5.1 code changed by this story, per its own In-Scope note):**
  `AppShell.tsx` gains a `/tickets` nav link and renders `<MfaEnrollmentBanner>` from its
  new caller site; `AppRoutes.tsx` registers `/tickets`, `/tickets/new`, `/tickets/:id`
  inside the existing `ProtectedRoute`+`AppShell` group and redirects `/` → `/tickets`;
  `GuestOnlyRoute.tsx`, `LoginScreen.tsx`, `MfaVerifyScreen.tsx` retarget their
  post-auth/guest-redirect literal from `/` to `/tickets`; `PlaceholderHomeScreen.tsx` (and
  its test) deleted, superseded by `TicketListScreen.tsx`.
- **No backend/API/DB change.** No new dependency added — `frontend/package.json` and
  `package-lock.json` are unchanged (`git status` shows neither modified nor new).

## Per-task status against `task_breakdown` v2 (T1–T20)

| Task | Files | Status | Evidence |
|---|---|---|---|
| T1 | `api/httpClient.ts`, `.test.ts` | Done | File present, modified; `type-check` clean; `test:coverage` shows `httpClient.test.ts` passing |
| T2 | `api/types.ts` | Done | File present, modified; `type-check` clean |
| T3 | `components/apiErrorHelpers.ts`, `.test.ts` | Done | File present, modified |
| T4 | `api/supportApi.ts` (new) | Done | File present; grep confirms only `httpClient`/`types` imports |
| T5 | `test/mswHandlers.ts` | Done | File present, modified |
| T6 | `hooks/useTickets.ts`, `.test.ts` (new) | Done | Files present |
| T7 | `hooks/useTicketDetail.ts`, `.test.ts` (new) | Done | Files present |
| T8 | `hooks/useCreateTicket.ts`, `.test.ts` (new) | Done | Files present |
| T9 | `hooks/useReplyToTicket.ts`, `.test.ts` (new) | Done | Files present |
| T10 | `hooks/useCloseTicket.ts`, `.test.ts` (new) | Done | Files present |
| T11 | `hooks/useReopenTicket.ts`, `.test.ts` (new) | Done | Files present |
| T12 | `hooks/useRetryAfterCountdown.ts`, `.test.ts` (new) | Done | Files present |
| T13 | `screens/TicketListScreen.tsx`, `.test.tsx` (new) | Done | Files present; grep confirms zero `api/` imports (type-only import excepted, see quality gate report item 5) |
| T14 | `screens/NewTicketScreen.tsx`, `.test.tsx` (new) | Done | Files present |
| T15 | `screens/TicketDetailScreen.tsx`, `.test.tsx` (new) | Done | Files present; this file is the sole source of the one open lint finding (see quality gate report) |
| T16 | `layouts/AppShell.tsx`, `.test.tsx`; `components/MfaEnrollmentBanner.tsx` (no internal change) | Done | `AppShell.tsx`/`.test.tsx` modified; `MfaEnrollmentBanner.tsx` shows no diff, consistent with the task's "no internal change — caller move only" |
| T17 | Delete `PlaceholderHomeScreen.tsx`, `.test.tsx` | Done | `git status` shows both deleted |
| T18 | `routes/AppRoutes.tsx`, `.test.tsx` | Done | File present, modified |
| T19 | `routes/GuestOnlyRoute.tsx`, `screens/LoginScreen.tsx`, `screens/MfaVerifyScreen.tsx` + tests | Done | All five files present, modified |
| T20 | gate-enforcer (this stage) | Done | This report + `docs/evidence/US-5.3-quality-gate-report.md`; verdict `PASS` — see that report's re-verification section |

All T1–T19 files named in `task_breakdown` v2 are present in the working tree, matching
the plan's file set exactly (verified against `git status --porcelain`); no extra file
outside that set and no missing file.

## Test evidence (captured directly this session)

```
 Test Files  53 passed (53)
      Tests  291 passed (291)
```
Coverage: Statements 97.47%, Branches 95.29%, Functions 87.39%, Lines 97.47% — all four
clear the story's 85% floor. Full detail in `docs/evidence/US-5.3-quality-gate-report.md`.

## Migrations / runtime rules (§6.6)

N/A — frontend track. No ORM, cache, or migration exists in this stack (`AGENTS.md` §6's
Frontend note).

## Resolved item (was: Known open item)

`npm run lint` previously failed with exactly one warning
(`react-refresh/only-export-components` on `TicketDetailScreen.tsx:44`), caused by the
TK-AC9-mandated named export `offeredActionsForStatus` with no code-side fix. Resolved by
human sign-off (2026-09-12) on the already-drafted `frontend/.eslintrc.cjs` override
(mirroring the existing `src/store/**/*.tsx` exception), applied and independently
re-verified clean (`0 errors, 0 warnings`, full repository). A separate, unrelated
`TEST_WRITING` loop-back fixed one timing-flaky test
(`ProfileScreen.test.tsx`'s 200-char `user.type()` call, swapped for `fireEvent.change`) in
between; no implementation code was touched by that fix. `QUALITY_GATE`'s verdict is now
`PASS` — see `docs/evidence/US-5.3-quality-gate-report.md`'s re-verification section.
