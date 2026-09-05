---
artifact_type: traceability
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
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/tests/US-4.2-ac-test-matrix.md
    version: 3
  - path: docs/evidence/US-4.2-implementation-report.md
    version: 1
---

# Traceability: Ticket Replies (US-4.2)

End-to-end AC → specification → design → test → code mapping. See
`docs/reviews/reconciliation/US-4.2-reconciliation.md` for findings, drift
register, and verdict rationale — this document is the standalone mapping
table only.

| AC ID | Spec (FR) | API Design | DB Design | Test(s) | Code |
|---|---|---|---|---|---|
| TR-AC1 | FR-1 (`US-4.2-spec.md`) | `POST /v1/support/tickets/{id}/replies` → `201 ReplyRead` (`US-4.2-openapi.yaml` v3) | `ticket_replies` table; `attachments.ticket_reply_id` (nullable, OD-1); `tickets.first_response_at` (`US-4.2-db-design.md` v3) | `test_create_reply_agent_public_returns_201_and_advances_status`, `test_create_reply_agent_public_second_reply_does_not_restamp_first_response_at`, `test_create_reply_attachment_owned_and_unbound_is_bound_to_the_reply`, `test_create_reply_attachment_owned_by_other_user_returns_422`, `test_create_reply_attachment_already_bound_to_another_reply_returns_422`, `test_create_reply_attachment_unknown_id_returns_422` | `app/modules/support/service.py::TicketReplyService.create_reply`, `app/modules/support/router.py`, `app/modules/support/repository.py::TicketReplyRepository.create`, `AttachmentRepository.bind_to_reply`, `app/core/email.py::send_ticket_reply_notification` |
| TR-AC2 | FR-2, Resolution OD-2/OD-8 | `POST /v1/support/tickets/{id}/replies` → `201 ReplyRead` (same route as TR-AC1) | Same `ticket_replies` table; no assignment column added (OD-2) | `test_create_reply_customer_returns_201_and_reverts_status`, `test_create_reply_customer_on_resolved_ticket_reopens_it` | `service.py::create_reply` (lines 515-518, `waiting_on_support` transition), `app/core/email.py::send_ticket_reply_queue_notification` |
| TR-AC3 | FR-3 | `GET /v1/support/tickets/{id}` → `200 TicketDetailRead` (`US-4.2-openapi.yaml` v3) | `ticket_replies_read`/`ticket_replies_write` Row-Level Security policies (`US-4.2-db-design.md` v3); `CHECK (visibility = 'public' OR author_kind = 'agent')` | `test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent`, `test_internal_reply_hidden_from_customer_context_by_rls_alone`, `test_agent_context_sees_internal_reply_via_rls`, `test_no_actor_kind_set_defaults_to_hiding_internal_reply` | `app/modules/support/repository.py` (RLS-backed queries), `migrations/versions/9132a68b73c8_add_ticket_replies.py` (`CREATE POLICY`), `app/modules/support/dependencies.py::get_rls_session` |
| TR-AC4 | FR-4, Resolution OD-7 | `404 not-found` (both routes) / `401` (`US-4.2-openapi.yaml` v3) | n/a (auth is session/token-based) | `test_create_reply_different_customer_returns_404`, `test_get_ticket_detail_different_customer_returns_404`, `test_create_reply_unknown_ticket_returns_404`, `test_get_ticket_detail_agent_lacking_tickets_read_returns_404`, 8 `_401` tests (POST/GET × no-token/malformed/expired/revoked) | `service.py::create_reply`/`get_ticket_detail` (`TicketNotFoundError`), `app/modules/users/dependencies.py::CurrentUserDep` |
| TR-AC5 | FR-5, Resolution OD-6 | `403 insufficient-permission` (`US-4.2-openapi.yaml` v3) | `CHECK (visibility = 'public' OR author_kind = 'agent')` backstop (`US-4.2-db-design.md` v3) | `test_create_reply_customer_visibility_internal_returns_403`, `test_create_reply_customer_omitted_visibility_defaults_to_public`, `test_create_reply_agent_internal_note_is_created_visible_to_agent` | `service.py::create_reply` (lines 460-466, `InsufficientPermissionError`), `app/modules/support/exceptions.py` |
| TR-AC6 | FR-6, Resolutions OD-5/OD-8 | `409 ticket-closed` (`problem+json`, `US-4.2-openapi.yaml` v3) | n/a (status-column logic only) | `test_create_reply_on_closed_ticket_returns_409`, `test_create_reply_agent_public_on_resolved_ticket_status_stays_resolved`, `test_create_reply_customer_on_resolved_ticket_reopens_it` | `service.py::create_reply` (lines 457-458 closed gate; lines 504-518 status table), `app/modules/support/exceptions.py::TicketClosedError` |
| TR-AC7 | FR-7 | `422 validation-failed` (`US-4.2-openapi.yaml` v3) | `ticket_replies.body Text`, no DB-level length constraint (enforced at schema layer) | `test_create_reply_invalid_body_returns_422_and_creates_nothing`, `test_create_reply_rejects_unknown_field_returns_422`, `test_create_reply_request_rejects_empty_body`, `test_create_reply_request_rejects_body_over_5000_chars`, `test_create_reply_request_accepts_body_at_5000_char_boundary` | `app/modules/support/schemas.py::CreateReplyRequest` |
