# Spec Review: Ticket Replies

**Original Story:** docs/backlog/US-4.2-ticket-replies.md
**Spec Reviewed:** docs/specifications/US-015-ticket-replies-spec.md
**Story ID:** US-015 (source story numbered US-4.2)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All seven Acceptance Criteria in the source story (TR-AC1–TR-AC7) are covered by the spec's Functional Requirements (FR-1 through FR-7), with no contradictions found between the two documents and no scope creep — every Functional and Non-Functional Requirement traces to an AC, the Data Model Notes, or the Assumptions & Defaults table. The spec is disciplined about not inventing answers where the story is silent: it correctly raises the rate-limit-exceeded response, `attachment_ids` validation, GET-endpoint authorization detail, agent-omitted `visibility` default, and the untraceable "No HTML rendering" Enforcement Matrix row as Open Questions rather than guessing. The one notable gap is that the story's NFR explicitly states the GET thread endpoint is "paginated at 50," but neither an FR nor an Open Question addresses the pagination interface (query parameters, response shape) needed to request replies beyond the first page — an omission of the same kind the spec correctly caught elsewhere.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| TR-AC1 | "Given a support agent with tickets:write and an open ticket When POST /v1/support/tickets/{id}/replies is called with {body, visibility: \"public\"} Then respond 201 with the created reply And the ticket's status becomes \"waiting_on_customer\" And first_response_at is stamped if this is the first public agent reply (a plain timestamp for later reporting — no SLA target is evaluated) And the requester is notified by email" | Covered | FR-1 | — |
| TR-AC2 | "Given the ticket's requester and a ticket in \"waiting_on_customer\" When POST /v1/support/tickets/{id}/replies is called with {body} Then respond 201 And the ticket's status becomes \"waiting_on_support\" And the assigned agent (or the queue, if unassigned) is notified" | Covered | FR-2 | See Ambiguities — notification channel is unspecified in both story and spec. |
| TR-AC3 | "Given an agent has added a reply with visibility \"internal\" When the requester calls GET /v1/support/tickets/{id} Then the internal reply is absent from the response entirely And it is absent from every notification email And when an agent calls the same endpoint, the internal reply IS returned, marked as internal And the exclusion holds even if the application layer forgets to filter, because a PostgreSQL Row-Level Security policy on ticket_replies hides visibility='internal' rows from any connection whose session context carries the customer role" | Covered | FR-3 | — |
| TR-AC4 | "Given customer A authenticated, and a ticket belonging to customer B When POST /v1/support/tickets/{id}/replies or GET /v1/support/tickets/{id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm the ticket id exists — unlike the self-scoped profile case in US-1.3 UP-AC7" | Covered | FR-4 | — |
| TR-AC5 | "Given the ticket's requester When POST /v1/support/tickets/{id}/replies is called with {visibility: \"internal\"} Then respond 403 with type \".../errors/insufficient-permission\" And no reply is created And visibility defaults to \"public\" when the field is omitted by a customer" | Covered | FR-5 | — |
| TR-AC6 | "Given a ticket whose status is \"closed\" When any actor calls POST /v1/support/tickets/{id}/replies Then respond 409 with type \".../errors/ticket-closed\" And the response points to creating a new ticket And a \"resolved\" ticket behaves differently — see US-4.3 TC-AC4 (reply reopens it)" | Covered | FR-6 | — |
| TR-AC7 | "Given an empty body or one exceeding 5000 characters When POST /v1/support/tickets/{id}/replies is called Then respond 422 with type \".../errors/validation-failed\"" | Covered | FR-7 | — |

## Ambiguities & Non-Verifiable Statements

- **[Low] Notification channel unspecified for customer→agent notification** — Spec says: "notifies the assigned agent (or the queue, if unassigned)" (FR-2), with no delivery channel stated, unlike FR-1 which explicitly says "notifies the requester by email." A developer cannot determine from FR-2 alone whether this reuses the same email pathway or a different mechanism (e.g., in-app/queue notification). This wording is carried over verbatim from the story's own TR-AC2 ("the assigned agent (or the queue, if unassigned) is notified"), so it is not a fidelity defect in the spec, but it remains a non-verifiable statement as written.

- **[Low] "points the caller to creating a new ticket" left unspecified** — Spec says: "the response points the caller to creating a new ticket" (FR-6). No field, link, or exact mechanism is defined for how the response conveys this; the story's separate Error Envelope example shows one possible `detail` string, but that example is not tied back into FR-6's text and the spec does not reproduce or reference it. A QA engineer could not write an assertion against "points to" without a more concrete contract.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Medium] GET thread pagination interface unaddressed** — The spec's Non-Functional Requirements state "Thread fetch performance: p95 ≤ 300 ms for 100 replies, paginated at 50" (mirrored from the story's own NFR section), which implies `GET /v1/support/tickets/{id}` supports pagination. Neither FR-3 (which defines the GET behavior for visibility filtering) nor any other FR specifies the pagination interface — query parameters, cursor/page semantics, or response shape — needed to retrieve replies beyond the first 50. This is the same category of gap the spec correctly caught and surfaced as an Open Question elsewhere (e.g., `attachment_ids` validation, GET-endpoint authorization detail, rate-limit-exceeded response), but this one was not raised. Since no Acceptance Criterion in the story defines pagination behavior either, it is unclear whether this is a genuine story gap the spec should flag as an Open Question, or considered out of this story's scope — but it is inconsistent that adjacent, equally-unaddressed gaps were flagged and this one was not.

## Verdict Rationale

Pass with Issues: every Acceptance Criterion is Covered and no Contradictions or Scope Creep were found, so the spec is not blocked from a coverage or accuracy standpoint. One Medium-severity omission — the unaddressed GET thread pagination interface, implied by the spec's own performance NFR but never specified as an FR or logged as an Open Question — should be resolved or explicitly deferred before implementation begins, consistent with how the spec already handled its other identified gaps. The two Low-severity ambiguities (notification channel, "points to creating a new ticket") originate in the source story and are not spec-introduced defects.
