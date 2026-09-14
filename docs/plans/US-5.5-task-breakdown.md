---
artifact_type: task_breakdown
story: US-5.5
version: 2
status: DRAFT
created_at: "2026-09-14T03:00:00Z"
updated_at: "2026-09-14T07:00:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
supersedes: docs/plans/US-5.5-task-breakdown.md (v1)
---

# Task Breakdown — US-5.5 (Agent Console, Frontend)

> **Revision (v2):** version 1 of this breakdown (`status: DRAFT`) was
> produced against specification v1 (OD-1–OD-5 `OPEN`), impact analysis v1,
> and implementation plan v1, and sequenced every task's interior markup as
> "the plan's concrete interim default" pending resolution of OD-1 through
> OD-5. All three of those inputs are now at version 2:
> `docs/decisions/US-5.5-open-decisions.md` v2 records OD-1 through OD-5 as
> `RESOLVED` by explicit human decision (2026-09-14, verified directly on
> disk, not by citation); `docs/specifications/US-5.5-spec.md` v2 folds each
> resolution into FR-1, FR-2, FR-3, FR-6, FR-7, and new FR-11's own
> requirement text; `docs/plans/US-5.5-implementation-plan.md` v2 states each
> Architectural Change as what the approved spec requires, not as a
> plan-level default bridging an open question. This revision re-derives the
> task sequence against that v2 chain: the file set, task count (T1–T14 plus
> `gate-enforcer` as T15), and dependency graph are **unchanged from v1** —
> `implementation-planner`'s own re-check confirms plan v2's only additions
> over v1 (the explicit `types.ts`-extension step and the restated React
> Hook Form visibility-leak mitigation/test) were already covered by v1's T1
> and T12 respectively, so no task is added, removed, or reordered. What
> changes is the *content* of several rows: every "interim default"/"OD-n"
> phrasing is replaced with a citation to the settled FR text; three new
> literal-rendering choices from plan v2's Architectural Change 8 (the
> `"—"`/`"Unassigned"` placeholders and unconditional, origin-agnostic queue
> invalidation) are folded into T4/T5/T6/T11/T12; and every Implementation
> Plan Risk citation is checked against plan v2's own renumbering (v1's Risk
> 3 is v2's Risk 1; v1's Risk 4 is v2's Risk 3; v2 adds a new Risk 4 with its
> own test-surface requirement, folded into T4/T11 below). One physical file
> per artifact type is retained per this story's convention — v1's content
> is available in git history, not carried forward in this file.

**Track:** `frontend` (`docs/stories/US-5.5-agent-console-ui.md` front matter, line 7,
confirmed directly). Per `docs/workflow/stage-map.yaml`'s `IMPLEMENTATION` stage
(`skills_by_track.frontend`), this track dispatches exactly one execution skill,
`frontend-builder` ("frontend/ scaffold, api-client, store, routes, screens, **tests**") —
there is no separate backend layering sequence and no per-layer execution-skill split;
every row below names `frontend-builder` and bundles a file's paired `*.test.ts(x)` with it,
matching the convention `docs/plans/US-5.4-task-breakdown.md` already established.
`API_DESIGN`/`DB_DESIGN` are `NOT_APPLICABLE` for this Story (design review v2, re-derived
against spec v2 — confirmed neither area became, nor required, a design change from any of
the five OD resolutions) — no `docs/designs/api/US-5.5-*` or `docs/designs/database/US-5.5-*`
artifact exists to attribute any task to.

**Scaffold check:** `frontend/` already exists (shipped by US-5.1/US-5.2/US-5.3/US-5.4) — the
frontend ordering rule's "scaffold before everything" step is already satisfied, not skipped.

**No `store/`-layer task exists in this sequence.** The impact analysis and the plan both
confirm `frontend/src/store/authStore.tsx` and `decodeTokenScopes.ts` are unmodified — this
Story's `tickets:read`/`tickets:write` gating reads the same existing `scopes` mechanism
US-5.4 already wired. The frontend ordering rule's "`api/` and `store/` before `hooks/`" is
therefore satisfied vacuously on the `store/` side; only the `api/`-before-`hooks/` half is a
live constraint below.

**Layer attribution note:** `frontend/src/layouts/AppShell.tsx` has no dedicated row in
AGENTS.md §3's Frontend layer table; it is attributed to the `routes/ (guards + layout)` row
(T14), per that row's own "guards + layout" label — same attribution `docs/plans/
US-5.4-task-breakdown.md` used for the same file. `frontend/src/test/mswHandlers.ts` is
shared test infrastructure with no §3 layer of its own; it is sequenced as a prerequisite of
every hook/screen test that consumes it (T3).

**Ordering-rule floor, applied even where no import forces it.** Per `docs/plans/
US-5.4-task-breakdown.md`'s own precedent ("the rule is applied as a sequencing floor, not
skipped because no hook happens to need it yet"), no `routes/`- or `screens/`-layer task below
is sequenced ahead of the `hooks/` block, even where its own file has no code-level import that
requires it: T14 (`AppShell.tsx`, `routes/`) states `T4` as a floor dependency though its nav
link imports nothing from `hooks/`; T10 (`TicketDetailScreen.test.tsx`, `screens/`, fixture-only)
states `T1` as its floor (the earliest task in the sequence, since it touches no `hooks/` file
at all and its only real dependency is the `api/`-layer type change). The "form/validation task
before the screen that wires it in" half of the frontend ordering rule is vacuous here too — no
task in this Story extracts a separate form/validation file from a screen.

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | frontend-builder | `api/` | — | `frontend/src/api/types.ts` | `npm run type-check` clean; `grep -n "AgentTicketStateRead" frontend/src/api/types.ts` and diff review confirm `AgentTicketStateRead` is a distinct interface from `AgentTicketRead` (carries `assignee_id`/`status`/`updated_at` but never `subject`/`category`/`body`/`requester_id`) per Implementation Plan Risk 3 and `router.py` lines 108/136; confirms `ReplyRead.visibility: "public" \| "internal"` is added as a **required** field (Architectural Change 1's stated hard prerequisite for every other new `hooks/`/`screens/` file — not an optional cleanup) and `CreateReplyRequest.visibility` is optional |
| T2 | frontend-builder | `api/` | T1 | `frontend/src/api/supportApi.ts` | `npm run type-check` clean; `grep -n "listAgentTickets\|assignTicket\|unassignTicket\|resolveTicket" frontend/src/api/supportApi.ts` confirms all four new functions exist; diff review confirms `unassignTicket` uses the existing `httpDelete<T>` verb with no body and that no existing exported function's signature changes (esp. `replyToTicket`) |
| T3 | frontend-builder | test infra (`frontend/src/test/`) | T1, T2 | `frontend/src/test/mswHandlers.ts` | `npm run type-check` clean; diff review confirms new default handlers exist for `POST /support/tickets/:id/assign`, `DELETE /support/tickets/:id/assign` (both `AgentTicketStateRead`-shaped), and `POST /support/tickets/:id/resolve` (`TicketStateRead`, `status: "resolved"`) — none exist today per the impact analysis's grep; confirms the `GET /support/tickets/:id` default handler's reply fixtures now carry an explicit `visibility: "public"` value (not omitted); confirms the existing `GET /support/tickets` default handler is left as the customer shape, with agent-branch (`AgentTicketListResponse`) responses supplied only via per-test `server.use(...)` — no second conflicting default on the same URL |
| T4 | frontend-builder | `hooks/` | T2, T3 | `frontend/src/hooks/useAgentTickets.ts`, `frontend/src/hooks/useAgentTickets.test.ts` | `npx vitest run src/hooks/useAgentTickets.test.ts --coverage` covering: a `status`/`category`/`assignee_id` filter change produces a new query key and resets the cursor (FR-1/AG-AC1); the `me`/`none` presets (mutually exclusive) and a raw-UUID "specific agent" value (FR-1's Resolution-OD-2 input) are sent as the literal `assignee_id` string with **no client-side substitution or UUID validation** (confirmed against `service.py::list_agent_queue`); a malformed `assignee_id` value renders the server's `422` problem+json detail inline rather than being blocked client-side (Implementation Plan Risk 4 — the test surface it explicitly requires); "Load more" appends on a non-null `next_cursor`; `grep -RniE "from ['\"](\.\./)*screens/\|from ['\"](\.\./)*components/" frontend/src/hooks/useAgentTickets.ts` returns nothing |
| T5 | frontend-builder | `hooks/` | T2, T3, T4 | `frontend/src/hooks/useAssignTicket.ts`, `frontend/src/hooks/useAssignTicket.test.ts` | `npx vitest run src/hooks/useAssignTicket.test.ts --coverage` covering: assign-to-me and assign-to-another-agent (FR-2's raw-UUID input) both call `POST .../assign` and unconditionally invalidate `useAgentTickets.ts`'s query key — one `onSuccess` handler, regardless of whether the call originated from the queue screen or the detail screen (Architectural Change 8's queue-invalidation-on-a-detail-screen-originated-assign resolution); a test case exercises invalidation from both origins; writes the response's `assignee_id`/`status`/`updated_at` into any open detail screen's local assignee state (FR-6); a 409 (closed ticket) and 422 (assignee is not an agent) render their problem+json detail; diff review confirms `onSuccess` merges only `assignee_id`/`status`/`updated_at` into an existing cache entry, **never** spreads the `AgentTicketStateRead` response over a full `AgentTicketRead`-shaped object (Implementation Plan Risk 3); same import grep as T4 |
| T6 | frontend-builder | `hooks/` | T2, T3, T4 | `frontend/src/hooks/useUnassignTicket.ts`, `frontend/src/hooks/useUnassignTicket.test.ts` | `npx vitest run src/hooks/useUnassignTicket.test.ts --coverage` covering: `DELETE .../assign` unconditionally invalidates the queue query key regardless of call origin (Architectural Change 8, same one-`onSuccess`-handler shape as T5) and a 409 on a closed ticket renders its problem+json detail; same cache-merge diff-review constraint (Risk 3) and import grep as T5 |
| T7 | frontend-builder | `hooks/` | T2, T3 | `frontend/src/hooks/useResolveTicket.ts`, `frontend/src/hooks/useResolveTicket.test.ts` | `npx vitest run src/hooks/useResolveTicket.test.ts --coverage` covering: a successful resolve writes the returned `TicketStateRead` (status `"resolved"`) into `ticketDetailQueryKey(id)`'s cache, the same "mutation response is the new truth" pattern as `useCloseTicket.ts` (FR-5/AG-AC5), and a 409 on a closed ticket renders its problem+json detail; same import grep as T4 |
| T8 | frontend-builder | `hooks/` | T1 | `frontend/src/hooks/useReplyToTicket.ts`, `frontend/src/hooks/useReplyToTicket.test.ts` | `npx vitest run src/hooks/useReplyToTicket.test.ts --coverage` covering: a new case asserting a supplied `visibility` ("public" or "internal") is included in the request body (FR-4), **and** the existing customer-path cases (no `visibility` supplied) still omit the key entirely — proving Architectural Change 2's additive-optional-field approach leaves `TicketDetailScreen.tsx`'s request byte-for-byte unchanged; diff review confirms the doc comment is updated to scope "never send `visibility`" to the customer path specifically |
| T9 | frontend-builder | `hooks/` (fixture-only, no production change) | T1 | `frontend/src/hooks/useTicketDetail.test.ts` | `npx vitest run src/hooks/useTicketDetail.test.ts --coverage`; diff review confirms only test fixtures changed (each `ReplyRead`-shaped literal now carries an explicit `visibility` value) and `frontend/src/hooks/useTicketDetail.ts` itself has zero diff (`git diff --stat -- frontend/src/hooks/useTicketDetail.ts` empty) |
| T10 | frontend-builder | `screens/` (fixture-only, no production change) | T1 | `frontend/src/screens/TicketDetailScreen.test.tsx` | `npx vitest run src/screens/TicketDetailScreen.test.tsx --coverage`; diff review confirms only reply fixtures changed and `frontend/src/screens/TicketDetailScreen.tsx` itself has zero diff (`git diff --stat -- frontend/src/screens/TicketDetailScreen.tsx` empty), consistent with Architectural Change 6's decision not to touch this file |
| T11 | frontend-builder | `screens/` | T3, T4, T5, T6 | `frontend/src/screens/AgentTicketQueueScreen.tsx`, `frontend/src/screens/AgentTicketQueueScreen.test.tsx` | `npx vitest run src/screens/AgentTicketQueueScreen.test.tsx --coverage` covering FR-1/AG-AC1 (columns, oldest-updated-first, filters reset cursor, mutually-exclusive `me`/`none` presets, raw-UUID "specific agent" filter, "Load more", explicit empty-result state — `"No tickets match these filters."`), the assignee column's shortened/truncated-UUID rendering per FR-1/Resolution OD-1 (first 8 hex characters, the plan's own concrete choice) and its literal `"Unassigned"` text for a null `assignee_id` (Architectural Change 8); FR-2/AG-AC2's queue-side assertions (assign/unassign call shape, 409/422 rendering, a malformed raw-UUID filter's 422 rendering inline per Implementation Plan Risk 4); the navigation-state handoff on row click (`state: { assigneeId: row.assignee_id }`, Architectural Change 7); the `tickets:write`-absent read-only/disabled-controls case (FR-6/AG-AC6); axe a11y pass with the table's cells associated to column headers (Enforcement Matrix); `grep -RniE "from ['\"](\.\./)*api/\|fetch\(" frontend/src/screens/AgentTicketQueueScreen.tsx` returns nothing |
| T12 | frontend-builder | `screens/` | T3, T5, T6, T7, T8 | `frontend/src/screens/AgentTicketDetailScreen.tsx`, `frontend/src/screens/AgentTicketDetailScreen.test.tsx` | `npx vitest run src/screens/AgentTicketDetailScreen.test.tsx --coverage` covering FR-3/AG-AC3 (thread rendering, internal-note distinct style **and** literal "internal" text label — not colour alone, "Load older replies"; the header's navigation-state-handoff assignee display rendered per Resolution OD-1's truncation rule, its literal `"Unassigned"` text for a genuinely unassigned ticket, and its literal `"—"` placeholder with `aria-label="Assignee unknown"` for the unknown/stale case on direct-URL entry — three distinct facts per Architectural Change 8, never a shared blank/dash), FR-4/AG-AC4 (composer visibility defaults to `"public"` on every mount/re-open — including immediately after a prior internal submission — via `reset({ body: "", visibility: "public" })` on mutation success, the concrete fix for Implementation Plan Risk 2; ticket-detail invalidation on a public reply), FR-5/AG-AC5 (resolve success, client-side empty-note **and** whitespace-only-note (post-`trim()`) block, 409 on closed), FR-6/AG-AC6 (`describe.each`/`it.each` table-driven case over all five statuses × `tickets:write` present/absent, asserting exactly FR-6's offered-action set and every write control's `disabled` state, plus a detail-screen-originated assign/unassign asserting the queue query is also invalidated — Architectural Change 8), FR-7/AG-AC6 (single-button close/reopen per Resolution OD-5, no `reason` field, no confirmation step), FR-8/AG-AC7 (problem+json detail, 422 field-error mapping), FR-9/AG-AC8 (429 message + disabled submit + no auto-retry loop via `useRetryAfterCountdown` reused unchanged), FR-10/AG-AC9 (network/5xx retry-capable state), plain-text rendering (an HTML-bearing reply body renders escaped — no `dangerouslySetInnerHTML`), axe a11y pass; same import grep as T11 |
| T13 | frontend-builder | `routes/` | T11, T12 | `frontend/src/routes/AppRoutes.tsx`, `frontend/src/routes/AppRoutes.test.tsx` | `npx vitest run src/routes/AppRoutes.test.tsx --coverage` covering `/agent/tickets` and `/agent/tickets/:id` rendering their respective screens (FR-11) and the unauthenticated-redirect-to-`/login` case; `grep -RniE "from ['\"](\.\./)*api/" frontend/src/routes/AppRoutes.tsx` returns nothing; `git diff --stat -- frontend/src/routes/ProtectedRoute.tsx` shows no change (scope gating stays at the presentation layer only) |
| T14 | frontend-builder | `routes/` (guards + layout) | T4 (sequencing floor only — no code import requires it; see ordering-rule note above) | `frontend/src/layouts/AppShell.tsx`, `frontend/src/layouts/AppShell.test.tsx` | `npx vitest run src/layouts/AppShell.test.tsx --coverage`, asserting the new `tickets:read`-gated `/agent/tickets` nav entry (FR-11, one shared shell, no separate entry point/role switcher) appears/is absent per seeded `scopes`, following the existing `canReadUsers`/`canReadAudit` test pattern; `grep -RniE "from ['\"](\.\./)*api/" frontend/src/layouts/AppShell.tsx` returns nothing (must read `scopes` off the store only) |
| T15 | gate-enforcer | — | T1–T14 | — | `npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:coverage` (AGENTS.md §2 Frontend subsection's four load-bearing scripts) all green from `frontend/`; diff review against AGENTS.md §3's Frontend layer table (no `lint-imports` equivalent exists for this stack) |

**Parallel-eligible batches** (dependency-minimal, not the only valid execution order):
- T1 — no dependencies, first.
- T2 (needs T1) ∥ T9, T10 (fixture-only tasks that need only T1 — no code dependency on any
  `hooks/`/`screens/` task, held to T1 as their real, non-floor dependency).
- T3 (needs T1, T2).
- T4, T7, T8 — all reach their dependencies once T2/T3 (and, for T8, only T1) land; parallel to
  each other.
- T5, T6 — parallel to each other once T4 lands (both need the queue query key to invalidate).
- T14 reaches its stated floor (T4) in this same batch — it can run any time after T4, in
  parallel with T5/T6/T7/T8/T11/T12, since nothing in `AppShell.tsx` actually imports from
  `hooks/`.
- T11 (needs T4, T5, T6) ∥ T12 (needs T5, T6, T7, T8) — parallel to each other.
- T13 is the sole task gating on both new screens; T15 is the sequence's sole terminal task.
- Ordering-rule note: T8 (`useReplyToTicket.ts`) depends only on T1, not on T2/T3, because
  `supportApi.ts::replyToTicket`'s signature does not change (Architectural Change 2) and its
  own test suite exercises the mutation hook directly against MSW, not through a new API
  function.

## Resolved Decisions Consumed by This Sequence

`docs/decisions/US-5.5-open-decisions.md` (v2) records OD-1 through OD-5 as
`RESOLVED` by explicit human decision (2026-09-14), folded into
`docs/specifications/US-5.5-spec.md` v2's FR-1, FR-2, FR-3, FR-6, FR-7, and
FR-11 as stated requirement text — verified directly on disk for this
revision, not inferred from an upstream artifact's own citation of them. This
stage resolves no Open Decision itself (`implementation-planner`'s own
Prohibited: "do not resolve Open Decisions"); every task below implements a
resolution already settled upstream, cited by FR number rather than by "OD-n
interim default" phrasing:

- **OD-1** (shortened/truncated UUID display, no name-resolution call) — FR-1,
  FR-3; implemented in T11 (queue assignee column) and T12 (detail header).
- **OD-2** (raw-UUID text input for assign-target and the "specific agent"
  filter, no agent-directory endpoint) — FR-1, FR-2; implemented in T4, T5,
  T11.
- **OD-3** (navigation-state handoff of the assignee value from the queue row
  into the detail screen, updated from assign/unassign responses,
  unknown/stale on direct-URL entry) — FR-3, FR-6; implemented in T5, T6
  (response write into detail local state), T11 (handoff on row click), T12
  (rendering, including the unknown/stale `"—"` case).
- **OD-4** (one shared AppShell, `tickets:read`-gated `/agent/*` nav entry, no
  separate entry point or role switcher) — FR-11; implemented in T14 (nav
  entry) and T13 (route registration inside the existing protected group).
- **OD-5** (single action button, no `reason` field, no confirmation modal
  for close/reopen) — FR-7; implemented in T12.

Three further ambiguities specification review v2 raised over the *resolved*
text (none blocking, per impact analysis v2's Non-Blocking Finding) are
settled as concrete implementation detail by Implementation Plan
Architectural Change 8, and are cited by task above: the unknown/stale
assignee placeholder (`"—"`, `aria-label="Assignee unknown"`, T12), the
null-assignee placeholder (`"Unassigned"`, T11 and T12), and unconditional
(origin-agnostic) queue invalidation on assign/unassign (T5, T6, asserted
from both origins in T5's test and from the detail screen in T12's test).

**Implementation Plan Risk citations, checked against plan v2's own
numbering (renumbered from v1):**

- **Risk 1** (`ReplyRead.visibility` becoming a required field breaks two
  existing untyped-but-now-inconsistent fixture files) is the entire reason
  T9 and T10 exist as their own tasks rather than being folded into T1 —
  they touch different files (`hooks/`/`screens/` test suites) than T1
  (`api/` type definitions) and have no other task to attach to.
- **Risk 2** (React Hook Form `defaultValues` caching could leak a prior
  "internal" choice into the next composer open) is mitigated by the
  `reset({ body: "", visibility: "public" })` call T12 requires, with its own
  explicit test assertion (not just assumed from the default value).
- **Risk 3** (`AgentTicketStateRead` vs. `AgentTicketRead` field-shape
  confusion) is enforced as an explicit diff-review check on T1, T5, and T6,
  not left as an unverified caveat.
- **Risk 4** (the queue's `assignee_id` text input accepts free-form text
  with no client-side UUID shape validation, by design) requires the test
  suite to assert the 422-renders-inline path rather than a client-side
  block FR-1 never asks for — folded into T4's and T11's Verification
  Command above.
