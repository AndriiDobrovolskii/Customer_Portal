---
artifact_type: impact_analysis
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-08T20:15:00Z"
updated_at: "2026-09-08T20:35:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/reviews/specifications/US-5.3-spec-review.md
    version: 1
  - path: docs/reviews/designs/US-5.3-design-review.md
    version: 1
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
supersedes: null
---

# Impact Analysis: Support Tickets (Frontend)

**Story ID:** US-5.3
**Track:** frontend (per `docs/stories/US-5.3-support-tickets-ui.md` front matter)
**Scope note:** `API_DESIGN` and `DB_DESIGN` both returned `NOT_APPLICABLE`, confirmed
by `docs/reviews/designs/US-5.3-design-review.md` (v1, `NOT_APPLICABLE`) — this is a
frontend-only story consuming six already-shipped `app/modules/support` endpoints
(designed/reviewed under US-4.1/US-4.2/US-4.3/US-4.4). This survey therefore covers the
`frontend/` blast radius against `AGENTS.md` §3's "Frontend (`frontend/`)" layer table
(`screens/`, `components/`, `hooks/`, `store/`, `api/`, `routes/`). Backend files
(`app/modules/support/router.py`, `schemas.py`, `exceptions.py`, `service.py`) are named
below only as the (unmodified) contract this story's frontend code must call correctly —
confirmed directly by reading them — they are not affected files.

## 1. Affected Files / Modules / Layers

### `api/` layer

| File | Reason |
|---|---|
| `frontend/src/api/httpClient.ts` | **Definite:** FR-3/FR-4 require `POST /support/tickets` to carry a caller-supplied `Idempotency-Key` header, stable across retries of the same composition. Current `httpPost<T>(path, body, { auth? })` (lines 130-136) has no mechanism to attach an arbitrary extra header — `buildHeaders()` (lines 87-99) only ever sets `Accept`/`Content-Type`/`Authorization`. This needs an additive extension analogous to `httpPatch`'s existing `ifMatch` option (lines 171-204), not a new verb. **Contingent on OD-1 (still OPEN):** FR-12's 429 `Retry-After` handling additionally requires `parseResponse<T>` (lines 57-68) to thread `response.headers` into the thrown `ApiError` — today `ApiError` (lines 25-37) carries only `status`/`fieldErrors`/`kind`, sourced from `normalizeApiError({ status, contentType, body })`, which never receives headers. This second change is real but its exact shape is undecided pending OD-1 (High) — flagged, not resolved, here per this skill's scope. |
| `frontend/src/api/errorNormalization.ts` | **Contingent on OD-1.** `NormalizeApiErrorInput` (lines 16-20) and `normalizeApiError()` (lines 51-75) read only `status`/`contentType`/`body`. If OD-1 resolves toward carrying `retryAfterSeconds` through this function (one candidate shape), this file changes; if OD-1 resolves toward a different mechanism (e.g. reading the header directly in `httpClient.ts` without touching normalization), it may not. Not affected for FR-11's `detail`/`errors` mapping — the existing `detail`-first branch and `extractFieldErrors()` already satisfy TK-AC11 with no new body shape among this story's six endpoints (`TicketRead`/`TicketDetailRead`/`ReplyRead`/`TicketStateRead` all use the same RFC 7807 envelope as US-4.x's already-covered endpoints; no `RegistrationValidationError`-style deviation exists in `app/modules/support/exceptions.py`). |
| `frontend/src/components/apiErrorHelpers.ts` | **Contingent on OD-1.** If `ApiError` gains a `retryAfterSeconds` field, `screens/`/`components/` need a structural getter (matching the existing `getErrorStatus`/`getErrorKind`/`getErrorMessage`/`getFieldErrors` pattern, lines 25-45) to read it without importing `api/httpClient.ts` directly (`AGENTS.md` §3's `screens/`, `components/` row forbids that import). Not affected if OD-1 resolves to a mechanism that doesn't touch `ApiError`'s shape. |
| `frontend/src/api/types.ts` | New DTOs needed for every shape this story's six endpoints use, none of which exist today (current file only has US-5.1/US-5.2 auth/session/profile/MFA/account DTOs): `TicketRead`, `TicketListResponse`, `CreateTicketRequest`, `TicketDetailRead`, `ReplyRead`, `ReplyThreadPage`, `CreateReplyRequest`, `TicketStateRead`, and the (optional-`reason`) `CloseTicketRequest`/`ReopenTicketRequest` bodies — mirrored verbatim off `app/modules/support/schemas.py` (confirmed directly: `CreateTicketRequest`, `TicketRead`, `TicketListResponse`, `CreateReplyRequest`, `ReplyRead`, `ReplyThreadPage`, `TicketDetailRead`, `CloseTicketRequest`, `ReopenTicketRequest`, `TicketStateRead`, lines 8-155 of that file). `AgentTicketRead`/`AgentTicketListResponse`/`AgentTicketStateRead`/`ResolveTicketRequest`/`AssignTicketRequest` are agent-only shapes this story never calls — out of scope, not mirrored. |
| `frontend/src/api/supportApi.ts` (new) | No file for the `/support/tickets` path family exists today (`authApi.ts`, `profileApi.ts`, `mfaApi.ts`, `accountApi.ts` cover only their own prefixes). Needs one typed function per operation this story calls: list (`GET /support/tickets` with `status`/`cursor` query params), create (`POST /support/tickets`, threading the `Idempotency-Key` header through the `httpClient.ts` extension above), get detail (`GET /support/tickets/{id}` with `cursor`/`limit`), reply (`POST /support/tickets/{id}/replies`), close (`POST /support/tickets/{id}/close`), reopen (`POST /support/tickets/{id}/reopen`) — matching `authApi.ts`'s existing one-function-per-operation convention (lines 25-76 of that file). |

### `hooks/` layer (all new — no existing hook covers any ticket operation)

| File | Reason |
|---|---|
| `frontend/src/hooks/useTickets.ts` (new) | FR-1/FR-2: wraps `supportApi`'s list call in a TanStack Query query, parameterized by `status` filter and cursor, following `useSessions.ts`'s query-wrapper shape (lines 1-13 of that file). No existing hook in this codebase manages cursor-based "load more" pagination — this is the first such pattern; `planner`/`frontend-builder` decide `useQuery` vs. `useInfiniteQuery` vs. manual accumulated-cursor state, not settled here. |
| `frontend/src/hooks/useTicketDetail.ts` (new) | FR-5: wraps `GET /support/tickets/{id}` (with its own, independent `replies.next_cursor` pagination per the spec's Client State Notes) — the query key this hook exposes is the one `useReplyToTicket.ts` below must invalidate. |
| `frontend/src/hooks/useCreateTicket.ts` (new) | FR-3/FR-4/OD-6: owns `Idempotency-Key` minting (once per composition, transient — not persisted across reload) and its stability across a retried submission of the *same* composed ticket. OD-6 (still OPEN) — whether an edited-then-resubmitted composition reuses or rotates the key — affects this hook's internal logic, not which file is in scope. |
| `frontend/src/hooks/useReplyToTicket.ts` (new) | FR-6: wraps `POST /support/tickets/{id}/replies`; `onSuccess` must invalidate (not just append to) `useTicketDetail.ts`'s query key, because a customer reply on `waiting_on_customer` transitions the ticket to `waiting_on_support` server-side and `ReplyRead` carries no status field to report that — the same "hook reaches into another hook's query key" shape as `useRevokeSession.ts` reaching into `SESSIONS_QUERY_KEY` (`useSessions.ts` line 5). |
| `frontend/src/hooks/useCloseTicket.ts` (new) | FR-7: wraps `POST /support/tickets/{id}/close`; `onSuccess` must update or invalidate the ticket-detail query so the screen reflects `closed` and the reply composer becomes unavailable (FR-9). |
| `frontend/src/hooks/useReopenTicket.ts` (new) | FR-8: wraps `POST /support/tickets/{id}/reopen`; must surface the `409` (outside the 7-day window) distinctly enough for the screen to render its `detail` rather than a generic failure (FR-8, OD-3 — reactive-only, no pre-disable). |

### `screens/` layer (all new)

| File | Reason |
|---|---|
| `frontend/src/screens/TicketListScreen.tsx` (new) | FR-1/FR-2: `/tickets` — list, five-status filter, cursor "Load more", empty state with "New ticket" CTA, unrecognized-`status` verbatim rendering. |
| `frontend/src/screens/NewTicketScreen.tsx` (new; exact name is a `planner`/`frontend-builder` naming call) | FR-3/FR-4/FR-10: the create-ticket form — subject/body/category bounds, `Idempotency-Key` handling, landing on the created ticket's detail screen on `201`. |
| `frontend/src/screens/TicketDetailScreen.tsx` (new) | FR-5/FR-6/FR-7/FR-8/FR-9/FR-10: ticket header, reply thread with its own cursor, reply composer (no visibility control), close/reopen actions gated by FR-9's status/offered-action table. |

### `screens/` layer — existing screen affected by FR-15

| File | Reason |
|---|---|
| `frontend/src/screens/PlaceholderHomeScreen.tsx` | FR-15 moves the authenticated home route from `/` (this screen) to `/tickets` (`TicketListScreen.tsx` above). Its own header comment (line 1-3) already names this story as the reason it was "intentionally minimal/placeholder." This screen currently renders `<MfaEnrollmentBanner deadline={...} />` (line 12) — since its mount point is being retired as "home," the banner's render site must move somewhere still reachable on every authenticated page load (candidates: `layouts/AppShell.tsx` so it appears everywhere, or into `TicketListScreen.tsx` so it appears only on the new home — a placement decision for `planner`, not resolved here). Whether the file itself is deleted or kept-but-unrouted is likewise a `planner` decision; either way it no longer serves as the `/` route's element once FR-15 lands. |

### `components/` layer

| File | Reason |
|---|---|
| `frontend/src/components/MfaEnrollmentBanner.tsx` | **New cross-file dependency, flagged explicitly per this skill's instruction.** Today this component is rendered from exactly one place — `screens/PlaceholderHomeScreen.tsx` (line 12) — a mount point FR-15 retires. It must be re-mounted from a different file (`layouts/AppShell.tsx` or `screens/TicketListScreen.tsx`, see row above); the component itself likely needs no internal change, but its *caller* changes, which is a real ripple this story introduces that did not exist before it. |

### `routes/` layer

| File | Reason |
|---|---|
| `frontend/src/routes/AppRoutes.tsx` | FR-1/FR-3/FR-5/FR-15: must register `/tickets` (`TicketListScreen`), a create route (`NewTicketScreen`), and `/tickets/:id` (`TicketDetailScreen`) inside the existing `ProtectedRoute`+`AppShell` group (same shape as `/sessions`, `/settings/*`, lines 69-81 today) — this is the **first route with a dynamic path segment** (`:id`) anywhere in this file; every existing route is static. FR-15 also requires replacing (or redirecting) the current `<Route path="/" element={<PlaceholderHomeScreen />} />` (line 76) — whether `/` is removed entirely, kept as a `<Navigate to="/tickets" replace>`, or literally reassigned to render `TicketListScreen` is a `planner` decision; all three satisfy "the home route move[d] to `/tickets`" but have different test/URL implications. |
| `frontend/src/routes/GuestOnlyRoute.tsx` | Line 15's `<Navigate to="/" replace />` is the authenticated-visitor-hits-a-guest-route redirect target. Per FR-15 this must become `/tickets` (or whatever `/` resolves to after the `AppRoutes.tsx` decision above) — confirmed this is the only hardcoded redirect target in this 20-line file. |
| `frontend/src/screens/LoginScreen.tsx` | Line 33: `const returnTo = locationState?.from?.pathname ?? "/";` — the post-login default landing target when no `from` state exists (a direct, un-redirected login) must become `/tickets` per FR-15's "home route move[d]." |
| `frontend/src/screens/MfaVerifyScreen.tsx` | Line 32: `navigate("/")` after a successful MFA challenge — same FR-15 home-route change, the MFA-required login path's equivalent of `LoginScreen.tsx`'s `returnTo` default. |

### `layouts/` layer

| File | Reason |
|---|---|
| `frontend/src/layouts/AppShell.tsx` | FR-15: "`/tickets` is added to the app shell's navigation." Today this file (23 lines) has **no navigation element at all** — only a `<header>` holding `LogoutControls` (line 18) and `<main>{children ?? <Outlet />}</main>` (line 20). Adding a nav entry is new structure, not an edit to an existing nav list. If `MfaEnrollmentBanner` also relocates here (see `components/` row above), that is a second, independent reason this file changes. |

## 1a. Checked — Not Affected (reference only)

| File | Why it was checked | Why it is not affected |
|---|---|---|
| `frontend/src/components/ErrorState.tsx`, `frontend/src/components/FieldError.tsx` | FR-10/FR-11/FR-13 apply to every new screen in this story. | Both are already generic (`kind`-based / field-message-based, confirmed by reading both files in full) and reusable as-is by `TicketListScreen`, `NewTicketScreen`, `TicketDetailScreen` with no new props or variants required. |
| `frontend/src/store/authStore.tsx` | Every screen needs to know the current user is authenticated; `PlaceholderHomeScreen.tsx` reads `user`/`mfaEnrollmentDeadline` from it today. | No new store field or action is implied by any FR — ticket ownership (`404` vs. showing another customer's ticket, FR-11) is enforced entirely server-side; the store's existing `isAuthenticated`/`user` shape is read-only-consumed exactly as today. |
| `frontend/src/routes/ProtectedRoute.tsx` | New routes (`/tickets`, `/tickets/:id`) sit inside its existing guarded group. | Guards on `isAuthenticated` only; contains no hardcoded path literal that FR-15's home-route change would touch (confirmed: its only `<Navigate>` target is `/login`, line 50). |
| `frontend/src/store/queryClient.ts` | Every new `hooks/` query/mutation above shares this client. | Existing `{ queries: { retry: 1 }, mutations: { retry: 0 } }` defaults (lines 8-11) are generic and sufficient; no FR asks for a per-query override. |
| `frontend/package.json` | OD-5 (still OPEN) asks whether this story's new interactive surfaces (status filter, cursor list, reply composer, close/reopen confirmation) change the hand-built-components precedent. | Confirmed no `zod`/`yup`/headless-UI/component-library dependency exists today (checked directly); nothing in FR-1 through FR-15 requires one — max-length/required validation uses `react-hook-form`'s built-in rules, the same mechanism `LoginScreen.tsx`/`RegisterScreen.tsx` already use. `Idempotency-Key` UUIDv4 generation uses the native `crypto.randomUUID()` Web API — no new package. |
| Any `*.css` file / a styling layer | NFR bar requires responsive layout (~375px through desktop) and visible focus on every control across three new screens. | Confirmed no styling layer exists anywhere in `frontend/src` today (`main.tsx` imports no stylesheet; a repo-wide glob for `frontend/**/*.css` returns matches only under `node_modules`/`coverage`, none under `src/` or `public/`). This is a pre-existing gap this story does not need to fill to satisfy its own ACs (none of TK-AC1–14 assert visual layout), but is recorded here as a fact `planner` needs rather than one it would have to rediscover — the three new screens will render unstyled (or with inline styles only) unless a styling decision is made, same as every existing screen today. |

## 2. Cross-Module Ripple

This is a frontend-only story; "cross-module" here means cross-layer calls within
`frontend/`, per `AGENTS.md` §3's Frontend layer table — there is no backend
service→service ripple to trace, because no backend `app/modules/*` file is modified.

Within `frontend/`:
- `screens/TicketListScreen.tsx` → `hooks/useTickets.ts` → `api/supportApi.ts` (list) →
  `api/httpClient.ts` → backend `GET /support/tickets`
  (`app/modules/support/router.py::list_own_tickets`, unmodified — confirmed this route
  already branches on `tickets:read` scope internally; the customer branch this story
  calls is unaffected by that branching).
- `screens/NewTicketScreen.tsx` → `hooks/useCreateTicket.ts` → `api/supportApi.ts`
  (create, threading `Idempotency-Key`) → `api/httpClient.ts` (extended for the header) →
  backend `POST /support/tickets` (`router.py::create_ticket`, unmodified — already
  declares `idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]`).
- `screens/TicketDetailScreen.tsx` → `hooks/useTicketDetail.ts`, `useReplyToTicket.ts`,
  `useCloseTicket.ts`, `useReopenTicket.ts` → `api/supportApi.ts` → `api/httpClient.ts` →
  backend `GET /support/tickets/{id}`, `POST .../replies`, `POST .../close`,
  `POST .../reopen` (`router.py`, all unmodified).
- `hooks/useReplyToTicket.ts` → `hooks/useTicketDetail.ts`'s query key (invalidation) —
  an intra-`hooks/` dependency, same shape as US-5.1's `useRevokeSession.ts` →
  `useSessions.ts`'s `SESSIONS_QUERY_KEY`.
- `components/MfaEnrollmentBanner.tsx`'s render site moves from
  `screens/PlaceholderHomeScreen.tsx` to `layouts/AppShell.tsx` or
  `screens/TicketListScreen.tsx` (placement undecided — see section 1). **This is the one
  new intra-frontend dependency this story introduces that did not exist before it**,
  flagged per the skill's instruction to call out a new cross-boundary dependency
  explicitly: today `PlaceholderHomeScreen.tsx` is `MfaEnrollmentBanner.tsx`'s only
  caller; after this story its caller changes.
- `routes/AppRoutes.tsx`, `routes/GuestOnlyRoute.tsx`, `screens/LoginScreen.tsx`,
  `screens/MfaVerifyScreen.tsx` all reference the literal home-route path — FR-15 changes
  that literal in all four simultaneously; none of the four calls into any of the others,
  so this is a shared-constant ripple, not a call-graph one.

No new dependency from `hooks/`/`api/` back into `screens/`/`components/` is introduced
(would violate `AGENTS.md` §3's downward-only import direction) and none was found
necessary.

## 3. Migration/Schema Impact

**None.** Confirmed explicitly, per the skill's requirement not to omit this section
silently:
- `API_DESIGN` and `DB_DESIGN` both recorded `NOT_APPLICABLE` for this story
  (corroborated directly by `docs/reviews/designs/US-5.3-design-review.md`, v1,
  `NOT_APPLICABLE`).
- The approved spec's Out of Scope section states this explicitly: "Any backend/API/DB
  change. This Story implements only against already-shipped backend endpoints; it does
  not add, modify, or design any API route, request/response contract, or database
  schema/table/column."
- Confirmed by direct inspection: `app/modules/support/schemas.py`, `router.py`, and
  `exceptions.py` already declare every field and status code FR-1 through FR-14
  reference (`ticket_number`, `subject`, `category`, `status`, `updated_at`,
  `created_at`, `first_response_at`, `next_cursor`, reply `author_kind`/`body`/
  `created_at`, the `Idempotency-Key` header, `TicketCreationRateLimitError`'s and
  `TicketReplyRateLimitError`'s `Retry-After` header, `IdempotencyKeyReuseError`'s
  `422`). No new column, table, index, or migration is implied by any FR.
- No existing backend repository query is affected — every endpoint this story calls is
  already shipped and unmodified.
- FR-4/FR-12/OD-1's `Idempotency-Key`/`Retry-After` handling is exclusively client-side
  (transient form state / HTTP-client header plumbing), not a persistence-layer decision,
  matching this story's design review's own conclusion.

## 4. Test-Surface Impact

### Existing test files that must change

| File | Reason |
|---|---|
| `frontend/src/routes/AppRoutes.test.tsx` | Currently asserts `"/"` as the landing route in three places (lines 47, 55, 103). Must gain route-table assertions for `/tickets`, the create route, and `/tickets/:id`, and must update or replace every existing `"/"`-target assertion per FR-15. |
| `frontend/src/routes/GuestOnlyRoute.test.tsx` | Currently asserts the authenticated-visitor redirect lands on `"/"` (line 19). Must change to the new home-route path per FR-15. |
| `frontend/src/screens/LoginScreen.test.tsx` | Covers the direct-login `returnTo` default (`LoginScreen.tsx` line 33); must assert landing on the new home path when no `from` state is present. |
| `frontend/src/screens/MfaVerifyScreen.test.tsx` | Covers the post-MFA-verify `navigate("/")` (`MfaVerifyScreen.tsx` line 32); must assert the new home path. |
| `frontend/src/screens/PlaceholderHomeScreen.test.tsx` | The screen it covers is being retired as the `/` route's element (FR-15) — this file is either deleted (if the screen is deleted) or repurposed, either way it changes. |
| `frontend/src/components/MfaEnrollmentBanner.test.tsx` | If the banner's render site moves per section 1/2, this test's rendering harness (however it currently mounts the banner) needs to reflect the new caller. |
| `frontend/src/layouts/AppShell.test.tsx` | Currently exercises only `LogoutControls` (both its tests target `/` as the pre-logout route via `renderWithProviders(<AppShell />, { route: "/", ... })`, lines 31/51). Must gain assertions for the new nav entry (FR-15) and, if the banner relocates here, for that too. Existing `route: "/"` fixture values may also need to become `/tickets` if `AppShell`'s own tests should reflect the new home. |
| `frontend/src/api/httpClient.test.ts` | Must gain coverage for the `Idempotency-Key` header-passing extension to `httpPost` (definite, FR-3/FR-4) and, contingent on OD-1's resolution, for `Retry-After` header threading into `ApiError`. |
| `frontend/src/api/errorNormalization.test.ts` | Contingent on OD-1 only — if `normalizeApiError`'s input/output shape changes, its existing test cases need a corresponding new case; otherwise unaffected. |
| `frontend/src/test/mswHandlers.ts` | Must gain baseline handlers for all six endpoints this story calls (`GET /support/tickets`, `POST /support/tickets`, `GET /support/tickets/{id}`, `POST /support/tickets/{id}/replies`, `POST /support/tickets/{id}/close`, `POST /support/tickets/{id}/reopen`), following the existing one-handler-per-operation convention (`mswHandlers.ts` lines 14-114). Not a new file — shared baseline infrastructure every new screen's tests will import. |
| `frontend/src/test/test-utils.tsx` | Two independent reasons. (1) Its own doc comment (lines 32-34) ties `mfaEnrollmentDeadline` to being "Surfaced by PlaceholderHomeScreen via the auth store" — stale once `MfaEnrollmentBanner`'s render site moves (section 1/2), needs updating to name the new caller. (2) `renderWithProviders`/`renderHookWithProviders` (lines 74-115) render `ui` as a bare element inside a route-less `MemoryRouter` — sufficient for every existing screen, none of which reads a URL param. `TicketDetailScreen.tsx` (section 1) is the first screen needing `useParams()` off `/tickets/:id`; a bare-element render leaves `useParams()` empty, so its test file must wrap `ui` in its own `<Routes><Route path="/tickets/:id" .../></Routes>` when calling `renderWithProviders` (still possible without changing this file's signature) — flagged here so `planner`/`test-writer` don't rediscover the gap mid-write, not because the file is provably forced to change. |

### New test files (net-new screens/hooks have no existing coverage to update)

- `frontend/src/screens/TicketListScreen.test.tsx`
- `frontend/src/screens/NewTicketScreen.test.tsx`
- `frontend/src/screens/TicketDetailScreen.test.tsx`
- `frontend/src/hooks/useTickets.test.ts`
- `frontend/src/hooks/useTicketDetail.test.ts`
- `frontend/src/hooks/useCreateTicket.test.ts`
- `frontend/src/hooks/useReplyToTicket.test.ts`
- `frontend/src/hooks/useCloseTicket.test.ts`
- `frontend/src/hooks/useReopenTicket.test.ts`
- An a11y test pass (axe, per the existing `vitest-axe` devDependency and
  `test/vitest-axe.d.ts`, same mechanism already used elsewhere in this codebase) on
  `TicketListScreen`, `NewTicketScreen`, and `TicketDetailScreen` specifically — the
  story's own Enforcement Matrix names list/create/detail for the automated a11y check;
  no existing a11y test covers them since they don't exist yet.
- A test asserting plain-text rendering of an HTML-bearing ticket/reply body (NFR bar,
  story's Enforcement Matrix) — likely folded into `TicketDetailScreen.test.tsx` rather
  than a standalone file; naming left to `planner`/`test-writer`.

## Non-Blocking Findings

- **OD-1 (High, still OPEN) has a genuine file-scope consequence, carried forward from
  `API_DESIGN`'s own recorded finding** ("OD-1 assessed as a frontend `httpClient`
  concern, not a backend API contract change"): whether `api/errorNormalization.ts` and
  `components/apiErrorHelpers.ts` are in scope for this story at all — not merely how
  they change — depends on OD-1's resolution. `api/httpClient.ts` is affected either way
  (the `Idempotency-Key` extension is unconditional), but the `Retry-After` extension is
  not. This is disclosed rather than resolved, matching `SPEC_REVIEW`'s and
  `DESIGN_REVIEW`'s own non-blocking treatment of the same item.
- `frontend/src/test/test-utils.tsx`'s bare-element render harness has no precedent for a
  screen reading a URL param (`TicketDetailScreen.tsx` off `/tickets/:id` is the first) —
  workable without a signature change (wrap `ui` in a local `<Routes>`), but flagged so it
  is not rediscovered mid-`IMPLEMENTATION`.
- No styling layer (`*.css` or equivalent) exists anywhere in `frontend/src` today; the
  three new screens inherit that same gap rather than this story introducing it.

## Notes for Downstream Stages

- Three placement/shape decisions are flagged as undecided in section 1 rather than
  resolved here (this is a survey, not a plan): (a) `MfaEnrollmentBanner.tsx`'s new
  render site — `AppShell.tsx` vs. `TicketListScreen.tsx`; (b) whether `/` is removed,
  redirected, or reassigned once `/tickets` becomes home; (c) `httpClient.ts`/
  `errorNormalization.ts`/`apiErrorHelpers.ts`'s exact `Retry-After` shape, which cannot
  be settled until OD-1 (High, still OPEN) is resolved.
- OD-1 (High) is the one Open Decision with a genuine file-scope consequence: depending
  on its resolution, `api/httpClient.ts`, `api/errorNormalization.ts`, and
  `components/apiErrorHelpers.ts` either do or do not need a `Retry-After`-carrying
  change, beyond the `Idempotency-Key` change to `httpClient.ts` those files need
  regardless (FR-3/FR-4 do not depend on OD-1).
- OD-2 (category free-text vs. future enum), OD-3 (reactive-only 7-day reopen window),
  OD-4 (`first_response_at` copy), and OD-6 (edited-resubmission key reuse) each affect
  the *behavior* of a file already listed above (`NewTicketScreen.tsx`,
  `useReopenTicket.ts`/`TicketDetailScreen.tsx`, `TicketDetailScreen.tsx`,
  `useCreateTicket.ts` respectively) — none implies an additional file beyond those
  already listed.
- OD-5 (component/design-system convention) is assessed in section 1a as not affecting
  `package.json`; if a future resolution reverses that precedent, this survey would need
  to be revisited, but nothing in the current spec forces that reversal.
