---
artifact_type: traceability
story: US-5.5
version: 2
status: ARCHIVED
created_at: "2026-09-14T13:30:00Z"
updated_at: "2026-09-14T16:45:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/reviews/designs/US-5.5-design-review.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.5-task-breakdown.md
    version: 2
  - path: docs/tests/US-5.5-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.5-implementation-report.md
    version: 3
  - path: docs/verification/US-5.5-implementation-verification.md
    version: 2
  - path: docs/reviews/security/US-5.5-security-review.md
    version: 2
supersedes: docs/reconciliation/US-5.5-traceability.md (v1)
---

# Traceability: Agent Console (Frontend) — US-5.5

End-to-end AC → specification → design → test → code mapping. Test function names are **as-built**
(confirmed present in the current working tree by direct read this session), not the prescriptive names
from `docs/tests/US-5.5-ac-test-matrix.md` v1 — that matrix's own header states test-writer wrote no test
source for this Story and frontend-builder named every function independently during `IMPLEMENTATION`.
This is a re-run: every row below was re-verified against the current working tree, not carried forward
from v1 on trust — line numbers and function sets shifted from v1 because `frontend-builder`'s attempt 3
added five new/strengthened tests closing v1's five named gaps. See the companion reconciliation report,
`docs/reviews/reconciliation/US-5.5-reconciliation.md` v2, for full method and the AG-AC7 special
determination. `api_design`/`database_design`/`entity_model` are `NOT_APPLICABLE` for this Story
(frontend-only, consumes US-4.4's already-shipped contract) — no design column applies below.

Coverage legend: **Full** = every clause of the AC text is asserted.

| AC ID | Spec (FR) | Plan (Architectural Change) | Test file(s) : function(s) | Production code | Coverage |
|---|---|---|---|---|---|
| AG-AC1 | FR-1 | Change 3, Files To Create (`useAgentTickets.ts`, `AgentTicketQueueScreen.tsx`) | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_renders_every_column_for_a_ticket_row`, `::test_agent_ticket_queue_screen_renders_a_truncated_uuid_for_an_assigned_ticket`, `::test_agent_ticket_queue_screen_renders_the_explicit_empty_result_state`, `::test_agent_ticket_queue_screen_status_and_category_filters_re_request_and_reset_the_cursor`, `::test_agent_ticket_queue_screen_me_and_none_presets_are_mutually_exclusive`, `::test_agent_ticket_queue_screen_a_raw_uuid_specific_agent_filter_clears_any_active_preset`, `::test_agent_ticket_queue_screen_load_more_appends_the_second_page`, `::test_agent_ticket_queue_screen_renders_tickets_in_the_servers_returned_order_and_shows_no_total_count_or_page_number` (new, attempt 3 — closes v1's ordering/no-count gap), `::test_format_assignee_id_null_renders_the_literal_unassigned_text`, `::test_format_assignee_id_truncates_a_uuid_to_its_first_8_hex_characters` | `frontend/src/screens/AgentTicketQueueScreen.tsx`, `frontend/src/hooks/useAgentTickets.ts`, `frontend/src/screens/agentTicketHelpers.ts` | Full |
| AG-AC2 | FR-2 | Change 3, Change 7, Change 8 | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_assign_to_me_calls_assign_endpoint_with_the_agents_own_id`, `::test_agent_ticket_queue_screen_assign_to_another_agent_raw_uuid_calls_the_assign_endpoint`, `::test_agent_ticket_queue_screen_unassign_calls_delete_assign_endpoint`, `::test_agent_ticket_queue_screen_assign_409_closed_ticket_renders_problem_json_detail`, `::test_agent_ticket_queue_screen_assign_422_assignee_not_an_agent_renders_problem_json_detail`, `::test_agent_ticket_queue_screen_assign_to_me_updates_the_row_to_reflect_the_new_assignee_after_success` (new, attempt 3 — closes v1's row-reflects-new-assignee gap), `::test_agent_ticket_queue_screen_navigates_with_assignee_id_navigation_state_on_row_click` | `frontend/src/hooks/useAssignTicket.ts`, `useUnassignTicket.ts`, `frontend/src/screens/AgentTicketQueueScreen.tsx` | Full |
| AG-AC3 | FR-3 | Change 7 | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_renders_header_fields_and_reply_thread`, `::test_agent_ticket_detail_screen_renders_a_direct_url_entrys_assignee_as_unknown_stale`, `::test_agent_ticket_detail_screen_renders_internal_replies_with_a_distinct_style_and_a_literal_internal_label`, `::test_agent_ticket_detail_screen_load_older_replies_fetches_using_its_own_cursor`; `describeAssignee` unit cases: `::test_describe_assignee_undefined_renders_the_em_dash_placeholder_with_an_aria_label`, `::test_describe_assignee_null_renders_the_literal_unassigned_text_with_no_aria_label`, `::test_describe_assignee_a_uuid_truncates_to_its_first_8_hex_characters` | `frontend/src/screens/AgentTicketDetailScreen.tsx`, `frontend/src/screens/agentTicketHelpers.ts` (`describeAssignee`) | Full |
| AG-AC4 | FR-4 | Change 2 (Risk 2 mitigation) | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_composer_defaults_to_public_and_sends_the_chosen_visibility`, `::test_agent_ticket_detail_screen_submitting_an_internal_note_sends_visibility_internal_and_renders_it_internally` (strengthened, attempt 3 — now explicitly asserts the header still reads "open," closing v1's no-status-change gap), `::test_agent_ticket_detail_screen_visibility_never_leaks_public_again_after_an_internal_submission`, `::test_agent_ticket_detail_screen_public_reply_invalidates_the_ticket_detail`; `hooks/useReplyToTicket.test.ts` visibility cases | `frontend/src/screens/AgentTicketDetailScreen.tsx`, `frontend/src/hooks/useReplyToTicket.ts` | Full |
| AG-AC5 | FR-5 | Files To Create (`useResolveTicket.ts`) | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_resolve_from_open_calls_resolve_endpoint_and_reflects_resolved` (`it.each` over `open`/`waiting_on_support`/`waiting_on_customer`), `::test_agent_ticket_detail_screen_resolve_blocks_submission_client_side_on_an_empty_note`, `::test_agent_ticket_detail_screen_resolve_blocks_submission_client_side_on_a_whitespace_only_note`, `::test_agent_ticket_detail_screen_resolve_blocks_submission_client_side_on_a_note_over_5000_characters` (new, attempt 3 — closes v1's 5000-char upper-bound gap), `::test_agent_ticket_detail_screen_resolve_409_on_closed_ticket_renders_problem_json_detail`; `hooks/useResolveTicket.test.ts` unit cases | `frontend/src/hooks/useResolveTicket.ts`, `frontend/src/screens/AgentTicketDetailScreen.tsx` | Full |
| AG-AC6 | FR-6, FR-7 | Change 5 | `screens/AgentTicketDetailScreen.test.tsx::test_offered_agent_actions_for_status_open_returns_the_exact_offered_set` (`it.each`, all five statuses), `::test_offered_agent_actions_for_status_an_unrecognized_status_offers_no_actions_fail_closed`, `::test_agent_ticket_detail_screen_status_open_wires_offered_actions_to_what_is_actually_rendered` (`it.each`, all five statuses), `::test_agent_ticket_detail_screen_disables_every_write_control_when_tickets_write_is_absent`, `::test_agent_ticket_detail_screen_a_detail_originated_assign_also_invalidates_the_queue`; `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_disables_every_write_control_when_tickets_write_is_absent` | `frontend/src/screens/agentTicketHelpers.ts` (`offeredAgentActionsForStatus`), `AgentTicketDetailScreen.tsx`, `AgentTicketQueueScreen.tsx` | Full — verified to match FR-6's status table field-by-field |
| AG-AC7 | FR-8 | (no dedicated Architectural Change; reuses existing `getErrorKind`/`getErrorMessage`/`getFieldErrors`/`FieldError`) | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_assign_409_closed_ticket_renders_problem_json_detail`, `::test_agent_ticket_queue_screen_assign_422_assignee_not_an_agent_renders_problem_json_detail`, `::test_agent_ticket_queue_screen_assign_422_maps_the_errors_array_onto_the_assignee_id_field` (new, attempt 3 — closes v1's blocking gap), `::test_agent_ticket_queue_screen_a_malformed_raw_uuid_filter_renders_the_422_inline`; `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_4xx_problem_json_renders_mapped_detail_with_no_raw_json`, `::test_agent_ticket_detail_screen_422_validation_failed_maps_the_errors_array_onto_the_matching_form_fields` (new, attempt 3) | `frontend/src/screens/AgentTicketQueueScreen.tsx`, `AgentTicketDetailScreen.tsx` — both now import/call `getFieldErrors` (`frontend/src/components/apiErrorHelpers.ts`, unmodified) and render `FieldError` (`components/FieldError.tsx`, unmodified) | Full — both clauses independently tested (detail-only path on a 409/403 with no `errors[]` present; field-mapping path on a 422 with `errors[]`); the AC text names no requirement that both co-render on one response, and the suppress-detail-when-a-field-error-renders behavior is the established, non-drifting convention already used on 7 pre-existing screens (see `docs/reviews/reconciliation/US-5.5-reconciliation.md` v2's Special Determination) |
| AG-AC8 | FR-9 | (reuses `useRetryAfterCountdown.ts` unchanged) | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_reply_429_shows_retry_time_disables_submit_and_fires_exactly_once` | `frontend/src/screens/AgentTicketDetailScreen.tsx`, `frontend/src/hooks/useRetryAfterCountdown.ts` (reused, unmodified) | Full |
| AG-AC9 | FR-10 | — | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_network_error_shows_retry_capable_error_state`, `::test_agent_ticket_queue_screen_5xx_response_shows_retry_capable_error_state`; `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_network_error_shows_retry_capable_error_state`, `::test_agent_ticket_detail_screen_5xx_response_shows_retry_capable_error_state` | `frontend/src/screens/AgentTicketQueueScreen.tsx`, `AgentTicketDetailScreen.tsx`, `frontend/src/components/ErrorState.tsx` (reused) | Full |

## FR-11 (no corresponding AC — routing/navigation, per spec v2's own Traceability Matrix)

| Spec (FR) | Plan (Architectural Change) | Test file(s) : function(s) | Production code | Coverage |
|---|---|---|---|---|
| FR-11 | Change 4 | `routes/AppRoutes.test.tsx::test_app_routes_agent_tickets_renders_agent_ticket_queue_screen`, `::test_app_routes_agent_tickets_redirects_unauthenticated_visitor_to_login`, `::test_app_routes_agent_tickets_id_renders_agent_ticket_detail_screen`, `::test_app_routes_agent_tickets_id_redirects_unauthenticated_visitor_to_login`; `layouts/AppShell.test.tsx::test_app_shell_renders_the_agent_queue_nav_entry_when_scopes_include_tickets_read`, `::test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read_scope` | `frontend/src/routes/AppRoutes.tsx`, `frontend/src/layouts/AppShell.tsx` | Full for route registration and individual scope-gating; no single test asserts both the `/tickets` and `/agent/tickets` nav entries render together in one shell (non-blocking — FR-11 traces to no AC, unchanged from v1) |

## Non-AC coverage confirmed present (NFR / Enforcement Matrix rows, not reconciled against a numbered AC)

| Row | Test | Status |
|---|---|---|
| a11y — queue | `AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_has_no_detectable_accessibility_violations` | Present |
| a11y — detail | `AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_has_no_detectable_accessibility_violations` | Present |
| Plain-text rendering (no `dangerouslySetInnerHTML`) | `AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_html_bearing_reply_body_renders_as_escaped_text_and_never_executes` | Present |
| Queue table column-header association | `AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_table_cells_are_associated_with_column_headers` | Present |
| Forced-403, detail screen | `AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_4xx_problem_json_renders_mapped_detail_with_no_raw_json` (uses 403 as its example status) | Present |
| Forced-403, queue screen | — | **Absent** (Low, non-blocking; carried forward unchanged from v1/`implementation-verifier`) |

## Summary

All 9 ACs (AG-AC1 through AG-AC9) now have Full coverage against their stated behavior, independently
re-verified against the current working tree this session. Attempt 1's sole blocking gap (AG-AC7's 422
`errors[]`-to-form-field mapping) and all four non-blocking gaps (AG-AC1, AG-AC2, AG-AC4, AG-AC5) are
confirmed closed. See `docs/reviews/reconciliation/US-5.5-reconciliation.md` v2 for full findings, the
AG-AC7 special determination on the detail/field-error suppression pattern, and verdict rationale.
