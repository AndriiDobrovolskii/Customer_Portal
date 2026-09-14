---
artifact_type: implementation_plan
story: US-5.5
version: 2
status: DRAFT
created_at: "2026-09-13T21:00:00Z"
updated_at: "2026-09-14T06:30:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.5-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.5-design-review.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
supersedes: docs/plans/US-5.5-implementation-plan.md (v1)
---

# Implementation Plan: Agent Console (Frontend)

**Story ID:** US-5.5
**Track:** frontend (`docs/stories/US-5.5-agent-console-ui.md` front matter, line 7)

> **Revision (v2):** version 1 of this plan (`status: DRAFT`) was produced
> against specification v1, whose OD-1 through OD-5 were still `OPEN` — v1
> carried each as a "working default... not resolved by this plan" and listed
> them under a "Dependencies on Unresolved Open Decisions" section. Both
> `docs/decisions/US-5.5-open-decisions.md` and `docs/specifications/US-5.5-spec.md`
> are now at version 2: all five items are `RESOLVED` by explicit human
> decision (2026-09-14) and folded directly into FR-1, FR-2, FR-3, FR-6, FR-7,
> and new FR-11's own requirement text — not merely referenced from a
> "Decisions Resolved by Human" appendix. `docs/impact-analysis/US-5.5-impact-analysis.md`
> v2 re-verified every file-level claim from v1 directly against the current
> codebase and found no drift. This revision therefore reads as decided **by
> the spec's own FR text** — every UUID-display, assign-target-input,
> assignee-source, nav-placement, and close/reopen-shape choice below is
> stated as what FR-1/FR-2/FR-3/FR-6/FR-7/FR-11 require, not as an interim
> assumption bridging an open question. The v1 "Dependencies on Unresolved
> Open Decisions" section is removed accordingly (nothing remains open for it
> to carry). Two items are carried forward unchanged because they remain live
> requirements, not resolved-by-citation history: the `ReplyRead.visibility`/
> `CreateReplyRequest.visibility` gap in `frontend/src/api/types.ts` (impact
> analysis v2's Non-Blocking Finding, re-verified still present) is called out
> as its own explicit step below (Architectural Change 1, Files To Modify),
> and the React Hook Form `defaultValues` visibility-leak risk (v1 Risk 2) is
> restated as Risk 2 below, since NFR "re-asserted... each time the composer
> opens" is unchanged, live text in spec v2. This plan also makes an explicit,
> concrete choice on the three new Low/Medium ambiguities specification review
> v2 raised over the *resolved* text (see Architectural Change 8) — none of
> the three was found blocking by any prior stage, so this plan resolves them
> as ordinary implementation detail, the same way it resolved v1's own
> not-yet-ambiguous points, rather than leaving them open.

## Goal

Deliver the agent-side console at `/agent/tickets` (queue) and
`/agent/tickets/:id` (detail) as a pure frontend consumer of US-4.4's
already-shipped backend contract — no backend/API/DB change (spec v2 Out of
Scope; design review v2 `NOT_APPLICABLE`, re-derived against spec v2). The
queue lets an agent see every non-closed ticket, filter by
status/category/assignee (`me`/`none` presets plus a raw-UUID "specific
agent" input, FR-1), and assign/unassign (FR-2). The detail screen renders
the full thread including internal-visibility replies (FR-3), an
explicit-visibility reply composer (FR-4), resolve with a mandatory note
(FR-5), status-/scope-driven affordances (FR-6), close/reopen (FR-7), and a
shared-app-shell nav entry (FR-11). Every screen handles problem+json, 429,
and network/5xx per FR-8/FR-9/FR-10. This plan builds directly on
`impact-analyzer`'s survey (`docs/impact-analysis/US-5.5-impact-analysis.md`
v2) rather than re-deriving the affected-file list; unlike v1, it has no
open architectural question left to resolve on the OD-1 through OD-5 axis —
those are now settled by the spec itself — and instead resolves the two
architectural questions the survey still explicitly leaves to this stage
(the `useReplyToTicket.ts` signature shape and the component-extraction
question, Architectural Changes 2 and 6) plus the three new ambiguities
specification review v2 raised (Architectural Change 8).

## Architectural Changes

1. **`api/` layer extension (additive), including the pre-existing
   `ReplyRead.visibility` gap.** `frontend/src/api/types.ts` gains
   `AgentTicketRead`, `AgentTicketListResponse` (FR-1's queue response —
   every `TicketRead` field plus `assignee_id: string | null`, confirmed
   against `app/modules/support/schemas.py::AgentTicketRead`),
   `AssignTicketRequest` (`{ assignee_id: string }`, FR-2), `AgentTicketStateRead`
   (the actual assign/unassign response shape — confirmed `router.py`
   declares `response_model=AgentTicketStateRead` on both the assign and
   unassign routes, **not** `AgentTicketRead`: it carries `assignee_id` but
   not `subject`/`category`/`body`/`requester_id` — the queue row and the
   assign/unassign response are different shapes and must not be conflated
   in one type; this is also FR-6's stated source for updating the detail
   screen's local assignee value per FR-3/FR-6's navigation-state-handoff
   text), and `ResolveTicketRequest` (`{ resolution_note: string }`, FR-5).
   Separately and independently of any OD: `ReplyRead` (currently `id`,
   `author_id`, `author_kind`, `body`, `created_at`) is missing
   `visibility: "public" | "internal"`, a field `app/modules/support/schemas.py::ReplyRead`
   (line 74) has always returned — confirmed unchanged on this revision by
   direct re-read of both files. FR-3's "internal-visibility replies are
   rendered visually distinct... and explicitly labelled" and FR-4's
   composer both depend on reading this field, so this addition is a hard
   prerequisite for every other new `hooks/`/`screens/` file in this Story,
   not an optional cleanup (impact analysis v2 Non-Blocking Finding, carried
   forward). `CreateReplyRequest` gains an optional
   `visibility?: "public" | "internal"` field for FR-4's composer to send.
   `frontend/src/api/supportApi.ts` gains `listAgentTickets`, `assignTicket`,
   `unassignTicket`, `resolveTicket` as new, additive functions — no existing
   exported function signature in this file changes.

2. **`useReplyToTicket.ts` signature change — additive parameter, not a form
   field.** `useReplyToTicket(id)` currently hardcodes `visibility` to
   omitted (customer composer, US-5.3 — confirmed unchanged: "the composer
   offers no visibility control at all — never send `visibility`"). FR-4
   needs the agent composer to send an explicit value. Decision: add
   `visibility?: "public" | "internal"` as an optional field on the
   mutation's input (`ReplyToTicketFormValues` gains an optional `visibility`
   field used only when the caller's form supplies it), rather than changing
   the hook's call signature (`useReplyToTicket(id)` stays a single-argument
   hook). The customer `TicketDetailScreen.tsx`'s
   `useForm<ReplyToTicketFormValues>()` call is unaffected — its form never
   registers a `visibility` field, so `values.visibility` is `undefined`
   there and the payload omits the key exactly as today; `TicketDetailScreen.tsx`
   itself requires no code change.

3. **New hooks, one per mutation, mirroring the existing `useCloseTicket.ts`/
   `useReopenTicket.ts` "mutation response is the new truth" pattern.**
   `useAgentTickets.ts` (a `useInfiniteQuery` cursor-paginated queue,
   parameterized by `status`/`category`/`assignee_id` — same shape as
   `useAdminUsers.ts`'s `queryKey: ["admin-users", q, status, role] as const`;
   a filter change changes the query key, which resets TanStack Query's page
   state, satisfying FR-1's "each re-issue[s] the request and reset[s] the
   cursor"). Confirmed directly against `app/modules/support/service.py::list_agent_queue`
   (lines 431-471, re-read this pass): `assignee_id` is a raw string the
   **service** resolves — the literal `"me"` maps server-side to the calling
   agent's own id, the literal `"none"` is passed through as its own
   repository-level unassigned-filter sentinel, and anything else that does
   not parse as a UUID raises `422 validation-failed` (rendered per FR-8).
   The frontend
   therefore sends the literal strings `"me"`/`"none"`/a raw UUID string as
   the `assignee_id` query param exactly as typed or clicked (FR-1's
   mutually-exclusive presets plus its independent raw-UUID "specific agent"
   input) — no client-side substitution of the caller's own id, no
   client-side UUID validation beyond what the `422` path already renders.
   `useAssignTicket.ts` and `useUnassignTicket.ts` (kept as two separate
   hooks, not one hook with a boolean flag, matching this codebase's
   one-hook-per-mutation convention — confirmed `useCloseTicket.ts`/
   `useReopenTicket.ts` are likewise separate) invalidate `useAgentTickets`'s
   query key on success (FR-2's "invalidate the queue") and — per FR-6's
   assign-affordance text — write the response's `AgentTicketStateRead`
   fields (`assignee_id`/`status`/`updated_at`) into any open detail screen's
   local assignee state (Architectural Change 7). `useResolveTicket.ts`
   writes its `TicketStateRead` response into `ticketDetailQueryKey(id)`,
   identical to `useCloseTicket.ts`'s existing pattern. `useTicketDetail.ts`,
   `useReplyToTicket.ts` (extended per Change 2, not replaced),
   `useCloseTicket.ts`, and `useReopenTicket.ts` are reused as-is by the new
   agent detail screen — `GET /support/tickets/{id}` returns the same
   `TicketDetailRead` shape for both actor kinds (confirmed: `router.py`
   declares one `response_model=TicketDetailRead`), so no agent-specific
   detail hook is needed.

4. **Routes and nav, additive, per FR-11's now-settled placement.**
   `frontend/src/routes/AppRoutes.tsx` registers `/agent/tickets` and
   `/agent/tickets/:id` inside the existing `ProtectedRoute`/`AppShell` group
   — auth-only gating at the router, same as every existing route (including
   US-5.4's `/admin/*`, confirmed lines 93-102); scope gating stays at the
   presentation layer. `frontend/src/layouts/AppShell.tsx` adds a
   `tickets:read`-gated nav link, reading `scopes` directly off
   `useAuthStore()` exactly like the existing `canReadUsers`/`canReadAudit`
   pattern (confirmed lines 32-33/40-41). FR-11 states this directly ("one
   shared authenticated app shell... a top-level `/agent/*` navigation entry
   is gated on `tickets:read` and offered alongside the existing `/tickets`
   entry... no separate entry point and no role switcher") — this is no
   longer a plan-level default standing in for an open OD-4, it is what the
   approved spec requires.

5. **Scope-gated write controls, mirroring `AdminUserDetailScreen.tsx`'s
   established pattern.** `AgentTicketDetailScreen.tsx` and
   `AgentTicketQueueScreen.tsx` read `tickets:write` off `useAuthStore()`
   (`const canWrite = scopes.includes("tickets:write")`) and pass
   `disabled={!canWrite || mutation.isPending}` to every write control
   (assign/unassign, reply submit, resolve, close, reopen) — the same
   disable-in-place shape `AdminUserDetailScreen.tsx` already uses for
   `users:write`/`roles:write` (confirmed lines 59-60, 272, 289, 345, 388),
   not a separate read-only render branch. This satisfies FR-6's "an agent
   holding `tickets:read` but not `tickets:write` sees a read-only view with
   every write control disabled" without inventing a new UI pattern. The
   server's `403` remains the enforced boundary regardless of what this
   renders (NFR: "client-side scope decoding is never treated as
   authorization").

6. **Component-extraction question: no shared `components/` extraction —
   reuse stays at the hook layer.** The impact analysis (§1 Note) flags that
   `TicketDetailScreen.tsx` inlines its reply-thread markup directly (no
   `components/ReplyList.tsx` or similar exists to import), and leaves
   "extract now vs. reuse only at the hook layer" as an open architectural
   call for this plan. **Decision: do not extract.**
   `AgentTicketDetailScreen.tsx` is written as its own, independent JSX tree
   that imports only `useTicketDetail.ts`, `useReplyToTicket.ts`,
   `useCloseTicket.ts`, `useReopenTicket.ts` (all unmodified except Change
   2's additive field) — the same `screens/` → `hooks/` import direction
   every existing screen uses. Rationale, unchanged from v1's reasoning and
   re-confirmed against impact analysis v2: (a) the survey lists
   `TicketDetailScreen.tsx` as "Checked — Not Affected" (§1a); extracting a
   shared component would require editing that file, contradicting the
   survey's file boundary and triggering `AGENTS.md` §7.8's "no opportunistic
   refactor of untouched code" for a file no AC in this Story touches; (b)
   the two screens' rendering diverges more than it overlaps — the agent
   screen must render an internal/public label+style distinction and a
   status-affordance table with two extra actions (assign/resolve) the
   customer screen has no reason to have; (c) Assumption #1's "extended, not
   duplicated" is satisfied at the layer this codebase already reuses code at
   for this exact pair of screens — the hook layer. This is a plan-level
   decision, not a spec change; it does not touch
   `docs/specifications/US-5.5-spec.md`. A future story is free to extract a
   shared component once real duplication (not just structural similarity)
   is observed across three or more screens.

7. **Detail-screen assignee state, per FR-3/FR-6's settled navigation-state
   handoff (Resolution OD-3).** `TicketDetailRead` carries no `assignee_id`
   (US-4.4's own approved OD-2, confirmed unchanged in
   `app/modules/support/schemas.py`). FR-3 states directly: "The header's
   current-assignee display is sourced as a navigation-state handoff: the
   `assignee_id` from the queue row the agent clicked to open this screen is
   carried into the detail screen's local state and rendered there... it is
   updated afterward from the response of any assign/unassign call made on
   this screen (FR-6). If the screen is opened by a direct URL rather than
   by clicking a queue row, no handed-off value exists and the assignee is
   treated as unknown/stale until the first assign/unassign call on this
   screen resolves it — no workaround endpoint is called to recover it."
   Implementation: `AgentTicketQueueScreen.tsx` passes the clicked row's
   `assignee_id` as React Router navigation `state`
   (`useNavigate(path, { state: { assigneeId } })`); `AgentTicketDetailScreen.tsx`
   reads it via `useLocation().state` into local component state on mount,
   and `useAssignTicket`/`useUnassignTicket`'s `onSuccess` (Change 3) writes
   the mutation's `AgentTicketStateRead.assignee_id` into that same local
   state. This is stated by the current spec, not a working default standing
   in for an unresolved OD.

8. **Three new specification-review-v2 ambiguities over the resolved text —
   resolved here as concrete implementation detail, not left open.** None of
   the three below was found blocking by specification review v2 or any
   later stage; each is confined to the already-identified files (per impact
   analysis v2's "Notes for Downstream Stages") and is settled now so
   implementation has one unambiguous target:
   - **Unknown/stale assignee rendering (FR-3).** Renders as a literal
     em-dash placeholder, `"—"`, with an `aria-label="Assignee unknown"` for
     the a11y bar — never a blank cell (which a screen reader announces as
     nothing) and never a guess. The same treatment used for a genuinely
     unassigned ticket's absent handoff value (below) is reused here rather
     than inventing a second placeholder string.
   - **Null-assignee rendering, unassigned ticket (FR-1, FR-3).** When
     `assignee_id` is `null` (a routinely-surfaced state, since FR-1's
     default queue view applies no `assignee_id` filter), the queue's
     assignee column and the detail header both render the literal text
     `"Unassigned"` — distinguishable at a glance and to a screen reader from
     the truncated-UUID case and from the "unknown/stale" case above, since
     these are three different facts (no agent assigned; an agent is
     assigned but this screen doesn't know who; this screen has no data at
     all) that a shared blank or dash would conflate.
   - **Queue invalidation on a detail-screen-originated assign/unassign
     (FR-6).** `useAssignTicket.ts`/`useUnassignTicket.ts` invalidate
     `useAgentTickets`'s query key unconditionally on every success,
     regardless of whether the mutation was invoked from
     `AgentTicketQueueScreen.tsx` or `AgentTicketDetailScreen.tsx` — one
     `onSuccess` handler, not two call sites with different invalidation
     behavior. This matches the story's own Client State Notes' blanket rule
     ("every successful reply, assign, resolve, close or reopen invalidates
     the ticket detail and the queue") and keeps `useAssignTicket`/
     `useUnassignTicket` themselves origin-agnostic, which is also simpler to
     test (one invalidation assertion per hook test, not two).

## Files To Create

| File | Purpose |
|---|---|
| `frontend/src/hooks/useAgentTickets.ts` | FR-1: cursor-paginated queue query, filtered by `status`/`category`/`assignee_id` (`me`/`none` presets or a raw-UUID value), sent verbatim per Architectural Change 3. |
| `frontend/src/hooks/useAssignTicket.ts` | FR-2 "assign to me"/"assign to another agent" (raw-UUID input): wraps `assignTicket`; unconditionally invalidates the queue query key (Change 8) and writes the response into any open detail screen's local assignee state (Change 7). |
| `frontend/src/hooks/useUnassignTicket.ts` | FR-2 unassign: same invalidation/local-state-write shape as `useAssignTicket.ts`. |
| `frontend/src/hooks/useResolveTicket.ts` | FR-5: wraps `resolveTicket`; writes the returned `TicketStateRead` into `ticketDetailQueryKey(id)`, same pattern as `useCloseTicket.ts`. |
| `frontend/src/screens/AgentTicketQueueScreen.tsx` | FR-1, FR-2: queue table (`ticket_number`, `subject`, `category`, `status`, assignee, `updated_at`), `status`/`category`/`assignee_id` filters plus `me`/`none` presets (mutually exclusive — a `<select>` or two toggle buttons that clear each other, not independent checkboxes) and the independent raw-UUID "specific agent" text input, "Load more", per-row assign-to-me/unassign controls, a raw-UUID text input for "assign to another agent" (FR-2). Assignee column renders a shortened/truncated UUID per FR-1's own wording (FR-1 says only "shortened/truncated," not a specific length; this plan's own concrete choice is the first 8 hex characters), `"Unassigned"` for a null `assignee_id` (Change 8, not FR text). An explicit empty-result state ("No tickets match these filters.") is included, addressing spec review's carried-forward Low finding on FR-1's empty-queue gap. Navigates to the detail screen with `state: { assigneeId: row.assignee_id }` (Change 7) on row click. |
| `frontend/src/screens/AgentTicketDetailScreen.tsx` | FR-3 through FR-7: ticket header including the assignee display (navigation-state handoff per Change 7, rendered per FR-1's truncation rule, `"Unassigned"`/`"—"` — both plan-level choices per Change 8, not FR text), full thread with internal replies visually distinct and labelled "internal" (a distinct wrapper element/class plus the literal text label — never colour alone, per NFR), "Load older replies", the visibility-aware composer (`<select>`/radio group whose `useForm` `defaultValues` are re-derived to `"public"` on every open — see Risk 2), resolve with a client-side non-empty (post-`trim()`) `resolution_note` check addressing spec review's carried-forward Low finding on whitespace-only notes, close/reopen as single action buttons with no `reason` field and no confirmation modal (FR-7), and the five-status × two-scope affordance table (FR-6). |
| `frontend/src/hooks/useAgentTickets.test.ts` | Filter-changes-query-key/resets-cursor, `me`/`none` presets, raw-UUID filter, "Load more". |
| `frontend/src/hooks/useAssignTicket.test.ts` | Assign-to-self, assign-to-other (raw-UUID), queue invalidation from both queue- and detail-originated calls, detail local-state write, 409/422 problem+json propagation. |
| `frontend/src/hooks/useUnassignTicket.test.ts` | Unassign, queue invalidation, detail local-state write, 409 propagation. |
| `frontend/src/hooks/useResolveTicket.test.ts` | Resolve success writes `TicketStateRead` into detail cache; 409 on closed ticket propagates. |
| `frontend/src/screens/AgentTicketQueueScreen.test.tsx` | FR-1 (rendering, filters, presets, raw-UUID filter, Load more, empty state, null-assignee "Unassigned" rendering), FR-2's queue-side assertions (assign/unassign call shape, 409/422 rendering, navigation-state handoff on row click), a11y check (axe) on the queue table with column-header association. |
| `frontend/src/screens/AgentTicketDetailScreen.test.tsx` | FR-3 (thread rendering, internal-note distinct style+label, Load older replies, unknown/stale-assignee "—" rendering on direct-URL entry), FR-4 (visibility default is always `"public"` on mount/re-open, never sticky, invalidation on reply), FR-5 (resolve success/empty-note block/whitespace-only block/409), FR-6 (five-status × `tickets:write`-present/absent table-driven test, queue-invalidation-from-detail assertion), FR-7 (single-button close/reopen, no confirmation), FR-8–FR-10 (problem+json, 429 with countdown, network/5xx retry state), plain-text rendering (HTML-bearing body escapes), a11y check. |

## Files To Modify

| File | Change |
|---|---|
| `frontend/src/api/types.ts` | Add `AgentTicketRead`, `AgentTicketListResponse`, `AssignTicketRequest`, `AgentTicketStateRead`, `ResolveTicketRequest` (all new, additive interfaces). Add `visibility: "public" \| "internal"` to the existing `ReplyRead` interface (a required field — the backend has always returned it; this closes impact analysis v2's carried-forward Non-Blocking Finding, and is a type-accuracy fix, not a new optional field). Add `visibility?: "public" \| "internal"` to `CreateReplyRequest` (optional — the existing customer call site never sets it). |
| `frontend/src/api/supportApi.ts` | Add `listAgentTickets(params)`, `assignTicket(id, data)`, `unassignTicket(id)` (via the existing `httpDelete<T>` verb, passing no body), `resolveTicket(id, data)` as new exported functions. No existing function's signature changes. |
| `frontend/src/hooks/useReplyToTicket.ts` | `ReplyToTicketFormValues` gains an optional `visibility?: "public" \| "internal"` field; `mutationFn` includes `visibility: values.visibility` in the payload only when defined (`CreateReplyRequest`'s field is optional, so omitting the key when `undefined` keeps the customer path's request body byte-for-byte identical to today). The doc comment's "never send `visibility`" is updated to describe the customer path specifically, not the hook generally. |
| `frontend/src/routes/AppRoutes.tsx` | Add `<Route path="/agent/tickets" element={<AgentTicketQueueScreen />} />` and `<Route path="/agent/tickets/:id" element={<AgentTicketDetailScreen />} />` inside the existing `ProtectedRoute`/`AppShell` group, alongside the `/admin/*` block. |
| `frontend/src/layouts/AppShell.tsx` | Add `const canReadTickets = scopes.includes("tickets:read");` and `{canReadTickets && <Link to="/agent/tickets">Agent Queue</Link>}` in the same `<nav>`, alongside the existing `/tickets`, `/admin/users`, `/admin/audit-logs` links — one shared shell, per FR-11's settled requirement. |
| `frontend/src/test/mswHandlers.ts` | Add default handlers for `POST /support/tickets/:id/assign`, `DELETE /support/tickets/:id/assign` (both returning an `AgentTicketStateRead`-shaped body), `POST /support/tickets/:id/resolve` (returning `TicketStateRead` with `status: "resolved"`) — none exist today. Extend the existing `GET /support/tickets/:id` default handler's reply fixtures to include `visibility: "public"` (an explicit value, not an omitted field, so tests exercising the field aren't accidentally passing against `undefined`). The existing `GET /support/tickets` handler is left returning the customer shape (`{ items: [], next_cursor: null }`) as the baseline; agent-branch queue responses (`AgentTicketListResponse`, with `assignee_id`) are supplied per-test via `server.use(...)`, following this file's own "baseline + per-test override" convention — not added as a second default handler, since the same URL cannot have two conflicting default bodies. |
| `frontend/src/hooks/useReplyToTicket.test.ts` | Add a case asserting a supplied `visibility` is included in the request body; confirm the existing customer-path cases (no `visibility` supplied) still omit the key. |
| `frontend/src/screens/TicketDetailScreen.test.tsx` | Update reply fixtures that omit `visibility` to include an explicit `"public"` value, so they stay contract-realistic against the now-accurate `ReplyRead` type (no behavior change — `TicketDetailScreen.tsx` itself is not modified by this Story, per Architectural Change 6). |
| `frontend/src/hooks/useTicketDetail.test.ts` | Same fixture update as above, for the same reason. |
| `frontend/src/routes/AppRoutes.test.tsx` | Add cases asserting `/agent/tickets` and `/agent/tickets/:id` render their respective new screens, following this file's existing per-route-addition pattern. |
| `frontend/src/layouts/AppShell.test.tsx` | Add a case asserting the `tickets:read`-gated nav entry's visibility, following the existing `canReadUsers`/`canReadAudit` test pattern. |

No change to `frontend/src/api/httpClient.ts` (confirmed by the impact
analysis and independently re-verified: `httpDelete<T>` already accepts a
typed response and no body; `429`'s `Retry-After` header is already parsed
generically into `ApiError.retryAfterSeconds`), `frontend/src/store/authStore.tsx`/
`decodeTokenScopes.ts` (scopes already exposed and already consumed
cosmetically elsewhere), `frontend/src/routes/ProtectedRoute.tsx`/
`GuestOnlyRoute.tsx`, `frontend/src/components/ErrorState.tsx`/`FieldError.tsx`/
`apiErrorHelpers.ts`, `frontend/src/hooks/useRetryAfterCountdown.ts`, or
`frontend/src/test/test-utils.tsx` (`scopes` seeding already exists, added
for US-5.4).

No `AGENTS.md` §7.9-protected file (`pyproject.toml`, `migrations/env.py`,
`.pre-commit-config.yaml`) is touched by this plan.

## Risks

1. **`ReplyRead.visibility` becoming a required field is a breaking type
   change for any untyped test fixture that omits it.** Two existing test
   files (`TicketDetailScreen.test.tsx`, `useTicketDetail.test.ts`) build
   reply fixtures as untyped `HttpResponse.json({...})` literals, so they do
   not fail `type-check` today regardless of this field's presence — but
   leaving them without `visibility` means they exercise a field that is
   `undefined` at runtime against a type that says it can't be. This is
   listed as a Files To Modify item above specifically to close that gap,
   not left as a latent inconsistency.
2. **A race between "internal is never sticky" (FR-4 + NFR, both live and
   unchanged in spec v2) and React Hook Form's default-value caching.**
   FR-4 itself states "Choosing 'internal' is a deliberate, visible action —
   it is never the default and never a silent state," and the NFR adds "The
   visibility control's state MUST be re-asserted (not remembered from the
   previous reply) each time the composer opens, so a prior 'internal'
   choice cannot leak into the next public reply." `useForm`'s
   `defaultValues` are captured once at first mount, not re-derived on every
   render; if `AgentTicketDetailScreen.tsx` keeps one `useForm` instance
   alive across multiple replies without remounting or explicitly
   `reset()`-ing the visibility field to `"public"` after each successful
   submit, a prior "internal" choice could leak into the next open of the
   composer — the exact failure both FR-4 and the NFR forbid. **Mitigation:** the reply mutation's `onSuccess`
   must call `reset({ body: "", visibility: "public" })` (extending the
   existing `reset({ body: "" })` call in the customer screen's pattern) —
   this is the concrete implementation of the NFR, and must be asserted
   directly by `AgentTicketDetailScreen.test.tsx` (submit an internal note,
   confirm the composer shows `"public"` again on its next render), not just
   assumed from the default value.
3. **Distinguishing the assign/unassign response shape (`AgentTicketStateRead`)
   from the queue row shape (`AgentTicketRead`) is easy to get wrong once,
   silently.** Both carry `assignee_id`, but only `AgentTicketRead` carries
   `subject`/`category`/`updated_at` — a developer writing
   `useAssignTicket.ts`'s cache-update logic could be tempted to
   `queryClient.setQueryData` a full queue row from the assign response and
   accidentally blank out `subject`/`category` with `undefined`. Mitigation:
   `useAssignTicket.ts`/`useUnassignTicket.ts` only ever merge
   `assignee_id`/`status`/`updated_at` (the fields `AgentTicketStateRead`
   actually has) into existing cache entries, never spread the response over
   a full `AgentTicketRead`-typed object.
4. **The queue's `assignee_id` text input accepts free-form text with no
   client-side UUID shape validation, by design (FR-1/FR-2).** A malformed
   value is rejected server-side with `422` (FR-8's problem+json handling),
   not blocked client-side — consistent with `list_agent_queue`'s own
   validation. This is not a gap to fix; it is the concrete, spec-required
   behavior. Noted here so the test suite (`useAgentTickets.test.ts`,
   `AgentTicketQueueScreen.test.tsx`) asserts the 422-renders-inline path
   rather than expecting a client-side blocking error that FR-1 never asks
   for.

## Validation Strategy

`npm run lint`, `npm run format:check`, `npm run type-check`, and
`npm run test:coverage` (`AGENTS.md` §2 Frontend subsection — these exact
script names) must all stay green. Since `frontend/src/api/types.ts` widens
`ReplyRead` with a new required field, `type-check` is the concrete gate that
catches any remaining untyped-but-now-inconsistent fixture the Files To
Modify list missed (though most of this codebase's fixtures are untyped
literals, so this is a secondary check, not the primary one — the fixture
updates listed above are the primary fix). No `lint-imports` equivalent
exists for the frontend layer table; `AGENTS.md` §3's Frontend layer
constraints (`screens/` never importing `api/` or calling `fetch` directly,
`hooks/` never importing JSX) are checked by reading the diff for each new
file, per that section's stated process until a mechanical contract exists.
Coverage stays at the existing 85% floor (`vitest --coverage`); no touched
module may lose coverage.

## Testing Strategy

Per `AGENTS.md` §5 Frontend subsection's unit/integration split:

- **Unit** — `useAgentTickets.test.ts`, `useAssignTicket.test.ts`,
  `useUnassignTicket.test.ts`, `useResolveTicket.test.ts` exercise each hook
  in isolation (Vitest, `renderHook`) against MSW handlers shaped like the
  real backend contract, not a hand-mocked `fetch` — per §5's "prefer a real
  MSW handler... a handler that actually matches the request shape catches
  more than a stub."
- **Integration** — `AgentTicketQueueScreen.test.tsx` and
  `AgentTicketDetailScreen.test.tsx` render the real component tree (screen +
  hooks + store) via React Testing Library, with MSW intercepting every
  network call, covering: FR-1 (queue rendering, filter/preset
  re-request-and-reset-cursor, raw-UUID "specific agent" filter, Load more,
  empty-result state, null-assignee `"Unassigned"` rendering — the literal
  string per Change 8, not FR text), FR-2
  (assign/unassign call shape and unconditional queue invalidation, 409/422
  problem+json), FR-3 (thread rendering, internal-note distinct style+label,
  Load older replies, navigation-state handoff for the assignee display
  including the direct-URL unknown/stale `"—"` case — the literal placeholder
  per Change 8, not FR text), FR-4 (visibility
  default always `"public"` including after a prior internal submission —
  the concrete test for Risk 2 above — and ticket-detail invalidation on a
  public reply), FR-5 (resolve success, empty-note and
  whitespace-only-note client-side blocks, 409 on a closed ticket), FR-6 (a
  table-driven Vitest case, `describe.each`/`it.each` over all five statuses
  × `tickets:write` present/absent, asserting exactly the offered-action set
  FR-6's table states, every write control's `disabled` state when
  `tickets:write` is absent, and that a detail-screen-originated assign
  invalidates the queue too), FR-7 (single-button close/reopen, no `reason`
  field, no confirmation step), FR-8 (problem+json detail rendering, 422
  field-error mapping), FR-9 (429 message + disabled submit + no auto-retry
  loop, via `useRetryAfterCountdown` reused unchanged), FR-10 (network/5xx
  retry-capable error state on every endpoint this Story calls), the
  internal-note distinction test (style + label, not colour alone — assert
  both a CSS class/attribute and the literal text "internal"), the
  plain-text-rendering test (an HTML-bearing reply body renders as escaped
  text, confirming no `dangerouslySetInnerHTML` anywhere in the new files),
  and an automated a11y check (axe) on both new screens per the Enforcement
  Matrix.
- No standalone `supportApi.test.ts` is added — matching the existing
  pattern (no such file exists today for any of this module's current
  functions); the new `api/` functions are exercised only through the
  hook/screen tests above plus the MSW handlers.
- `AppRoutes.test.tsx` and `AppShell.test.tsx` gain cases for the two new
  routes and the new nav entry (FR-11), following each file's existing
  per-story pattern.

## Dependency on Prior Stories

- **US-5.1** — auth store (`scopes`), API client (`httpClient.ts`), route
  guards (`ProtectedRoute`), problem+json rendering (`ErrorState`,
  `apiErrorHelpers`). Reused unmodified.
- **US-5.3** — `useTicketDetail.ts`, `useCloseTicket.ts`,
  `useReopenTicket.ts`, `useRetryAfterCountdown.ts` reused unmodified;
  `useReplyToTicket.ts` extended (Architectural Change 2).
- **US-5.4** — the scope-derived nav-entry pattern (`AppShell.tsx`'s
  `canReadUsers`/`canReadAudit`) and the scope-gated disabled-control pattern
  (`AdminUserDetailScreen.tsx`) are both reused as direct precedent, not
  reinvented.
- **US-4.4 (hard blocker, already discharged)** — per impact analysis v2's
  codebase re-check, US-4.4's agent-branch queue, assign, unassign endpoints
  and `AgentTicketRead`/`AgentTicketListResponse`/`AgentTicketStateRead`
  schemas this plan consumes are shipped, unchanged since `d69132b`, and
  re-verified directly against `app/modules/support/schemas.py`/`router.py`
  this session (see this plan's own re-read of `service.py::list_agent_queue`
  above).

## Open Decisions Status

All five items in `docs/decisions/US-5.5-open-decisions.md` (v2) — OD-1
(assignee-UUID display), OD-2 (no agent-directory mechanism), OD-3
(detail-screen assignee source), OD-4 (shared app shell), OD-5 (close/reopen
interaction shape) — are `RESOLVED` by explicit human decision (2026-09-14)
and incorporated as requirement text in `docs/specifications/US-5.5-spec.md`
v2's FR-1, FR-2, FR-3, FR-6, FR-7, and FR-11. None is a dependency this plan
is waiting on; this plan implements each resolution as stated spec behavior
(Architectural Changes 1, 3, 4, 7 above), not as an interim default. This
plan resolves no Open Decision itself — it consumes resolutions already
recorded upstream.
