---
artifact_type: test_strategy
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-08T23:00:00Z"
updated_at: "2026-09-09T09:30:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.3-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.3-plan-review.md
    version: 2
supersedes: null
---

# Test Strategy: Support Tickets — Frontend (US-5.3)

## Track and binding context

`track: frontend` (`docs/stories/US-5.3-support-tickets-ui.md` front matter).
API/DB design are `NOT_APPLICABLE` for this Story — the spec's own API
Contract table (verified directly against `app/modules/support/router.py`
and `schemas.py`) is the reference contract, per this skill's Required
Context for this track.

**OD-1 through OD-6 are treated as firm architecture, not open questions,**
per `implementation_plan` v2's re-plan note: the human supplied binding
resolutions on 2026-09-08T21:00:00Z (`docs/workflow/history.jsonl`), recorded
in `implementation_plan` v2 and `task_breakdown` v2 (both consumed here).
`docs/decisions/US-5.3-open-decisions.md` (v1, DRAFT, OD-1..6 shown `OPEN`)
and the spec's own hedged FR-12 prose are stale relative to this resolution
and are **not** treated as blocking — this is recorded as a non-blocking
finding in the generation report, not a loop-back trigger, since neither
document is in this stage's authoritative input registry and the plan/task
breakdown that are in it already resolve the six items as delivered
architecture.

## Unit vs. integration split (`AGENTS.md` §5 Frontend subsection)

- **Unit** (`frontend/src/hooks/*.test.ts`, `frontend/src/api/httpClient.test.ts`,
  `frontend/src/components/apiErrorHelpers.test.ts`): a hook or pure function
  in isolation, MSW as the network boundary (never a hand-mocked `fetch`),
  no DOM beyond what a bare `renderHook` needs.
- **Integration** (`frontend/src/screens/*.test.tsx`): React Testing Library
  renders the real screen + hooks + store tree; MSW intercepts every network
  call with a handler shaped like the real backend contract (status, body,
  content-type — including the `Retry-After` header on a `429` and the
  `application/problem+json` content type on every `ProblemError`
  subclass, both confirmed directly against `app/modules/support/exceptions.py`
  and `app/core/problem_details.py`).

**No `vi.mock()` on the unit under test anywhere in this pass** — self-checked
by grep in the generation report. Every new file defines its own
`server.use(...)` overrides rather than depending on `frontend/src/test/mswHandlers.ts`'s
baseline (that file is `task_breakdown` v2 Task T5's own deliverable,
`frontend-builder`'s territory, not this stage's — same precedent as
`docs/evidence/US-5.2-test-generation-report.md`). `frontend/src/test/test-utils.tsx`
is **not** modified (`implementation_plan` v2 Risk 2 forbids it) —
`TicketDetailScreen.test.tsx` wraps `ui` in its own local
`<Routes><Route path="/tickets/:id" element={ui} /></Routes>` to supply the
`useParams<{id}>()` this Story's first URL-param screen needs.

## Fixtures and collaborator-shape decisions this pass had to fix

No design doc exists on this track to fix an internal hook signature or a
component's prop/DOM shape beyond `implementation_plan` v2's prose. To write
concrete, executable assertions, this pass fixes the following (flagged here,
per the `US-5.2` precedent, as decisions for `frontend-builder`/
`reconciliation-reviewer` to check the shipped shape against — not resolved
Open Decisions):

1. **`api/supportApi.ts`'s six function signatures** are taken verbatim from
   `implementation_plan` v2 Architectural Change 3 (`listTickets`,
   `createTicket`, `getTicketDetail`, `replyToTicket`, `closeTicket`,
   `reopenTicket`) — not this pass's own invention, but recorded here since
   every hook test's mocked collaborator boundary is the MSW-intercepted
   HTTP call, not this function layer directly.
2. **`api/types.ts` DTO field lists** mirror `app/modules/support/schemas.py`
   verbatim (`TicketRead`, `TicketListResponse`, `CreateTicketRequest`,
   `TicketDetailRead`, `ReplyRead`, `ReplyThreadPage`, `CreateReplyRequest`,
   `TicketStateRead`, `CloseTicketRequest`, `ReopenTicketRequest`), confirmed
   directly against the backend file for this pass. `status`/`author_kind`/
   `visibility` stay plain `string`-shaped per the spec's "render an
   unrecognized status verbatim" instruction; `category` is plain `string`
   (OD-2).
3. **`useTicketDetail.ts`'s exact return shape**: `{ ticketQuery, repliesQuery }`
   — `ticketQuery` a `useQuery` on `ticketDetailQueryKey(id)` wrapping
   `getTicketDetail`'s first page (header fields + first replies page),
   `repliesQuery` a **sibling** `useInfiniteQuery` on
   `ticketRepliesQueryKey(id)` re-fetching `replies` pages independently via
   the same endpoint with an explicit `cursor`. This means the thread's first
   page is fetched once by each query the first time both are consumed — an
   accepted trade-off of two independently-invalidatable caches per
   `implementation_plan` v2's explicit query-key-prefix rationale (Change 5),
   not a defect.
4. **`useCreateTicket.ts`'s key lifecycle** is implemented as a `useRef`-held
   `{ key, lastPayload }` pair inside the hook closure: a new
   `crypto.randomUUID()` is minted whenever no key exists yet, or the
   submitted `{subject, body, category}` differs by strict equality from the
   previous attempt's; otherwise the held key is reused. This is OD-6's
   binding rule translated into the only mechanism that survives a
   `useMutation` call without external state (`implementation_plan` v2
   Architectural Change 8).
5. **`useReplyToTicket`/`useCloseTicket`/`useReopenTicket` accept `ticketId`
   as a hook argument** (not part of the mutation payload) so their
   `onSuccess` can close over the right query keys — this pass's tests
   construct them as `useReplyToTicket(ticketId)` etc.
6. **`useRetryAfterCountdown(retryAfterSeconds: number | undefined)`** returns
   `{ secondsRemaining: number; isBlocked: boolean }`, reinitializing and
   restarting its interval whenever the input value changes (a new mutation
   error arrives), per `implementation_plan` v2 Architectural Change 5's own
   description.
7. **Field labels / control names** (no design doc fixes UI copy): "Status"
   (list filter `<select>`), "Load more" / "Load older replies" (buttons),
   "New ticket" (empty-state CTA and nav-adjacent create link), "Subject" /
   "Body" / "Category" (create form), "Post reply" (reply composer submit),
   "Close ticket" / "Reopen" (detail screen actions), "First response"
   (OD-4's label for `first_response_at`). Query matchers use case-insensitive
   regexes loose enough to tolerate minor copy differences while still
   pinning presence and accessible-name pattern, per `US-5.2`'s documented
   matcher policy.
8. **`category` renders as `<input maxLength={50}>`, not `<select>`** (OD-2) —
   `NewTicketScreen.test.tsx` asserts the element's tag name directly.
9. **429 message copy** is asserted only as "names when the customer may
   retry" via a loose regex (`/try again in|retry in/i` plus the numeric
   seconds value), not a pinned full sentence, since `implementation_plan`
   fixes no exact copy for `useRetryAfterCountdown`'s consumer message.
10. **`offeredActionsForStatus` must be exported from `TicketDetailScreen.tsx`.**
    `implementation_plan` v2 Change 6 places this pure function inside the
    screen module itself (not a separate `hooks/`/pure-function file), but
    this pass's own Unit-vs-integration split (above) and `task_breakdown` v2
    T15's verification command both test it directly by name. Without an
    explicit named export, `screens/TicketDetailScreen.test.tsx`'s
    `import { TicketDetailScreen, offeredActionsForStatus } from
    "./TicketDetailScreen"` fails at module-resolution — a collaborator-shape
    decision `frontend-builder` must honor, exactly like the nine above, not
    a resolved Open Decision.

## Statement-count ceiling

Not applicable — `AGENTS.md` §5's statement-count ceiling is a backend/list
-endpoint concern (SQL statement counting against a real DB). This track's
list/nested-data equivalent (TK-AC1/TK-AC5's pagination) is instead proven by
asserting the exact MSW-observed request count and cursor values per fetched
page (e.g. "Load more" issues exactly one additional `GET` carrying the
previous page's `next_cursor`), which is this track's analogous regression
guard against an accidental N-refetch-per-render bug.

## Coverage floor

85% via `test:coverage`, CI-enforced (`AGENTS.md` §5/§6 Frontend subsection).
Not measured by this stage — no implementation exists yet for the new files
to run against (RED state, see the generation report). Enforced at
`QUALITY_GATE`/Task T20, per `task_breakdown` v2.

## Known gaps this pass records rather than papers over

- **NFR "no ticket body / reply body / `Idempotency-Key` in the browser
  console in production builds"** is a build/grep check
  (`frontend-builder`'s self-check + `SECURITY_REVIEW`), not a Vitest-testable
  assertion — no test in this pass invents a `console.log` spy for it.
- **NFR "responsive ~375px through desktop"** is not Vitest-testable without
  a visual/viewport-emulation tool this project does not use — not asserted
  here.
- **Reopen's 7-day window (OD-3)** is deliberately *not* tested as a
  client-side computation, because none exists by binding resolution — the
  test suite instead asserts the 409 is rendered and the button stays
  clickable, and a grep in the generation report confirms no date/window
  arithmetic was introduced.
