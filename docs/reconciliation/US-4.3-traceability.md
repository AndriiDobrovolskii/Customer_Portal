---
artifact_type: traceability
story: US-4.3
version: 1
status: DRAFT
created_at: "2026-09-07T08:00:00Z"
updated_at: "2026-09-07T08:00:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/designs/database/US-4.3-db-design.md
    version: 3
  - path: docs/tests/US-4.3-ac-test-matrix.md
    version: 2
supersedes: null
---

# Traceability: Ticket Resolution (US-4.3)

End-to-end mapping from source Acceptance Criterion through specification,
design, test, and shipped code. See `docs/reviews/reconciliation/US-4.3-reconciliation.md`
for the reconciliation verdict and rationale; this table is the standalone
reference `pr-preparer` and a human reviewer read on its own.

| AC ID | Spec FR | API Design / OpenAPI | DB Design | Test(s) | Code |
|---|---|---|---|---|---|
| TC-AC1 | FR-1 (Agent Resolves a Ticket) | `POST /v1/support/tickets/{id}/resolve`, `ResolveTicketRequest`, `TicketStateRead` (US-4.3-openapi.yaml v2) | `tickets.resolved_at`, `resolution_note String(5000)`, `ck_tickets_resolved_requires_resolution_fields` (db-design.md v3) | `test_resolve_ticket_agent_from_eligible_status_returns_200_and_persists`, `test_resolve_ticket_agent_from_each_eligible_status_succeeds`, `test_resolve_ticket_email_dispatch_failure_does_not_fail_the_request`, `test_resolve_ticket_commits_exactly_once` | `TicketService.resolve_ticket` (`service.py:393`), `EmailSender.send_ticket_resolved_email` (`email.py`) |
| TC-AC2 | FR-2 (Ticket Closed by Requester or Agent) | `POST /v1/support/tickets/{id}/close`, `CloseTicketRequest` | `tickets.closed_at`, `closed_by` (no-FK, OD-7) | `test_close_ticket_requester_returns_200_and_persists_closed_by`, `test_close_ticket_agent_returns_200_and_persists_closed_by_agent`, `test_close_ticket_from_resolved_returns_200`, `test_close_ticket_commits_exactly_once` | `TicketService.close_ticket` (`service.py:456`) |
| TC-AC3 | FR-3 (Auto-Close After the Grace Period) | narrative only (no operation; cron job) | auto-close predicate `resolved_at < now() - interval '7 days'` (strict, OD-4), `SYSTEM_ACTOR_ID` sentinel | `test_auto_close_resolved_past_window_closes_ticket_older_than_7_days`, `test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_untouched`, `test_auto_close_resolved_past_window_leaves_recently_resolved_ticket_untouched`, `test_auto_close_resolved_past_window_leaves_non_resolved_ticket_untouched`, `test_auto_close_resolved_past_window_reopened_ticket_survives`, `test_auto_close_resolved_past_window_returns_one_id_per_ticket_not_a_count`, `test_auto_close_resolved_past_window_is_idempotent_on_rerun`, `test_auto_close_job_writes_one_ticket_auto_closed_audit_row_per_ticket` | `TicketRepository.auto_close_resolved_past_window`, `scripts/auto_close_resolved_tickets.py` |
| TC-AC4 | FR-4 (Reply Reopens a Resolved Ticket) | narrative side-effect on existing US-4.2 `POST .../replies` (api-design.md v2) | reopen guard `resolved_at >= now() - interval '7 days'` (inclusive, OD-4), audit write added per DESIGN_REVIEW v2 DR-4 | `test_create_reply_customer_on_resolved_within_window_writes_reopened_audit_entry`, `test_create_reply_customer_on_resolved_outside_window_makes_no_status_change` | `TicketReplyService.create_reply` (FR-4 branch) |
| TC-AC5 | FR-6 (Illegal Transition Rejected) | `409` responses on `/resolve`, `/close`, `/reopen`; error envelope `allowed_events` field | n/a | `test_transition_endpoints_ineligible_status_returns_409_with_allowed_events`, `test_allowed_events_by_status_matches_the_plan_s_stated_table` | `_ALLOWED_EVENTS_BY_STATUS` (`service.py:49`), `InvalidStateTransitionError` (`exceptions.py`) |
| TC-AC6 | FR-7 (Customer Attempts to Resolve) | `403` response, `insufficient-permission` slug | n/a | `test_resolve_ticket_customer_on_open_ticket_returns_403`, `test_resolve_ticket_customer_on_closed_ticket_returns_409_not_403` (check-order NFR) | `InsufficientPermissionError`; permission check ordered after transition check in `resolve_ticket` |
| TC-AC7 | FR-8 (Acting on Someone Else's Ticket) | `404` response, `not-found` slug | n/a | `test_transition_endpoints_different_customer_returns_404` | `TicketNotFoundError`; ownership check in all three service methods |
| TC-AC8 | FR-9 (Concurrent Resolution) | conditional-update NFR | `TicketRepository.transition_status` scoped `UPDATE ... WHERE status IN (...)` | `test_resolve_ticket_second_concurrent_caller_returns_409_first_note_intact`, `test_resolve_ticket_concurrency_loss_raises_409_not_silent_overwrite` | `TicketRepository.transition_status` |
| TC-AC9 | FR-10 (Missing Resolution Note Rejected) | `422` response, `validation-failed` slug, `resolution_note` `maxLength: 5000` | `resolution_note String(5000)` | `test_resolve_ticket_invalid_resolution_note_returns_422_and_leaves_ticket_unchanged`, plus 5 `ResolveTicketRequest` schema unit tests | `ResolveTicketRequest` (`schemas.py:110`) |
| (no source AC) | FR-5 (Direct Reopen of a Resolved Ticket, OD-3) | `POST /v1/support/tickets/{id}/reopen`, `ReopenTicketRequest` | same reopen guard as FR-4 | `test_reopen_ticket_requester_within_window_returns_200_and_clears_resolved_at`, `test_reopen_ticket_agent_within_window_returns_200`, `test_reopen_ticket_outside_window_returns_409`, `test_reopen_ticket_at_exactly_7_days_boundary_succeeds` | `TicketService.reopen_ticket` (`service.py:498`) |

## Non-AC-Anchored Rows (structural / NFR)

| Concern | Test(s) | Code |
|---|---|---|
| Auth matrix (no token / malformed / expired / revoked × all 3 routes) | `test_transition_endpoints_auth_matrix_returns_401` | shared auth dependency |
| `TicketStateRead` data-minimization (no `closed_by`/`resolution_note`) | `test_ticket_state_read_from_attributes_excludes_closed_by_and_resolution_note`, `test_ticket_state_read_closed_at_present_once_closed` | `TicketStateRead` (`schemas.py:142`) |
| `reason` field on `/close`, `/reopen` (accepted, unconstrained, unpersisted — Open Questions #4) | `test_close_ticket_request_*`, `test_reopen_ticket_request_*` | `CloseTicketRequest.reason`, `ReopenTicketRequest.reason` |

## Known, Carried-Forward Gaps (not this stage's to resolve)

- Resolved-but-expired-not-yet-auto-closed ticket's response on `/resolve`/`/reopen`/reply is undefined by any FR (API_DESIGN Open Questions #1, DESIGN_REVIEW DR-5); tested as the documented `409`-fallthrough default, not an open gap.
- `reason` field's purpose/persistence/audit visibility is unstated by any FR (API_DESIGN Open Questions #4); schema accepts it, nothing asserts persistence because nothing requires it.
- DR-6 (partial index `CREATE INDEX CONCURRENTLY` mechanics) and DR-7 (`reason` maxLength) — Minor, non-blocking, carried since DESIGN_REVIEW.
- `scripts/auto_close_resolved_tickets.py`'s own `main()` wiring (engine/Valkey construction from `get_settings()`) is not exercised by an automated test; the repository predicate and audit composition it calls are tested directly instead.
