---
artifact_type: traceability
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T22:50:00Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-db-design.md
    version: 1
  - path: docs/tests/US-4.4-ac-test-matrix.md
    version: 1
supersedes: null
---

# Traceability: Agent Ticket Queue & Assignment (US-4.4)

End-to-end mapping from source Acceptance Criterion through specification,
design, test, and shipped code. See
`docs/reviews/reconciliation/US-4.4-reconciliation.md` for the reconciliation
verdict and rationale; this table is the standalone reference `pr-preparer`
and a human reviewer read on its own.

| AC ID | Spec FR | API Design / OpenAPI | DB Design | Test(s) | Code |
|---|---|---|---|---|---|
| AQ-AC1 | FR-1 (Agent Views the Ticket Queue) | `GET /v1/support/tickets` (agent branch), `AgentTicketRead`, `AgentTicketListResponse` (US-4.4-openapi.yaml v1) | `ix_tickets_queue_default_updated_at_id` partial index (`status != 'closed'`, `(updated_at, id)`) | `test_list_agent_queue_passes_status_category_and_cursor_through_unresolved`, `test_list_agent_queue_item_carries_assignee_id`, `test_list_own_tickets_agent_branch_orders_oldest_updated_first`, `test_list_own_tickets_agent_branch_excludes_closed_by_default`, `test_list_own_tickets_agent_branch_paginates_by_cursor`, `test_agent_queue_default_query_uses_partial_index` | `TicketService.list_agent_queue` (`service.py:431`), `TicketRepository.list_for_agent_queue` (`repository.py`), `router.py`'s `list_own_tickets` agent branch (`router.py:65`) |
| AQ-AC2 | FR-2 (Queue Filtering) | `status`/`category`/`assignee_id` query params on `GET /v1/support/tickets` | `ix_tickets_status_updated_at_id`, `ix_tickets_assignee_id_updated_at_id` | `test_list_agent_queue_assignee_id_me_resolves_to_calling_agent`, `test_list_agent_queue_assignee_id_none_filters_unassigned`, `test_list_agent_queue_assignee_id_specific_uuid_passed_through`, `test_list_agent_queue_malformed_assignee_id_raises_422`, `test_list_agent_queue_invalid_cursor_raises_422`, `test_list_agent_queue_out_of_range_limit_raises_422`, `test_list_own_tickets_agent_branch_filters_by_category`, `test_list_own_tickets_agent_branch_assignee_id_me_returns_only_own`, `test_list_own_tickets_agent_branch_assignee_id_none_returns_only_unassigned`, `test_list_own_tickets_agent_branch_assignee_id_specific_uuid`, `test_list_own_tickets_agent_branch_malformed_assignee_id_returns_422`, `test_list_own_tickets_agent_branch_status_closed_is_the_only_way_closed_appears` | `TicketService.list_agent_queue`'s `assignee_id` resolution (`service.py:462-481`), `TicketRepository.list_for_agent_queue` filter predicates |
| AQ-AC3 | FR-3 (Assign a Ticket) | `POST /v1/support/tickets/{id}/assign`, `AssignTicketRequest`, `AgentTicketStateRead` | `Ticket.assignee_id` FK to `users.id`, `ticket_audit_log` | `test_assign_ticket_happy_path_sets_assignee_and_audits_and_commits`, `test_assign_ticket_self_assign_follows_identical_success_path`, `test_assign_ticket_reassign_already_assigned_replaces_and_audits`, `test_assign_ticket_commits_exactly_once`, `test_assign_ticket_returns_200_and_persists_assignee_with_audit_row`, `test_assign_ticket_reassign_replaces_assignee_and_audits_the_change`, `test_assign_ticket_self_assign_succeeds` | `TicketService.assign_ticket` (`service.py:500`), `TicketRepository.assign_ticket`, `router.py:106-110` |
| AQ-AC4 | FR-4 (Unassign a Ticket) | `DELETE /v1/support/tickets/{id}/assign`, `AgentTicketStateRead` | same `assignee_id` column, unconditional clear | `test_unassign_ticket_happy_path_clears_assignee_and_audits_and_commits`, `test_unassign_ticket_already_unassigned_is_idempotent_200`, `test_unassign_ticket_returns_200_and_clears_assignee_with_audit_row` | `TicketService.unassign_ticket` (`service.py:573`), `TicketRepository.unassign_ticket`, `router.py:134-138` |
| AQ-AC5 | FR-5 (Customer Branch Unchanged) | `GET /v1/support/tickets` (customer branch, unchanged `TicketRead`/`TicketListResponse`) | n/a — no schema change to the customer path | `test_list_own_tickets_customer_branch_response_has_no_assignee_id_field`, `test_list_own_tickets_returns_only_callers_tickets_newest_first` (pre-existing, unmodified) | `list_own_tickets`'s customer branch (unmodified), `TicketRead`/`TicketListResponse` (unmodified, `schemas.py:24-46`) |
| AQ-AC6 | FR-6 (Agent-Only Query Parameters Ignored for a Customer Caller) | customer branch declares no `assignee_id`/`category` params of its own | n/a | `test_list_own_tickets_customer_branch_ignores_agent_only_query_params` | `router.py`'s branch-on-`tickets:read` dispatch (`router.py:87-98` per implementation-verification) |
| AQ-AC7 | FR-7 (Assignment Requires `tickets:write`) | `404`/`403` responses on both assign endpoints | n/a | `test_assign_and_unassign_customer_caller_raises_404_before_any_lookup`, `test_assign_and_unassign_read_only_agent_raises_403_before_any_lookup`, `test_assign_and_unassign_unknown_ticket_raises_404`, `test_assign_ticket_customer_returns_404_indistinguishable_from_unknown_id`, `test_assign_ticket_read_only_agent_returns_403`, `test_unassign_ticket_customer_returns_404`, `test_unassign_ticket_read_only_agent_returns_403`, `test_assign_and_unassign_auth_matrix_returns_401` | `TicketNotFoundError`/`InsufficientPermissionError`; permission gate at the top of `assign_ticket`/`unassign_ticket` (`service.py:519-522`, `584-587`) |
| AQ-AC8 | FR-8 (Assignee Must Hold `tickets:write`) | `422 validation-failed` on `POST .../assign` | `RoleServiceProtocol.resolve_scopes_for_user`, `UserServiceProtocol.get_account_status_for_user` (cross-module, OD-4) | `test_assign_ticket_target_lacks_tickets_write_raises_422`, `test_assign_ticket_target_deactivated_raises_422`, `test_assign_ticket_target_lacking_tickets_write_returns_422`, `test_assign_ticket_deactivated_target_returns_422` | `service.py:531-553` (target-scope then target-status check) |
| AQ-AC9 | FR-9 (Assigning a Closed Ticket Is Rejected) | `409 invalid-state-transition` | n/a | `test_assign_and_unassign_closed_ticket_raises_409`, `test_assign_ticket_closed_ticket_returns_409` | `InvalidStateTransitionError(allowed_events=[])` raised in `assign_ticket` (`service.py:528-529`) |
| AQ-AC10 | FR-10 (Concurrent Assignment) | conditional-update NFR ("Concurrency Design", API design) | `Ticket.assignee_id.is_not_distinct_from(...)` conditional `WHERE` | `test_assign_ticket_concurrency_loss_raises_409_assignment_conflict`, `test_assign_ticket_repository_conditional_update_rejects_stale_expected_value` | `TicketRepository.assign_ticket`'s conditional `UPDATE`; `AssignmentConflictError` (`exceptions.py`) mapped from a `None` return (`service.py:558-559`) |

## Non-AC-Anchored Rows (structural / NFR / design-review findings)

| Concern | Test(s) | Code |
|---|---|---|
| FR-4/OD-3: `DELETE .../assign` on a closed ticket also returns 409 | `test_assign_and_unassign_closed_ticket_raises_409` (unassign case), `test_unassign_ticket_closed_ticket_returns_409` | `InvalidStateTransitionError(allowed_events=[])` in `unassign_ticket` (`service.py:593-594`, plus the repository-`WHERE`-backstop at `597-601`) |
| DR-3 (implementation_plan.md Architectural Change #9): assign/unassign must not bump `updated_at` | `test_assign_ticket_does_not_change_updated_at`, `test_unassign_ticket_does_not_change_updated_at` | `TicketRepository.assign_ticket`/`unassign_ticket`'s explicit `updated_at=Ticket.updated_at` in `.values()` |
| DR-1: default agent-queue query must use the partial index, not a sequential scan | `test_agent_queue_default_query_uses_partial_index` | `ix_tickets_queue_default_updated_at_id`, literal `Ticket.status != "closed"` predicate in `list_for_agent_queue` |
| NFR: the retired `reject_agent_queue_access` 403 test must be updated, not deleted | `test_list_own_tickets_agent_scope_caller_returns_403` (same function name, body updated to assert `200`) | `reject_agent_queue_access` and `AgentQueueNotAvailableError` removed from `dependencies.py`/`exceptions.py` |

## Known, Carried-Forward Gaps (not this stage's to resolve)

- **OD-2**: whether `GET /v1/support/tickets/{id}` (`TicketDetailRead`) also gains `assignee_id` for an agent caller. The spec's own drafting default is "no" (the API Contract table is the authoritative, itemized endpoint list); no AC exercises this and no test in the matrix asserts either presence or absence of `assignee_id` on `TicketDetailRead`. `docs/decisions/US-4.4-open-decisions.md` shows OD-2 is now `APPROVED` with this same "no" answer — consistent with what was actually shipped (`TicketDetailRead` unchanged).
- **API design Open Questions #5** (idempotent-no-op `unassign` audit write): `test_unassign_ticket_already_unassigned_is_idempotent_200` (both unit and integration) deliberately asserts only the response shape (`200`, `assignee_id: null`), not whether a fresh audit row is written on a true no-op. `service.py:573-582`'s docstring records the implementation's own choice (a fresh audit entry is written even on a no-op) as "the simpler of the two undecided options" — no FR or AC requires either answer, so this is a disclosed, non-blocking design choice, not a test gap against any AC.
- **Security-reviewer's [Medium] advisory**: the two distinct `ValidationFailedError` messages in `assign_ticket`'s target-validation branches (`service.py:537`, `549`) let an authenticated `tickets:write` holder distinguish "target lacks the scope" from "target is deactivated" via message text alone. This is a non-blocking advisory finding (not a §7 violation, not spec drift — OD-4 approves the 422 *outcome*, not this specific wording) carried forward for a future tightening pass, not a defect in this story's AC compliance.
