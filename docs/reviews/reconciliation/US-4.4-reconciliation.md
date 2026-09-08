---
artifact_type: reconciliation
story: US-4.4
version: 1
status: APPROVED
created_at: "2026-09-07T22:50:00Z"
updated_at: "2026-09-07T22:50:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.4-spec-review.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-db-design.md
    version: 1
  - path: docs/designs/database/US-4.4-entity-model.md
    version: 1
  - path: docs/reviews/designs/US-4.4-design-review.md
    version: 1
  - path: docs/impact-analysis/US-4.4-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.4-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.4-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-4.4-plan-review.md
    version: 1
  - path: docs/tests/US-4.4-test-strategy.md
    version: 2
  - path: docs/tests/US-4.4-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-4.4-test-generation-report.md
    version: 2
  - path: docs/evidence/US-4.4-implementation-report.md
    version: 2
  - path: docs/verification/US-4.4-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-4.4-security-review.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
  - path: docs/catalog/US-4.4-pipeline-status.md
    version: 2
supersedes: null
---

# Reconciliation Report: Agent Ticket Queue & Assignment

**Story ID:** US-4.4
**Reviewed:** 2026-09-07
**Overall Verdict:** PASS

## Summary

Every Acceptance Criterion in `US-4.4-spec.md` (v1) — AQ-AC1 through AQ-AC10 — has exactly one row in `US-4.4-ac-test-matrix.md` (v1), a named test function confirmed by direct read to exist at the stated path (both `tests/unit/modules/support/test_support_service.py` and `tests/integration/modules/support/test_support_router.py`), and a test body confirmed to assert the AC's specific stated behavior — status code, persisted `assignee_id` value, audit-row `event`/`actor_id`/`target_id`, filter-scoped result sets, and the negative/no-op cases (no repository call before a permission failure, no audit/commit on a concurrency loss, unchanged `assignee_id` after a rejected assign) — not merely proximity to the right endpoint. Direct reading of `app/modules/support/service.py`, `router.py`, `exceptions.py`, and `schemas.py` against the approved spec found no drift: the check order (permission gate before lookup, FR-7), the `IS NOT DISTINCT FROM` conditional-update mechanism (FR-10), the `problem+json` type slugs (`validation-failed`, `insufficient-permission`, `invalid-state-transition`, `assignment-conflict`), and the `AgentTicketRead`/`AgentTicketStateRead` schema split (OD-1) all match what was approved, and the `repository.py` `assignee_id` -> `new_assignee_id` parameter rename found mid-pipeline (`docs/catalog/US-4.4-pipeline-status.md` v2) is fully reconciled on both sides (service call site and both test suites all use `new_assignee_id`).

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| AQ-AC1 | "Given an agent holding tickets:read When GET /v1/support/tickets is called Then respond 200 with every non-closed ticket regardless of requester, ordered oldest-updated first And each item carries assignee_id And the response pages by cursor with no total count" | Yes | Unit: `test_list_agent_queue_passes_status_category_and_cursor_through_unresolved`, `test_list_agent_queue_item_carries_assignee_id`. Integration: `test_list_own_tickets_agent_scope_caller_returns_403` (updated to assert 200), `test_list_own_tickets_agent_branch_orders_oldest_updated_first`, `test_list_own_tickets_agent_branch_excludes_closed_by_default`, `test_list_own_tickets_agent_branch_paginates_by_cursor` | Yes | Yes | Integration test asserts three seeded tickets with distinct explicit `updated_at` values come back oldest-first (`ids.index` ordering), every item's key-set equals `_AGENT_TICKET_READ_FIELDS` (includes `assignee_id`), and `"total"`/`"count"` are absent from the envelope — not merely "200 with an items list". |
| AQ-AC2 | "Given an agent holding tickets:read When GET /v1/support/tickets is called with status, category or assignee_id Then only matching tickets are returned And assignee_id=me resolves to the calling agent's own id And assignee_id=none returns only unassigned tickets And status=closed is the only way a closed ticket appears" | Yes | Unit: `test_list_agent_queue_assignee_id_me_resolves_to_calling_agent`, `test_list_agent_queue_assignee_id_none_filters_unassigned`, `test_list_agent_queue_assignee_id_specific_uuid_passed_through`, `test_list_agent_queue_malformed_assignee_id_raises_422`, `test_list_agent_queue_invalid_cursor_raises_422`, `test_list_agent_queue_out_of_range_limit_raises_422`. Integration: `test_list_own_tickets_agent_branch_filters_by_category`, `test_list_own_tickets_agent_branch_assignee_id_me_returns_only_own`, `test_list_own_tickets_agent_branch_assignee_id_none_returns_only_unassigned`, `test_list_own_tickets_agent_branch_assignee_id_specific_uuid`, `test_list_own_tickets_agent_branch_malformed_assignee_id_returns_422`, `test_list_own_tickets_agent_branch_status_closed_is_the_only_way_closed_appears` | Yes | Yes | Each filter case seeds a matching and a non-matching ticket and asserts the matching id is present while the non-matching one is absent (positive and negative assertion together), including the `me`-resolves-to-caller and `none`-means-unassigned semantics specifically. |
| AQ-AC3 | "Given an agent holding tickets:write and a ticket with no assignee When POST /v1/support/tickets/{id}/assign is called with another agent's id Then respond 200 with assignee_id set And an audit entry is written (event=ticket_assigned, actor=the caller, target=the ticket) And re-assigning an already-assigned ticket replaces the assignee and audits the change" | Yes | Unit: `test_assign_ticket_happy_path_sets_assignee_and_audits_and_commits`, `test_assign_ticket_self_assign_follows_identical_success_path`, `test_assign_ticket_reassign_already_assigned_replaces_and_audits`, `test_assign_ticket_commits_exactly_once`. Integration: `test_assign_ticket_returns_200_and_persists_assignee_with_audit_row`, `test_assign_ticket_reassign_replaces_assignee_and_audits_the_change`, `test_assign_ticket_self_assign_succeeds` | Yes | Yes | Integration test queries the real `audit_log` table for `target_id`/`event="ticket_assigned"` and asserts `actor_id == caller.id`; re-assign test asserts the persisted `assignee_id` moved to the second target and exactly one new audit row exists (not two, closing the earlier off-by-one defect). |
| AQ-AC4 | "Given a ticket with an assignee When DELETE /v1/support/tickets/{id}/assign is called by a tickets:write holder Then respond 200 with assignee_id null And an audit entry is written (event=ticket_unassigned)" | Yes | Unit: `test_unassign_ticket_happy_path_clears_assignee_and_audits_and_commits`, `test_unassign_ticket_already_unassigned_is_idempotent_200`. Integration: `test_unassign_ticket_returns_200_and_clears_assignee_with_audit_row`, `test_unassign_ticket_already_unassigned_is_idempotent_200` | Yes | Yes | Integration test asserts persisted `assignee_id is None` and a `ticket_unassigned` audit row with `actor_id == caller.id`. |
| AQ-AC5 | "Given a customer holding no tickets:* scope When GET /v1/support/tickets is called Then they receive only their own tickets, exactly as US-4.1 specified And no response field exposes assignee_id" | Yes | Integration: `test_list_own_tickets_customer_branch_response_has_no_assignee_id_field` (byte-identical field-set assertion); pre-existing, unmodified `test_list_own_tickets_returns_only_callers_tickets_newest_first` (regression, confirmed still present at line 299) | Yes | Yes | `set(body["items"][0].keys()) == _CUSTOMER_TICKET_READ_FIELDS` is a byte-for-byte field-set equality, stronger than "no `assignee_id` key present" — matches implementation_plan.md Risk 1's explicit requirement. No unit test is needed: `list_own_tickets` (the customer-branch service method) is unmodified by this story, so its absence from the unit suite is not a gap. |
| AQ-AC6 | "Given a customer holding no tickets:read When GET /v1/support/tickets is called with assignee_id or another agent's filter Then the filter is ignored and only their own tickets are returned — never another customer's" | Yes | Integration: `test_list_own_tickets_customer_branch_ignores_agent_only_query_params` | Yes | Yes | Seeds the caller's own ticket and another customer's ticket, then asserts the result set is identical (`{mine.id}`) with and without agent-only query params present, and that the malformed-for-agent-purposes `assignee_id` value produces `200`, not `422`. |
| AQ-AC7 | "Given a caller without tickets:write When POST or DELETE /v1/support/tickets/{id}/assign is called Then respond 404 for a customer ... And 403 ... for a tickets:read-only agent" | Yes | Unit: `test_assign_and_unassign_customer_caller_raises_404_before_any_lookup`, `test_assign_and_unassign_read_only_agent_raises_403_before_any_lookup`, `test_assign_and_unassign_unknown_ticket_raises_404`. Integration: `test_assign_ticket_customer_returns_404_indistinguishable_from_unknown_id`, `test_assign_ticket_read_only_agent_returns_403`, `test_unassign_ticket_customer_returns_404`, `test_unassign_ticket_read_only_agent_returns_403`, `test_assign_and_unassign_auth_matrix_returns_401` | Yes | Yes | The 404-indistinguishability test explicitly asserts the response bodies for an existing-but-forbidden ticket and a genuinely unknown ticket are equal (minus `instance`), proving the id-existence-hiding half of the AC, not just the status code. Unit tests additionally assert zero repository calls were made before the 404/403 raise, proving the "before any lookup" check-order claim. |
| AQ-AC8 | "Given an assign request naming a user who holds no tickets:write ... Then respond 422 ..." (plus OD-4's adopted deactivated-target default) | Yes | Unit: `test_assign_ticket_target_lacks_tickets_write_raises_422`, `test_assign_ticket_target_deactivated_raises_422`. Integration: `test_assign_ticket_target_lacking_tickets_write_returns_422`, `test_assign_ticket_deactivated_target_returns_422` | Yes | Yes | Integration test for the missing-scope case additionally re-reads the ticket and asserts `assignee_id is None` afterward (the rejected write never landed). Unit test for the deactivated case asserts the account-status check ran against the *target* id (`target_id in user_service.status_calls`), not the caller's own — proving OD-4's mechanism, not just its outcome. |
| AQ-AC9 | "Given a ticket in status \"closed\" When POST .../assign is called Then respond 409 ..." | Yes | Unit: `test_assign_and_unassign_closed_ticket_raises_409` (parametrized; the `assign_ticket` case is AQ-AC9). Integration: `test_assign_ticket_closed_ticket_returns_409` | Yes | Yes | Integration test asserts `409`, the `invalid-state-transition` type slug, and — via a DB refresh — that `assignee_id` stayed `None` (the rejected assign did not partially apply). |
| AQ-AC10 | "Given two agents assigning the same unassigned ticket simultaneously ... exactly one wins ... the loser receives 409, not a silent overwrite" | Yes | Unit: `test_assign_ticket_concurrency_loss_raises_409_assignment_conflict`. Integration: `test_assign_ticket_repository_conditional_update_rejects_stale_expected_value` | Yes | Yes | The unit test proves the service-layer `None` -> `AssignmentConflictError` mapping (zero audit calls, zero commits on loss). The integration test drives `TicketRepository.assign_ticket` directly with two calls sharing a stale `expected_assignee_id=None`, proving the first wins and returns the updated row while the second returns `None` and the ticket's persisted `assignee_id` is the winner's — a genuine proof of the `IS NOT DISTINCT FROM` conditional-update mechanism, with an explicit, well-reasoned note in the test itself for why an HTTP-level two-request race (this project's usual concurrency-test pattern) cannot prove this for `assign` under the shared-`db_session` fixture. This is a deliberate, disclosed test-mechanism substitution, not a coverage gap. |

## Non-AC Findings (informational, does not affect verdict)

- **DR-3 (`updated_at` preservation)** — `test_assign_ticket_does_not_change_updated_at` and `test_unassign_ticket_does_not_change_updated_at` seed an explicit distinct past `updated_at` and assert it is byte-identical after the operation, correctly avoiding the frozen-`func.now()`-per-transaction trap the tests' own comments call out. This is a plan-level architectural decision (implementation_plan.md Architectural Change #9), not a numbered AC, and is fully proven.
- **Index coverage (DR-1)** — `test_agent_queue_default_query_uses_partial_index` disables `enable_seqscan` and asserts the partial index's name appears in the `EXPLAIN` output for the literal `status != 'closed'` predicate, correctly avoiding a false pass from PostgreSQL's empty-table cost model.
- **`repository.py` parameter rename** — `docs/catalog/US-4.4-pipeline-status.md` (v2) records that `assign_ticket`'s keyword-only parameter was found renamed mid-pipeline (`assignee_id` -> `new_assignee_id`) after both test suites and `service.py`'s call site were already written against the new name; direct read of `service.py:555-557` and both test files' `assign_ticket(...)`/`repository.assign_ticket(...)` call sites confirms all three now agree on `new_assignee_id`. No residual inconsistency found.
- **Security-reviewer's [Low] finding** — a stale "not yet human-confirmed" comment on OD-3/OD-4 remains in two test docstrings (`test_unassign_ticket_already_unassigned_is_idempotent_200`'s neighboring block and `test_assign_ticket_deactivated_target_returns_422`'s arrange comment) even though `docs/decisions/US-4.4-open-decisions.md` (v1) shows all four ODs `APPROVED` (confirmed directly: OD-2/OD-3/OD-4's own **Resolution** lines and the file's "Verdict input" section, lines 78-91). The *implemented behavior* in both cases matches the approved decision exactly (OD-3: unassign-on-closed returns 409; OD-4: a deactivated target is rejected with 422) — this is a comment-freshness gap already flagged by `security-reviewer`, not a functional or spec-compliance defect, and does not change any test's validity or this stage's verdict.
- **Security-reviewer's [Medium] finding, carried forward** — `assign_ticket`'s two `ValidationFailedError` branches (`service.py:531-553`) use distinguishable messages ("does not hold tickets:write" vs. "account is deactivated"), letting an authenticated `tickets:write` holder learn a target's account status via message text. Not a §7 violation, not spec drift (OD-4 approves the 422 outcome, not the specific wording); carried forward for a future tightening pass, not this stage's to fix.
- **FR-1 tiebreak, confirmed first-hand** — `repository.py:158`'s `list_for_agent_queue` orders `Ticket.updated_at.asc(), Ticket.id.asc()` exactly matching FR-1's "ordered oldest-`updated_at` first (stable-tiebroken by `id`)"; read directly rather than inherited from `pipeline-status`/`security-review`. No test exercises the `id` tiebreak itself (every ordering test seeds three tickets with distinct `updated_at` values), and no agent-branch test mixes tickets from two different requesters in one response to prove "regardless of requester" against an ownership filter that could otherwise silently exist — `list_for_agent_queue` has no `requester_id` predicate at all, so this is not a coverage gap against any AC's literal text, but a tightening opportunity for `test-writer` if revisited (non-blocking).

## Spec Drift

None found. `service.py`'s `assign_ticket`/`unassign_ticket` (lines 500-613) implement the exact check order the spec/API design call for (permission gate before any ticket lookup — FR-7; closed-ticket check before target validation — FR-9/OD-3; target-scope check then target-account-status check — FR-8/OD-4; conditional update before audit before commit — FR-10), and `exceptions.py`'s four relevant `type_slug` values (`validation-failed`, `insufficient-permission`, `invalid-state-transition`, `assignment-conflict`) match the spec's stated `.../errors/...` types verbatim. `router.py` declares `response_model=TicketListResponse | AgentTicketListResponse` on the single `GET` route (line 62) and separate `response_model=AgentTicketStateRead` on both new routes (lines 108, 136), matching OD-1's adopted schema split; `TicketRead`/`TicketListResponse`/`TicketStateRead` were independently confirmed unchanged by `implementation-verifier` and `security-reviewer`, and this review found nothing to add to that.

## Verdict Rationale

Every AC (AQ-AC1 through AQ-AC10) has exactly one traceability-matrix row, a test function confirmed by direct read to exist at its stated path, and a test body confirmed by direct read to assert the AC's specific stated behavior — not merely proximity to the right endpoint — and no drift was found between the approved spec and the shipped `app/modules/support/` code. Per the verdict rules, this is PASS.
