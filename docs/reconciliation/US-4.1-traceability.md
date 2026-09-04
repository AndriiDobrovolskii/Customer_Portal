---
artifact_type: traceability
story: US-4.1
version: 2
status: ARCHIVED
created_at: "2026-09-04T03:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: reconciliation-reviewer
supersedes: 1
inputs:
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/tests/US-4.1-ac-test-matrix.md
    version: 5
  - path: docs/evidence/US-4.1-implementation-report.md
    version: 5
---

# Traceability: Support Tickets (Create) (US-4.1)

End-to-end AC → specification → design → test → code mapping. See
`docs/reviews/reconciliation/US-4.1-reconciliation.md` for findings, drift
register, and verdict rationale — this document is the standalone mapping
table only.

| AC ID | Spec (FR) | API Design | DB Design | Test(s) | Code |
|---|---|---|---|---|---|
| ST-AC1 | FR-1 (`US-4.1-spec.md`) | `POST /v1/support/tickets` → `201 TicketRead` (`US-4.1-openapi.yaml` v3) | `tickets` table, `ticket_number_seq` (`US-4.1-db-design.md` v3); audit write routed to existing `audit_log` (category="tickets") per DR-1 | `test_create_ticket_returns_201_and_persists_row`, `test_create_ticket_happy_path_writes_audit_event_and_queues_email`, `test_create_ticket_no_email_on_file_skips_dispatch_without_failing`, `test_create_ticket_email_dispatch_failure_does_not_fail_the_request`, `test_create_ticket_commits_exactly_once_with_attachment_bound` | `app/modules/support/{service,router,models,schemas}.py`; `app/modules/audit/service.py::record_event`; `app/modules/users/service.py::get_email_for_user`; `app/core/email.py::send_ticket_created_email` |
| ST-AC2 | FR-2, Open Question 1 (OD-4) | `GET /v1/support/tickets` → `200 TicketListResponse` / `403` agent branch (`US-4.1-openapi.yaml` v3) | `(requester_id, created_at DESC, id DESC)` composite index (`US-4.1-db-design.md` v3) | `test_list_own_tickets_returns_only_callers_tickets_newest_first`, `test_list_own_tickets_malformed_cursor_returns_422`, `test_list_own_tickets_agent_scope_caller_returns_403`, `test_list_own_tickets_scopes_to_requester_and_passes_through_paging` | `app/modules/support/{service,router,dependencies}.py::list_own_tickets`, `AgentQueueNotAvailableError` |
| ST-AC3 | FR-3, Open Question 2 (OD-3) | `422 validation-failed` (`US-4.1-openapi.yaml` v3) | `tickets.category String(50)`, no CHECK/ENUM (OD-3 open) | `test_create_ticket_invalid_input_returns_422_and_creates_nothing` (×3: empty_subject, subject_over_150_chars, body_over_5000_chars). Unknown-category sub-case: no test (OD-3 unresolved) | `app/modules/support/schemas.py::CreateTicketRequest` |
| ST-AC4 | FR-4, Open Question 3 (OD-2) | `201` replay / `422 idempotency-key-reuse` (`US-4.1-openapi.yaml` v3) | `SET NX EX` claim/replay gate, bounded poll (`US-4.1-db-design.md` v3 DR-3 fix) | `test_create_ticket_replay_same_key_returns_original_ticket`, `test_create_ticket_key_reused_with_different_body_returns_422`, `test_create_ticket_missing_idempotency_key_returns_422`, `test_create_ticket_replay_returns_original_ticket_without_second_write`, `test_create_ticket_idempotency_key_reused_with_different_body_raises`, `test_create_ticket_idempotency_poll_exhausted_propagates_unhandled` | `app/modules/support/cache.py::TicketIdempotencyCache`, `app/modules/support/service.py::create_ticket` |
| ST-AC5 | FR-5 | `401` (both routes) / `403 account-deactivated` (`US-4.1-openapi.yaml` v3) | n/a (auth is session/token-based, not a `tickets` column) | 8 `_401` tests (`POST`/`GET` × no-token/malformed/expired/revoked), `test_create_ticket_deactivated_account_returns_403`, `test_create_ticket_deactivated_account_raises_before_any_write`, `test_create_ticket_active_account_proceeds` | `app/modules/users/dependencies.py::CurrentUserDep`; `app/modules/users/service.py::get_account_status_for_user`; `app/modules/support/exceptions.py::AccountDeactivatedError` |
| ST-AC6 | FR-6 | `429` + `Retry-After` (`US-4.1-openapi.yaml` v3) | `ticket_create_rate:{user_id}` INCR+EXPIRE (`US-4.1-db-design.md` v3) | `test_create_ticket_sixth_in_hour_returns_429_and_existing_tickets_unaffected`, `test_create_ticket_rate_limit_exceeded_raises_429_and_releases_the_claimed_key`, `test_create_ticket_within_rate_limit_succeeds` | `app/modules/support/cache.py::TicketCreationRateLimitCache`, `app/modules/support/exceptions.py::TicketCreationRateLimitError` |
| ST-AC7 | FR-7, Open Question 4 (OD-1) | `422 attachment-not-owned` (single slug, `US-4.1-openapi.yaml` v3) | `attachments` table, `ticket_id` nullable-until-bound, partial index `WHERE ticket_id IS NULL` (`US-4.1-db-design.md` v3) | `test_create_ticket_attachment_owned_by_other_user_returns_422`, `test_create_ticket_attachment_already_bound_returns_422`, `test_create_ticket_attachment_unknown_id_returns_422`, `test_create_ticket_attachment_owned_and_unbound_is_bound_and_immutable`, `test_create_ticket_attachment_not_owned_raises_indistinguishable_error` (×3), `test_create_ticket_attachment_owned_and_unbound_is_bound`. Purge-job clause: `test_purge_unbound_attachments_deletes_unbound_attachment_older_than_24h`, `test_purge_unbound_attachments_leaves_unbound_attachment_within_24h_untouched`, `test_purge_unbound_attachments_leaves_bound_attachment_older_than_24h_untouched`, `test_purge_unbound_attachments_purge_of_empty_candidate_list_deletes_nothing` | `app/modules/support/{repository,exceptions}.py::AttachmentRepository`, `AttachmentNotOwnedError`; `scripts/purge_unbound_attachments.py` |

## Known Gaps (not invented here, carried from upstream)

- **ST-AC3 unknown-category sub-case** — untestable pending OD-3 (stakeholder-supplied category enum). Disclosed, non-blocking, carried for `HUMAN_PR_APPROVAL`.

## Resolved since v1

- **ST-AC7 purge-job test** — was Fail-forcing at `US-4.1-reconciliation.md` v1 (routed `test_gap` → `TEST_WRITING`). `TEST_WRITING` attempt 5 added `tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests against `AttachmentRepository.find_unbound_older_than`/`.purge`); confirmed closed at `US-4.1-reconciliation.md` v2.
