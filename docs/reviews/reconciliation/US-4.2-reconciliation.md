---
artifact_type: reconciliation
story: US-4.2
version: 1
status: DRAFT
created_at: "2026-09-06T02:00:00Z"
updated_at: "2026-09-06T02:00:00Z"
produced_by: reconciliation-reviewer
supersedes: null
inputs:
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/reviews/specifications/US-4.2-spec-review.md
    version: 6
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.2-design-review.md
    version: 3
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/plans/US-4.2-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-4.2-plan-review.md
    version: 2
  - path: docs/tests/US-4.2-test-strategy.md
    version: 3
  - path: docs/tests/US-4.2-ac-test-matrix.md
    version: 3
  - path: docs/evidence/US-4.2-test-generation-report.md
    version: 3
  - path: docs/evidence/US-4.2-implementation-report.md
    version: 1
  - path: docs/evidence/US-4.2-quality-gate-report.md
    version: 1
  - path: docs/verification/US-4.2-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-4.2-security-review.md
    version: 1
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
---

# Reconciliation Report: Ticket Replies (US-4.2)

**Story ID:** US-4.2
**Reviewed:** 2026-09-06
**Overall Verdict:** PASS

## Summary

Every Acceptance Criterion (TR-AC1–TR-AC7) has exactly one row in
`US-4.2-ac-test-matrix.md` v3, each named test function was opened and
confirmed to exist at its stated path (grep count also matches the recorded
60 integration / 42 unit-service / 12 unit-schemas totals), and each test's
assertions were read and confirmed to check the AC's actual stated
behavior — not just proximity to it (e.g. the two Resolution OD-5/OD-8
"resolved ticket" tests assert the specific divergent status outcomes, not
merely a `201`; the three RLS tests query through a raw customer-context
connection with no application filter, per the NFR's own requirement).
`service.py::create_reply`'s status/first-response-at logic
(`app/modules/support/service.py:504-518`) and `exceptions.py`'s five error
`type_slug`s were compared line-by-line against the spec and found to match
exactly, with no drift.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| TR-AC1 | "Given a support agent with tickets:write and an open ticket... respond 201 with the created reply And the ticket's status becomes \"waiting_on_customer\" And first_response_at is stamped if this is the first public agent reply... And the requester is notified by email" | Yes | `test_create_reply_agent_public_returns_201_and_advances_status` (+ `test_create_reply_agent_public_second_reply_does_not_restamp_first_response_at`) | Yes | Yes | Integration test asserts `201`, `ticket.status == "waiting_on_customer"`, `ticket.first_response_at is not None`, and the persisted reply row; the second-reply test asserts the stamp does not move. Requester-notification is asserted at the unit level (`test_create_reply_agent_notifies_requester`). |
| TR-AC1 (OD-1 attachment binding, BR-016) | Attachment binding to the reply; attachment-not-owned indistinguishability | Yes | `test_create_reply_attachment_owned_and_unbound_is_bound_to_the_reply`, `test_create_reply_attachment_owned_by_other_user_returns_422`, `test_create_reply_attachment_already_bound_to_another_reply_returns_422`, `test_create_reply_attachment_unknown_id_returns_422` | Yes | Yes | Bound-attachment test asserts `attachment.ticket_reply_id == reply_id` and `attachment.ticket_id is None` (reply-scoped, not ticket-scoped). All three not-owned causes assert the identical `422 attachment-not-owned` type, matching BR-016's non-enumeration requirement; the unit-level indistinguishability test additionally parametrizes all three causes to the same raised exception. |
| TR-AC2 | "Given the ticket's requester and a ticket in \"waiting_on_customer\"... respond 201 And the ticket's status becomes \"waiting_on_support\" And the assigned agent (or the queue, if unassigned) is notified" | Yes | `test_create_reply_customer_returns_201_and_reverts_status` | Yes | Yes | Asserts `201` and `ticket.status == "waiting_on_support"`. Queue notification (not requester) asserted at the unit level (`test_create_reply_customer_notifies_queue_not_requester`). |
| TR-AC3 | "...the internal reply is absent from the response entirely... absent from every notification email... when an agent calls the same endpoint, the internal reply IS returned, marked as internal... the exclusion holds even if the application layer forgets to filter, because a PostgreSQL Row-Level Security policy..." | Yes | `test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent`, `test_internal_reply_hidden_from_customer_context_by_rls_alone`, `test_agent_context_sees_internal_reply_via_rls`, `test_no_actor_kind_set_defaults_to_hiding_internal_reply` | Yes | Yes | The application-level test asserts the internal reply id is absent from the customer's `items` list and present (with `visibility == "internal"`) in the agent's. The RLS-alone test deliberately bypasses the repository/service and issues a bare `SELECT` through a customer-context connection, asserting `{row.visibility for row in rows} == {"public"}` — this is the NFR's own explicit "application filter deliberately disabled" requirement, not merely an HTTP-level check. The no-context test asserts the fail-closed default. |
| TR-AC4 | "...respond 404 with type \".../errors/not-found\"... Because 403 would confirm the ticket id exists" (+ agent-lacking-scope GET 404, + unauthenticated 401) | Yes | `test_create_reply_different_customer_returns_404`, `test_get_ticket_detail_different_customer_returns_404`, `test_create_reply_unknown_ticket_returns_404`, `test_get_ticket_detail_agent_lacking_tickets_read_returns_404`, 8 `_401` tests (no-token/malformed/expired/revoked × POST/GET) | Yes | Yes | All assert the exact status code and, where applicable, the `not-found` type slug — never `403` for the enumeration-prevention cases. The agent-lacking-`tickets:read` test explicitly withholds both scopes and asserts `404`, matching FR-4's GET-specific rule. |
| TR-AC5 | "...respond 403 with type \".../errors/insufficient-permission\" And no reply is created And visibility defaults to \"public\" when the field is omitted by a customer" | Yes | `test_create_reply_customer_visibility_internal_returns_403`, `test_create_reply_customer_omitted_visibility_defaults_to_public`, `test_create_reply_agent_internal_note_is_created_visible_to_agent` (OD-6) | Yes | Yes | 403 test asserts the status and (per service unit test) that rejection happens before any repository call. Omission-defaults-to-public is asserted at both integration and unit level for both actor kinds (OD-6). |
| TR-AC6 | "...a ticket whose status is \"closed\"... respond 409 with type \".../errors/ticket-closed\"... And a \"resolved\" ticket behaves differently" | Yes | `test_create_reply_on_closed_ticket_returns_409`, `test_create_reply_agent_public_on_resolved_ticket_status_stays_resolved` (OD-5), `test_create_reply_customer_on_resolved_ticket_reopens_it` (OD-8) | Yes | Yes | Closed-ticket test asserts `409`, the `ticket-closed` type, and that no reply row was persisted. The two resolved-ticket tests assert the specific divergent outcomes the spec's OD-5/OD-8 resolutions require: agent reply leaves `status == "resolved"`; customer reply moves it to `status == "waiting_on_support"` — read directly, this is the correct, spec-accurate divergence (not a copy-paste of the same assertion). |
| TR-AC7 | "Given an empty body or one exceeding 5000 characters... respond 422 with type \".../errors/validation-failed\"" | Yes | `test_create_reply_invalid_body_returns_422_and_creates_nothing` (parametrized: empty/over-5000), `test_create_reply_rejects_unknown_field_returns_422` | Yes | Yes | Asserts `422`, the `validation-failed` type, and (for the body cases) that no reply row was persisted. Schema-level boundary (`5000` accepted, `5001` rejected) is separately unit-tested in `test_support_schemas.py`. |

## Spec Drift

None found. `service.py::create_reply` (`app/modules/support/service.py:504-518`) implements the exact status-transition table FR-1/FR-2/FR-6 describe: agent public reply → `waiting_on_customer` unless already `resolved` (line 510); customer reply on `waiting_on_customer` or `resolved` → `waiting_on_support` (lines 515-518, the single `elif` branch correctly unifying FR-2's ordinary case and OD-8's reopening case at the same target status the spec calls for); internal notes and the API_DESIGN OQ-1 no-op statuses correctly make no status write. `exceptions.py`'s five `type_slug` values (`validation-failed`, `attachment-not-owned`, `not-found`, `insufficient-permission`, `ticket-closed`) match the spec's Error Envelope section verbatim.

## Verdict Rationale

Every AC has a matrix row, an existing test, and that test asserts the AC's actual stated behavior; the two known coverage gaps already recorded in the ac-test-matrix's own "Gaps Not Covered" section (API_DESIGN OQ-2's exact scope-split combination, not reachable under the shipped role seed; migration reversibility, owned by migration-manager) are pre-existing, documented limitations rather than reconciliation defects, and neither corresponds to an AC this stage owns. No spec drift was found between the approved spec and the shipped implementation. PASS.
