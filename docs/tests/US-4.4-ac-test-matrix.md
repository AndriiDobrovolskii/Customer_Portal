---
artifact_type: ac_test_matrix
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T17:07:56Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-entity-model.md
    version: 1
  - path: docs/plans/US-4.4-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.4-task-breakdown.md
    version: 1
supersedes: null
---

# AC → Test Matrix: Agent Ticket Queue & Assignment (US-4.4)

Unit tests live in `tests/unit/modules/support/test_support_service.py`.
Integration tests live in `tests/integration/modules/support/test_support_router.py`.

| AC ID | Summary | Unit test(s) | Integration test(s) |
|---|---|---|---|
| AQ-AC1 | Agent sees the queue: 200, non-closed, oldest-updated first, `assignee_id` on every item, cursor-paginated, no total count | `test_list_agent_queue_passes_status_category_and_cursor_through_unresolved`, `test_list_agent_queue_item_carries_assignee_id` | `test_list_own_tickets_agent_scope_caller_returns_403` (updated: now asserts 200), `test_list_own_tickets_agent_branch_orders_oldest_updated_first`, `test_list_own_tickets_agent_branch_excludes_closed_by_default`, `test_list_own_tickets_agent_branch_paginates_by_cursor` |
| AQ-AC2 | Queue filters: `status`/`category`/`assignee_id`; `me`/`none` resolution; `status=closed` is the only way closed appears | `test_list_agent_queue_assignee_id_me_resolves_to_calling_agent`, `test_list_agent_queue_assignee_id_none_filters_unassigned`, `test_list_agent_queue_assignee_id_specific_uuid_passed_through`, `test_list_agent_queue_malformed_assignee_id_raises_422`, `test_list_agent_queue_invalid_cursor_raises_422`, `test_list_agent_queue_out_of_range_limit_raises_422` | `test_list_own_tickets_agent_branch_filters_by_category`, `test_list_own_tickets_agent_branch_assignee_id_me_returns_only_own`, `test_list_own_tickets_agent_branch_assignee_id_none_returns_only_unassigned`, `test_list_own_tickets_agent_branch_assignee_id_specific_uuid`, `test_list_own_tickets_agent_branch_malformed_assignee_id_returns_422`, `test_list_own_tickets_agent_branch_status_closed_is_the_only_way_closed_appears` |
| AQ-AC3 | Assign: 200 + `assignee_id` set + audit (`ticket_assigned`); re-assign replaces and re-audits | `test_assign_ticket_happy_path_sets_assignee_and_audits_and_commits`, `test_assign_ticket_self_assign_follows_identical_success_path`, `test_assign_ticket_reassign_already_assigned_replaces_and_audits`, `test_assign_ticket_commits_exactly_once` | `test_assign_ticket_returns_200_and_persists_assignee_with_audit_row`, `test_assign_ticket_reassign_replaces_assignee_and_audits_the_change`, `test_assign_ticket_self_assign_succeeds` |
| AQ-AC4 | Unassign: 200 + `assignee_id` null + audit (`ticket_unassigned`) | `test_unassign_ticket_happy_path_clears_assignee_and_audits_and_commits`, `test_unassign_ticket_already_unassigned_is_idempotent_200` | `test_unassign_ticket_returns_200_and_clears_assignee_with_audit_row`, `test_unassign_ticket_already_unassigned_is_idempotent_200` |
| AQ-AC5 | Customer branch unchanged: own tickets only, never exposes `assignee_id` | — (byte-shape assertion is integration-level; unit tests don't touch `list_own_tickets`, which is unmodified by this story) | `test_list_own_tickets_customer_branch_response_has_no_assignee_id_field`; pre-existing, unmodified `test_list_own_tickets_returns_only_callers_tickets_newest_first` (regression, not re-asserted here) |
| AQ-AC6 | Agent-only query params are ignored (never 422) for a customer caller | — | `test_list_own_tickets_customer_branch_ignores_agent_only_query_params` |
| AQ-AC7 | Assignment requires the scope: 404 for a customer (indistinguishable from unknown ticket id), 403 for a `tickets:read`-only agent | `test_assign_and_unassign_customer_caller_raises_404_before_any_lookup`, `test_assign_and_unassign_read_only_agent_raises_403_before_any_lookup`, `test_assign_and_unassign_unknown_ticket_raises_404` | `test_assign_ticket_customer_returns_404_indistinguishable_from_unknown_id`, `test_assign_ticket_read_only_agent_returns_403`, `test_unassign_ticket_customer_returns_404`, `test_unassign_ticket_read_only_agent_returns_403`, `test_assign_and_unassign_auth_matrix_returns_401` |
| AQ-AC8 | Assignee must hold `tickets:write` (422); OD-4's adopted default also rejects a deactivated target | `test_assign_ticket_target_lacks_tickets_write_raises_422`, `test_assign_ticket_target_deactivated_raises_422` | `test_assign_ticket_target_lacking_tickets_write_returns_422`, `test_assign_ticket_deactivated_target_returns_422` |
| AQ-AC9 | Assigning a closed ticket returns 409 invalid-state-transition | `test_assign_and_unassign_closed_ticket_raises_409` (parametrized; the `assign_ticket` case is AQ-AC9 itself) | `test_assign_ticket_closed_ticket_returns_409` |
| AQ-AC10 | Concurrent assignment: exactly one wins, the loser gets 409, never a silent overwrite | `test_assign_ticket_concurrency_loss_raises_409_assignment_conflict` | `test_assign_ticket_repository_conditional_update_rejects_stale_expected_value` (drives `TicketRepository.assign_ticket` directly with a deliberately stale `expected_assignee_id` — see US-4.4-test-strategy.md's "Concurrency-test mechanism" note for why an HTTP-level `real_client`+`db_session` race does not actually prove this for `assign`'s re-assignment-generalized guard) |

## Non-AC coverage (NFR / design-review / plan findings, not a numbered AC)

| Source | Summary | Test(s) |
|---|---|---|
| FR-4 / OD-3 (spec) | `DELETE .../assign` on a closed ticket also returns 409 (not itself an AC — AQ-AC4 is silent on the closed case) | Unit: `test_assign_and_unassign_closed_ticket_raises_409` (the `unassign_ticket` case). Integration: `test_unassign_ticket_closed_ticket_returns_409` |
| implementation_plan.md Architectural Change #9 (DR-3) | `assign`/`unassign` must not change `updated_at` — preserves the "longest-waiting-first" queue ordering | Integration only (a unit fake cannot exercise SQLAlchemy `onupdate` mechanics): `test_assign_ticket_does_not_change_updated_at`, `test_unassign_ticket_does_not_change_updated_at` |
| Enforcement Matrix "Index coverage" / DR-1 | The default agent-queue query must be served by `ix_tickets_queue_default_updated_at_id`, not a sequential scan | Integration: `test_agent_queue_default_query_uses_partial_index` |
| NFR (Removing `reject_agent_queue_access`) | The US-4.1 test asserting the retired 403 must be updated, not deleted | `test_list_own_tickets_agent_scope_caller_returns_403` (same function name, updated body — see US-4.4-test-generation-report.md) |

## Explicitly not covered (gaps, not silently assumed)

- **OD-2** (spec): whether `GET /v1/support/tickets/{id}` (`TicketDetailRead`)
  also gains `assignee_id` for an agent caller. The spec's own drafting
  default is "no" (the API Contract table is the authoritative, itemized
  endpoint list; `GET /{id}` is not in it) — no AC exercises this, and no
  test in this matrix asserts either presence or absence of `assignee_id`
  on `TicketDetailRead`. If OD-2 is reversed at `HUMAN_SPEC_APPROVAL`, this
  matrix has zero rows to update — a new FR and new tests would be needed
  from scratch, not a reversal of an existing one.
- **API design Open Questions #5** (idempotent-no-op `unassign` audit
  write): `test_unassign_ticket_already_unassigned_is_idempotent_200`
  (both unit and integration) deliberately asserts only the response shape
  (200, `assignee_id: null`), not whether a fresh audit row is written on a
  true no-op — no artifact states an answer.
