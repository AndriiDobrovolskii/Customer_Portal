---
artifact_type: test_strategy
story: US-5.5
version: 1
status: DRAFT
created_at: "2026-09-14T08:15:00Z"
updated_at: "2026-09-14T08:15:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.5-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.5-plan-review.md
    version: 2
supersedes: null
---

# Test Strategy: Agent Console — Frontend (US-5.5)

## Track and binding context

`track: frontend` (`docs/stories/US-5.5-agent-console-ui.md` front matter, line
7). `API_DESIGN`/`DB_DESIGN` are `NOT_APPLICABLE` for this Story (design
review v2, re-derived against spec v2) — the spec's own API Contract table,
cross-checked against the already-shipped US-4.4 backend, is the reference
contract, per this skill's Required Context for this track.

OD-1 through OD-5 are `RESOLVED` (`docs/decisions/US-5.5-open-decisions.md`
v2) and are incorporated directly into specification v2's FR-1, FR-2, FR-3,
FR-6, FR-7, and new FR-11 as firm requirement text. This pass treats all five
as settled, not as open questions to hedge around.

## This stage's division of labor on this Story (read before the rest of this document)

**No test source file is written by this pass.** `docs/plans/US-5.5-task-breakdown.md`
v2's own header states this for this Story explicitly: `IMPLEMENTATION` runs
exactly one execution skill, `frontend-builder`, and "every row below names
`frontend-builder` and bundles a file's paired `*.test.ts(x)` with it, matching
the convention `docs/plans/US-5.4-task-breakdown.md` already established."
Tasks T4–T14's own "Files Touched" columns each list the `.test.ts(x)` file
alongside its production file, and T9/T10 are explicitly "fixture-only, no
production change" tasks — none of this is coherent if `test-writer` also
lands those same files here. This mirrors US-5.4's approved division of labor
exactly, not the US-5.1/US-5.2/US-5.3 precedent (where `test-writer` wrote
`frontend/src/**/*.test.ts(x)` directly).

Every test function name in this document and in
`docs/tests/US-5.5-ac-test-matrix.md` is therefore **prescriptive**: a binding
name and assertion `frontend-builder` must create verbatim under the file
mapping below, **not a claim that the function already exists in the working
tree.** This stage's own completion criterion ("the matrix rows name test
functions that exist") is satisfied only once `frontend-builder` has adopted
these names unchanged — recorded plainly here and in the generation report so
no downstream reader (especially `RECONCILIATION`, whose own job is "the
referenced test function exists and actually asserts the AC's stated
behavior") mistakes this matrix for as-built evidence. A renamed or reshaped
test at `IMPLEMENTATION` is drift to flag at `RECONCILIATION`, not silently
accepted as equivalent.

`frontend/src/test/mswHandlers.ts` is Task T3's own deliverable on this Story
(`frontend-builder`'s territory, matching the US-5.4 precedent, unlike the
US-5.1 precedent where `test-writer` wrote it) — this pass specifies what new
default handlers it must add (see "MSW handler shape" below) without writing
the file. `frontend/src/test/test-utils.tsx` is confirmed **unchanged** by
both the impact analysis and the plan ("no change... `scopes` seeding already
exists, added for US-5.4"); this pass's prescribed tests are written to that
constraint (see "Navigation-state handoff mechanism" below), not against a
widened harness.

## Unit vs. integration split (`AGENTS.md` §5 Frontend subsection)

- **Unit** (`frontend/src/hooks/*.test.ts`): a hook in isolation
  (`renderHookWithProviders`), MSW as the network boundary for every hook that
  performs I/O, never a hand-mocked `fetch`. A pure exported function tested
  in isolation (no render, no network) is also Unit regardless of which file
  it lives in, per `AGENTS.md` §5's "a hook **or a pure function** in
  isolation" — `agentOfferedActionsForStatus`'s own describe block lives
  inside `AgentTicketDetailScreen.test.tsx` (a `.test.tsx` file) the same way
  US-5.3's `offeredActionsForStatus` precedent does, and is still Unit-level.
- **Integration** (`frontend/src/screens/*.test.tsx`, additive cases in
  `frontend/src/routes/AppRoutes.test.tsx` and `frontend/src/layouts/AppShell.test.tsx`):
  React Testing Library renders the real screen + hooks + store tree; MSW
  intercepts every network call with a handler shaped like the real US-4.4
  contract (status, body, `application/problem+json` content type on every
  4xx, `Retry-After` header on `429`).

**No `vi.mock()` on the unit under test anywhere in this pass's prescriptions**
— `frontend-builder` mocks the network (MSW) only, per `AGENTS.md` §5's
explicit prohibition.

## Collaborator-shape decisions this pass fixes

No design doc exists on this track to fix an internal hook signature, a query
key, or a component's accessible name beyond `implementation_plan` v2's prose.
To write concrete, executable-when-implemented assertions, this pass fixes the
following — flagged, per the `US-5.3`/`US-5.4` precedent, as decisions for
`frontend-builder`/`reconciliation-reviewer` to check the shipped shape
against, not resolved Open Decisions, and not FR text itself where noted:

1. **`useAgentTickets.ts`** returns a bare `useInfiniteQuery` result,
   `queryKey: ["agent-tickets", status, category, assigneeId] as const`
   (mirroring `useAdminUsers.ts`'s shape), `getNextPageParam` reading
   `next_cursor`. `status`/`category`/`assigneeId` (populated by the `me`/
   `none` presets or the Resolution-OD-2 raw-UUID input) are sent as the
   **literal, unvalidated string** query parameter `assignee_id` — Risk 4's
   stated behavior: no client-side substitution of "me"/"none", no
   client-side UUID shape check. A malformed value's `422` is left to render
   through the existing problem+json path, never blocked client-side.
2. **The queue/assign/unassign/resolve cross-hook cache shape (Architectural
   Changes 3, 7, 8; Risk 3).** `FR-6`/OD-3 requires that a successful
   assign/unassign write into "any open detail screen's local assignee
   state," and that this write happen unconditionally regardless of whether
   the mutation was invoked from the queue screen or the detail screen. This
   pass fixes the concrete mechanism as a **shared TanStack Query cache
   entry**, not literal component `useState`, so it is unit-testable at the
   hook level exactly as T5/T6 require: an exported helper
   `agentTicketAssigneeQueryKey(id)` (e.g. `["agent-ticket-assignee", id] as
   const`, colocated in `useAssignTicket.ts` and imported by
   `useUnassignTicket.ts` and `AgentTicketDetailScreen.tsx`, the same
   "one hook exports the key, siblings import it" pattern
   `ticketDetailQueryKey`/`ticketRepliesQueryKey` already establish).
   `useAssignTicket.ts`/`useUnassignTicket.ts`'s `onSuccess` **always**
   (regardless of caller) invalidates `["agent-tickets"]` (queue, via a
   predicate/prefix match, not the fully-parameterized queue key, since the
   mutation does not know the queue's current filter values) and writes only
   `{ assignee_id, status, updated_at }` — never a spread of the full
   response over an `AgentTicketRead`-shaped object (Risk 3) — into
   `agentTicketAssigneeQueryKey(id)` via `queryClient.setQueryData`.
   `AgentTicketDetailScreen.tsx` seeds this same cache entry on mount from
   `useLocation().state?.assigneeId` (Change 7's navigation-state handoff)
   when present, and reads it via `useQueryClient().getQueryData(...)` (not a
   live `useQuery`, since there is no `queryFn` — this is a write-only,
   locally-seeded cache slot, not a network resource). This is the
   collaborator-shape choice `frontend-builder` must implement; it satisfies
   both T5/T6's own stated hook-level test surface and Change 8's
   origin-agnostic invalidation without widening `test-utils.tsx`.
3. **Navigation-state handoff mechanism (Resolution OD-3, Architectural
   Change 7) — the test mechanism, fixed here since `test-utils.tsx` is
   unchanged.** `AgentTicketQueueScreen.tsx` navigates via
   `useNavigate()(path, { state: { assigneeId: row.assignee_id } })` on row
   click. Since `frontend/src/test/test-utils.tsx`'s `RenderWithProvidersOptions.route`
   is a plain string (no location-state parameter, confirmed unchanged by
   impact analysis v2 and the plan), the handoff is asserted by rendering
   **both** `AgentTicketQueueScreen` and `AgentTicketDetailScreen` inside one
   local `<Routes>` tree (the same "wrap `ui` in its own local `<Routes>`"
   pattern `TicketDetailScreen.test.tsx`/`AdminUserDetailScreen.test.tsx`
   already use for a URL param) and clicking a queue row — the real router
   then carries `state` exactly as production code would. The
   direct-URL/no-handoff case (FR-3's "opened by a direct URL... treated as
   unknown/stale") is asserted the ordinary way: `renderWithProviders` with a
   plain `route: "/agent/tickets/t-1"` string, which carries no
   `location.state` by construction. Neither case requires a change to
   `test-utils.tsx`.
4. **`agentOfferedActionsForStatus(status)`** — a pure, exported function on
   `AgentTicketDetailScreen.tsx`, the same "collaborator-shape precedent"
   `TicketDetailScreen.tsx`'s own `offeredActionsForStatus` already
   established for US-5.3, extended with FR-6's two new action keys:
   ```
   { reply: boolean; assign: boolean; resolve: boolean; close: boolean; reopen: boolean }
   ```
   implementing FR-6's table exactly: `open`/`waiting_on_support`/
   `waiting_on_customer` → `{reply:true, assign:true, resolve:true,
   close:true, reopen:false}`; `resolved` → `{reply:true, assign:true,
   resolve:false, close:true, reopen:true}` (never `resolve:true` —
   explicitly asserted, this is the easiest cell to invert by mistake);
   `closed` → all five `false`; any unrecognized status defaults to all five
   `false` (fail closed, same discipline as US-5.3's function). This governs
   only which action *sections render at all*; within a rendered section, the
   control's own `disabled` attribute is set independently by
   `!canWrite || mutation.isPending` (Architectural Change 5) — a
   `tickets:read`-only scope does not hide sections FR-6's status table
   offers, it disables their controls, per FR-6's own "sees a read-only view
   with every write control disabled" (not "hidden").
5. **Assignee-display rendering (Resolution OD-1, Architectural Change 8) —
   plan-level literals, not FR text; RECONCILIATION should read them as
   implementation detail, not spec requirement.**
   - Shortened/truncated UUID: the first 8 hex characters of `assignee_id`
     (`assignee_id.slice(0, 8)`), the plan's own concrete choice — FR-1/FR-3
     say only "shortened/truncated."
   - Null `assignee_id` (a genuinely unassigned ticket): the literal text
     `"Unassigned"`.
   - Unknown/stale (no navigation-state handoff and no assign/unassign yet
     resolved it, on direct-URL entry): the literal placeholder `"—"` with
     `aria-label="Assignee unknown"`.
   - These three are visually and semantically distinct render paths — a test
     asserting one must not accidentally also satisfy another (e.g. a blank
     cell would satisfy neither the "Unassigned" nor the "—" assertion
     correctly).
6. **Queue empty-result state and whitespace-only `resolution_note` block —
   plan-level literals (plan_review v2 Non-Blocking Findings), not FR text.**
   The queue's empty-result message is the literal text
   `"No tickets match these filters."`; the resolve composer's client-side
   block treats a post-`trim()` empty string the same as a literal empty
   string (so `"   "` alone is blocked, not just `""`).
7. **Accessible names / control labels** (no design doc fixes UI copy;
   matchers below are case-insensitive regexes loose enough to tolerate minor
   copy differences while still pinning presence and pattern, per the
   `US-5.3`/`US-5.4` documented matcher policy):
   - "Assign to me" / an "agent id"-labelled raw-UUID input (assign-to-another
     target and the queue's "specific agent" filter both use this same
     control shape) / "Unassign".
   - "Status" / "Category" — the queue's two `<select>` filters.
   - "Load more" (queue) / "Load older replies" (thread) — matching the
     existing per-screen labels this codebase already uses for the customer
     and admin equivalents; never the same label for both cursors on the
     detail screen.
   - "Visibility" — the composer's public/internal control; its two values
     match on `/public/i`/`/internal/i`.
   - "Resolution note" — the resolve form's required field; "Resolve" its
     submit button.
   - "Close ticket" / "Reopen" — single-button, no confirmation, matching
     `TicketDetailScreen.tsx`'s existing customer-side labels exactly (FR-7,
     Resolution OD-5).
   - "Agent Queue" — the new `AppShell.tsx` nav entry's link text.
8. **MSW handler shape** (Task T3's deliverable; specified, not written, by
   this pass): `POST /support/tickets/:id/assign` and
   `DELETE /support/tickets/:id/assign` both default to an
   `AgentTicketStateRead`-shaped 200 body (`{id, status, assignee_id,
   updated_at}` — no `subject`/`category`, per Risk 3); `POST
   /support/tickets/:id/resolve` defaults to a `TicketStateRead`-shaped 200
   body with `status: "resolved"`; the existing `GET /support/tickets/:id`
   default handler's reply fixtures must carry an explicit `visibility:
   "public"` value (Risk 1). Every test below that needs an agent-branch
   queue response (`AgentTicketListResponse`, carrying `assignee_id`)
   supplies it via a per-test `server.use(...)` override on `GET
   /support/tickets`, since the existing default handler for that URL stays
   the customer shape (`{items, next_cursor}` with no `assignee_id`) — the
   established "baseline + per-test override" convention, not a second
   conflicting default.

## Statement-count-ceiling analogue

This Story has **two independent cursors on the detail screen** (the queue's
own cursor, and the reply thread's own cursor, per the story's own Client
State Notes: "Queue and thread paginate independently"), in addition to the
existing customer-side precedent. Every cursor-paginated screen/hook test
(`AgentTicketQueueScreen`, `AgentTicketDetailScreen`'s "Load older replies",
`useAgentTickets`) asserts the exact MSW-observed request count and the
`cursor` value carried on each request — "Load more"/"Load older replies"
each issue exactly one additional request carrying the previous page's
`next_cursor` — so a cross-invalidation regression (e.g. an assign
accidentally also refetching the reply thread, or vice versa) fails a named
test, not only latency.

## Coverage floor

85% via `test:coverage`, CI-enforced (`AGENTS.md` §5/§6 Frontend subsection).
Not measured by this stage — no implementation exists yet, and this stage
writes no test source either; enforced at `QUALITY_GATE` per `task_breakdown`
v2 Task T15.

## Risk-to-test mapping (Implementation Plan v2's four Risks)

- **Risk 1** (`ReplyRead.visibility` becoming required breaks two existing
  untyped fixture files) — closed by T9/T10's fixture-parity updates (see
  "Existing-file test-surface impact" below), not a new behavioral assertion.
- **Risk 2** (React Hook Form `defaultValues` caching could leak a prior
  "internal" choice into the next composer open) — a **named, explicit**
  assertion, not assumed from the default value:
  `AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_visibility_is_never_sticky_composer_reads_public_again_immediately_after_an_internal_submission`
  submits an internal note, then asserts the composer's visibility control
  reads `"public"` again on its very next render.
- **Risk 3** (`AgentTicketStateRead` vs. `AgentTicketRead` field-shape
  confusion) — an explicit hook-level assertion in both
  `useAssignTicket.test.ts` and `useUnassignTicket.test.ts` that the cache
  write never carries `subject`/`category`/`body`/`requester_id`.
- **Risk 4** (the queue's `assignee_id` free-text filter has no client-side
  UUID validation, by design) — asserted as the **absence** of a client-side
  block plus the presence of the server's `422`-renders-inline path, in both
  `useAgentTickets.test.ts` and `AgentTicketQueueScreen.test.tsx`. This pass
  does not prescribe a client-side validation test FR-1 never asks for.

## Non-blocking findings this pass records

- **Every test function name below is prescriptive, not as-built** (see
  "This stage's division of labor" above) — recorded so `RECONCILIATION`
  checks the real, shipped files rather than this document.
- **Five items are the plan's own literal choices, not FR/AC text**
  (Collaborator-shape decisions 5 and 6 above): the `"—"`/`"Unassigned"`
  assignee placeholders, the first-8-hex-character truncation rule, the empty
  -queue message, and the whitespace-only `resolution_note` block. Carried
  forward from `docs/reviews/plans/US-5.5-plan-review.md` v2's own
  Non-Blocking Findings so they are not later mistaken for spec requirements.
- **FR-11 has no Acceptance Criterion of its own** (specification v2's own
  Traceability Matrix states this explicitly: "no AC in this Story tests
  navigation placement"). This pass's routing/nav test rows are grouped under
  a non-AC "Routing and navigation (FR-11)" section in the matrix rather than
  attached to an invented AC id.
- **This Story has no `XC-AC*` cross-cutting band** (unlike US-5.4). The
  server-403-render requirement and the route-guard-redirect requirement both
  come from the NFR list and AG-AC7/the story's own security posture rather
  than a numbered AC — both are given their own non-AC matrix sections rather
  than silently dropped or force-fit under AG-AC7.

## Existing-file test-surface impact (impact analysis v2 §4; Risk 1)

- `frontend/src/hooks/useReplyToTicket.test.ts` — **additive** case only
  (Task T8): a new `visibility` value supplied on the mutation input is
  included in the request body; the existing customer-path cases (no
  `visibility` supplied) are unchanged and keep omitting the key.
- `frontend/src/hooks/useTicketDetail.test.ts` (Task T9) and
  `frontend/src/screens/TicketDetailScreen.test.tsx` (Task T10) —
  **fixture-parity only**: each file's existing `ReplyRead`-shaped literal
  fixtures gain an explicit `visibility` value so they stay contract-realistic
  against the now-widened `ReplyRead` type; this is not a new behavioral
  assertion; both files' own production file (`useTicketDetail.ts`,
  `TicketDetailScreen.tsx`) has zero diff, per the task breakdown's own
  verification commands (`git diff --stat` empty).

## Known gaps this pass records rather than papers over

- **NFR "responsive ~375px through desktop; queue table scrolls within its
  own container"** — not Vitest-testable without a visual/viewport-emulation
  tool this project does not use; not asserted here, consistent with the
  US-5.3/US-5.4 identical recorded gap.
- **a11y bar** — asserted via the existing `vitest-axe` devDependency on
  exactly the two screens the Enforcement Matrix names
  (`AgentTicketQueueScreen`, `AgentTicketDetailScreen`).
- **Open Question #1** (`assignee_id` resolving to a display name) is
  resolved by Resolution OD-1 (shortened/truncated UUID, no name-resolution
  call) — nothing further for this stage to test; a test asserting the
  *absence* of any `GET /admin/users/{id}` call from either new screen is not
  prescribed, since no test in this Story's suite seeds a `users:read`-scoped
  MSW handler that could tempt such a call, and the production code has
  nothing to import to make one (no `usersApi` import exists in either new
  screen's Files To Create entry).
