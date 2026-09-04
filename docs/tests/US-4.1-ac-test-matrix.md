---
artifact_type: ac_test_matrix
story: US-4.1
version: 5
status: ARCHIVED
created_at: "2026-09-03T13:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: test-writer
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
  - path: docs/reviews/reconciliation/US-4.1-reconciliation.md
    version: 1
supersedes: 4
---

# Traceability Matrix: Support Tickets (Create) (US-4.1 / spec US-4.1)

**Spec:** docs/specifications/US-4.1-spec.md (version 1)
**Status:** TEST_WRITING (gap-fill pass, attempt 5) — routed from
`RECONCILIATION` v1's `test_gap` verdict: ST-AC7's 24h unbound-attachment
purge sub-clause had no test after four prior `TEST_WRITING` passes. Fixed
this pass — see the updated ST-AC7 purge row below. All other rows are
unchanged from v4. See `US-4.1-test-generation-report.md` for detail.

| AC / FR | Case | Level | Test function | File |
|---|---|---|---|---|
| ST-AC1 / FR-1 | Happy path: `201`, `status="open"`, `requester_id`=caller, `ticket_number` present, no ticket created twice | Integration | `test_create_ticket_returns_201_and_persists_row` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC1 / FR-1 | `audit_log` row written (`category="tickets"`, `event="ticket_created"`, `target_id`=ticket id, `outcome="success"`) | Integration | `test_create_ticket_returns_201_and_persists_row` (same test, second assertion block) | `tests/integration/modules/support/test_support_router.py` |
| ST-AC1 / FR-1 | Service-level: ticket returned open, audit collaborator called once, idempotency key resolved to the new ticket, confirmation email queued with the ticket number | Unit | `test_create_ticket_happy_path_writes_audit_event_and_queues_email` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC1 / FR-1 (email best-effort, plan-gap collaborator) | No email on file → creation still succeeds, dispatch skipped | Unit | `test_create_ticket_no_email_on_file_skips_dispatch_without_failing` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC1 / FR-1 (email best-effort, plan-gap collaborator) | Email dispatch raises → creation still succeeds (already committed) | Unit | `test_create_ticket_email_dispatch_failure_does_not_fail_the_request` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC1 / FR-1 (transaction boundary, implementation-plan §2) | `create_ticket` commits exactly once, covering the ticket insert + attachment bind + audit write together | Unit | `test_create_ticket_commits_exactly_once_with_attachment_bound` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC2 / FR-2 | Happy path: `200`, only the caller's own tickets, newest first | Integration | `test_list_own_tickets_returns_only_callers_tickets_newest_first` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC2 / FR-2 | Malformed `cursor` → `422 validation-failed` | Integration | `test_list_own_tickets_malformed_cursor_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC2 / FR-2 (OD-4 resolution) | A caller holding `tickets:read`/`tickets:write` (support_agent/admin) → `403 agent-queue-not-available` | Integration | `test_list_own_tickets_agent_scope_caller_returns_403` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC2 / FR-2 | Pagination/filter parameter pass-through in isolation | Unit | `test_list_own_tickets_scopes_to_requester_and_passes_through_paging` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC3 / FR-3 | Empty `subject` → `422 validation-failed`, no ticket created | Integration | `test_create_ticket_invalid_input_returns_422_and_creates_nothing[empty_subject]` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC3 / FR-3 | `subject` over 150 chars → `422 validation-failed`, no ticket created | Integration | `test_create_ticket_invalid_input_returns_422_and_creates_nothing[subject_over_150_chars]` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC3 / FR-3 | `body` over 5000 chars → `422 validation-failed`, no ticket created | Integration | `test_create_ticket_invalid_input_returns_422_and_creates_nothing[body_over_5000_chars]` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC3 / FR-3 | Unknown `category` → `422 validation-failed` | — (gap) | — | Not testable: OD-3's value list is unresolved (stakeholder decision, not inferable) — see `US-4.1-test-strategy.md` Known Gaps. |
| ST-AC4 / FR-4 | Same `Idempotency-Key` retried within 24h with the same body → `201` with the *original* ticket, only one row exists | Integration | `test_create_ticket_replay_same_key_returns_original_ticket` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC4 / FR-4 | Same key reused with a different body → `422 idempotency-key-reuse`, still only one row | Integration | `test_create_ticket_key_reused_with_different_body_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC4 / FR-4 (OD-2 resolution) | Missing `Idempotency-Key` header → `422 validation-failed` | Integration | `test_create_ticket_missing_idempotency_key_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC4 / FR-4 | Replay branch: no second insert, no second audit write, rate limit never consulted | Unit | `test_create_ticket_replay_returns_original_ticket_without_second_write` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC4 / FR-4 | Reuse-with-different-body branch raises before any write | Unit | `test_create_ticket_idempotency_key_reused_with_different_body_raises` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC4 / FR-4 (DB design DR-3 fix, poll-exhaustion path) | Poll budget exhausted on the mid-flight race → propagates unhandled (framework default `500`, no new contract slug), no write | Unit | `test_create_ticket_idempotency_poll_exhausted_propagates_unhandled` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC5 / FR-5 | No token → `401` (`POST`) | Integration | `test_create_ticket_no_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 | No token → `401` (`GET`) | Integration | `test_list_own_tickets_no_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 | Malformed token → `401` (`POST`) | Integration | `test_create_ticket_malformed_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 | Expired token → `401` (`POST`) | Integration | `test_create_ticket_expired_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 | Revoked session → `401` (`POST`) | Integration | `test_create_ticket_revoked_session_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 (added attempt 3) | Malformed token → `401` (`GET`) | Integration | `test_list_own_tickets_malformed_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 (added attempt 3) | Expired token → `401` (`GET`) | Integration | `test_list_own_tickets_expired_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 (added attempt 3) | Revoked session → `401` (`GET`) | Integration | `test_list_own_tickets_revoked_session_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC5 / FR-5 | Authenticated but `status="deactivated"` → `403 account-deactivated` | Integration | `test_create_ticket_deactivated_account_returns_403` | `tests/integration/modules/support/test_support_router.py` — now passing (`IMPLEMENTATION` attempt 1, third pass, added the check to `service.py`). |
| ST-AC5 / FR-5 (added attempt 4) | Service-level: `get_account_status_for_user` returns `"deactivated"` → `AccountDeactivatedError` raised before the idempotency claim, no repository/audit write | Unit | `test_create_ticket_deactivated_account_raises_before_any_write` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC5 / FR-5 (added attempt 4) | Service-level: `get_account_status_for_user` returns `"active"` → creation proceeds | Unit | `test_create_ticket_active_account_proceeds` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC6 / FR-6 | 6th creation within the hour → `429` with `Retry-After`; the customer's existing 5 open tickets are unaffected | Integration | `test_create_ticket_sixth_in_hour_returns_429_and_existing_tickets_unaffected` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC6 / FR-6 (idempotency-key release, found mid-build) | Over-limit branch raises with `Retry-After` header, no ticket created, the claimed idempotency key is released so a retry does not poll a stuck envelope | Unit | `test_create_ticket_rate_limit_exceeded_raises_429_and_releases_the_claimed_key` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC6 / FR-6 | At-limit boundary (5th of 5) still succeeds | Unit | `test_create_ticket_within_rate_limit_succeeds` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC7 / FR-7 | `attachment_id` owned by a different user → `422 attachment-not-owned` | Integration | `test_create_ticket_attachment_owned_by_other_user_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC7 / FR-7 | `attachment_id` already bound to another ticket → `422 attachment-not-owned` (same slug, indistinguishable) | Integration | `test_create_ticket_attachment_already_bound_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC7 / FR-7 | `attachment_id` unknown/does not exist → `422 attachment-not-owned` (same slug, indistinguishable) | Integration | `test_create_ticket_attachment_unknown_id_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC7 / FR-7 | Owned, unbound `attachment_id` → bound to the new ticket, persisted | Integration | `test_create_ticket_attachment_owned_and_unbound_is_bound_and_immutable` | `tests/integration/modules/support/test_support_router.py` |
| ST-AC7 / FR-7 | All three failure causes raise the identical error at the service layer (indistinguishability proven where the branching actually happens) | Unit | `test_create_ticket_attachment_not_owned_raises_indistinguishable_error` (parametrized ×3) | `tests/unit/modules/support/test_support_service.py` |
| ST-AC7 / FR-7 | Owned, unbound attachment is bound; binding call recorded | Unit | `test_create_ticket_attachment_owned_and_unbound_is_bound` | `tests/unit/modules/support/test_support_service.py` |
| ST-AC7 / FR-7 (24h unbound purge, added attempt 5) | `AttachmentRepository.find_unbound_older_than`/`.purge` (the sweep `scripts/purge_unbound_attachments.py` composes) deletes an unbound attachment past the 24h cutoff | Integration | `test_purge_unbound_attachments_deletes_unbound_attachment_older_than_24h` | `tests/integration/scripts/test_purge_unbound_attachments.py` |
| ST-AC7 / FR-7 (24h unbound purge, added attempt 5) | An unbound attachment within the 24h window survives the sweep | Integration | `test_purge_unbound_attachments_leaves_unbound_attachment_within_24h_untouched` | `tests/integration/scripts/test_purge_unbound_attachments.py` |
| ST-AC7 / FR-7 (24h unbound purge, added attempt 5) | A bound attachment past 24h is never purged, regardless of age | Integration | `test_purge_unbound_attachments_leaves_bound_attachment_older_than_24h_untouched` | `tests/integration/scripts/test_purge_unbound_attachments.py` |
| ST-AC7 / FR-7 (24h unbound purge, added attempt 5) | `purge([])` (no candidates) deletes nothing | Integration | `test_purge_unbound_attachments_purge_of_empty_candidate_list_deletes_nothing` | `tests/integration/scripts/test_purge_unbound_attachments.py` |

## Gaps Not Covered (carried forward, not invented here)

- **ST-AC3's "unknown `category`" sub-case** — OD-3's value list is an
  unresolved stakeholder decision (`docs/decisions/US-4.1-open-decisions.md`);
  no enum exists to test an "unknown" value against. Add the test once OD-3
  resolves.

`app/modules/audit/service.py`'s own `record_event` unit test (plan Risk 1)
was a v1 gap; closed at attempt 4 — see `tests/unit/modules/audit/
test_audit_service.py::test_record_event_writes_without_committing` and
`::test_record_event_actor_role_none_when_no_roles_held`.
`scripts/purge_unbound_attachments.py`'s purge sweep (ST-AC7's last clause)
was open since v1; closed this pass (attempt 5) — see the ST-AC7 rows above.
