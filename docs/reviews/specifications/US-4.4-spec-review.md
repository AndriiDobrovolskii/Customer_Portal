---
artifact_type: specification_review
story: US-4.4
version: 1
status: APPROVED
created_at: "2026-09-07T12:00:00Z"
updated_at: "2026-09-07T16:00:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# Spec Review: Agent Ticket Queue & Assignment

**Original Story:** docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
**Spec Reviewed:** docs/specifications/US-4.4-spec.md (v1, DRAFT)
**Story ID:** US-4.4
**Reviewed:** 2026-09-07
**Overall Verdict:** PASS

## Summary

All 10 Acceptance Criteria (AQ-AC1–AQ-AC10) are Covered by a corresponding Functional Requirement, with no contradictions between the spec and the source story. The spec's four carried-forward Open Decisions (OD-1..OD-4) are handled correctly per this review's brief: each drafting default is explicitly labeled "not yet human-confirmed," traced to its Open Decision, and gated at `HUMAN_SPEC_APPROVAL` rather than silently treated as final. A handful of non-blocking gaps remain — most notably that the spec drops the story's concrete Data Model Notes (column definition, FK-delete semantics, both index shapes), leaving only a generic "MUST be index-backed" NFR for `db-designer` to work from.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| AQ-AC1 | "Given an agent holding tickets:read When GET /v1/support/tickets is called Then respond 200 with every non-closed ticket regardless of requester, ordered oldest-updated first And each item carries assignee_id And the response pages by cursor with no total count" | Covered | FR-1 | — |
| AQ-AC2 | "Given an agent holding tickets:read When GET /v1/support/tickets is called with status, category or assignee_id Then only matching tickets are returned And assignee_id=me resolves to the calling agent's own id And assignee_id=none returns only unassigned tickets And status=closed is the only way a closed ticket appears" | Covered | FR-2 | — |
| AQ-AC3 | "Given an agent holding tickets:write and a ticket with no assignee When POST /v1/support/tickets/{id}/assign is called with another agent's id Then respond 200 with assignee_id set And an audit entry is written (event=ticket_assigned, actor=the caller, target=the ticket) And re-assigning an already-assigned ticket replaces the assignee and audits the change" | Covered | FR-3 | See Missing Edge Cases — self-assignment (Assumption #5) is not restated as an explicit case. |
| AQ-AC4 | "Given a ticket with an assignee When DELETE /v1/support/tickets/{id}/assign is called by a tickets:write holder Then respond 200 with assignee_id null And an audit entry is written (event=ticket_unassigned)" | Covered | FR-4 | AC4's own text is generic ("a ticket with an assignee," no closed-status carve-out); FR-4 narrows the closed-ticket case to `409` per OD-3's unconfirmed default. The narrowing is explicitly flagged as not yet human-confirmed, so this is Covered rather than Partially Covered — but see Ambiguities. |
| AQ-AC5 | "Given a customer holding no tickets:* scope When GET /v1/support/tickets is called Then they receive only their own tickets, exactly as US-4.1 specified And no response field exposes assignee_id" | Covered | FR-5 | — |
| AQ-AC6 | "Given a customer holding no tickets:read When GET /v1/support/tickets is called with assignee_id or another agent's filter Then the filter is ignored and only their own tickets are returned — never another customer's Because the customer branch already ignores query parameters it does not declare; a 422 here would let an unauthenticated-for-the-queue caller probe which agent-only parameters exist, and the ownership filter is what actually protects the data" | Covered | FR-6 | — |
| AQ-AC7 | "Given a caller without tickets:write When POST or DELETE /v1/support/tickets/{id}/assign is called Then respond 404 for a customer (never confirming the ticket id exists, consistent with TR-AC4/TC-AC7) And 403 with type \".../errors/insufficient-permission\" for a tickets:read-only agent" | Covered | FR-7 | — |
| AQ-AC8 | "Given an assign request naming a user who holds no tickets:write When POST /v1/support/tickets/{id}/assign is called Then respond 422 with type \".../errors/validation-failed\" Because a ticket assigned to someone who cannot act on it is an invisible dead end" | Covered | FR-8 | FR-8 additionally extends the check to deactivated accounts per OD-4's unconfirmed default; the extension is explicitly flagged. |
| AQ-AC9 | "Given a ticket in status \"closed\" When POST /v1/support/tickets/{id}/assign is called Then respond 409 with type \".../errors/invalid-state-transition\"" | Covered | FR-9 | — |
| AQ-AC10 | "Given two agents assigning the same unassigned ticket simultaneously When both requests are processed Then exactly one wins via a conditional update scoped to the expected assignee_id And the loser receives 409, not a silent overwrite" | Covered | FR-10 | — |

## Ambiguities & Non-Verifiable Statements

- **[Medium] OD-3's closed-ticket unassign default stated without a competing test case to anchor it** — Spec says: "Whether this success path applies when the ticket is `"closed"`, ... is OD-3 — not resolved by any Acceptance Criterion. Per OD-3's recommended default, not yet human-confirmed: a closed ticket also returns `409` here." (FR-4). This is written clearly enough for `test-writer` to act on today (the default is unambiguous, and the "not yet confirmed" flag is explicit), so it does not block drafting. It is listed here rather than as a defect because a developer implementing strictly from FR-4's default, without re-reading OD-3, could miss that `HUMAN_SPEC_APPROVAL` may still flip this to a `200`/cleared-field behavior before `API_DESIGN` locks the contract.

## Contradictions With Original Story

None found.

## Scope Creep

None found. The two new response shapes (`AgentTicketRead`, `AgentTicketStateRead`) introduced in "Response Schemas" are not named verbatim in the story, but they are the direct, explicitly-flagged drafting default recommended by OD-1 (`docs/decisions/US-4.4-open-decisions.md`) to resolve a genuine tension the story itself creates (API Contract's "(agent shape)" wording vs. Assumption #7's customer-invisibility rule) — this is traceable elaboration of a logged Open Decision, not invented scope. The two additional Out of Scope bullets (no assignee-notification email, no status transition on assign) are likewise direct citations of the story's own Open Questions #1 and #2 and their stated default answers.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Medium] Self-assignment not restated as an explicit FR case** — Assumption #5 in the story states: "Any `tickets:write` holder may assign to themselves or to another agent; assigning to a non-agent is a 422." FR-3, mirroring AQ-AC3's own literal wording, only describes the request being "called with `{assignee_id}` naming another agent." Nothing in the spec explicitly states that assigning to oneself follows the same success path. No FR denies it either, so this does not contradict the story — but a developer building strictly from the Functional Requirements (without cross-referencing the story's Assumptions table) could reasonably ask whether self-assignment is a distinct, untested case. Does FR-3 implicitly cover self-assignment, or should it be stated explicitly per Assumption #5?

- **[Low] Query parameter `limit` is named in the story's API Contract but not mentioned by any FR** — Story says: "`?status=&category=&assignee_id=&cursor=&limit=`" (API Contract table). FR-1/FR-2 describe cursor pagination ("no total count") but never mention a caller-supplied `limit`/page-size parameter or its bounds. Is `limit` in scope for this story's FRs, or is its behavior assumed to be inherited unchanged from the existing cursor-pagination mechanism (and therefore intentionally not restated)?

- **[Low] Data Model Notes (concrete column/FK/index definitions) are not carried into the spec** — Story's Data Model Notes give a specific column definition (`tickets.assignee_id UUID NULL REFERENCES users(id)`, "nullable, no cascade delete (US-1.4's retention job owns erasure)") and two named index shapes (`(status, updated_at, id)`, `(assignee_id, updated_at, id)`). The spec's NFR section retains only the generic requirement that "The queue query MUST be index-backed for its default ordering and every supported filter." Per `stage-map.yaml`, neither `API_DESIGN` nor `DB_DESIGN` receives the `story` artifact directly — the specification is their sole carrier of story content. This does not block `SPEC_REVIEW` (column/FK/index design is `DB_DESIGN`'s stage responsibility, not `SPECIFICATION`'s), but flagging it here so `db-designer` is not left to re-derive the FK-delete semantics and index shapes the story already fixed.

## Verdict Rationale

PASS: every Acceptance Criterion is Covered by an explicit, traceable Functional Requirement, and no Contradiction was found between the spec and the source story. The Ambiguity and Missing Edge Case items above are non-blocking — they are clarifying questions and a completeness note for downstream design stages, not gaps in AC coverage or conflicts with the story. The spec's handling of its four carried-forward Open Decisions (OD-1 Critical; OD-2/OD-3/OD-4 Medium/Low) meets this review's bar: each drafted default is traced to its Open Decision, explicitly marked not yet human-confirmed, and none is silently treated as final.
