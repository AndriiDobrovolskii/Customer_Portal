---
artifact_type: open_decisions
story: US-4.4
version: 1
status: APPROVED
created_at: "2026-09-07T00:00:00Z"
updated_at: "2026-09-07T17:30:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
supersedes: null
---

# Open Decisions: US-4.4 Agent Ticket Queue & Assignment

**Story:** `docs/stories/US-4.4-agent-ticket-queue-and-assignment.md` (`AQ-AC` prefix)
**Logged:** 2026-09-07 (v1)

## OD-1 (Critical) — Assign/unassign responses reuse `TicketStateRead`, which is also returned to customers by `/resolve`/`/close`/`/reopen`

**Question:** The story's API Contract table states `POST`/`DELETE .../assign` return `200 TicketStateRead (agent shape)`. But `TicketStateRead` (`app/modules/support/schemas.py`) is the *same* schema already returned by `/resolve`, `/close`, and `/reopen` (US-4.3), and `/close`/`/reopen` are reachable by the ticket's **requester** (a customer), not just an agent — `close_ticket`/`reopen_ticket` in `app/modules/support/router.py` accept either actor kind. If `assignee_id` is added to the existing `TicketStateRead` class to satisfy this story's "agent shape," a customer closing or reopening their own ticket would receive `assignee_id` in the response body, directly violating this story's own Assumption #7 / Non-Functional Requirement ("`assignee_id` MUST NOT appear on any customer-facing response shape"). The same tension applies to `GET /v1/support/tickets`'s per-item shape: the customer branch and agent branch of that endpoint currently share one `TicketRead` class.

**Why it can't be inferred:** The story asserts two things that are only simultaneously true if the response schemas for assign/unassign (and the queue) are *not* literally the shared `TicketRead`/`TicketStateRead` classes: (1) "`assignee_id` MUST NOT appear on any customer-facing response shape" (Assumption #7, NFR), and (2) assign/unassign return "`TicketStateRead` (agent shape)" (API Contract) — the parenthetical "(agent shape)" implies a variant, but no such variant is named anywhere in Data Model Notes or In Scope. Out of Scope explicitly excludes "Any change to the resolve/close/reopen state machine (US-4.3)," which cuts against silently widening the shared `TicketStateRead` return type used by those three existing endpoints.

**Impact if left unresolved:** `openapi-designer` cannot write a single `TicketStateRead`/`TicketRead` schema definition that satisfies both the customer-invisibility rule and the "agent shape" language without a named resolution. `schema-builder` would otherwise have to guess between mutating a schema three other endpoints already depend on (regression risk to US-4.3's shipped contract) versus introducing new schema names this story never proposes.

**Recommendation:** Introduce two new, distinct response schemas scoped to this story's own endpoints only — e.g. `AgentTicketRead` (queue item / `GET /v1/support/tickets` agent branch, carrying `assignee_id`) and `AgentTicketStateRead` (assign/unassign response, carrying `assignee_id`) — and leave `TicketRead`/`TicketStateRead` exactly as US-4.1/US-4.3 shipped them. This satisfies the API Contract's "(agent shape)" language, keeps Assumption #7 enforced by type separation rather than per-caller runtime branching, and touches nothing on `/resolve`, `/close`, `/reopen`'s existing contract. Confirm before `SPECIFICATION`/`API_DESIGN` commit to a schema shape.

**Resolution:** APPROVED. "Create new distinct schemas (AgentTicketRead and AgentTicketStateRead) for the agent-facing endpoints. Do not modify the existing shared TicketRead/TicketStateRead schemas." — decided_by: sbruhov@gmail.com — 2026-09-07T17:25:48Z

## OD-2 (Medium) — Should `GET /v1/support/tickets/{id}` (ticket detail) also expose `assignee_id` for an agent caller?

**Question:** In Scope states "`assignee_id` exposed on the agent-facing read shapes **only**" (plural), but the API Contract table only lists `GET /v1/support/tickets` and the two `/assign` endpoints — it does not mention `GET /{id}` (`TicketDetailRead`, US-4.2's existing ticket-detail endpoint, which is also actor-kind-aware via `resolve_actor_kind`/RLS). Is `TicketDetailRead`'s agent branch expected to gain `assignee_id` in this story, or is "agent-facing read shapes" limited to the two shapes the API Contract table actually names?

**Why it can't be inferred:** The plural wording in In Scope and the singular, non-exhaustive API Contract table point in different directions; no Acceptance Criterion exercises `GET /{id}`'s response body for `assignee_id`.

**Impact if left unresolved:** `openapi-designer` cannot decide whether `TicketDetailRead` needs an agent-branch variant in this story or is untouched (deferred). `test-writer` cannot write an AC-traceable test for `GET /{id}` exposing (or not exposing) `assignee_id`.

**Recommendation:** Treat the API Contract table as authoritative (it is the story's own normative, itemized list of endpoints this story touches) — do not extend `GET /{id}`/`TicketDetailRead` in this story. Confirm before `SPECIFICATION`.

**Resolution:** APPROVED. "Do not extend GET /v1/support/tickets/{id} with assignee_id in this story. Stick strictly to the endpoints explicitly listed in the API Contract table." — decided_by: sbruhov@gmail.com — 2026-09-07T17:25:48Z

## OD-3 (Medium) — Unassign (`DELETE .../assign`) on a `closed` ticket: blocked or allowed?

**Question:** AQ-AC9 states `POST .../assign` on a `"closed"` ticket returns `409 invalid-state-transition`. AQ-AC4 (unassign) states no such restriction and is written against "a ticket with an assignee" generically. Does `DELETE .../assign` on a closed ticket also `409`, for symmetry with assign and consistency with `closed` being terminal elsewhere in this module (US-4.3), or does it succeed (`200`, `assignee_id` cleared) since nulling a field on an already-terminal ticket has no operational consequence the way re-assigning it would?

**Why it can't be inferred:** No AC exercises this combination; the story's own "closed tickets are terminal" framing (US-4.3, CHECK constraints on `status`/`closed_at`/`closed_by`) does not extend to `assignee_id`, which this story introduces and which those constraints don't reference.

**Impact if left unresolved:** `test-writer` cannot write a passing- vs. failing-case test for unassign-on-closed. `service-and-router-builder` cannot implement the conditional update's WHERE clause without knowing whether `status = 'closed'` is an exclusion.

**Recommendation:** Mirror AQ-AC9 for symmetry: `DELETE .../assign` on a `"closed"` ticket also returns `409 invalid-state-transition`. Confirm before `SPECIFICATION`.

**Resolution:** APPROVED. "DELETE .../assign on a closed ticket must return 409 invalid-state-transition (symmetric with POST)." — decided_by: sbruhov@gmail.com — 2026-09-07T17:25:48Z

## OD-4 (Low) — Does AQ-AC8's "must be an agent" check also reject a *deactivated* agent account?

**Question:** AQ-AC8 rejects assigning to "a user who holds no `tickets:write`" with `422`, rationale: "a ticket assigned to someone who cannot act on it is an invisible dead end." A deactivated account cannot log in at all (BR-006) and so cannot act on a ticket either, even if its role grants still nominally include `tickets:write`. Should the assign-target check also verify the target account's `status` is active, or does AQ-AC8's literal wording ("holds no tickets:write") limit the check to role/scope only?

**Why it can't be inferred:** AQ-AC8's stated rationale would support checking account status too, but its Given/When/Then text names only the scope condition; `docs/product/business-rules.md` has no rule tying assignment validity to account status (this is a new interaction between BR-006 and this story's own new rule).

**Impact if left unresolved:** `test-writer` cannot write a deactivated-assignee test case without knowing whether it belongs under AQ-AC8's `422` or is out of scope. Minor in isolation, but the same `422` error type is used either way, so this only affects test coverage, not the API contract.

**Recommendation:** Extend the check to also reject a deactivated target account with the same `422 validation-failed`, consistent with AQ-AC8's own stated rationale. Low stakes; does not block drafting — confirm at `HUMAN_SPEC_APPROVAL` alongside the others.

**Resolution:** APPROVED. "Assigning a ticket to a deactivated user account must be rejected with 422 validation-failed." — decided_by: sbruhov@gmail.com — 2026-09-07T17:25:48Z

## Carried forward, non-blocking

- **Story's own Open Question 1** (does assigning transition ticket status?) — resolved by direct citation to the story's own default ("no — assignment is orthogonal to the US-4.3 state machine"), consistent with this story's Out of Scope entry excluding any resolve/close/reopen state-machine change. Not logged as an Open Decision.
- **Story's own Open Question 3** (should US-4.3 TC-AC4's reopen-notification now target the assignee, since `assignee_id` exists?) — resolved by citation: this story's own Out of Scope list excludes "Any change to the resolve/close/reopen state machine (US-4.3)," and `docs/specifications/US-4.3-spec.md` FR-4/OD-2 already fixed the reopen-notification recipient as the shared support-queue address. Not logged as an Open Decision; the notification path is unchanged by this story.
- **Story's own Open Question 4** (US-4.3 "reopened" vs. shipped "waiting_on_support" drift) — the story explicitly states this is "out of scope here either way" and that it uses the shipped five statuses. No action needed from this story.
- **Assignee holding `tickets:write` via the `admin` role, not just `support_agent`.** Not an Open Decision — BR-010 authorizes on permission scope, never role name, and the story text itself grounds "agent" in `tickets:write`, which `admin` also holds. An admin is therefore a valid assignment target.
- **Unknown/non-existent `assignee_id` on assign.** Not an Open Decision — a target user id that does not exist trivially "holds no `tickets:write`" and falls into AQ-AC8's existing `422` branch without a separate rule.

---

## Verdict input

All four Open Decisions (OD-1 through OD-4) have been reviewed and confirmed
by the human stakeholder (sbruhov@gmail.com), each exactly as recommended
above: OD-1 (new distinct `AgentTicketRead`/`AgentTicketStateRead` schemas,
shared `TicketRead`/`TicketStateRead` left untouched), OD-2 (do not extend
`GET /v1/support/tickets/{id}` with `assignee_id`; the API Contract table is
authoritative), OD-3 (`DELETE .../assign` on a `"closed"` ticket returns `409
invalid-state-transition`, symmetric with `POST`), and OD-4 (assigning to a
deactivated user account is rejected with `422 validation-failed`). See each
Open Decision's **Resolution** line above for the verbatim confirmation and
timestamp. None of these resolutions require any change to already-produced
downstream artifacts — the specification, API/DB designs, implementation
plan, and test matrix already encode these exact adopted defaults.
