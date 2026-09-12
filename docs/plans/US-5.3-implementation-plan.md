---
artifact_type: implementation_plan
story: US-5.3
version: 2
status: APPROVED
created_at: "2026-09-08T19:49:34Z"
updated_at: "2026-09-08T22:30:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/reviews/specifications/US-5.3-spec-review.md
    version: 1
  - path: docs/reviews/designs/US-5.3-design-review.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/workflow/history.jsonl
    version: null
supersedes: docs/plans/US-5.3-implementation-plan.md
---

# Implementation Plan: Support Tickets — Frontend (US-5.3)

## Re-plan note (v2, attempt 2)

Version 1 of this plan was rejected at `HUMAN_PLAN_APPROVAL` specifically because it left
OD-1 through OD-6 unresolved and only planned *around* them with hedged, provisional
language ("narrowest reading pending OD-1," "does not resolve OD-6 as a product decision,"
"OD-5's de facto precedent"). The human has since supplied final, binding resolutions for
all six, recorded in the `HUMAN_REJECTED` event's `comment` field
(`docs/workflow/history.jsonl`, `2026-09-08T21:00:00Z`). `docs/decisions/US-5.3-open-decisions.md`
still shows version 1 / `DRAFT` with OD-1..OD-6 marked `OPEN` on disk — `us-clarifier`, not
`planner`, owns rewriting that artifact — but for the purposes of this plan the six
resolutions below are treated as **firm architectural requirements**, not workarounds:

| # | Severity | Binding resolution |
|---|---|---|
| OD-1 | High | `httpClient.ts`'s `ApiError` gains a first-class `retryAfterSeconds` field; `parseResponse` reads the `Retry-After` header on a `429` and threads it in. This is the target architecture, not a helper scoped narrowly to FR-12. |
| OD-2 | Medium | `category` ships as a plain text input, `maxLength=50`. No stakeholder value list is waited on. |
| OD-3 | Medium | The backend's `409` enforces the 7-day reopen window. "Reopen" is **not** proactively disabled client-side. |
| OD-4 | Low | `first_response_at` renders as plain text — no SLA-breach context or styling. |
| OD-5 | Low | Continue the project's own hand-built React components. No new UI/headless component library. |
| OD-6 | Medium | An edited-then-resubmitted create attempt (subject/body/category changed) mints a new `Idempotency-Key`; a verbatim resubmission reuses the same key. |

Every place in v1 that hedged, flagged-as-at-risk, or deferred one of these six is rewritten
below to state the resolution as delivered architecture. Sections unaffected by any of the
six (Changes 3, 4, 5, 7, 9, 11 and their file lists) are carried forward from v1 essentially
unchanged, since `impact_analysis` v1 (`PASS`) and `design_review` v1 (`NOT_APPLICABLE`)
still hold and neither this replan nor the human's resolutions touch any backend contract.

## Goal

Add the customer-facing support-ticket surface to US-5.1/US-5.2's `frontend/`
tree per the approved spec (v1, `APPROVED`): a five-status-filterable,
cursor-paginated ticket list (FR-1/FR-2), ticket creation with a stable
per-composition `Idempotency-Key` that rotates on an edited resubmission
(FR-3/FR-4, OD-6), ticket detail plus an independently cursor-paginated reply
thread (FR-5), posting a public reply that invalidates ticket detail (FR-6),
close/reopen with status-driven affordances and a reactive-only (never
pre-disabled) reopen control (FR-7/FR-8/FR-9, OD-3), client-side validation
including a free-text `category` field (FR-10, OD-2), problem+json error
rendering including a dedicated 404 state (FR-11), 429 rate-limit handling
built on `ApiError.retryAfterSeconds` as first-class shared-client
architecture (FR-12, OD-1), network/5xx handling (FR-13), and the existing
401 silent-refresh interaction (FR-14) — against six already-shipped
`app/modules/support` endpoints, no backend/API/DB change (`API_DESIGN`/
`DB_DESIGN` both `NOT_APPLICABLE`, reconfirmed by `design_review` v1 and
`impact_analysis` v1, `PASS`). It also carries FR-15: the authenticated home
route and post-login redirect move from `/` (`PlaceholderHomeScreen.tsx`) to
`/tickets`, and `/tickets` is added to the app shell's navigation — the one
change to already-shipped US-5.1/US-5.2 code this story makes. No new UI
component library is introduced (OD-5) — every new interactive surface
(status filter, cursor list, reply composer, close/reopen controls) is built
from this codebase's existing hand-rolled primitives.

All six Open Decisions the source story left open (OD-1 through OD-6) are
resolved by binding human directive as of this plan's re-run and are
incorporated below as firm architecture, not contingencies. Architectural
Change 2 (formerly the narrowest-reading, OD-1-pending shape of `httpClient.ts`'s
`Retry-After` handling) is rewritten to state the target architecture
directly: `ApiError` itself carries `retryAfterSeconds` as a permanent,
first-class field of the shared HTTP client, not a mechanism scoped to this
story's two rate-limited endpoints.

## Architectural Changes

### 1. `httpClient.ts`: an additive `Idempotency-Key` option on `httpPost`

FR-3/FR-4 need `POST /support/tickets` to carry a caller-supplied
`Idempotency-Key` header, stable across retries of the same composition.
`httpPost<T>(path, body, { auth? })` today has no way to attach an arbitrary
extra header (`buildHeaders()` sets only `Accept`/`Content-Type`/
`Authorization`). This plan extends `httpPost`'s options bag, mirroring
`httpPatch`'s existing `ifMatch` precedent exactly:

```ts
export function httpPost<T>(
  path: string,
  body?: unknown,
  options: { auth?: boolean; idempotencyKey?: string } = {},
): Promise<T>
```

`buildHeaders()` gains a fourth, optional parameter threaded only into the
`POST` path; when `options.idempotencyKey` is supplied it is set verbatim as
the `Idempotency-Key` header. Every existing `httpPost` call site
(`authApi.ts`'s `register`/`login`/`verifyMfa`/`refresh`/`logout`/
`logoutAll`/`requestPasswordReset`/`confirmPasswordReset`/`verifyEmail`/
`resendVerificationEmail`, plus US-5.2's `mfaApi.ts`/`accountApi.ts`
functions) omits the new option and keeps behaving exactly as before —
purely additive, same shape as `httpPatch`'s `ifMatch` (US-5.2 Plan Change
1). Unaffected by any of the six OD resolutions; unchanged from v1.

### 2. `ApiError.retryAfterSeconds` — a first-class field on the shared `ApiError`, sourced from `Retry-After` on every `429` (OD-1's binding resolution — this is the target architecture, superseding v1's narrower reading)

FR-12 needs the customer-facing message naming "when the customer may
retry" on a `429` from `POST /support/tickets` or `POST /{id}/replies`. The
value exists only in the `Retry-After` response header
(`TicketCreationRateLimitError`/`TicketReplyRateLimitError` both set
`self.headers = {"Retry-After": str(retry_after_seconds)}`, confirmed
directly in `app/modules/support/exceptions.py`); `parseResponse<T>` today
never passes `response.headers` into `normalizeApiError()`.

**v1 treated this as the narrowest change that satisfied FR-12 pending
OD-1's resolution, flagged as a blocking dependency subject to revision.
That framing is retired.** The human's binding resolution states this
mechanism *is* the final target architecture for the shared HTTP client, not
a helper bounded to this story's two endpoints:

- `ApiError` gains one new, first-class field: `readonly retryAfterSeconds?:
  number`, declared on the class itself alongside `status`/`fieldErrors`/
  `kind` — not a bolt-on attached after construction as a stopgap, but a
  permanent part of `ApiError`'s public shape.
- The `ApiError` constructor gains a third, optional parameter —
  `constructor(normalized: NormalizedApiError, kind?: "network" | "server",
  retryAfterSeconds?: number)` — that sets `this.retryAfterSeconds`
  directly. `NormalizedApiError` itself (defined in
  `errorNormalization.ts`) is **not** extended and gains no new field;
  `normalizeApiError()`'s existing signature, return shape, and every
  existing call site are untouched, so `errorNormalization.ts` stays
  unmodified (`impact_analysis`'s conditional listing of that file
  resolves to "not needed," now confirmed rather than provisional).
- `parseResponse<T>` is the single place that supplies the constructor's
  third argument: it reads `response.headers.get("Retry-After")` and, when
  the response status is `429` and the header parses as a non-negative
  integer, calls `new ApiError(normalized, undefined, retryAfterSeconds)`
  instead of the current `new ApiError(normalized)`. Every other status/
  response shape passes `undefined` (the parameter's default), so
  `ApiError.retryAfterSeconds` is `undefined` everywhere except a
  successfully-parsed `429`.
- `apiErrorHelpers.ts` gains one new structural getter,
  `getRetryAfterSeconds(error: unknown): number | undefined`, mirroring
  `getErrorStatus`'s existing pattern exactly, so `NewTicketScreen.tsx`/
  `TicketDetailScreen.tsx` never import `api/httpClient.ts`'s `ApiError`
  class directly (`AGENTS.md` §3's `screens/`/`components/` row). This
  getter is the permanent, layering-correct read path for the field — not
  a workaround scoped to FR-12.

Because `ApiError.retryAfterSeconds` is now a permanent part of the shared
client's error shape (not a mechanism special-cased to this story), any
future `429` reached through `performRequest`/`parseResponse` — i.e.
`httpGet`, `httpPost`, or `httpDelete`, which covers every endpoint this
story calls — automatically carries this field with no further change,
rather than a per-endpoint mechanism repeated for each new rate-limited
route. This does **not** extend to `httpPatch`'s separate error path
(`parseResponseWithMeta`, its own `throw new ApiError(normalized)` branch,
added in US-5.2 for `ETag` handling) — no endpoint this story calls uses
`PATCH`, and the human's resolution names `parseResponse` specifically, so
this plan leaves `parseResponseWithMeta` untouched. A future story adding
`Retry-After` handling to a `PATCH` endpoint would need the same
one-line constructor-argument change applied symmetrically there; that is
a small, obvious follow-up, not evidence this shape is provisional. This
is no longer a blocking dependency or an at-risk item pending a future
decision; `IMPLEMENTATION` builds exactly this shape.

### 3. New `api/supportApi.ts`, one function per operation, mirroring `authApi.ts`'s convention

No file for the `/support/tickets` path family exists today. New file, one
typed function per endpoint this story calls:

```ts
listTickets(params: { status?: TicketStatus; cursor?: string }): Promise<TicketListResponse>
createTicket(payload: CreateTicketRequest, idempotencyKey: string): Promise<TicketRead>
getTicketDetail(id: string, params: { cursor?: string; limit?: number }): Promise<TicketDetailRead>
replyToTicket(id: string, payload: CreateReplyRequest): Promise<ReplyRead>
closeTicket(id: string, payload: CloseTicketRequest): Promise<TicketStateRead>
reopenTicket(id: string, payload: ReopenTicketRequest): Promise<TicketStateRead>
```

`listTickets`/`getTicketDetail` build their query string with
`URLSearchParams` inside `supportApi.ts` itself (no precedent for query
params exists anywhere in this codebase today — `httpGet`'s signature is
untouched; the caller composes the full `path` string, same pattern
`httpDelete`'s `revokeSession` already uses for a path-embedded id).
`createTicket` threads `idempotencyKey` into `httpPost`'s new option
(Change 1). `closeTicket`/`reopenTicket` always send a body (`{ reason:
undefined }` is a legal `CloseTicketRequest`/`ReopenTicketRequest` per
`app/modules/support/schemas.py` — both fields are optional, not absent);
this story's UI never collects a `reason` (no FR/AC asks for one), so both
functions send `{}`. `replyToTicket` never sets `visibility` (Client State
Notes / FR-6: the composer has no visibility control at all) and always
sends `attachment_ids: []` alongside `createTicket`, matching Assumption
#3. Unaffected by any of the six OD resolutions; unchanged from v1.

### 4. `types.ts`: additive DTOs mirrored off `app/modules/support/schemas.py`

`TicketRead`, `TicketListResponse`, `CreateTicketRequest`, `TicketDetailRead`,
`ReplyRead`, `ReplyThreadPage`, `CreateReplyRequest`, `TicketStateRead`,
`CloseTicketRequest`, `ReopenTicketRequest` — field lists copied verbatim
from the backend schemas already read for this plan (`status`/`author_kind`/
`visibility` as plain `string`/string-literal-union types matching the
backend's `Literal[...]`, per the spec's Client State Notes instruction to
render an unrecognized `status` verbatim rather than narrowing the type in
a way that would make an unexpected value a TypeScript error). A
`TicketStatus` union type (`"open" | "waiting_on_support" |
"waiting_on_customer" | "resolved" | "closed"`) is exported alongside for
the status filter and the FR-9 affordance table, but `TicketRead.status`/
`TicketDetailRead.status` stay typed as plain `string` (not
`TicketStatus`), matching the backend's own un-enforced `str` field and the
spec's explicit "plain string, not an enum" instruction — narrowing
happens only where FR-9's table is evaluated, never at the DTO boundary.
`category` is typed as plain `string` (OD-2's binding resolution: free
text, `maxLength=50`, no enum) with no companion literal-union type, since
no value list exists to enumerate.
`AgentTicketRead`/`AgentTicketListResponse`/`AgentTicketStateRead`/
`ResolveTicketRequest`/`AssignTicketRequest` are agent-only shapes this
story never calls and are not mirrored (Out of Scope).

### 5. `hooks/`: one hook per operation, cursor pagination via `useInfiniteQuery`

Six new hooks. This codebase's only existing list-consuming hook
(`useSessions.ts`) has no pagination at all — this is the first cursor
pagination in this frontend. This plan chooses TanStack Query's
`useInfiniteQuery` for both paginators (the ticket list's own cursor, FR-1/
FR-2, and the reply thread's independent cursor, FR-5) over hand-rolled
accumulated-cursor `useState`, because `useInfiniteQuery` already gives
"Load more"/"Load older replies" (`fetchNextPage`, `hasNextPage` derived
from `next_cursor !== null`) and status-filter/cursor-reset (FR-2, a
`queryKey` change on `status` naturally invalidates and restarts pagination)
without hand-written cache-merging logic — the same trade-off `authStore`
already makes elsewhere in this codebase (prefer the library's own primitive
over hand-rolled state where one directly fits).

- `useTickets.ts` — `useInfiniteQuery` keyed on `["tickets", status]`,
  `getNextPageParam` reading `next_cursor`. FR-1/FR-2.
- `useTicketDetail.ts` — `useQuery` keyed on `["ticket", id]` for the
  header fields, wrapping `getTicketDetail`'s first page; a **sibling**
  (not nested) `useInfiniteQuery` keyed on `["ticket-replies", id]` for
  `replies.next_cursor`'s own pagination (FR-5's "two separate
  paginators" requirement). The replies key is deliberately **not**
  `["ticket", id, "replies"]` — TanStack Query treats a query key as a
  prefix match for invalidation, so a nested key would make
  `invalidateQueries({ queryKey: ["ticket", id] })` also invalidate and
  reset the replies pagination, silently discarding any "Load older
  replies" pages the customer already fetched every time a reply posts.
  The two top-level keys (`["ticket", id]` and `["ticket-replies", id]`)
  share no prefix, so invalidating one is provably independent of the
  other. This hook exposes both as named exports —
  `ticketDetailQueryKey(id)` and `ticketRepliesQueryKey(id)` — which the
  mutation hooks below invalidate selectively (`useReplyToTicket.ts`
  invalidates both; `useCloseTicket.ts`/`useReopenTicket.ts` invalidate
  only `ticketDetailQueryKey(id)`, since neither changes the reply
  thread). Same "hook reaches into another hook's query key" shape as
  US-5.1's `useRevokeSession.ts` → `useSessions.ts`'s
  `SESSIONS_QUERY_KEY`.
- `useCreateTicket.ts` — owns `Idempotency-Key` minting via
  `crypto.randomUUID()` (native Web API, no new dependency, confirmed
  available per `impact_analysis`'s OD-5 finding). See Change 8 for the
  exact minting/reuse/rotation rule, OD-6's binding resolution. FR-3/FR-4.
- `useReplyToTicket.ts` — `useMutation`; `onSuccess` invalidates **both**
  `ticketDetailQueryKey(id)` (FR-6's explicit instruction that ticket
  detail, not just the thread, must refetch — `ReplyRead` carries no
  status field to report the possible `waiting_on_customer` →
  `waiting_on_support` transition) **and** `ticketRepliesQueryKey(id)`
  (so the new reply appears in the thread, FR-6's first clause).
  Invalidating an already-fetched `useInfiniteQuery` refetches every page
  currently loaded, in order — it does not collapse the thread back to
  page one, so a customer who already clicked "Load older replies" keeps
  those pages after posting.
- `useCloseTicket.ts` — `useMutation`; `onSuccess` invalidates
  `ticketDetailQueryKey(id)` so the screen reflects `closed` (FR-7) and
  the reply composer becomes unavailable (FR-9 reads the refreshed
  status).
- `useReopenTicket.ts` — `useMutation`; `onSuccess` invalidates
  `ticketDetailQueryKey(id)`; `onError` leaves the thrown `ApiError`
  on the mutation result unmodified so `TicketDetailScreen.tsx` can read
  its `status === 409` (via `getErrorStatus`) and render the returned
  `detail` per FR-8's second clause, rather than the hook swallowing or
  reshaping it. Per OD-3's binding resolution, this hook (and the screen
  that calls it) never inspects a client-computed eligibility window —
  the `409` from the backend is the sole source of truth for whether a
  reopen is allowed.
- `useRetryAfterCountdown.ts` — a small, non-network local-state hook
  (`useState`/`useEffect` with a single `setInterval`, cleared on unmount)
  taking a `retryAfterSeconds: number | undefined` and returning
  `{ secondsRemaining: number; isBlocked: boolean }`, ticking down to
  zero. Both `NewTicketScreen.tsx` (FR-12 on `POST /support/tickets`) and
  `TicketDetailScreen.tsx`'s reply composer (FR-12 on `POST
  /support/tickets/{id}/replies`) call it with the value read via
  `getRetryAfterSeconds` (Change 2) off their respective mutation's
  error. Shared here, in `hooks/`, rather than duplicated per screen,
  since both call sites need the identical behavior: disable submit,
  show the remaining time, never re-issue the request itself.

### 6. `screens/`: three new screens, following `LoginScreen.tsx`'s existing error-handling pattern

- `TicketListScreen.tsx` (`/tickets`) — FR-1/FR-2: status `<select>`
  filter (five options + "All"), ticket rows, "Load more" wired to
  `useTickets`'s `fetchNextPage`/`hasNextPage`, empty state with a "New
  ticket" link to the create route, unrecognized-`status` rendered
  verbatim with neutral styling (no status-to-label lookup table that
  could silently hide an unknown value — render the raw string).
- `NewTicketScreen.tsx` — FR-3/FR-4/FR-10: subject/body/category fields
  via `react-hook-form`'s built-in `required`/`maxLength` rules (matching
  `LoginScreen.tsx`'s existing validation pattern). `category` is a plain
  `<input maxLength={50}>` — free text, no enum, no autocomplete
  (OD-2's binding resolution — see also Change 10). No new validation or
  UI/headless component library is introduced anywhere in this screen or
  story (OD-5's binding resolution). A 429 branch uses the shared
  `useRetryAfterCountdown` to show "You can try again in N seconds" and
  disables submit until then, on `201` navigates to `/tickets/:id` with
  the returned `id`.
- `TicketDetailScreen.tsx` (`/tickets/:id`) — FR-5 through FR-9: reads
  `id` via `useParams<{ id: string }>()` (this story's first screen doing
  so, see Risk 2), renders the header — including `first_response_at`,
  when present, labeled **"First response"** and rendered as a **plain
  timestamp with no SLA-breach context or styling** (OD-4's binding
  resolution: no target/deadline language, no color/urgency treatment,
  just a neutral label and the timestamp) — the reply thread with
  "Load older replies", the reply composer (gated unavailable when
  `status === "closed"`, FR-7's second clause, and applying the same
  shared `useRetryAfterCountdown` on its own 429 from `POST .../replies`),
  and close/reopen buttons whose visibility is driven by one small pure
  function, `offeredActionsForStatus(status: string): { reply: boolean;
  close: boolean; reopen: boolean }`, implementing FR-9's table exactly
  (`resolved` → all three; `closed` → none; every other listed status →
  reply+close only; any *unrecognized* status value defaults to no
  actions offered). **The "Reopen" button, when offered for a `resolved`
  ticket, is never proactively disabled or grayed out based on any
  client-side date computation (OD-3's binding resolution)** — it is
  always clickable when `offeredActionsForStatus` includes it, and a
  `409` outside the 7-day window is handled entirely by the existing
  problem+json rendering path (FR-8's second clause), not by a pre-check.
  FR-9's own explicit "never offered to a customer under any status" is
  satisfied by `offeredActionsForStatus` never having a `resolve` key at
  all, not by a runtime check. A `404` from `getTicketDetail` renders a
  dedicated "ticket not found" state (Change 9), distinct from the
  generic problem+json message.

### 7. `PlaceholderHomeScreen.tsx` is deleted, not kept-but-unrouted; `MfaEnrollmentBanner` relocates to `AppShell.tsx`

FR-15 retires `/` as `PlaceholderHomeScreen.tsx`'s route. This plan
**deletes** the screen and its test file rather than keeping an orphaned,
unrouted component — its entire purpose (per its own header comment,
"intentionally minimal/placeholder pending" this story) was to hold the
spot until this story existed; keeping a dead file with no route pointing
to it would violate `AGENTS.md` §7.8's narrow-change principle in the
opposite direction (leaving unreachable code instead of removing what a
story explicitly supersedes).

`MfaEnrollmentBanner`'s render site moves to `layouts/AppShell.tsx` (not
`TicketListScreen.tsx`) — chosen over the screen-level alternative because
`AppShell.tsx` wraps every authenticated route (confirmed:
`AppRoutes.tsx`'s single `ProtectedRoute`+`AppShell` group), so an
enrollment deadline banner stays visible regardless of which authenticated
screen the customer is on, matching its original intent (a global,
dismissible-per-US-5.1 warning) rather than narrowing its visibility to
one specific screen as a side effect of this story's routing change.
`AppShell.tsx` reads `mfaEnrollmentDeadline` off `useAuthStore()` directly
(same store read `PlaceholderHomeScreen.tsx` used to do) — `AppShell.tsx`
already sits in the `screens/`, `components/` row of `AGENTS.md` §3's
Frontend layer table (store read-only, no `api/` import), so this is not a
new layer violation. Unaffected by any of the six OD resolutions; unchanged
from v1.

### 8. `Idempotency-Key` lifecycle: minted on first submit, reused verbatim on retry, rotated on any field edit (OD-6's binding resolution — final architecture)

The human's binding resolution states this exactly: *"If, after a
ticket-creation failure, the customer edits any form field (subject, body,
category) and resubmits, generate a new Idempotency-Key. If they resubmit
verbatim/unchanged, reuse the same key."* `useCreateTicket.ts` implements
this directly, not as a hedge against an unresolved product question:

- A UUIDv4 (`crypto.randomUUID()`) is minted lazily, on the *first*
  `mutate()` call for a given form-mount lifetime.
- That exact value is reused on every subsequent `mutate()` call from the
  same mounted form **unless** the submitted payload (`subject`/`body`/
  `category`) differs from the payload of the previous attempt, in which
  case a new key is minted before the retry fires. This is a direct
  equality check on the three form fields — not a "has the user touched
  any field" flag — since the binding resolution's test is what is
  actually resubmitted ("verbatim/unchanged"), not merely whether a field
  was focused.
- This satisfies TK-AC4 literally (identical key on a verbatim retry) and
  never reaches the backend's `IdempotencyKeyReuseError` `422` for the
  edited-resubmission case, because an edit always rotates the key before
  the resubmission fires.
- `NewTicketScreen.tsx` unmounting (navigating away) discards the key
  entirely, per Assumption #4/FR-4's "not persisted across a full
  reload" — no `sessionStorage`/`localStorage` write.

### 9. `TicketDetailScreen.tsx`'s own inline 404 branch — no new shared component, extending `ErrorState`'s existing pattern rather than overloading it

`ErrorState.tsx` (`{ kind: "network" | "server"; onRetry }`) already
covers FR-13 and is reused as-is (`impact_analysis`'s "Checked — Not
Affected" finding holds for the network/server branch). It does not cover
FR-11's 404 "not found" state or the generic 4xx `detail`/`fieldErrors`
message (`LoginScreen.tsx`'s existing pattern renders that inline per
screen, `{apiError && !errorKind && <p role="alert">{getErrorMessage(...)}</p>}`).
This plan does **not** widen `ErrorState`'s `kind` union to add
`"not-found"` (that would force every existing `ErrorState` consumer —
`LoginScreen.tsx`, `RegisterScreen.tsx`, and every US-5.2 screen — to
handle a new case in an exhaustive switch if one exists, an unrelated-file
change `AGENTS.md` §7.8 forbids). Instead, `TicketDetailScreen.tsx` reads
`getErrorStatus(error) === 404` directly (Change 2's existing helper,
already exported) and renders a small inline "This ticket could not be
found" block itself — no new shared component needed beyond what
`apiErrorHelpers.ts` already exports, keeping this change scoped to the
one screen FR-11's 404 case actually applies to (`GET /support/tickets/{id}`
is the only endpoint in this story that can 404). Unaffected by any of the
six OD resolutions; unchanged from v1.

### 10. `category`: a plain `<input maxLength={50}>`, no dropdown (OD-2's binding resolution — final architecture)

Per the human's binding resolution, `NewTicketScreen.tsx`'s `category`
field ships as free text with `maxLength=50` client-side validation — no
enum, no autocomplete, and no waiting on a stakeholder-supplied value list.
This plan builds no forward-compatible dropdown seam beyond what a plain
controlled `<input>` already offers (swapping to a `<select>` later, if
product ever supplies a value list, is a contained, single-field change to
one screen — not something this plan needs to design a seam for now).

### 11. Routing: `/` becomes a `<Navigate to="/tickets" replace>`; `/tickets` is the sole canonical home path

`impact_analysis` named three options for how `/` resolves once `/tickets`
becomes home (removed, redirected, or reassigned). This plan takes the
literal reading of FR-15/Assumption #7 ("authenticated home becomes
`/tickets`") and the story's/spec's own consistent use of `/tickets` as
the one path every AC and every other routing reference names
(`LoginScreen.tsx`'s `returnTo` default, `GuestOnlyRoute.tsx`'s redirect
target, `MfaVerifyScreen.tsx`'s post-verify `navigate()` all move to the
literal string `"/tickets"`): `/tickets` is the only route rendering
`TicketListScreen`, and `/` becomes `<Route path="/" element={<Navigate
to="/tickets" replace />} />` inside the same `ProtectedRoute` group, so a
bookmarked or hand-typed `/` still lands an authenticated customer on
their tickets without a second, parallel route to maintain.
`AppRoutes.test.tsx` asserts `/` redirects to `/tickets` and `/tickets`
itself renders `TicketListScreen`.

`/tickets/new` (`NewTicketScreen`) and `/tickets/:id` (`TicketDetailScreen`)
are both registered as children of `/tickets`. React Router v6 ranks a
static path segment above a dynamic one when both match the same URL, so
`/tickets/new` resolves to `NewTicketScreen`, never to `TicketDetailScreen`
with `id === "new"` — this is v6's built-in route-ranking behavior, not
something this plan's code needs to implement, but it depends on the
route order/nesting not being restructured later without preserving that
ranking. `AppRoutes.test.tsx` asserts `/tickets/new` renders
`NewTicketScreen` explicitly, so a future reorder that breaks the ranking
fails the build rather than silently misrouting. Unaffected by any of the
six OD resolutions; unchanged from v1.

## Files To Create

### `api/`
- `frontend/src/api/supportApi.ts` — Change 3. FR-1 through FR-9.

### `hooks/`
- `frontend/src/hooks/useTickets.ts` — Change 5. FR-1/FR-2.
- `frontend/src/hooks/useTicketDetail.ts` — Change 5, exports `ticketDetailQueryKey(id)` and `ticketRepliesQueryKey(id)`. FR-5.
- `frontend/src/hooks/useCreateTicket.ts` — Change 5/8. FR-3/FR-4, OD-6.
- `frontend/src/hooks/useReplyToTicket.ts` — Change 5. FR-6.
- `frontend/src/hooks/useCloseTicket.ts` — Change 5. FR-7.
- `frontend/src/hooks/useReopenTicket.ts` — Change 5. FR-8, OD-3.
- `frontend/src/hooks/useRetryAfterCountdown.ts` — Change 5, shared by `NewTicketScreen.tsx` and `TicketDetailScreen.tsx`. FR-12, OD-1.

### `screens/`
- `frontend/src/screens/TicketListScreen.tsx` — Change 6/11, `/tickets`. FR-1/FR-2.
- `frontend/src/screens/NewTicketScreen.tsx` — Change 6, `/tickets/new`. FR-3/FR-4/FR-10, OD-2/OD-5.
- `frontend/src/screens/TicketDetailScreen.tsx` — Change 6/9, `/tickets/:id`. FR-5 through FR-10, OD-3/OD-4.

## Files To Modify

- `frontend/src/api/httpClient.ts` — Change 1 (`Idempotency-Key` option on `httpPost`) and Change 2 (`ApiError.retryAfterSeconds` first-class, `429`-only `Retry-After` threading — OD-1's binding, final resolution). `ApiError` gains `retryAfterSeconds?: number` as a permanent field.
- `frontend/src/api/types.ts` — Change 4, additive new DTOs + `TicketStatus`; `category` typed as plain `string` (OD-2).
- `frontend/src/components/apiErrorHelpers.ts` — Change 2, additive `getRetryAfterSeconds`, the permanent layering-correct read path for `ApiError.retryAfterSeconds`.
- `frontend/src/components/MfaEnrollmentBanner.tsx` — no internal change; only its caller changes (Change 7). Listed here because its render-site move is a real ripple `impact_analysis` flagged explicitly, even though the component's own code is untouched.
- `frontend/src/layouts/AppShell.tsx` — Change 7 (renders `<MfaEnrollmentBanner deadline={mfaEnrollmentDeadline} />`, reading `useAuthStore()`) and a new `/tickets` nav link (FR-15's "added to the app shell's navigation" — this file has no nav element at all today, so this is new structure, not an edit to an existing list).
- `frontend/src/routes/AppRoutes.tsx` — Change 11: the `<Route path="/" element={<PlaceholderHomeScreen />} />` line and its import are removed and replaced with `<Route path="/" element={<Navigate to="/tickets" replace />} />`; `/tickets` renders `TicketListScreen`; `/tickets/new` renders `NewTicketScreen`; `/tickets/:id` renders `TicketDetailScreen` (all inside the existing `ProtectedRoute`+`AppShell` group).
- `frontend/src/routes/GuestOnlyRoute.tsx` — its one `<Navigate to="/" replace />` becomes `<Navigate to="/tickets" replace />` (FR-15).
- `frontend/src/screens/LoginScreen.tsx` — `returnTo` default (`?? "/"`) becomes `?? "/tickets"` (FR-15).
- `frontend/src/screens/MfaVerifyScreen.tsx` — post-verify `navigate("/")` becomes `navigate("/tickets")` (FR-15).

## Files To Delete

- `frontend/src/screens/PlaceholderHomeScreen.tsx` — Change 7, superseded by `TicketListScreen.tsx` as home.
- `frontend/src/screens/PlaceholderHomeScreen.test.tsx` — deleted alongside the screen it covers.

**Not modified, confirmed by `impact_analysis`'s "Checked — Not Affected"
section and independently re-confirmed while reading these files for this
plan:** `errorNormalization.ts` (Change 2's shape keeps this file
untouched — confirmed, not provisional, now that OD-1 is resolved),
`ErrorState.tsx`, `FieldError.tsx` (both reused as-is, Change 9),
`store/authStore.tsx`, `routes/ProtectedRoute.tsx`, `store/queryClient.ts`,
`frontend/package.json` (no new dependency — OD-5's binding resolution
confirms this: Change 5/8 use `useInfiniteQuery`, already a
`@tanstack/react-query` export, and `crypto.randomUUID()`, a native Web
API; no UI/headless component library is added). No protected file under
`AGENTS.md` §7.9 (`pyproject.toml`, `migrations/env.py`,
`.pre-commit-config.yaml`) is touched by this plan.

## Risks

1. **`httpClient.ts` is shared, load-bearing infrastructure for every
   already-shipped US-5.1/US-5.2 screen.** Changes 1 and 2 are both
   additive-only (`buildHeaders`'s existing three headers, `httpGet`/
   `httpDelete`/`httpPatch`'s existing signatures, and `normalizeApiError`'s
   existing signature are all untouched) specifically to avoid regressing
   any existing call site. `frontend-builder` must not touch
   `performRequest`'s/`parseResponse`'s existing 401→refresh→retry or
   error-normalization behavior for `GET`/non-429 `POST`/`DELETE`/`PATCH`
   while adding these two extensions. This risk is unchanged by OD-1's
   resolution — the extension is still additive, only its framing (target
   architecture vs. narrow stopgap) has changed.
2. **`test-utils.tsx`'s `renderWithProviders` has no precedent for a
   screen reading a URL param — `TicketDetailScreen.tsx` (`useParams<{ id: string
   }>()` off `/tickets/:id`) is the first.** `impact_analysis` flagged this
   explicitly. This plan does not change `test-utils.tsx`'s signature;
   `TicketDetailScreen.test.tsx` instead wraps `ui` in its own local
   `<Routes><Route path="/tickets/:id" element={ui} /></Routes>` when
   calling `renderWithProviders({ route: "/tickets/<test-id>" })`, following
   the workaround `impact_analysis` already named as workable. If a second
   story later needs a URL param, promoting this to a `test-utils.tsx`
   signature change (e.g. an optional `routePath` option) becomes worth
   doing then, not speculatively now.
3. **Cursor pagination via `useInfiniteQuery` is a first for this codebase
   (Change 5).** `useSessions.ts` is the only prior list-consuming hook and
   has no pagination at all, so there is no in-repo precedent to mirror for
   `getNextPageParam`/page-flattening conventions; `frontend-builder` and
   `test-writer` should treat `useTickets.ts` as the reference
   implementation for `useTicketDetail.ts`'s reply-thread pagination, not
   invent a second pattern.
4. **FR-9's status-driven affordance table is customer-facing security
   surface, not just UI polish** — "Resolve" must never be offered "under
   any status." `offeredActionsForStatus` (Change 6) has no `resolve` key at
   all (a structural guarantee, not a runtime `if`), and defaults an
   unrecognized `status` string to zero offered actions (fail closed) rather
   than falling through to `open`'s permissive set. A table-driven test over
   all five known statuses **plus** at least one unrecognized value is
   required (already named in the story's own Enforcement Matrix).
5. **`Idempotency-Key` minting/reuse/rotation logic (Change 8) remains the
   most behaviorally subtle piece of new client state in this story, even
   though OD-6 is now resolved.** The binding rule (rotate on any edit to
   subject/body/category, reuse verbatim on an unchanged retry) must be
   covered by TK-AC4's literal cases (verbatim retry keeps the key; a
   genuinely new composition, i.e. a fresh mount, gets a new key) **and**
   OD-6's edited-resubmission case (reuse rejected — a new key is minted) —
   three distinct test cases, not two. The behavior itself is no longer at
   risk of changing; the risk is purely in getting the equality check
   (subject/body/category comparison) exactly right in implementation and
   tests.
6. **Deleting `PlaceholderHomeScreen.tsx` (Change 7) touches an
   already-shipped US-5.1 file and its test.** This is the one deletion in
   this plan; confirm no other file still imports it before removing
   (`impact_analysis`'s survey found exactly one caller — `AppRoutes.tsx` —
   confirmed again while reading `AppRoutes.tsx` for this plan; no other
   file references `PlaceholderHomeScreen`).
7. **`MfaEnrollmentBanner`'s render site moving into `AppShell.tsx` (Change
   7) changes an already-shipped US-5.1 component's only caller.**
   `MfaEnrollmentBanner.test.tsx`'s existing rendering harness (however it
   currently mounts the banner, per `impact_analysis`) must be updated to
   reflect the new caller without weakening any existing assertion on
   dismiss behavior.
8. **No styling layer exists anywhere in `frontend/src` today** (confirmed
   directly by `impact_analysis` — no stylesheet import, no `*.css` under
   `src/`). This story's NFR bar (responsive ~375px through desktop,
   visible focus on every control) must be met with the same tools every
   existing screen already uses (semantic HTML, native focus outlines, no
   new styling dependency) — consistent with OD-5's binding resolution
   against adding any new UI library. This is a pre-existing gap this story
   inherits rather than introduces, not a defect in this plan, and is not
   something `IMPLEMENTATION` should silently "fix" by introducing a
   styling layer (that would be a §7.8 scope/dependency decision requiring
   sign-off, exactly like US-5.2's QR-library precedent).
9. **`/tickets/new` vs. `/tickets/:id` (Change 11) relies on React Router
   v6's static-over-dynamic route ranking, the first place this codebase
   has two routes that can match the same URL.** This is standard v6
   behavior, not a workaround, but it is silent if broken — a future edit
   that restructures route nesting without preserving both routes as
   siblings under the same parent could invert the ranking with no
   compile-time signal. `AppRoutes.test.tsx`'s explicit `/tickets/new`
   assertion (Change 11) is the only thing that would catch a regression
   here.

## Validation Strategy

- **Gate green**: `npm run lint`, `npm run format:check`, `npm run
  type-check`, `npm run test:coverage` (`AGENTS.md` §2's Frontend
  subsection — load-bearing script names, already wired into
  `.pre-commit-config.yaml` scoped to `files: ^frontend/`). `test:coverage`
  runs in CI only, same as the backend's coverage threshold.
- **Contracts intact (no `lint-imports` equivalent yet)**: the `AGENTS.md`
  §3 Frontend layer table is checked by reading the diff. Specifically for
  this story: `TicketListScreen.tsx`/`NewTicketScreen.tsx`/
  `TicketDetailScreen.tsx` must import only `hooks/`, `store/` (read-only,
  none needed directly by these three), and shared components (`ErrorState`,
  `FieldError`) — never `api/supportApi.ts` or `api/httpClient.ts` directly
  (this is exactly why Change 2 adds `getRetryAfterSeconds` to
  `apiErrorHelpers.ts` rather than having a screen read `ApiError.retryAfterSeconds`
  itself). `api/supportApi.ts` must import only `httpClient`/`types` — no
  React, no TanStack Query. `hooks/` files must import only `api/`, `store/`
  (none needed), and TanStack Query — never JSX.
- **Migrations / runtime rules**: not applicable to this stack (`AGENTS.md`
  §6's Frontend subsection) — no ORM, cache, or migration exists here, and
  this story adds none (reconfirmed: `design_review` v1 `NOT_APPLICABLE`,
  `impact_analysis` v1 §3 "None").
- **Contract & security**: the NFR bar's "no ticket body, reply body, or
  `Idempotency-Key` written to the browser console in production builds"
  and "no `dangerouslySetInnerHTML` anywhere in this Story" (plain-text
  rendering only) are verified by `frontend-builder`'s grep-based
  self-check (the US-5.1/US-5.2 precedent) and independently at
  `SECURITY_REVIEW`. The existing access/refresh-token handling
  (`AGENTS.md` §3's session-handling rule) is unchanged by this story and
  must not be touched while adding Changes 1/2 to `httpClient.ts` (Risk 1).
- **No new dependency**: `package.json` is confirmed unchanged (OD-5's
  binding resolution) — this is now a hard constraint on `IMPLEMENTATION`,
  not a default subject to reconsideration.

## Testing Strategy

Per `AGENTS.md` §5's Frontend subsection: Vitest unit tests for hooks/pure
functions, React Testing Library + MSW integration tests per screen, 85%
coverage floor via `test:coverage`, CI-enforced. No `vi.mock()` of the unit
under test anywhere; MSW is the network boundary.

- **Unit**:
  - `httpPost`'s new `idempotencyKey` option (Change 1) and
    `parseResponse`'s `429`-only `Retry-After` → `retryAfterSeconds` threading
    onto the now first-class `ApiError` field (Change 2), including a case
    proving a non-`429` `4xx`/`5xx` response never populates
    `retryAfterSeconds` even when a `Retry-After` header happens to be
    present — a new `httpClient.test.ts` (flagged missing by
    `impact_analysis`; this story is the first to need it).
  - `getRetryAfterSeconds` (Change 2) alongside the existing
    `getErrorStatus`/`getErrorKind`/`getErrorMessage`/`getFieldErrors`
    coverage pattern.
  - `offeredActionsForStatus` (Change 6): table-driven over all five known
    statuses plus at least one unrecognized value, asserting the exact
    offered-action set including that `resolve` is never a possible output
    — the story's own Enforcement Matrix names this test explicitly
    (TK-AC9). Includes a case confirming `resolved` always includes
    `reopen: true` regardless of any date input (OD-3: no client-side
    eligibility computation exists to test).
  - `useCreateTicket.ts`'s key lifecycle (Change 8, OD-6): mint-once-per-mount,
    identical key on a verbatim retry (TK-AC4), a distinct key on a fresh
    mount (TK-AC4), and a distinct key on an edited-then-resubmitted
    payload (OD-6's binding case) — three separate assertions.
- **Integration (RTL + MSW)**, one module per screen plus the modified
  existing test files `impact_analysis`'s Test-Surface Impact section
  named:
  - **TK-AC1/FR-1** (`TicketListScreen.test.tsx`): fields render per row;
    "Load more" appends using `next_cursor` and disappears when
    `next_cursor` is `null`; empty `items` shows the "New ticket" CTA, not
    a blank screen; an unrecognized `status` string renders verbatim.
  - **TK-AC2/FR-2** (`TicketListScreen.test.tsx`): selecting each of the
    five statuses re-issues the request with that filter and a reset
    cursor; clearing the filter re-issues the unfiltered request.
  - **TK-AC3/FR-3, TK-AC10/FR-10** (`NewTicketScreen.test.tsx`): valid
    submission sends `Idempotency-Key` + `attachment_ids: []`, lands on
    `/tickets/:id` on `201`; empty/over-length subject (150), body (5000),
    category (50) each block submission with a field-level error and no
    network call (asserted via an MSW `onUnhandledRequest: "error"`
    handler or a request-count spy, per this story's own `[gate]`
    requirement); `category` is asserted to be a plain text `<input>`,
    not a `<select>` (OD-2).
  - **TK-AC4/FR-4** (`NewTicketScreen.test.tsx`): a network-error or 5xx
    response on first submit, followed by a verbatim retry, sends the
    identical `Idempotency-Key`; starting a fresh composition (remount)
    sends a different one; an edited-then-resubmitted payload sends a
    **different** key and never triggers a `422` (OD-6).
  - **TK-AC5/FR-5** (`TicketDetailScreen.test.tsx`): header fields
    (`ticket_number`, `status`, `category`, `created_at`,
    `first_response_at` when present/absent, labeled "First response" and
    rendered as a plain timestamp with no SLA copy or styling — OD-4)
    render; each reply shows
    `author_kind`/`body`/`created_at`; "Load older replies" fetches using
    `replies.next_cursor`, independent of the list's own cursor (a
    dedicated assertion that the thread's MSW handler receives its own
    cursor value distinct from the list endpoint's).
  - **TK-AC6/FR-6** (`TicketDetailScreen.test.tsx`): a reply submission
    sends no `visibility` field and `attachment_ids: []`; on `201` the new
    reply appears and the composer clears; the ticket-detail query is
    proven invalidated/refetched (assert a second `GET
    /support/tickets/{id}` call, not just an optimistic local append).
  - **TK-AC7/FR-7** (`TicketDetailScreen.test.tsx`): "Close ticket" from
    each of the four eligible statuses calls the close endpoint and the
    screen reflects `closed`; the reply composer becomes unavailable once
    closed.
  - **TK-AC8/FR-8** (`TicketDetailScreen.test.tsx`): "Reopen" from
    `resolved` is rendered enabled/clickable unconditionally (OD-3: no
    proactive disable) and calls the reopen endpoint, and the screen
    reflects `waiting_on_support`; a `409` response renders the returned
    problem+json `detail`, not a generic failure message, and the button
    remains present/clickable afterward (not disabled by the client).
  - **TK-AC9/FR-9** (`TicketDetailScreen.test.tsx`): integration-level
    confirmation of the unit-level `offeredActionsForStatus` table (the
    unit test proves the pure function; this test proves the screen
    actually wires it to what's rendered) across all five statuses.
  - **TK-AC11/FR-11** (`TicketDetailScreen.test.tsx` primarily, plus a
    shared case in `TicketListScreen.test.tsx`/`NewTicketScreen.test.tsx`):
    a problem+json 4xx renders its `detail`/mapped message with no raw
    JSON; a 422 with an `errors[]` array maps onto the matching form
    field(s) (`NewTicketScreen.test.tsx`); a 404 on `GET
    /support/tickets/{id}` renders the dedicated "not found" state (Change
    9), distinct from the generic-4xx branch.
  - **TK-AC12/FR-12** (`NewTicketScreen.test.tsx`,
    `TicketDetailScreen.test.tsx`'s reply composer): a 429 with a
    `Retry-After` header shows a message naming the retry time (sourced
    from the now first-class `ApiError.retryAfterSeconds`, Change 2) and
    disables submit until it elapses; the request is asserted to fire
    exactly once (no auto-retry loop).
  - **TK-AC13/FR-13** (all three screens): a network error and a 5xx per
    screen's primary request render `ErrorState`, never a blank screen or
    an unhandled rejection.
  - **TK-AC14/FR-14**: the 401→refresh→retry path is already covered by
    US-5.1's `httpClient`-level test and `refreshCoordinator.ts` — this
    story adds one integration assertion (`TicketListScreen.test.tsx` or
    `TicketDetailScreen.test.tsx`) proving a ticket-domain request
    triggers the same existing coordinator, not a duplicate of US-5.1's
    own coverage; the deactivated-account `403` on `POST /support/tickets`
    renders its problem+json `detail` (`NewTicketScreen.test.tsx`).
  - **Plain-text rendering** (`TicketDetailScreen.test.tsx`): an
    HTML-bearing ticket/reply `body` (e.g. `<img src=x onerror=alert(1)>`)
    renders as escaped text, never executes — asserted via the DOM (no
    `<img>` element present), not a string-contains check, per this
    story's own Enforcement Matrix.
  - **Routing (`AppRoutes.test.tsx`)**: replaces every existing `"/"`-target
    assertion per FR-15; adds coverage that `/` redirects to `/tickets`,
    `/tickets` renders `TicketListScreen`, `/tickets/new` renders
    `NewTicketScreen` and not `TicketDetailScreen` (Risk 9's route-ranking
    regression check), `/tickets/:id` renders `TicketDetailScreen`, and all
    of `/tickets`, `/tickets/new`, `/tickets/:id` sit inside `ProtectedRoute`
    (redirect an unauthenticated visitor to `/login`).
  - **`GuestOnlyRoute.test.tsx`**: authenticated-visitor redirect target
    becomes `/tickets`.
  - **`LoginScreen.test.tsx`**: no-`from`-state landing target becomes
    `/tickets`.
  - **`MfaVerifyScreen.test.tsx`**: post-verify navigation target becomes
    `/tickets`.
  - **`AppShell.test.tsx`**: gains assertions for the new `/tickets` nav
    entry and for `MfaEnrollmentBanner` now rendering from this file
    (Change 7); existing `LogoutControls` coverage and any `route: "/"`
    fixture values are preserved or updated to `/tickets` as needed.
  - **`MfaEnrollmentBanner.test.tsx`**: updated rendering harness to mount
    from its new caller (`AppShell`, via `renderWithProviders`), existing
    dismiss-behavior assertions kept unweakened.
  - **a11y bar**: an automated `vitest-axe` pass (existing devDependency)
    on `TicketListScreen`, `NewTicketScreen`, and `TicketDetailScreen`
    specifically, per the story's own Enforcement Matrix `[gate]` row —
    including keyboard reachability of the status filter, "Load more"/
    "Load older replies" controls, and the close/reopen/reply controls.
- **New test infrastructure**: `frontend/src/test/mswHandlers.ts` gains one
  baseline handler per new endpoint (list, create, detail, reply, close,
  reopen), following the existing one-handler-per-operation convention —
  not a new file. `frontend/src/test/test-utils.tsx` is not modified (Risk
  2) — each screen test wraps `ui` in its own local `<Routes>` where a URL
  param is needed.
- **Coverage** — 85% floor via `test:coverage`, a floor not a goal; no
  exclusion for the `offeredActionsForStatus` unrecognized-status branch,
  the 429-only `Retry-After` gate in `parseResponse`, or the
  `useCreateTicket.ts` key-rotation branch.
