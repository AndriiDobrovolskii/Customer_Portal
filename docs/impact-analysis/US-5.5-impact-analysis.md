---
artifact_type: impact_analysis
story: US-5.5
version: 2
status: ARCHIVED
created_at: "2026-09-14T02:00:00Z"
updated_at: "2026-09-14T06:00:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.5-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.5-design-review.md
    version: 2
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
supersedes: docs/impact-analysis/US-5.5-impact-analysis.md (v1)
---

# Impact Analysis: Agent Console (Frontend)

**Story ID:** US-5.5
**Track:** frontend (per `docs/stories/US-5.5-agent-console-ui.md` front matter, line 7)

> **Revision (v2):** version 1 of this analysis (`status: DRAFT`) was produced
> against specification v1, whose OD-1–OD-5 were still `OPEN`. Specification
> v2 (`APPROVED`, 2026-09-14) resolves all five by explicit human decision
> (`docs/decisions/US-5.5-open-decisions.md` v2) and adds FR-11 (shared
> app-shell navigation, resolving the story's own Open Question #2 /
> OD-4). Design review v2 (`NOT_APPLICABLE`, re-derived against spec v2)
> confirms none of the five resolutions touches API or persistence design.
> This revision re-verifies every file-level claim from v1 directly against
> the current codebase (no drift found — no backend or frontend file this
> survey names changed between v1 and v2's production) and updates the
> analysis to state the five resolutions as settled facts rather than open
> risk. The v1 non-blocking finding on `ReplyRead.visibility` is re-verified
> below and carried forward unchanged: it still holds.

## Precondition Check

- Specification v2: `APPROVED`. Specification review v2: `APPROVED`, verdict
  `PASS` (all nine ACs Covered, no Scope Creep, no Contradictions; three new
  Low/Medium ambiguities from the v2 resolution text, none blocking).
- `API_DESIGN`/`DB_DESIGN`: recorded `NOT_APPLICABLE`, re-derived against
  spec v2 (`docs/workflow/history.jsonl`, `openapi-designer` at
  `2026-09-14T05:00:00Z`, `db-designer` at `2026-09-14T05:10:00Z`). Design
  review v2: `APPROVED`, verdict `NOT_APPLICABLE` — independently
  re-confirmed both areas out of scope and that none of the five resolved
  Open Decisions became, or required, an API or database design change.
- Open decisions v2 (`docs/decisions/US-5.5-open-decisions.md`): OD-1
  through OD-5 are all `RESOLVED` (human decision, 2026-09-14). Verified
  directly: each resolution is a frontend UX/state-management choice
  (assignee display, assign-target input mechanism, detail-screen assignee
  source, shared-shell nav placement, close/reopen interaction shape) — none
  proposes a new endpoint, request/response field, or persistence change.
  No unresolved blocking Open Decision remains for this stage to enforce.
- No input is stale: the specification's own front matter records consuming
  open decisions v2; the specification review's own front matter records
  consuming spec v2 and open decisions v2 and `supersedes` its own v1; the
  design review's own front matter records consuming spec v2, spec review
  v2, and open decisions v2 and `supersedes` its own v1. All match what is
  on disk.
- `docs/workflow/active-story.yaml` (`active_story: US-5.5`) and
  `docs/workflow/workflow-state.yaml` (`story: US-5.5`,
  `current_stage: IMPACT_ANALYSIS`) agree on the active story and stage —
  read directly, not inferred from an upstream artifact's own citation of
  them.
- Codebase re-check: every file this survey names as unchanged/reused in §1,
  §1a, and §2 was individually re-read against the current working tree this
  session (not re-derived from v1's text) — `supportApi.ts`, `httpClient.ts`,
  `useReplyToTicket.ts`, `useCloseTicket.ts`, `useReopenTicket.ts`,
  `useTicketDetail.ts`, `authStore.tsx`, `decodeTokenScopes.ts`,
  `AppShell.tsx`, `AppRoutes.tsx`, plus `app/modules/support/schemas.py` and
  `router.py`. None changed shape from what v1 described: `supportApi.ts`
  still exposes only `listTickets`/`createTicket`/`getTicketDetail`/
  `replyToTicket`/`closeTicket`/`reopenTicket` (no `assign`/`unassign`/
  `resolve` function exists yet); `useReplyToTicket.ts` still hardcodes
  "never send `visibility`"; `useCloseTicket.ts`/`useReopenTicket.ts` still
  take no `reason` argument; `AppShell.tsx` lines 32-33/39-41 and
  `AppRoutes.tsx` lines 85-102 are unchanged; `app/modules/support/schemas.py`
  still defines `AgentTicketRead`/`AgentTicketListResponse`/
  `AssignTicketRequest`/`AgentTicketStateRead`/`ResolveTicketRequest`/
  `TicketDetailRead` with the same shapes, and `router.py` still declares
  `response_model=TicketListResponse | AgentTicketListResponse` for the
  queue GET, `response_model=AgentTicketStateRead` for assign/unassign, and a
  single `response_model=TicketDetailRead` for the detail GET. `git log
  --oneline -- frontend/src app/modules/support` shows the most recent
  commit touching either tree is `d69132b` (US-5.4, already reflected above
  v1); `git status --porcelain -- frontend/src app/modules/support` returns
  empty, confirming no uncommitted code change exists in either tree that
  the working-tree re-read could have missed.

No blocking condition found. Proceeding with `PASS`.

## 1. Affected Files / Modules / Layers

Layer names below are `AGENTS.md` §3 Frontend subsection's table: `screens/`,
`components/` → `hooks/` → `store/` (read-only from screens) / `api/` → the
backend, plus `routes/` (guards + layout) and `layouts/`.

### `api/` layer

| File | Change | Reason |
|---|---|---|
| `frontend/src/api/types.ts` | Modify (additive types + one field addition on an existing type) | Add `AgentTicketRead`, `AgentTicketListResponse` (FR-1's queue response — confirmed against `app/modules/support/schemas.py` `AgentTicketRead`/`AgentTicketListResponse`, which add `assignee_id` over the customer `TicketRead`/`TicketListResponse`; FR-1's Resolution OD-1 governs how that UUID is *rendered*, not the type shape itself). Add `AssignTicketRequest` (`{assignee_id}`, FR-2 — the same field a Resolution-OD-2 raw-UUID text input populates) and `AgentTicketStateRead` (assign/unassign's actual response shape per `router.py`'s `response_model=AgentTicketStateRead` on both the assign and unassign routes — NOT `AgentTicketRead`; carries `assignee_id` but not `subject`/`category`, and is now also FR-6's stated source for updating the detail screen's local assignee value per Resolution OD-3). Add `ResolveTicketRequest` (`{resolution_note}`, FR-5). `ReplyRead` (line ~197) is still missing the `visibility: "public" \| "internal"` field that `app/modules/support/schemas.py::ReplyRead` (line 74) has always returned — confirmed unchanged on this revision by direct re-read of both files — FR-3's internal/public distinction requires reading it. Confirmed by re-grepping `screens/`/`hooks/` for a `ReplyRead`-typed literal: none exists; every existing reply fixture is an untyped `HttpResponse.json({...})` body, so adding this field does not fail `type-check`. `CreateReplyRequest` (line ~222) also needs an optional `visibility` field for FR-4's composer to send it — additive; existing customer call sites that never set it are unaffected. |
| `frontend/src/api/supportApi.ts` | Modify (additive functions) | Add `listAgentTickets(params)` for FR-1 (same `GET /support/tickets` URL as `listTickets`, but typed to `AgentTicketListResponse` and accepting `assignee_id` — the backend discriminates the response shape server-side by caller scope, confirmed by `router.py`'s `response_model=TicketListResponse \| AgentTicketListResponse`, not by a query flag this function invents). Add `assignTicket(id, data)` (POST `.../assign`) and `unassignTicket(id)` (DELETE `.../assign`, using the existing `httpDelete<T>` verb — FR-2, both endpoints taking the Resolution-OD-2 raw-UUID input as their `assignee_id`). Add `resolveTicket(id, data)` (POST `.../resolve`, FR-5). Extend `CreateReplyRequest` usage in `replyToTicket`'s call site so an agent caller can pass `visibility` (FR-4) — the function signature itself does not need to change since `CreateReplyRequest` already carries the field once `types.ts` is extended. |
| `frontend/src/api/httpClient.ts` | **No change** | `httpDelete<T>` already accepts a typed response and an optional body (used today by `useRevokeSession.ts`); `429`'s `Retry-After` header is already parsed generically into `ApiError.retryAfterSeconds` for every endpoint, not per-route — FR-9/AG-AC8 needs no new transport-layer work. Listed here only to record that it was checked, not assumed unaffected. |

### `hooks/` layer

| File | Change | Reason |
|---|---|---|
| `frontend/src/hooks/useAgentTickets.ts` (new) | New | FR-1: cursor-paginated queue query parameterized by `status`/`category`/`assignee_id` (the latter populated by the `me`/`none` presets or the Resolution-OD-2 raw-UUID text input), mirroring `useAdminUsers.ts`'s `useInfiniteQuery` shape (`queryKey: ["admin-users", ...] as const` pattern) — a filter change becomes a query-key change, resetting the cursor per AG-AC1's "filters... reset the cursor." |
| `frontend/src/hooks/useAssignTicket.ts` (new) | New | FR-2 "assign to me" / "assign to another agent" (Resolution OD-2's raw-UUID input for the latter): wraps `assignTicket`; `onSuccess` must invalidate the queue (`useAgentTickets`'s query key) per AG-AC2's "the queue is invalidated," and — per FR-6's now-settled Resolution OD-3 — write the returned `AgentTicketStateRead.assignee_id` into any open detail-screen local assignee state (the navigation-state handoff value), since `TicketDetailRead`'s own invalidated-and-refetched shape carries no `assignee_id` to source it from. |
| `frontend/src/hooks/useUnassignTicket.ts` (new) | New | FR-2 unassign: same invalidation/response-write shape as `useAssignTicket.ts` (including the FR-6/OD-3 local-state write), wrapping `unassignTicket`. Kept as a separate hook (not a boolean flag on one hook) to match this codebase's existing one-hook-per-mutation convention (`useCloseTicket.ts`/`useReopenTicket.ts` are separate, not unified). |
| `frontend/src/hooks/useResolveTicket.ts` (new) | New | FR-5: wraps `resolveTicket`; `onSuccess` writes the returned `TicketStateRead` into `ticketDetailQueryKey(id)`'s cache, the same "mutation response is the new truth" pattern `useCloseTicket.ts`/`useReopenTicket.ts` already use (confirmed by direct re-read of `useCloseTicket.ts`) — reused here as a pattern, not by importing those hooks. |
| `frontend/src/hooks/useTicketDetail.ts` | **No change** | `GET /support/tickets/{id}` is the same URL and the same `TicketDetailRead` response shape for both the customer and agent branch (confirmed: `router.py` declares a single `response_model=TicketDetailRead`, no agent-specific detail schema exists — the basis for Resolution OD-3's navigation-state-handoff answer, since there is no `assignee_id` on this response to read instead) — this hook is reused as-is by the new agent detail screen, satisfying Assumption #1 ("extended, not duplicated") at the hook layer. |
| `frontend/src/hooks/useReplyToTicket.ts` | Modify | Currently hardcodes the reply payload to omit `visibility` entirely (comment at line ~21, confirmed unchanged: "the composer offers no visibility control at all — never send `visibility`"). FR-4 requires the agent composer to send an explicit `"public"`/`"internal"` value. Needs a signature change — either an added optional argument or an added field on `ReplyToTicketFormValues` — so the customer call site (`TicketDetailScreen.tsx`, unchanged) keeps omitting `visibility` while the new agent screen supplies it. This is the concrete file where Assumption #1's "extended, not duplicated" is decided for the reply composer; `planner` must pick the exact shape (new optional param vs. shared form field) — not decided by this survey. |
| `frontend/src/hooks/useCloseTicket.ts`, `frontend/src/hooks/useReopenTicket.ts` | **No change** | Both already wrap the generic `POST .../close` / `POST .../reopen` endpoints with no `reason` field collected and no confirmation step — now matching FR-7's settled Resolution OD-5 ("a single action button, no reason field, no confirmation modal") exactly, confirmed by direct re-read of `useCloseTicket.ts` (`mutationFn: () => closeTicket(id, {})`, no `reason` argument accepted). Reusable as-is by the new agent detail screen. |

### `store/` layer

| File | Change | Reason |
|---|---|---|
| `frontend/src/store/authStore.tsx`, `frontend/src/store/decodeTokenScopes.ts` | **No change** | `scopes` (decoded from the JWT) is already exposed by `useAuthStore()` and already used for cosmetic gating elsewhere (US-5.4 FR-9 in `AppShell.tsx`, confirmed lines 32-33/40-41). This Story's `tickets:read`/`tickets:write` gating (FR-6, Assumption #3) reads the same existing mechanism; no new claim, decoder change, or store shape change is needed. |

### `routes/` layer

| File | Change | Reason |
|---|---|---|
| `frontend/src/routes/AppRoutes.tsx` | Modify | Register `/agent/tickets` (queue) and `/agent/tickets/:id` (detail) inside the existing `ProtectedRoute`/`AppShell` route group (Assumption #2's route namespace), the same auth-only-gating pattern US-5.4's `/admin/*` routes already established (confirmed lines 85-102: scope gating stays at the presentation layer, not the router). FR-11's now-settled Resolution OD-4 ("one shared AppShell ... no separate entry point") confirms these two routes live inside the *same* protected route group as `/tickets` and `/admin/*`, not a separate route tree — resolving what v1 flagged as an open question. |

### `layouts/` layer

| File | Change | Reason |
|---|---|---|
| `frontend/src/layouts/AppShell.tsx` | Modify | Add an `/agent/tickets` nav entry gated on `scopes.includes("tickets:read")`, following the exact `canReadUsers`/`canReadAudit` pattern already in this file (confirmed lines 32-33, 40-41) for US-5.4 FR-9. FR-11's Resolution OD-4 settles the placement question v1 left open: one shared `AppShell` gains a third scope-gated `<Link>` alongside `Tickets`/`Users`/`Audit Log` — no separate entry point, no role switcher, no new layout file. |

### `screens/` layer (net-new)

| File | Change | Reason |
|---|---|---|
| `frontend/src/screens/AgentTicketQueueScreen.tsx` (new) | New | FR-1, FR-2: renders the queue table (`ticket_number`, `subject`, `category`, `status`, assignee, `updated_at`), the `status`/`category`/`assignee_id` filters plus `me`/`none` presets and the Resolution-OD-2 raw-UUID "specific agent" text input, "Load more," and per-row assign/unassign controls, with the assignee column rendering per Resolution OD-1 (shortened/truncated UUID, no name-resolution call). Composed from `hooks/`, `store/` (read-only), and shared `components/` only, per AGENTS.md §3. |
| `frontend/src/screens/AgentTicketDetailScreen.tsx` (new) | New | FR-3 through FR-7: renders the ticket header (current-assignee value sourced via Resolution OD-3's navigation-state handoff, rendered per Resolution OD-1, and treated as unknown/stale on direct-URL entry), the full thread with internal replies visually distinct and labelled, the visibility-aware reply composer, resolve (with the client-side non-empty `resolution_note` check), close/reopen as single action buttons (Resolution OD-5), and the status/scope-driven affordance table (FR-6) — a superset of what `TicketDetailScreen.tsx` renders for a customer. |

**Note (not a decision made here, flagged for `planner`):** `TicketDetailScreen.tsx` inlines all of its reply-thread rendering markup directly (no extracted `components/ReplyList.tsx` or similar exists today, confirmed unchanged) — there is no existing shared *component* file the new agent detail screen can import to satisfy Assumption #1's "extended, not duplicated" at the component level; today that reuse is only achievable at the hook level (`useTicketDetail.ts`, above). Whether `planner` extracts shared reply-thread-rendering markup into a new `components/` file both screens then import, or leaves `AgentTicketDetailScreen.tsx` as an independent JSX tree reusing only the hooks, is an architectural decision this survey does not make.

## 1a. Checked — Not Affected (reference only)

- `frontend/src/screens/TicketDetailScreen.tsx`, `frontend/src/screens/TicketListScreen.tsx`,
  `frontend/src/screens/NewTicketScreen.tsx` (US-5.3, customer-facing) — no functional
  requirement in this Story changes customer behavior; the backend's agent/customer branch
  split (confirmed in `router.py`) means these screens keep calling the same endpoints and
  receiving the same response shapes they always have.
- `frontend/src/components/ErrorState.tsx`, `FieldError.tsx`, `apiErrorHelpers.ts` — generic,
  already used by every screen in the codebase for FR-8/FR-9/FR-10 (AG-AC7-9); no new
  problem+json shape, retry-after mechanism, or network/5xx pattern is introduced by this
  Story that these do not already handle.
- `frontend/src/hooks/useRetryAfterCountdown.ts` — already generic (consumed today by
  `NewTicketScreen.tsx` and `TicketDetailScreen.tsx`'s reply composer); the new agent reply
  composer reuses it unchanged for FR-9/AG-AC8.
- `frontend/src/routes/ProtectedRoute.tsx`, `GuestOnlyRoute.tsx` — auth-only gating; this
  Story introduces no new guard, per the established "scope gating lives at the
  presentation layer only" precedent (US-5.4), and FR-11's Resolution OD-4 keeps the new
  routes inside the same shared protected group, not a new guard.
- `frontend/src/test/test-utils.tsx` — `RenderWithProvidersOptions.scopes` already exists
  (added for US-5.4); seeding `tickets:read`/`tickets:write` needs no change here.
- Any backend file under `app/modules/support/` — confirmed `NOT_APPLICABLE` per the
  approved specification (v2) and design review (v2, re-derived); this Story calls only
  already-shipped US-4.4 endpoints.

## 2. Cross-Module Ripple

This is a pure frontend story; there is no backend `service.py` → `service.py` call to
trace (`AGENTS.md` §3's cross-module discipline is a backend concept). The frontend-side
analogue — a `hooks/` file importing another `hooks/` file's exported query key — already
exists in this codebase (`useReplyToTicket.ts` imports `ticketDetailQueryKey`/
`ticketRepliesQueryKey` from `useTicketDetail.ts`; `useCloseTicket.ts`/`useReopenTicket.ts`
each import `ticketDetailQueryKey`, confirmed by direct re-read). This Story extends that
same pattern, not a new one:

| Caller | Callee | Reason |
|---|---|---|
| `useAssignTicket.ts` (new) | `useAgentTickets.ts`'s queue query key (new) | AG-AC2: a successful assign "invalidates the queue" — the mutation hook must import and invalidate the queue hook's query key, the same shape as `useReplyToTicket.ts` → `useTicketDetail.ts` today. |
| `useUnassignTicket.ts` (new) | `useAgentTickets.ts`'s queue query key (new) | Same as above, for unassign. |
| `useAssignTicket.ts` / `useUnassignTicket.ts` (new) | `useTicketDetail.ts`'s `ticketDetailQueryKey` (existing) | Per FR-6's now-settled Resolution OD-3: when assign/unassign is invoked from the detail screen, the mutation's `AgentTicketStateRead` response (which carries `assignee_id`) updates the detail screen's local assignee state — this is a new cross-hook reach, no different in kind from the existing `useCloseTicket.ts` → `ticketDetailQueryKey` reach, but it is a **new** caller of that key from a hook that did not exist before this Story. |
| `useResolveTicket.ts` (new) | `useTicketDetail.ts`'s `ticketDetailQueryKey` (existing) | AG-AC5: resolve must update the detail screen's status to "resolved" — same "mutation response is the new truth" pattern as `useCloseTicket.ts`. |
| `AgentTicketDetailScreen.tsx` (new) | `useTicketDetail.ts`, `useReplyToTicket.ts`, `useCloseTicket.ts`, `useReopenTicket.ts` (all existing, unmodified except `useReplyToTicket.ts`) | Reuse, not a new dependency direction — same screens→hooks import direction every existing screen already uses. |

No new cross-module dependency direction is introduced (all calls stay within
`hooks/` → `hooks/`'s query-key-sharing pattern, or `screens/` → `hooks/`) — nothing here
crosses a layer boundary `AGENTS.md` §3's Frontend table forbids.

## 3. Migration/Schema Impact

**None.** This Story makes no backend, API, or database change — confirmed by the
approved specification v2 (Summary: "It makes no backend, API, or database change"), the
design review v2 (`NOT_APPLICABLE` for both `API_DESIGN` and `DB_DESIGN`, re-derived
against spec v2), and directly against `app/modules/support/schemas.py`/`router.py`
(every endpoint and schema this Story's FRs call — `AgentTicketRead`,
`AgentTicketListResponse`, `AssignTicketRequest`, `AgentTicketStateRead`,
`TicketDetailRead`, `ReplyRead`, `ResolveTicketRequest`, `TicketStateRead`,
`CloseTicketRequest`, `ReopenTicketRequest` — already exists, shipped under US-4.1
through US-4.4, unchanged since v1's inspection). No Alembic migration, no
`models.py`/`repository.py` change, no new table/column/index. The only "schema"
changes in this Story are frontend TypeScript interfaces in `frontend/src/api/types.ts`
(§1 above), which are not database schema and carry no migration.

## 4. Test-Surface Impact

### Existing test files that must change

| File | Reason |
|---|---|
| `frontend/src/hooks/useReplyToTicket.test.ts` | `useReplyToTicket.ts`'s signature change (visibility support) needs new cases: default customer path still omits `visibility`; a new agent-path case asserts `visibility: "public"`/`"internal"` is sent when supplied. (Existing cases in this file already inline `visibility: "public"` into mock reply bodies, ahead of the type existing — harmless today since the literal is untyped, but a signal this file already anticipates the field.) |
| `frontend/src/screens/TicketDetailScreen.test.tsx` | Not a compile requirement — its reply fixtures are untyped `HttpResponse.json({...})` bodies, not `ReplyRead`-annotated literals, so they type-check today regardless. Affected because several of this file's reply fixtures (e.g. the two-reply thread case) omit `visibility` entirely; once `ReplyRead.visibility` exists and any shared rendering path reads it, these fixtures should carry an explicit value to stay contract-realistic rather than exercise an undefined field at runtime. |
| `frontend/src/hooks/useTicketDetail.test.ts` | Same reason: its `ReplyRead`/`TicketDetailRead`-shaped fixture objects are untyped literals too; they should gain `visibility` to stay contract-realistic, not to satisfy the compiler. |
| `frontend/src/test/mswHandlers.ts` | Add default handlers for `POST .../assign`, `DELETE .../assign`, `POST .../resolve` (none exist today — confirmed by re-grep: only `close`/`reopen`/`replies`/list/detail exist for `/support/tickets`). Extend the existing `GET /support/tickets` and `GET /support/tickets/:id` default handlers' response bodies to include `visibility` on replies and (where the agent branch is being simulated) `assignee_id`, since MSW's default handler is shared baseline for every test file per this codebase's existing "one handler per operation, overridden per test" convention. |
| `frontend/src/routes/AppRoutes.test.tsx` | Existing file asserts every registered route; must add cases for the two new `/agent/tickets` and `/agent/tickets/:id` routes (the file's own established pattern for every prior story's new routes, e.g. US-5.4's `/admin/*` additions). |
| `frontend/src/layouts/AppShell.test.tsx` | Existing file asserts nav-entry visibility per scope (the established pattern for `canReadUsers`/`canReadAudit`); must add a case for the new `tickets:read`-gated `/agent/tickets` entry, now a settled requirement per FR-11/Resolution OD-4 rather than an open question. |

### New test files (net-new screens/hooks have no existing coverage to update)

- `frontend/src/hooks/useAgentTickets.test.ts`
- `frontend/src/hooks/useAssignTicket.test.ts`
- `frontend/src/hooks/useUnassignTicket.test.ts`
- `frontend/src/hooks/useResolveTicket.test.ts`
- `frontend/src/screens/AgentTicketQueueScreen.test.tsx` (covers AG-AC1, AG-AC2's queue-side
  assertions, the Resolution-OD-1 UUID-display rendering, the Resolution-OD-2 raw-UUID
  filter input, the empty-filter-result and a11y checks per the Enforcement Matrix)
- `frontend/src/screens/AgentTicketDetailScreen.test.tsx` (covers AG-AC3 through AG-AC9's
  detail-screen assertions: internal-note distinct styling/label, visibility-default/
  non-sticky composer behavior, resolve's empty-note client-side block, the Resolution-OD-3
  navigation-state-handoff assignee behavior including the direct-URL unknown/stale case,
  the Resolution-OD-5 single-button close/reopen with no confirmation, the five-status ×
  scope affordance table, problem+json/429/5xx handling, a11y)

No dedicated `frontend/src/api/supportApi.test.ts` file exists today for any of its
existing functions (confirmed: absent from the current `api/` directory listing, unchanged
since v1). This Story's new `supportApi.ts` functions match that existing pattern: they are
exercised only through the hook/screen integration tests above plus the MSW handlers, not a
standalone unit-test file.

## Non-Blocking Findings

- **`ReplyRead.visibility` — re-verified, still holds.** `frontend/src/api/types.ts`'s
  `ReplyRead` interface (confirmed by direct re-read on this revision) still has no
  `visibility` field, even though `app/modules/support/schemas.py::ReplyRead` (line 74)
  has always returned `visibility: Literal["public", "internal"]` and
  `CreateReplyRequest` on the backend accepts an optional `visibility` on write. This is
  unchanged from v1's finding — `git log --oneline -- frontend/src app/modules/support`
  shows no commit since `d69132b` (US-5.4, the same commit v1 was already produced
  against) touched either file, and `git status --porcelain` on both trees is empty.
  Every new file in this Story's `hooks/`/`screens/` layers that
  renders or reads reply visibility (FR-3's internal/public thread rendering, FR-4's
  composer) depends on this field's existence on `ReplyRead`/`CreateReplyRequest`, so
  extending `types.ts` (§1) is a hard prerequisite, not an optional cleanup.
- **OD-1 through OD-5 are now RESOLVED (v1 carried them as open); no residual risk to the
  file boundary.** Every one of the five human resolutions (shortened/truncated UUID
  display; raw-UUID text input for assign-target and the specific-agent filter;
  navigation-state handoff for the detail screen's assignee value; one shared AppShell with
  a `tickets:read`-gated nav entry; single-button close/reopen with no reason field or
  confirmation) matches the "interim default" v1 had already anticipated as the shape of
  each affected file — so the file list in §1 is unchanged from v1 in *which* files are
  touched, only firmer in *why* (a settled requirement, not an open question the resolution
  might have pushed a different way). Specification review v2 separately flags three new
  Low/Medium ambiguities in the resolved text itself (unspecified literal rendering for the
  "unknown/stale" assignee state and for a null `assignee_id`; whether a detail-screen-
  originated assign also invalidates the queue) — these affect what `planner` specifies
  inside the already-identified files, not which files are affected, so they do not change
  this survey's file boundary and are left for `planner`/`implementation-planner` to resolve
  or raise further.

## Notes for Downstream Stages

- `planner`/`ARCHITECTURE_PLANNING` must decide the `useReplyToTicket.ts` signature shape
  (added optional parameter vs. a shared form field) and whether reply-thread rendering is
  extracted into a shared `components/` file or left screen-local (§1 Note above) — both
  are architectural choices, not surveyed here.
- The `types.ts` additions (including `ReplyRead.visibility`) are a dependency of every
  other new `hooks/`/`screens/` file listed in §1, and of the
  `useReplyToTicket.test.ts`/`TicketDetailScreen.test.tsx`/`useTicketDetail.test.ts` fixture
  updates in §4 — a structural fact for `implementation-planner` to account for, not an
  ordering this survey itself prescribes.
- Specification review v2's three new ambiguities (unspecified "unknown/stale" assignee
  rendering; unspecified null-assignee rendering; unrestated queue-invalidation on a
  detail-screen-originated assign) fall inside `AgentTicketQueueScreen.tsx`/
  `AgentTicketDetailScreen.tsx`'s already-identified markup and `useAssignTicket.ts`/
  `useUnassignTicket.ts`'s already-identified invalidation logic — `planner` should account
  for them as open specification detail within those files, not as a reason to expand the
  file list.
