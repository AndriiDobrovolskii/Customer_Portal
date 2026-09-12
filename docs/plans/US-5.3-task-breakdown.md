---
artifact_type: task_breakdown
story: US-5.3
version: 2
status: APPROVED
created_at: "2026-09-08T21:30:00Z"
updated_at: "2026-09-08T22:30:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
supersedes: docs/plans/US-5.3-task-breakdown.md
---

# Task Breakdown — US-5.3 (Support Tickets — Frontend)

**Re-run note (v2).** This supersedes task_breakdown v1, which sequenced against
`implementation_plan` v1 (rejected at `HUMAN_PLAN_APPROVAL` for hedging on
OD-1..OD-6). `implementation_plan` v2 resolves all six as firm architecture, not
workarounds. `impact_analysis` v1 (`PASS`) is unaffected — the OD resolutions
change *behavior* within files it already listed, not the file set — so the file
list and dependency shape below are carried forward from v1 essentially
unchanged; only task descriptions/verification steps that referenced an OD as
contingent, blocking, or "narrowest reading pending resolution" are rewritten to
state the resolved behavior directly, per plan v2's own framing.

**Track:** frontend. Per `AGENTS.md` §3's Frontend layer table (`api/` → `hooks/` →
`routes/`/`screens/`, with `store/` at the same level as `api/`; `api_design`/
`database_design` both `NOT_APPLICABLE` for this story, so no backend layer
attribution applies). Every task below is executed by `frontend-builder` — the sole
execution skill on this track — except the final `gate-enforcer` task. No `store/`
task exists: this story reads `useAuthStore()` read-only in `AppShell.tsx` and adds
no new store field/action (`impact_analysis` §1a, "Checked — Not Affected").

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | frontend-builder | `api/` | — | `frontend/src/api/httpClient.ts` (plan v2 Change 1: additive `idempotencyKey` option on `httpPost`; Change 2, OD-1 firm resolution: `ApiError` gains a first-class `retryAfterSeconds?: number` field via a new third constructor parameter, set by `parseResponse` on any `429` reading `Retry-After` — this is the permanent shared-client shape, not a helper scoped to FR-12), `frontend/src/api/httpClient.test.ts` (existing file — confirmed present; `impact_analysis` files it under "Existing test files that must change") | `npx vitest run src/api/httpClient.test.ts` proves the new `idempotencyKey` option; proves `ApiError.retryAfterSeconds` is populated on any `429` parsed by `parseResponse` (not just this story's two endpoints) and stays `undefined` on a non-429 4xx/5xx even when a `Retry-After` header is present; `npm run type-check` clean; grep confirms `httpGet`/`httpDelete`/`httpPatch` signatures, `parseResponseWithMeta`'s separate error path, and `normalizeApiError()`'s signature are byte-identical to before this change |
| T2 | frontend-builder | `api/` | — | `frontend/src/api/types.ts` (Change 4: `TicketRead`, `TicketListResponse`, `CreateTicketRequest`, `TicketDetailRead`, `ReplyRead`, `ReplyThreadPage`, `CreateReplyRequest`, `TicketStateRead`, `CloseTicketRequest`, `ReopenTicketRequest`, `TicketStatus` union; `category` typed as plain `string`, OD-2's firm resolution — no companion literal-union type) | `npm run type-check` clean; grep confirms `TicketRead.status`/`TicketDetailRead.status` are typed `string`, not `TicketStatus`, and `category` is typed plain `string` with no enum/union alongside it |
| T3 | frontend-builder | `components/` (shared helper, existing `getErrorStatus`/`getErrorKind` pattern) | T1 | `frontend/src/components/apiErrorHelpers.ts` (Change 2: additive `getRetryAfterSeconds(error: unknown): number \| undefined` — the permanent, layering-correct read path for the now-first-class field, not a workaround scoped to FR-12), `frontend/src/components/apiErrorHelpers.test.ts` (existing file — confirmed present) | `npx vitest run src/components/apiErrorHelpers.test.ts` covers `getRetryAfterSeconds` alongside the existing getters; grep confirms no screen imports `api/httpClient.ts`'s `ApiError` class directly |
| T4 | frontend-builder | `api/` | T1, T2 | `frontend/src/api/supportApi.ts` (new — Change 3: `listTickets`, `createTicket`, `getTicketDetail`, `replyToTicket`, `closeTicket`, `reopenTicket`) | `npm run type-check` clean; grep confirms `supportApi.ts` imports only `httpClient`/`types` — zero React or `@tanstack/react-query` imports |
| T5 | frontend-builder | test infrastructure (`frontend/src/test/`) | T2, T4 | `frontend/src/test/mswHandlers.ts` (baseline handler for each of the 6 endpoints: list, create, detail, reply, close, reopen) | grep/manual count confirms one handler per operation, following the existing one-handler-per-operation convention; `npm run type-check` clean |
| T6 | frontend-builder | `hooks/` | T4, T5 | `frontend/src/hooks/useTickets.ts` (new — Change 5: `useInfiniteQuery` keyed `["tickets", status]`), `frontend/src/hooks/useTickets.test.ts` (new) | `npx vitest run src/hooks/useTickets.test.ts` proves `fetchNextPage`/`hasNextPage` derived from `next_cursor`, and a `status` change resets pagination |
| T7 | frontend-builder | `hooks/` | T4, T5 | `frontend/src/hooks/useTicketDetail.ts` (new — Change 5: `useQuery` on `["ticket", id]` + sibling `useInfiniteQuery` on `["ticket-replies", id]`, exporting `ticketDetailQueryKey(id)`/`ticketRepliesQueryKey(id)`), `frontend/src/hooks/useTicketDetail.test.ts` (new) | `npx vitest run src/hooks/useTicketDetail.test.ts` proves the two query keys share no prefix and the replies paginator is independent of the ticket-detail query |
| T8 | frontend-builder | `hooks/` | T4, T5 | `frontend/src/hooks/useCreateTicket.ts` (new — Change 5/8, OD-6 firm resolution: `Idempotency-Key` minted lazily via `crypto.randomUUID()` on the first `mutate()` per form-mount; reused verbatim on a resubmission whose `subject`/`body`/`category` are unchanged from the previous attempt; rotated to a new key when any of those three fields differ from the previous attempt — a direct equality check on the three fields, not a "touched" flag), `frontend/src/hooks/useCreateTicket.test.ts` (new) | `npx vitest run src/hooks/useCreateTicket.test.ts` asserts all three key-lifecycle cases as dedicated test cases per plan v2's Risk 5: (1) identical key on a verbatim retry (TK-AC4), (2) a distinct key on a fresh mount (TK-AC4), (3) a distinct key on an edited-then-resubmitted payload — subject/body/category equality check, OD-6's binding case — and that case never reaches the backend's `IdempotencyKeyReuseError` `422` shape |
| T9 | frontend-builder | `hooks/` | T4, T5, T7 | `frontend/src/hooks/useReplyToTicket.ts` (new — Change 5), `frontend/src/hooks/useReplyToTicket.test.ts` (new) | `npx vitest run src/hooks/useReplyToTicket.test.ts` asserts `onSuccess` invalidates **both** `ticketDetailQueryKey(id)` and `ticketRepliesQueryKey(id)` |
| T10 | frontend-builder | `hooks/` | T4, T5, T7 | `frontend/src/hooks/useCloseTicket.ts` (new — Change 5), `frontend/src/hooks/useCloseTicket.test.ts` (new) | `npx vitest run src/hooks/useCloseTicket.test.ts` asserts `onSuccess` invalidates `ticketDetailQueryKey(id)` only |
| T11 | frontend-builder | `hooks/` | T4, T5, T7 | `frontend/src/hooks/useReopenTicket.ts` (new — Change 5, OD-3 firm resolution: the hook performs no client-computed reopen-eligibility check of any kind — the `409` from the backend is the sole source of truth), `frontend/src/hooks/useReopenTicket.test.ts` (new) | `npx vitest run src/hooks/useReopenTicket.test.ts` asserts `onSuccess` invalidates `ticketDetailQueryKey(id)`; asserts a `409` `ApiError` reaches the caller unmodified (no swallow/reshape, `detail` intact); grep confirms zero date/window computation anywhere in this file |
| T12 | frontend-builder | `hooks/` | — | `frontend/src/hooks/useRetryAfterCountdown.ts` (new — Change 5: local-state countdown reading the now-first-class `retryAfterSeconds`, no network), `frontend/src/hooks/useRetryAfterCountdown.test.ts` (new) | `npx vitest run src/hooks/useRetryAfterCountdown.test.ts` (fake timers) proves the countdown ticks to zero, `isBlocked` flips to `false` at zero, and the interval is cleared on unmount. Parallel-eligible with T6–T11 (no shared dependency). |
| T13 | frontend-builder | `screens/` | T6 | `frontend/src/screens/TicketListScreen.tsx` (new — Change 6/11), `frontend/src/screens/TicketListScreen.test.tsx` (new) | `npx vitest run src/screens/TicketListScreen.test.tsx` covers TK-AC1/TK-AC2 (row fields, "Load more" append/disappear, empty-state CTA, unrecognized-`status` verbatim, all-five-statuses filter reissue); the TK-AC11 shared case (a problem+json 4xx renders its `detail`/mapped message with no raw JSON); the TK-AC14 401→refresh-coordinator assertion (a ticket-domain request triggers the existing silent-refresh coordinator, assigned here); `vitest-axe` pass on this screen; grep confirms zero `api/` imports |
| T14 | frontend-builder | `screens/` | T8, T12, T3 | `frontend/src/screens/NewTicketScreen.tsx` (new — Change 6, OD-2/OD-5 firm resolutions: `category` is a plain `<input maxLength={50}>`, free text, no `<select>`, no autocomplete, no enum; no new UI/validation/component library of any kind is introduced anywhere in this screen — `react-hook-form`'s built-in `required`/`maxLength` rules only, matching `LoginScreen.tsx`'s existing pattern), `frontend/src/screens/NewTicketScreen.test.tsx` (new) | `npx vitest run src/screens/NewTicketScreen.test.tsx` covers TK-AC3/TK-AC4/TK-AC10/TK-AC12/TK-AC13 and TK-AC14 (403 deactivated-account clause only — the 401→refresh-coordinator assertion is assigned to T13); explicitly asserts `category` renders as a text `<input>` element, not a `<select>` (OD-2); `vitest-axe` pass; grep confirms zero `api/` imports and (per `frontend/package.json`, confirmed unchanged) no new dependency was added to implement this screen |
| T15 | frontend-builder | `screens/` | T7, T9, T10, T11, T12, T3 | `frontend/src/screens/TicketDetailScreen.tsx` (new — Change 6/9, including the pure `offeredActionsForStatus` function; OD-3 firm resolution: the "Reopen" button, when offered for a `resolved` ticket, is never proactively disabled/grayed out by any client-side date computation — always clickable when `offeredActionsForStatus` includes it, with a `409` handled entirely by the existing problem+json rendering path; OD-4 firm resolution: `first_response_at`, when present, renders as plain labeled text — "First response" plus the timestamp — with no SLA-breach language, no color/urgency styling), `frontend/src/screens/TicketDetailScreen.test.tsx` (new) | `npx vitest run src/screens/TicketDetailScreen.test.tsx` covers TK-AC5 through TK-AC9, TK-AC11, TK-AC12, TK-AC13 plus the table-driven `offeredActionsForStatus` test over all five known statuses **and** at least one unrecognized value (asserting `resolve` is never a possible output, and that `resolved` always includes `reopen: true` regardless of any date input); asserts the "Reopen" control is rendered enabled/clickable unconditionally from `resolved` and remains clickable after a `409` (not disabled by the client); asserts `first_response_at` renders with no SLA-styling class/attribute/copy; the plain-text-rendering assertion (DOM-based, no injected `<img>`); `vitest-axe` pass; grep confirms zero `dangerouslySetInnerHTML`, zero `api/` imports, and zero client-side reopen-eligibility date computation |
| T16 | frontend-builder | `screens/`, `components/` (layout) | — (no dependency on T1–T15: `AppShell.tsx` imports none of this story's new `hooks/`/`api/` code, only the pre-existing `useAuthStore()`) | `frontend/src/layouts/AppShell.tsx` (Change 7: renders `<MfaEnrollmentBanner>` off `useAuthStore()`, adds a `/tickets` nav link — first nav element in this file), `frontend/src/components/MfaEnrollmentBanner.tsx` (no internal change — caller move only, listed per the plan's own Files To Modify), `frontend/src/layouts/AppShell.test.tsx`, `frontend/src/components/MfaEnrollmentBanner.test.tsx` | `npx vitest run src/layouts/AppShell.test.tsx src/components/MfaEnrollmentBanner.test.tsx` — new nav-entry assertion, banner rendering from its new caller, existing `LogoutControls`/dismiss-behavior assertions kept unweakened |
| T17 | frontend-builder | `screens/` | T16 | Delete `frontend/src/screens/PlaceholderHomeScreen.tsx` and `frontend/src/screens/PlaceholderHomeScreen.test.tsx` (Change 7 — superseded by `TicketListScreen.tsx`; deleted only after T16 relocates `MfaEnrollmentBanner`'s render site so it is never orphaned) | grep across `frontend/src` confirms zero remaining references to `PlaceholderHomeScreen` before deletion; `npm run type-check` clean after deletion |
| T18 | frontend-builder | `routes/` | T13, T14, T15, T17 | `frontend/src/routes/AppRoutes.tsx` (Change 11: registers `/tickets` → `TicketListScreen`, `/tickets/new` → `NewTicketScreen`, `/tickets/:id` → `TicketDetailScreen` inside the existing `ProtectedRoute`+`AppShell` group; `/` → `<Navigate to="/tickets" replace>`), `frontend/src/routes/AppRoutes.test.tsx` | `npx vitest run src/routes/AppRoutes.test.tsx` asserts `/` redirects to `/tickets`, `/tickets` renders `TicketListScreen`, `/tickets/new` renders `NewTicketScreen` (not `TicketDetailScreen` — plan v2 Risk 9's route-ranking regression check), `/tickets/:id` renders `TicketDetailScreen`, all three sit inside `ProtectedRoute` |
| T19 | frontend-builder | `routes/`, `screens/` | T18 | `frontend/src/routes/GuestOnlyRoute.tsx` (its one `<Navigate to="/" replace>` → `/tickets`), `frontend/src/screens/LoginScreen.tsx` (`returnTo` default `?? "/"` → `?? "/tickets"`), `frontend/src/screens/MfaVerifyScreen.tsx` (`navigate("/")` → `navigate("/tickets")`), plus `GuestOnlyRoute.test.tsx`/`LoginScreen.test.tsx`/`MfaVerifyScreen.test.tsx` | `npx vitest run src/routes/GuestOnlyRoute.test.tsx src/screens/LoginScreen.test.tsx src/screens/MfaVerifyScreen.test.tsx` — each asserts a `/tickets` target in place of the old `/` literal |
| T20 | gate-enforcer | — | T1–T19 | — | `npm run lint && npm run format:check && npm run type-check && npm run test:coverage` (`AGENTS.md` §2 Frontend subsection — load-bearing script names); confirms 85% coverage floor with no exclusion for `offeredActionsForStatus`'s unrecognized-status branch, the 429-only `Retry-After` gate in `parseResponse`, or `useCreateTicket.ts`'s key-rotation branch; confirms `frontend/package.json` gained no new dependency (OD-5) |

**Field notes / ordering rationale:**

- **Ordering rule applied** (`AGENTS.md` §3 Frontend layer table, `implementation-planner`
  §"track: frontend"): `api/` (T1–T5) before `hooks/` (T6–T12); `hooks/` before
  `routes/`/`screens/` (T13–T19); `gate-enforcer` (T20) is the final task, once, not
  embedded per-file.
- **T1 and T2 are parallel-eligible** (neither depends on the other — `httpClient.ts`'s
  header extension and `types.ts`'s new DTOs are independent). **T12 is parallel-eligible
  with T6–T11** (a pure local-state hook with no `api/`/query-key dependency).
- **T16 is deliberately sequenced before T17**, not after: relocating
  `MfaEnrollmentBanner`'s render site into `AppShell.tsx` before deleting
  `PlaceholderHomeScreen.tsx` means the banner is never orphaned mid-sequence — plan v2's
  Risk 6/Risk 7 both name this as a real ripple on already-shipped US-5.1 code, worth
  sequencing deliberately rather than leaving to execution order.
- **T18 depends on T17, not the reverse**: `AppRoutes.tsx`'s route table can only stop
  pointing at `PlaceholderHomeScreen` once that screen is confirmed gone (T17), and can
  only route to the three new screens once they exist (T13–T15).
- **T19 depends on T18**: the four home-route literal changes (`GuestOnlyRoute.tsx`,
  `LoginScreen.tsx`, `MfaVerifyScreen.tsx`) target `/tickets` as the canonical path, which
  only becomes real once `AppRoutes.tsx` (T18) registers it.
- **No task's scope spans more than one execution skill's job** — every task here is
  `frontend-builder`'s alone; `gate-enforcer` (T20) is isolated as the sole non-builder
  task, per the skill's own constraint.
- **What changed from v1 (this is the substantive delta):**
  - **T1/T3**: OD-1 is no longer carried as a risk bounding scope to a 429-only
    FR-12-specific helper. Plan v2 states `ApiError.retryAfterSeconds` as a permanent,
    first-class field set by `parseResponse` on *any* `429` it parses — T1's
    verification now explicitly proves this is not endpoint-scoped (any `429` through
    `httpGet`/`httpPost`/`httpDelete`), while leaving `parseResponseWithMeta`'s separate
    `PATCH` error path untouched, matching the plan's explicit non-extension of that path.
  - **T2**: `category`'s plain-`string` typing is now stated as OD-2's firm resolution
    (no enum, ever waited on) rather than a provisional shape.
  - **T8**: OD-6's mint/reuse/rotate rule is now the literal binding rule (equality check
    on subject/body/category, not a "touched" flag), with three dedicated test cases
    named explicitly, matching plan v2's Risk 5.
  - **T11/T15**: OD-3 is now stated as a hard "never proactively disabled" constraint,
    with an explicit grep check for absence of client-side eligibility-window
    computation, replacing v1's "reactive-only" hedge.
  - **T14**: OD-2 (plain text input) and OD-5 (no new dependency) are now asserted as
    hard constraints in both the task description and its verification step.
  - **T15**: OD-4's plain-text, no-SLA-styling rendering of `first_response_at` is now an
    explicit verification line.
  - **T20**: gains an explicit OD-5 "no new dependency" confirmation, matching plan v2's
    Validation Strategy naming this a hard constraint, not a default subject to
    reconsideration.
  - The file set, dependency graph, and task count (T1–T20) are otherwise unchanged from
    v1 — `impact_analysis` v1 (`PASS`) already covered every file touched by the OD
    resolutions; no new file, screen, hook, or test is introduced by this replan.
- **Every task traces to an item `implementation_plan` v2 or `impact_analysis` v1 already
  named** — no additional file, screen, hook, or test beyond what those two artifacts'
  "Architectural Changes," "Files To Create/Modify/Delete," and "Testing Strategy"/
  "Test-Surface Impact" sections specify. `errorNormalization.ts` and its test are
  correctly absent from this breakdown: plan v2's Change 2 explicitly keeps that file
  unmodified even under the now-first-class `retryAfterSeconds` shape (the field lives on
  `ApiError`'s constructor, not on `NormalizedApiError`). `test-utils.tsx` is correctly
  absent: plan v2's Risk 2 explicitly keeps its signature unchanged, with
  `TicketDetailScreen.test.tsx` (T15) wrapping `ui` in its own local `<Routes>` instead.
