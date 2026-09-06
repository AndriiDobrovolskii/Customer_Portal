---
artifact_type: reconciliation
story: US-4.3
version: 1
status: ARCHIVED
created_at: "2026-09-07T08:00:00Z"
updated_at: "2026-09-07T08:00:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/reviews/specifications/US-4.3-spec-review.md
    version: 3
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/designs/database/US-4.3-db-design.md
    version: 3
  - path: docs/designs/database/US-4.3-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.3-design-review.md
    version: 3
  - path: docs/impact-analysis/US-4.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.3-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.3-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-4.3-plan-review.md
    version: 1
  - path: docs/tests/US-4.3-test-strategy.md
    version: 2
  - path: docs/tests/US-4.3-ac-test-matrix.md
    version: 2
  - path: docs/evidence/US-4.3-test-generation-report.md
    version: 2
  - path: docs/evidence/US-4.3-implementation-report.md
    version: 1
  - path: docs/verification/US-4.3-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-4.3-security-review.md
    version: 1
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
supersedes: null
---

# Reconciliation Report: Ticket Resolution

**Story ID:** US-4.3
**Reviewed:** 2026-09-07
**Overall Verdict:** PASS

## Summary

Every Acceptance Criterion in `US-4.3-spec.md` (v2) — TC-AC1 through TC-AC9, plus FR-5's source-derived direct-`/reopen` success path with no covering source AC — has a row in `US-4.3-ac-test-matrix.md` (v2), a test function that exists exactly once in the working tree, and a test body that asserts the AC's actual stated behavior (status code, persisted field values, audit-row actor/event, and negative assertions such as "no audit write" or "ticket unchanged"), not merely proximity to the right endpoint. Direct reading of `app/modules/support/service.py`, `schemas.py`, `exceptions.py`, and `scripts/auto_close_resolved_tickets.py` against the approved spec, API design, and DB design found no drift: the `_ALLOWED_EVENTS_BY_STATUS` table, OD-4's inclusive/strict boundary split, OD-5/OD-6/OD-7's status-eligibility and audit-actor rules, the `resolution_note` 5000-char bound, and every `problem+json` `type` slug all match what was approved, character for character.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| TC-AC1 | "Given an agent with tickets:write and a ticket in an open state When POST /v1/support/tickets/{id}/resolve is called with {resolution_note} Then respond 200 with status \"resolved\" and resolved_at set And resolved_at is the only timing field written; no SLA target is evaluated And the requester is emailed the resolution note plus a link to reopen And a ticket_audit_log entry is written (event=ticket_resolved, actor=agent:{id})" | Yes | `tests/integration/modules/support/test_support_router.py::test_resolve_ticket_agent_from_eligible_status_returns_200_and_persists` (+ unit `test_resolve_ticket_agent_from_each_eligible_status_succeeds`, `test_resolve_ticket_email_dispatch_failure_does_not_fail_the_request`) | Yes | Yes | Integration test asserts `200`, `status=="resolved"`, `resolved_at` set, `resolution_note`/`closed_by` absent from body, persisted `resolution_note`, and a `ticket_resolved` audit row with `outcome=="success"`. Unit test covers the email-dispatch path and its best-effort-after-commit semantics. |
| TC-AC2 | "Given the ticket's requester and a ticket in any non-closed state When POST /v1/support/tickets/{id}/close is called Then respond 200 with status \"closed\" and closed_at set And the audit entry records actor=self" | Yes | `test_close_ticket_requester_returns_200_and_persists_closed_by` | Yes | Yes | Asserts `200`, `closed_at` set, `ticket.closed_by == requester.id`, and audit row `actor_id == requester.id` for the `ticket_closed` event. |
| TC-AC3 | "Given a ticket resolved more than 7 days ago with no reply since When the scheduled auto-close job runs Then status becomes \"closed\" and closed_at is set And a ticket_audit_log entry is written (event=ticket_auto_closed, actor=system) And the job's update is conditioned on the ticket still being resolved with the same resolved_at, so a reply committed first makes the job a no-op" | Yes | `tests/integration/scripts/test_auto_close_resolved_tickets.py::test_auto_close_resolved_past_window_closes_ticket_older_than_7_days`, `test_auto_close_job_writes_one_ticket_auto_closed_audit_row_per_ticket`, `test_auto_close_resolved_past_window_reopened_ticket_survives`, `test_auto_close_resolved_past_window_is_idempotent_on_rerun` | Yes | Yes | Full behavior chain covered: strict->7-day closure, `closed_by=SYSTEM_ACTOR_ID`, one `ticket_auto_closed` audit row per ticket, no-op on a ticket reopened since (status no longer `resolved`), and idempotent re-run. The audit-composition test re-implements the script's own call sequence rather than invoking `main()`; this is a documented, disclosed scope choice (matrix "Gaps Not Covered"), not a gap in AC coverage — the repository predicate and the audit call are both exercised directly. |
| TC-AC4 | "Given a ticket resolved less than 7 days ago When the requester posts a reply (US-4.2) Then status becomes \"reopened\" and resolved_at is cleared And the previously assigned agent is notified" | Yes | `test_create_reply_customer_on_resolved_within_window_writes_reopened_audit_entry`, `test_create_reply_customer_on_resolved_outside_window_makes_no_status_change` | Yes | Yes | Target status is `waiting_on_support`, not the source's literal `"reopened"` string — an approved, human-confirmed correction (OD-1, spec Revision Note), not drift. Test asserts `201`, `status=="waiting_on_support"`, `resolved_at is None`, and (new since DESIGN_REVIEW v2 DR-4) a `ticket_reopened` audit row — matching db-design.md v3's decision that this transition is audited identically to FR-5's. The outside-window case asserts no status change. |
| TC-AC5 | "Given a ticket that is already \"closed\" When POST /v1/support/tickets/{id}/resolve or /reopen is called Then respond 409 with type \".../errors/invalid-state-transition\" And the problem+json body lists the transitions actually permitted from the current state" | Yes | `test_transition_endpoints_ineligible_status_returns_409_with_allowed_events` (parametrized ×4, incl. `/close` from `closed`) | Yes | Yes | Asserts `409`, `type` ends with `invalid-state-transition`, and `allowed_events` equals the exact list `_ALLOWED_EVENTS_BY_STATUS` produces for each source status (verified against `app/modules/support/service.py:49-55` directly). |
| TC-AC6 | "Given the ticket's requester, who does not hold tickets:write When POST /v1/support/tickets/{id}/resolve is called Then respond 403 with type \".../errors/insufficient-permission\" Because a customer may close their ticket (TC-AC2) but only an agent may declare it resolved" | Yes | `test_resolve_ticket_customer_on_open_ticket_returns_403` | Yes | Yes | Asserts `403` and `type` ending `insufficient-permission`. Companion test `test_resolve_ticket_customer_on_closed_ticket_returns_409_not_403` proves the spec's own NFR (state checked before actor) — a customer resolving a `closed` ticket gets `409`, not `403`. |
| TC-AC7 | "Given customer A and a ticket belonging to customer B When any of /resolve, /close or /reopen is called Then respond 404 with type \".../errors/not-found\"" | Yes | `test_transition_endpoints_different_customer_returns_404` (parametrized ×3) | Yes | Yes | Asserts `404` and `type` ending `not-found` for all three endpoints against an owned-by-another-customer ticket. |
| TC-AC8 | "Given two agents resolving the same ticket simultaneously When both requests are processed Then exactly one succeeds; the transition is a conditional update scoped to the expected current status And the loser receives 409, not a silent overwrite of the first agent's resolution_note" | Yes | `test_resolve_ticket_second_concurrent_caller_returns_409_first_note_intact` | Yes | Yes | Two sequential calls against the same ticket via the real conditional `UPDATE`; asserts first `200`, second `409`, and the persisted `resolution_note` is the first agent's text, not the second's — proves no silent overwrite, not just "second call failed". |
| TC-AC9 | "Given a resolve request with an empty or absent resolution_note When POST /v1/support/tickets/{id}/resolve is called Then respond 422 with type \".../errors/validation-failed\" Because the note is what the customer receives and what the next agent reads" | Yes | `test_resolve_ticket_invalid_resolution_note_returns_422_and_leaves_ticket_unchanged` (parametrized: empty, missing) | Yes | Yes | Asserts `422`, `type` ending `validation-failed`, and that the ticket's `status` is unchanged (`"open"`) after the rejected request — the persistence-side half of the AC, not just the status code. |
| FR-5 (no source AC — derived, OD-3-confirmed) | Direct `POST /reopen` by requester or agent on a resolved ticket within the 7-day window succeeds; outside the window it does not. | Yes | `test_reopen_ticket_requester_within_window_returns_200_and_clears_resolved_at`, `test_reopen_ticket_agent_within_window_returns_200`, `test_reopen_ticket_outside_window_returns_409`, `test_reopen_ticket_at_exactly_7_days_boundary_succeeds` | Yes | Yes | Within-window tests assert `200`, `status=="waiting_on_support"`, `resolved_at is None`, and a `ticket_reopened` audit row with the correct actor. The outside-window test asserts `409` and the ticket left `"resolved"`. The exact-7-day boundary test seeds `resolved_at` server-side via Postgres's own frozen `now()` (not Python's wall clock), eliminating the timing non-determinism IMPLEMENTATION attempt 1 found and TEST_WRITING v2 fixed — confirmed by direct read of the helper and its docstring. |

## Spec Drift

None found. Every checked implementation detail — the `_ALLOWED_EVENTS_BY_STATUS` table (`app/modules/support/service.py:49-55`), the OD-5/OD-6/OD-7 status-eligibility and audit-actor rules in `resolve_ticket`/`close_ticket`/`reopen_ticket` (`service.py:393-533`), the `resolution_note` `min_length=1, max_length=5000` bound and `extra="forbid"` on all three inbound schemas (`schemas.py:16,55,110-139`), the `problem+json` `type` slugs (`exceptions.py`), and `scripts/auto_close_resolved_tickets.py`'s call sequence — matches the approved spec, API design, and DB design exactly, including the two human-confirmed corrections from the source story (OD-1's `waiting_on_support` target instead of a literal `"reopened"` status, and DESIGN_REVIEW v2 DR-4's addition of an audit write to FR-4's reply-driven transition) — both of which are documented, approved deviations from the source story's literal text, not undocumented drift introduced during coding.

## Verdict Rationale

Every AC (TC-AC1 through TC-AC9) and the source-uncovered FR-5 has exactly one traceability-matrix row, a test function confirmed to exist by direct grep and read, and a test body confirmed by direct read to assert the AC's specific stated behavior (status code, persisted field, audit actor/event, and the relevant negative case) rather than merely exercising the same endpoint — and no drift was found between the approved spec/designs and the shipped code. Per the verdict rules, this is PASS.
