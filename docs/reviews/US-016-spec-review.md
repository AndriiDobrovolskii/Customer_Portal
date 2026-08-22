# Spec Review: Ticket Resolution

**Original Story:** docs/backlog/US-4.3-ticket-resolution.md
**Spec Reviewed:** docs/specifications/US-016-ticket-resolution-spec.md
**Story ID:** US-016 (source story numbered US-4.3)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All 9 Acceptance Criteria (TC-AC1–TC-AC9) are fully covered by FR-1 through FR-9, with accurate, faithful derivations and no contradictions against the source story. The spec's Open Questions section shows strong diligence — it independently surfaces two real internal inconsistencies in the story itself (the `/reopen` success path has no AC, and FR-1's "open state" wording is narrower than the normative state-machine table). The issues found here are lower-severity: one undocumented field name in the error envelope, one inherited ambiguity around boundary comparisons, and a gap — parallel to the ones the spec already caught — around the agent-initiated `/close` path and the `closed_by` data field, which the spec does not surface as an Open Question despite catching analogous gaps elsewhere.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| TC-AC1 | "Given an agent with tickets:write and a ticket in an open state When POST /v1/support/tickets/{id}/resolve is called with {resolution_note} Then respond 200 with status \"resolved\" and resolved_at set And resolved_at is the only timing field written; no SLA target is evaluated And the requester is emailed the resolution note plus a link to reopen And a ticket_audit_log entry is written (event=ticket_resolved, actor=agent:{id})" | Covered | FR-1 | Faithful, complete restatement. |
| TC-AC2 | "Given the ticket's requester and a ticket in any non-closed state When POST /v1/support/tickets/{id}/close is called Then respond 200 with status \"closed\" and closed_at set And the audit entry records actor=self" | Covered | FR-2 | See Missing Edge Cases — the wider `close` permission ("requester or agent" per the story's State machine table and API Contract) is not addressed by any FR. |
| TC-AC3 | "Given a ticket resolved more than 7 days ago with no reply since When the scheduled auto-close job runs Then status becomes \"closed\" and closed_at is set And a ticket_audit_log entry is written (event=ticket_auto_closed, actor=system) And the job's update is conditioned on the ticket still being resolved with the same resolved_at, so a reply committed first makes the job a no-op" | Covered | FR-3 | Faithful, complete restatement. |
| TC-AC4 | "Given a ticket resolved less than 7 days ago When the requester posts a reply (US-4.2) Then status becomes \"reopened\" and resolved_at is cleared And the previously assigned agent is notified" | Covered | FR-4 | Notification channel ambiguity correctly logged by the spec's own Open Questions. |
| TC-AC5 | "Given a ticket that is already \"closed\" When POST /v1/support/tickets/{id}/resolve or /reopen is called Then respond 409 with type \".../errors/invalid-state-transition\" And the problem+json body lists the transitions actually permitted from the current state" | Covered | FR-5 | See Ambiguities — the field name carrying the permitted-transitions list is not documented. |
| TC-AC6 | "Given the ticket's requester, who does not hold tickets:write When POST /v1/support/tickets/{id}/resolve is called Then respond 403 with type \".../errors/insufficient-permission\" Because a customer may close their ticket (TC-AC2) but only an agent may declare it resolved" | Covered | FR-6 | Faithful, complete restatement. |
| TC-AC7 | "Given customer A and a ticket belonging to customer B When any of /resolve, /close or /reopen is called Then respond 404 with type \".../errors/not-found\"   # consistent with TR-AC4" | Covered | FR-7 | Faithful restatement (the stray `TR-AC4` cross-reference from the story is correctly dropped rather than propagated as an error). |
| TC-AC8 | "Given two agents resolving the same ticket simultaneously When both requests are processed Then exactly one succeeds; the transition is a conditional update scoped to the expected current status And the loser receives 409, not a silent overwrite of the first agent's resolution_note" | Covered | FR-8 | Faithful, complete restatement. |
| TC-AC9 | "Given a resolve request with an empty or absent resolution_note When POST /v1/support/tickets/{id}/resolve is called Then respond 422 with type \".../errors/validation-failed\" Because the note is what the customer receives and what the next agent reads" | Covered | FR-9 | Faithful, complete restatement. |

## Ambiguities & Non-Verifiable Statements

- **[Medium] Error envelope field name undocumented** — FR-5 says the response body "lists the transitions actually permitted from the current state" but never states the JSON field that carries this list. The story's own `## Error Envelope` section shows the concrete field: `"allowed_events": []`. The spec has no equivalent section reproducing this schema anywhere (Summary, FRs, NFRs, and Traceability Matrix all omit it), so a developer building only from the spec cannot know the field is named `allowed_events` rather than, say, `permitted_transitions` or `allowed_transitions`. This is not verifiable as written — a test asserting the response shape cannot be written from the spec alone.

- **[Low] Strict/inclusive boundary comparison left unresolved** — The spec's Non-Functional Requirements section states: "The reply guard and the job predicate must use complementary strict/inclusive comparisons so the boundary instant belongs to exactly one of them." This does not say which of the two (the reply-reopen guard in FR-4, or the auto-close job predicate in FR-3) uses the strict comparison and which uses the inclusive one. A developer cannot write a test for the exact 7-day boundary instant from this text alone. Note: this ambiguity is quoted verbatim from the source story's own Non-Functional / Security Requirements section, so it is inherited rather than introduced by the spec — but it remains unresolved in the artifact that will drive implementation.

## Contradictions With Original Story

None found. All Functional Requirements, Non-Functional Requirements, and Out of Scope items in the spec are faithful restatements of the corresponding story sections with no conflicting statements identified.

## Scope Creep

None found. Every Functional Requirement traces to a specific TC-AC, the Non-Functional Requirements reproduce the story's Non-Functional / Security Requirements section verbatim, and the Out of Scope section matches the story's Out of Scope section. The spec's four Open Questions beyond the story's original two are phrased as questions, not asserted as new requirements or behavior, which is consistent with (not a departure from) the "log ambiguity, don't invent scope" discipline this skill checks for.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Medium] Agent-initiated `/close` path is not addressed by any Functional Requirement** — The story's API Contract table lists the Auth for `POST /v1/support/tickets/{id}/close` as "Requester or `tickets:write`", and the State machine table has the row "any non-closed | close | closed | **requester or agent**". FR-2, the spec's only close-related requirement, is titled "Customer Closes Their Own Ticket" and derives strictly from TC-AC2, which only exercises the requester path and states "the audit entry records `actor=self`". No FR states what happens, or what audit-actor value is recorded, when an agent (not the requester) calls `/close`. Does an agent-initiated close follow the same 200/`closed_at` response as FR-2, and if so, does the audit entry record `actor=agent:{id}` instead of `actor=self`? This mirrors the exact kind of story/AC-coverage gap the spec's own Open Questions section already caught for the `/reopen` success path and for FR-1's resolve-eligible states — but this parallel gap involving `/close` was not similarly surfaced.

- **[Low] `closed_by` field is unaddressed for both agent-close and auto-close** — The story's Data Model Notes include `CHECK ((status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL))`, meaning a `closed_by` value is mandatory whenever a ticket is closed. Neither FR-2 (customer close) nor FR-3 (system auto-close, `actor=system`) states what value `closed_by` takes. Is `closed_by` set to `system` for FR-3's auto-close path, matching the audit log's `actor=system`, and does this field exist and get populated at all per FR-2 (which only mentions the audit entry's `actor=self`, not a ticket-row `closed_by` value)? This is arguably a gap in the story's own Data Model Notes vs. its ACs rather than something the spec should have resolved unilaterally, but the spec does not log it as an Open Question the way it did for other comparable gaps.

## Verdict Rationale

Pass with Issues: AC coverage is complete (9/9 Covered) and no contradictions were found, so the verdict does not fall to Fail. However, one Medium-severity ambiguity (undocumented `allowed_events` field name), one Low-severity inherited ambiguity (unresolved strict/inclusive boundary assignment), and two Missing Edge Case findings (agent-initiated `/close` and the `closed_by` data field) are worth resolving — ideally as additional Open Questions, consistent with the pattern the spec already uses successfully elsewhere in the same document — before implementation begins.
