---
artifact_type: specification_review
story: US-4.2
version: 6
status: DRAFT
created_at: "2026-09-04T20:00:00Z"
updated_at: "2026-09-05T09:45:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
supersedes: docs/reviews/specifications/US-4.2-spec-review.md (v5)
---

# Spec Review: Ticket Replies

**Original Story:** docs/stories/US-4.2-ticket-replies.md
**Spec Reviewed:** docs/specifications/US-4.2-spec.md (version 6)
**Story ID:** US-4.2
**Reviewed:** 2026-09-05
**Overall Verdict:** PASS

## Summary

Spec version 6 revises FR-2 and FR-6 to incorporate **OD-8's actual
resolution** (`docs/decisions/US-4.2-open-decisions.md` v3, human decision
supplied 2026-09-05): a customer reply on a `"resolved"` ticket is accepted
(`201`) and the ticket's status transitions to `"waiting_on_support"` —
reopening it, using the same target status FR-2's ordinary case already
produces. This replaces v5's "stays `"resolved"`" default, which
`DESIGN_REVIEW` v2 found had never actually been confirmed by a human
decision despite being treated as settled by the downstream designs. TR-AC6
is now genuinely **Covered**, not Partially Covered: the AC's own text ("a
`"resolved"` ticket behaves differently... reply reopens it") is satisfied
by FR-6 stating an actual reopening transition, rather than the story's own
unformalizable `US-4.3 TC-AC4` citation. The Out of Scope section is
correctly narrowed — it no longer excludes "reopening transitions" wholesale
while FR-2/FR-6 perform one; it now excludes only the auto-close job and
boundary constant (BR-017) this story does not build, which is consistent
rather than self-contradictory. No blocking issues remain.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| TR-AC1 | "Given a support agent with tickets:write and an open ticket When POST /v1/support/tickets/{id}/replies is called with {body, visibility: \"public\"} Then respond 201 with the created reply And the ticket's status becomes \"waiting_on_customer\" And first_response_at is stamped if this is the first public agent reply (a plain timestamp for later reporting — no SLA target is evaluated) And the requester is notified by email" | Covered | FR-1 | Unchanged from v5. |
| TR-AC2 | "Given the ticket's requester and a ticket in \"waiting_on_customer\" When POST /v1/support/tickets/{id}/replies is called with {body} Then respond 201 And the ticket's status becomes \"waiting_on_support\" And the assigned agent (or the queue, if unassigned) is notified" | Covered | FR-2 | Scoped exactly as the AC's own Given (`"waiting_on_customer"`); see Missing Edge Cases for the carried-forward, non-blocking question about statuses outside this AC's scope. |
| TR-AC3 | "Given an agent has added a reply with visibility \"internal\" When the requester calls GET /v1/support/tickets/{id} Then the internal reply is absent from the response entirely And it is absent from every notification email And when an agent calls the same endpoint, the internal reply IS returned, marked as internal And the exclusion holds even if the application layer forgets to filter, because a PostgreSQL Row-Level Security policy on ticket_replies hides visibility='internal' rows from any connection whose session context carries the customer role" | Covered | FR-3 | Unchanged from v5. |
| TR-AC4 | "Given customer A authenticated, and a ticket belonging to customer B When POST /v1/support/tickets/{id}/replies or GET /v1/support/tickets/{id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm the ticket id exists — unlike the self-scoped profile case in US-1.3 UP-AC7" | Covered | FR-4 | Unchanged from v5. |
| TR-AC5 | "Given the ticket's requester When POST /v1/support/tickets/{id}/replies is called with {visibility: \"internal\"} Then respond 403 with type \".../errors/insufficient-permission\" And no reply is created And visibility defaults to \"public\" when the field is omitted by a customer" | Covered | FR-5 | Unchanged from v5. |
| TR-AC6 | "Given a ticket whose status is \"closed\" When any actor calls POST /v1/support/tickets/{id}/replies Then respond 409 with type \".../errors/ticket-closed\" And the response points to creating a new ticket And a \"resolved\" ticket behaves differently — see US-4.3 TC-AC4 (reply reopens it)" | **Covered** (upgraded from Partially Covered in v3/v4/v5) | FR-6 | Closed-ticket clause covered directly. Agent-on-resolved clause covered per Resolution OD-5 (status unchanged). Customer-on-resolved clause — the AC's own "reply reopens it" text — is now covered directly per Resolution OD-8: `201`, status transitions to `"waiting_on_support"`. This is the first revision where FR-6 actually implements a reopening transition rather than declining to (v3/v4) or asserting one still pending confirmation (v5). |
| TR-AC7 | "Given an empty body or one exceeding 5000 characters When POST /v1/support/tickets/{id}/replies is called Then respond 422 with type \".../errors/validation-failed\"" | Covered | FR-7 | Unchanged from v5. |

## Contradictions

None found. v5's residual risk — FR-2/FR-6 asserting a "stays resolved" default that was not an actual human decision, which `DESIGN_REVIEW` v2 flagged as a design-level problem rather than a spec-review one (the spec text was internally consistent with itself; the risk was whether it matched what a human had actually decided) — is resolved: FR-2/FR-6 now state the human-decided resolution, cited to `docs/decisions/US-4.2-open-decisions.md` v3's `Resolution (2026-09-05T09:00:00Z, human, sbruhov@gmail.com)` line, not a working default.

Out of Scope's "reopening transitions" exclusion, which stood in direct tension with FR-6's assertion of a reopening transition since v3, is now correctly narrowed to exclude only the auto-close job and boundary constant, not the one transition this story performs. No remaining tension between Out of Scope and FR-2/FR-6.

## Scope Creep

None found. The BR-017 auto-close-job/boundary-constant note in Out of Scope and FR-2's "this story implements only this reply-side transition" sentence are both framing of what is *excluded*, not new in-scope behavior — they trace to the story's own citation of `US-4.3 TC-AC4` (which pulls in BR-017's full rule) and narrow it back down to what Resolution OD-8 actually decided, rather than adding anything new.

## Ambiguities

None found in the revised FR-2/FR-6 text. "Transitions to `"waiting_on_support"`" is a concrete, testable status value already established elsewhere in this same spec (FR-2's ordinary case), not a vague or underspecified term.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low, carried forward unchanged from v5's review] Does FR-2's status transition apply to a customer reply on a ticket that is not yet `"waiting_on_customer"` or `"resolved"`?** — FR-2 now states behavior for three specific statuses: `"waiting_on_customer"` (→ `"waiting_on_support"`) and `"resolved"` (→ `"waiting_on_support"`, per OD-8). TR-AC2's own Given is scoped to `"waiting_on_customer"`, so the story does not demand an answer for a customer reply on, say, an `"open"` ticket (before any agent reply) or one already `"waiting_on_support"`. Non-blocking — no AC requires this, and TR-AC2/TR-AC6 are fully Covered as scoped — but still worth a follow-up question before `service-and-router-builder` writes FR-2's status-gating branches completely.

## Verdict Rationale

PASS: every AC is Covered (TR-AC6 upgraded from Partially Covered), no
Contradictions or Scope Creep were found, and the one remaining observation
(FR-2's unaddressed non-`waiting_on_customer`/non-`resolved` statuses) is a
non-blocking question outside any AC's stated scope, unchanged in severity
from v5's review. The defect that forced `CHANGES_REQUIRED` at v3/v4, and the
distinct risk `DESIGN_REVIEW` v2 flagged at v5 (a design-level assertion that
a spec default had been human-confirmed when the record did not actually
show that), are both resolved in this revision: FR-2/FR-6 now state an
actual human decision, correctly cited, with Out of Scope narrowed to match.
