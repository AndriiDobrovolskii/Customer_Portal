---
artifact_type: specification_review
story: US-4.1
version: 1
status: ARCHIVED
created_at: "2026-09-03T00:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
supersedes: null
---

# Spec Review: Support Tickets (Create)

**Original Story:** docs/stories/US-4.1-create-ticket.md
**Spec Reviewed:** docs/specifications/US-4.1-spec.md (version 1)
**Story ID:** US-4.1
**Reviewed:** 2026-09-03
**Overall Verdict:** PASS

> Supersedes the pre-migration review previously at this path (dated
> 2026-08-22, "Pass with Issues", reviewing an FR-1–FR-10 spec draft). That
> spec was rewritten fresh by `story-spec-writer` on 2026-09-03 as FR-1–FR-7;
> the prior review no longer matches the artifact on disk and is retained
> only as historical context per `docs/catalog/stories.yaml`.

## Summary

All seven Acceptance Criteria (ST-AC1–ST-AC7) are Covered by the spec's
Functional Requirements FR-1–FR-7, in a clean 1:1 mapping, with no
contradictions and no scope creep found. The spec resolves the one Medium
gap the prior (superseded) review had flagged — `ticket_number`
non-guessability is now stated as an explicit requirement in FR-1, not just
an example format — and it correctly declines to invent answers to the five
gaps logged in `docs/decisions/US-4.1-open-decisions.md` (OD-1–OD-5),
instead citing each by name at the point in the FR it affects. No Critical
or Major findings.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| ST-AC1 | "Given an authenticated, active customer When POST /v1/support/tickets is called with {subject, body, category} and an Idempotency-Key header Then respond 201 with the ticket, including a human-readable ticket_number And status is \"open\" and requester_id is the caller And no SLA target field is written — only the raw timestamps other stories stamp And a confirmation email containing the ticket number is queued to the requester And a ticket_audit_log entry is written (event=ticket_created)" | Covered | FR-1 | Also carries the story's Assumption #2 non-guessability property into the requirement text itself, not just an example. |
| ST-AC2 | "Given an authenticated customer with existing tickets When GET /v1/support/tickets is called Then respond 200 with only that customer's tickets, newest first And a support agent calling the same endpoint sees the queue their permissions allow, not other customers' private views" | Covered | FR-2 | Customer-facing behavior is fully specified. The agent-visibility clause and the `status`/`cursor`/`limit` query parameters are correctly deferred to Open Question 1 / OD-4 rather than guessed. |
| ST-AC3 | "Given a request with an empty subject, a subject over 150 characters, a body over 5000 characters, or an unknown category When POST /v1/support/tickets is called Then respond 422 with type \".../errors/validation-failed\" And the errors array names each offending field And no ticket is created" | Covered | FR-3 | `category`'s value set is deferred to Open Question 2 / OD-3, consistent with OD-3's own recommendation that this needs a product decision. |
| ST-AC4 | "Given a request that is retried with the same Idempotency-Key within 24 hours When POST /v1/support/tickets is called again Then respond 201 with the ORIGINAL ticket, and no second ticket exists Given the same key is reused with a different body Then respond 422 with type \".../errors/idempotency-key-reuse\"" | Covered | FR-4 | Key scoping, missing-header response, and comparison scope are deferred to Open Question 3 / OD-2. |
| ST-AC5 | "Given a request with no valid access token Then respond 401 Given an authenticated user whose account is deactivated Then respond 403 with type \".../errors/account-deactivated\"" | Covered | FR-5 | — |
| ST-AC6 | "Given a customer who has created 5 tickets in the last hour When POST /v1/support/tickets is called again Then respond 429 with a Retry-After header And the existing open tickets are unaffected" | Covered | FR-6 | — |
| ST-AC7 | "Given a request containing an attachment_id that was uploaded by a different user, or is already bound to another ticket, or does not exist When POST /v1/support/tickets (or a reply, US-4.2) is called Then respond 422 with type \".../errors/attachment-not-owned\" And no ticket or reply is created, and the response does not reveal which of the three cases applied Given an attachment_id uploaded by the caller and not yet bound Then it is bound to this ticket and becomes immutable — an attachment belongs to exactly one ticket forever And unbound attachments older than 24 hours are purged by a scheduled job" | Covered | FR-7 | Whether this FR is buildable as stated this story, or must become a rejection behavior, is deferred to Open Question 4 / OD-1 — correctly, since the story's own Assumptions table and Open Questions section conflict on this point. Correctly excludes the reply-endpoint clause ("or a reply, US-4.2") as out of scope. |

## Verdict Rationale

PASS: every Acceptance Criterion is Covered, no Contradictions With Original
Story were found, and no Scope Creep was found. The spec's five Open
Questions all trace to genuine gaps already logged as Open Decisions
(OD-1–OD-5) rather than to spec-introduced ambiguity, so none of them is a
Major finding against this document — that is the correct behavior for a
spec that must not resolve decisions reserved for CLARIFICATION/human input.
No Ambiguities, Missing Edge Cases, or Contradictions sections are needed.
