---
artifact_type: specification_review
story: US-4.3
version: 3
status: ARCHIVED
created_at: "2026-09-06T08:00:00Z"
updated_at: "2026-09-06T10:00:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
supersedes: 2
---

# Spec Review: Ticket Resolution

**Original Story:** docs/stories/US-4.3-ticket-resolution.md
**Spec Reviewed:** docs/specifications/US-4.3-spec.md (v2, revised 2026-09-06)
**Story ID:** US-4.3
**Reviewed:** 2026-09-06
**Overall Verdict:** PASS

## Summary

This review supersedes v2 of this report, which reviewed spec v1 before `HUMAN_SPEC_APPROVAL` rejected it on 2026-09-06T08:15:00Z. Spec v2 applies the human's exact resolutions for OD-1 through OD-8 (`docs/decisions/US-4.3-open-decisions.md`, v1) and, in doing so, deliberately departs from several literal statements in the source story — most notably FR-4/FR-5 targeting `"waiting_on_support"` instead of the story's literal `"reopened"` (OD-1), and FR-4's notification going to the shared support-queue address instead of "the previously assigned agent" (OD-2). Every one of these departures is explicitly cited back to its resolved Open Decision and the 2026-09-06T08:15:00Z human decision in the spec's own Revision Note and each FR's "Derived from" line, so they are treated here as authorized corrections rather than contradictions: the spec accurately reflects what the human directed, which is this review's actual fidelity bar at this stage, not literal agreement with text the human has already overridden. All 9 Acceptance Criteria are covered (with two AC's scope faithfully corrected per OD-5/OD-6, also human-confirmed), no unauthorized contradictions or scope creep were found, and the one ambiguity the prior review carried forward (the strict/inclusive boundary assignment) is now fully resolved (OD-4). One new, inherited gap is noted below: the FRs do not state the response for a `/resolve` or `/reopen` call on a ticket that is `"resolved"` but outside `/reopen`'s 7-day window and not yet auto-closed — this is not Critical or Major and does not block progression.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| TC-AC1 | "Given an agent with tickets:write and a ticket in an open state When POST /v1/support/tickets/{id}/resolve is called with {resolution_note} Then respond 200 with status \"resolved\" and resolved_at set And resolved_at is the only timing field written; no SLA target is evaluated And the requester is emailed the resolution note plus a link to reopen And a ticket_audit_log entry is written (event=ticket_resolved, actor=agent:{id})" | Covered | FR-1 | Scope widened from literal "open state" to all three active non-closed states, per OD-5 (human-confirmed 2026-09-06T08:15:00Z), consistent with the story's own normative State Machine table. Reopen-link target resolved per OD-8. |
| TC-AC2 | "Given the ticket's requester and a ticket in any non-closed state When POST /v1/support/tickets/{id}/close is called Then respond 200 with status \"closed\" and closed_at set And the audit entry records actor=self" | Covered | FR-2 | Requester path matches verbatim; FR-2 additionally covers the agent-close path per OD-6/OD-7 (human-confirmed), which the AC is silent on rather than contradicts. |
| TC-AC3 | "Given a ticket resolved more than 7 days ago with no reply since When the scheduled auto-close job runs Then status becomes \"closed\" and closed_at is set And a ticket_audit_log entry is written (event=ticket_auto_closed, actor=system) And the job's update is conditioned on the ticket still being resolved with the same resolved_at, so a reply committed first makes the job a no-op" | Covered | FR-3 | Faithful, complete restatement; boundary comparison (strict `>`) resolved per OD-4. |
| TC-AC4 | "Given a ticket resolved less than 7 days ago When the requester posts a reply (US-4.2) Then status becomes \"reopened\" and resolved_at is cleared And the previously assigned agent is notified" | Covered | FR-4 | FR-4 targets `"waiting_on_support"`, not the AC's literal `"reopened"`, and notifies the shared support-queue address, not "the previously assigned agent" — both are the human-confirmed resolutions of OD-1 and OD-2 (2026-09-06T08:15:00Z), correcting the story's own text to match already-shipped US-4.2 behavior. Traced explicitly in FR-4's "Derived from" line and the spec's Revision Note; not an unauthorized deviation. |
| TC-AC5 | "Given a ticket that is already \"closed\" When POST /v1/support/tickets/{id}/resolve or /reopen is called Then respond 409 with type \".../errors/invalid-state-transition\" And the problem+json body lists the transitions actually permitted from the current state" | Covered | FR-6, Response Schemas | `allowed_events` field reproduced verbatim in the Response Schemas section. |
| TC-AC6 | "Given the ticket's requester, who does not hold tickets:write When POST /v1/support/tickets/{id}/resolve is called Then respond 403 with type \".../errors/insufficient-permission\" Because a customer may close their ticket (TC-AC2) but only an agent may declare it resolved" | Covered | FR-7 | Faithful, complete restatement. |
| TC-AC7 | "Given customer A and a ticket belonging to customer B When any of /resolve, /close or /reopen is called Then respond 404 with type \".../errors/not-found\"   # consistent with TR-AC4" | Covered | FR-8 | Faithful restatement; the stray `TR-AC4` cross-reference is correctly dropped. |
| TC-AC8 | "Given two agents resolving the same ticket simultaneously When both requests are processed Then exactly one succeeds; the transition is a conditional update scoped to the expected current status And the loser receives 409, not a silent overwrite of the first agent's resolution_note" | Covered | FR-9 | Faithful, complete restatement. |
| TC-AC9 | "Given a resolve request with an empty or absent resolution_note When POST /v1/support/tickets/{id}/resolve is called Then respond 422 with type \".../errors/validation-failed\" Because the note is what the customer receives and what the next agent reads" | Covered | FR-10 | Faithful, complete restatement. |

## Contradictions With Original Story

None found. FR-4/FR-5's `"waiting_on_support"` target and FR-4's support-queue notification recipient depart from TC-AC4's literal wording, but both departures are explicit, human-confirmed resolutions of OD-1 and OD-2 recorded at `HUMAN_SPEC_APPROVAL` (2026-09-06T08:15:00Z) and cited by name in the spec — see the TC-AC4 row above. Treating a directed, traceable correction to the story's own text as a reviewable "contradiction" would be inconsistent with this harness's Open-Decision-resolution mechanism, which exists precisely to let a human override story text that conflicts with already-shipped behavior.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Response for `/resolve` or `/reopen` on a `"resolved"` ticket outside `/reopen`'s window but not yet auto-closed is unstated** — FR-1 permits `/resolve` only from `open`, `waiting_on_support`, or `waiting_on_customer` (excluding `resolved`), and FR-5 permits `/reopen` only when `now - resolved_at <= 7 days`. Neither FR states the response when a ticket is `"resolved"` and past that window but the auto-close job (FR-3) hasn't yet run — this transitional case matches neither a success path nor FR-6's 409, which is scoped only to a ticket "that is already `closed`." TC-AC5's phrasing ("lists the transitions actually permitted from the current state") suggests this generalizes to any illegal transition, but neither the source story nor the spec confirms it does. This ambiguity is inherited from the source story's own TC-AC5 wording, not introduced by the spec rewrite, and is narrow enough (a timing window between job runs) that it does not block implementation planning.

## Verdict Rationale

PASS: AC coverage is complete (9/9 Covered), no unauthorized contradictions or scope creep were found, and the single carried-forward ambiguity from the prior review (strict/inclusive boundary assignment) is now fully resolved via OD-4. The FR-4/FR-5 departures from TC-AC4's literal text are traceable, human-confirmed corrections (OD-1, OD-2), not spec defects. The one new finding (resolved-but-expired transitional state) is Low severity, inherited from the source, and does not block progression to `HUMAN_SPEC_APPROVAL`.
