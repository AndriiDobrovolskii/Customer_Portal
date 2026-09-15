---
artifact_type: ac_test_matrix
story: US-5.5
version: 1
status: ARCHIVED
created_at: "2026-09-14T08:15:00Z"
updated_at: "2026-09-14T08:15:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.5-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.5-plan-review.md
    version: 2
supersedes: null
---

# AC → Test Matrix: Agent Console — Frontend (US-5.5)

**Every test function named below is prescriptive, not as-built.** Per
`docs/tests/US-5.5-test-strategy.md`'s "This stage's division of labor"
section, `test-writer` writes no test source file for this Story —
`frontend-builder` creates each file/function named here verbatim, paired
with the production file it tests, during `IMPLEMENTATION`
(`docs/plans/US-5.5-task-breakdown.md` v2, Tasks T4–T14). None of these
symbols exist in the working tree yet. `RECONCILIATION` is where "does the
named function exist and actually assert this AC" gets checked against the
real files, once they exist.

| AC ID | Acceptance Criterion (summary) | Test Function(s) | Level |
|---|---|---|---|
| AG-AC1 | Queue renders `ticket_number`/`subject`/`category`/`status`/assignee/`updated_at` per row, oldest-updated first; `status`/`category`/`assignee_id` filters re-request and reset the cursor; `me`/`none` mutually-exclusive presets; non-null `next_cursor` drives "Load more"; no total count/page number | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_renders_ticket_number_subject_category_status_assignee_and_updated_at_per_row` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_renders_rows_in_the_oldest_updated_first_order_the_server_returns` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_status_category_and_assignee_id_filters_re_request_the_queue_and_reset_the_cursor` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_me_and_none_presets_are_mutually_exclusive_and_set_assignee_id_accordingly` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_specific_agent_raw_uuid_filter_sends_the_typed_value_verbatim_as_assignee_id` (OD-2) | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_load_more_appends_the_next_page_on_a_non_null_next_cursor` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_load_more_issues_exactly_one_additional_request_carrying_the_previous_pages_next_cursor` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_never_renders_a_total_count_or_page_number` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_assignee_column_renders_a_shortened_truncated_uuid_first_8_hex_characters` (OD-1, plan literal) | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_assignee_column_renders_unassigned_for_a_null_assignee_id` (Change 8, plan literal) | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_empty_result_renders_no_tickets_match_these_filters_message` (plan literal) | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_a_malformed_assignee_id_filter_value_renders_the_servers_422_problem_detail_inline` (Risk 4) | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_renders_a_distinct_loading_state_before_the_query_resolves` | Integration |
| | | `hooks/useAgentTickets.test.ts::test_use_agent_tickets_a_status_filter_change_produces_a_new_query_key_and_resets_the_cursor` | Unit |
| | | `hooks/useAgentTickets.test.ts::test_use_agent_tickets_a_category_filter_change_produces_a_new_query_key_and_resets_the_cursor` | Unit |
| | | `hooks/useAgentTickets.test.ts::test_use_agent_tickets_an_assignee_id_filter_change_produces_a_new_query_key_and_resets_the_cursor` | Unit |
| | | `hooks/useAgentTickets.test.ts::test_use_agent_tickets_me_none_and_a_raw_uuid_are_all_sent_as_the_literal_assignee_id_query_parameter_verbatim` (Risk 4, OD-2) | Unit |
| | | `hooks/useAgentTickets.test.ts::test_use_agent_tickets_has_next_page_true_when_next_cursor_is_present` | Unit |
| | | `hooks/useAgentTickets.test.ts::test_use_agent_tickets_has_next_page_false_when_next_cursor_is_null` | Unit |
| AG-AC2 `[gate]` | "Assign to me" calls `POST .../assign` with the caller's own id; assign-to-another/unassign call the corresponding endpoint and invalidate the queue; `409`/`422` render problem+json detail | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_assign_to_me_calls_assign_with_the_callers_own_id_and_the_row_reflects_the_new_assignee` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_assign_to_another_agent_via_the_raw_uuid_input_calls_assign_with_the_entered_id` (OD-2) | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_unassign_calls_delete_assign_and_the_row_reflects_no_assignee` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_a_successful_assign_or_unassign_invalidates_the_queue` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_409_on_a_closed_ticket_assign_renders_its_problem_json_detail` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_422_assignee_is_not_an_agent_renders_its_problem_json_detail` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_row_click_navigates_to_the_detail_screen_carrying_the_rows_assignee_id_as_navigation_state` (OD-3, Change 7) | Integration |
| | | `hooks/useAssignTicket.test.ts::test_use_assign_ticket_calls_post_assign_with_the_supplied_assignee_id` | Unit |
| | | `hooks/useAssignTicket.test.ts::test_use_assign_ticket_on_success_invalidates_the_use_agent_tickets_query_key_regardless_of_caller_origin` (Change 8) | Unit |
| | | `hooks/useAssignTicket.test.ts::test_use_assign_ticket_on_success_writes_assignee_id_status_and_updated_at_into_the_shared_agent_ticket_assignee_cache_entry` (Change 7) | Unit |
| | | `hooks/useAssignTicket.test.ts::test_use_assign_ticket_never_spreads_the_response_over_a_full_agent_ticket_read_shaped_cache_entry` (Risk 3) | Unit |
| | | `hooks/useAssignTicket.test.ts::test_use_assign_ticket_409_on_a_closed_ticket_propagates_the_problem_json_error` | Unit |
| | | `hooks/useAssignTicket.test.ts::test_use_assign_ticket_422_assignee_is_not_an_agent_propagates_the_problem_json_error` | Unit |
| | | `hooks/useUnassignTicket.test.ts::test_use_unassign_ticket_calls_delete_assign_with_no_body` | Unit |
| | | `hooks/useUnassignTicket.test.ts::test_use_unassign_ticket_on_success_invalidates_the_use_agent_tickets_query_key_regardless_of_caller_origin` (Change 8) | Unit |
| | | `hooks/useUnassignTicket.test.ts::test_use_unassign_ticket_on_success_writes_the_response_into_the_shared_agent_ticket_assignee_cache_entry` (Change 7) | Unit |
| | | `hooks/useUnassignTicket.test.ts::test_use_unassign_ticket_409_on_a_closed_ticket_propagates_the_problem_json_error` | Unit |
| AG-AC3 `[gate]` | Detail renders header + full thread; internal replies visually distinct and labelled "internal"; "Load older replies" pages its own cursor | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_renders_the_ticket_header_and_the_full_thread` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_internal_visibility_replies_render_a_distinct_style_and_are_explicitly_labelled_internal` (also satisfies the Enforcement Matrix's "Internal-note distinction" row) | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_public_visibility_replies_render_without_the_internal_label_or_style` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_load_older_replies_pages_the_thread_by_its_own_cursor` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_load_older_replies_issues_exactly_one_additional_request_carrying_the_previous_pages_next_cursor_independent_of_the_queue` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_assignee_handoff_from_a_queue_row_click_renders_the_truncated_uuid_or_unassigned` (OD-1, OD-3) | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_direct_url_entry_with_no_handoff_renders_the_unknown_stale_placeholder_with_its_aria_label` (OD-3, Change 8, plan literal) | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_a_successful_assign_or_unassign_made_here_updates_the_local_assignee_display` (Change 7) | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_renders_a_distinct_loading_state_before_the_ticket_query_resolves` | Integration |
| AG-AC4 `[gate]` | Composer defaults to "public"; a public reply sends `visibility:"public"` and invalidates the ticket detail; an internal note sends `visibility:"internal"` and renders internal-styled with no status change; "internal" is never the default and never sticky | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_composer_visibility_control_defaults_to_public_on_first_open` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_submitting_a_public_reply_sends_visibility_public_and_invalidates_the_ticket_detail` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_submitting_an_internal_note_sends_visibility_internal_and_renders_it_in_the_internal_style_with_no_status_change_expected` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_visibility_is_never_sticky_composer_reads_public_again_immediately_after_an_internal_submission` (Risk 2, explicit named assertion — not assumed from the default) | Integration |
| | | `hooks/useReplyToTicket.test.ts::test_use_reply_to_ticket_a_supplied_visibility_value_is_included_in_the_request_body` (additive case, Task T8; existing customer-path-omits-the-key cases are unchanged) | Unit |
| AG-AC5 `[gate]` | Resolve with non-empty `resolution_note` (1..5000) calls `POST /resolve`, reflects `"resolved"`; empty note blocks client-side; `409` on closed renders detail | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_resolve_with_a_non_empty_resolution_note_calls_resolve_and_reflects_status_resolved` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_resolve_with_an_empty_note_blocks_submission_client_side_with_a_field_level_error` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_resolve_with_a_whitespace_only_note_blocks_submission_client_side_after_trim` (plan literal, plan_review v2 Non-Blocking Finding) | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_resolve_409_on_a_closed_ticket_renders_its_problem_json_detail` | Integration |
| | | `hooks/useResolveTicket.test.ts::test_use_resolve_ticket_calls_post_resolve_with_the_resolution_note` | Unit |
| | | `hooks/useResolveTicket.test.ts::test_use_resolve_ticket_on_success_writes_the_returned_ticket_state_read_into_the_ticket_detail_cache` | Unit |
| | | `hooks/useResolveTicket.test.ts::test_use_resolve_ticket_409_on_a_closed_ticket_propagates_the_problem_json_error` | Unit |
| AG-AC6 `[gate]` | Only actions valid for the current status are offered (five-status table); `tickets:read`-only sees a read-only view with every write control disabled (both screens) | `screens/AgentTicketDetailScreen.test.tsx::test_agent_offered_actions_for_status_%s_returns_the_exact_offered_set` (`it.each` over `open`/`waiting_on_support`/`waiting_on_customer`/`resolved`/`closed`) | Unit |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_offered_actions_for_status_resolved_never_includes_resolve` (easiest cell to invert) | Unit |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_offered_actions_for_status_closed_offers_no_actions_at_all` | Unit |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_offered_actions_for_status_an_unrecognized_status_offers_no_actions_fail_closed` | Unit |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_status_%s_wires_offered_actions_to_what_is_actually_rendered` (`it.each` over all five statuses) | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_tickets_read_only_scope_renders_every_write_control_disabled_not_hidden` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_an_assign_or_unassign_made_from_this_screen_also_invalidates_the_queue` (Change 8) | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_tickets_read_only_scope_renders_every_row_write_control_disabled_not_hidden` (Architectural Change 5 applies to both screens; T11's own Verification Command names this case) | Integration |
| AG-AC7 `[gate]` | 4xx `application/problem+json` renders detail/mapped message, never raw JSON; `422` `errors[]` maps onto matching fields | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_4xx_problem_json_renders_its_detail_with_no_raw_json` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_4xx_problem_json_renders_its_detail_with_no_raw_json` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_422_validation_failed_maps_the_errors_array_onto_the_matching_form_fields` | Integration |
| AG-AC8 `[gate]` | `POST /replies` `429` shows a retry-time message, disables submit until then, does not auto-retry | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_reply_429_shows_a_retry_time_disables_submit_and_fires_exactly_once` | Integration |
| AG-AC9 `[gate]` | Network error or 5xx from any endpoint shows a retry-capable error state, never blank/spinner/unhandled exception | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_network_error_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_5xx_response_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_network_error_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_5xx_response_shows_a_retry_capable_error_state` | Integration |

## Routing and navigation (FR-11; not itself a numbered AC)

Specification v2's own Traceability Matrix states FR-11 "has no corresponding
row... it traces to resolved Decision OD-4... not to an Acceptance
Criterion — no AC in this Story tests navigation placement." Grouped here
rather than attached to an invented AC id.

| Test Function | Level |
|---|---|
| `routes/AppRoutes.test.tsx::test_app_routes_agent_tickets_renders_agent_ticket_queue_screen` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_agent_tickets_redirects_unauthenticated_visitor_to_login` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_agent_tickets_id_renders_agent_ticket_detail_screen` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_agent_tickets_id_redirects_unauthenticated_visitor_to_login` | Integration |
| `layouts/AppShell.test.tsx::test_app_shell_renders_the_agent_queue_nav_entry_when_scopes_include_tickets_read` | Integration |
| `layouts/AppShell.test.tsx::test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read` | Integration |
| `layouts/AppShell.test.tsx::test_app_shell_renders_both_tickets_and_agent_tickets_nav_entries_together_no_separate_entry_point_or_role_switcher` (OD-4) | Integration |

## Server-403 handling (NFR "every screen handles a server 403"; not itself a numbered AC)

This Story has no `XC-AC*` cross-cutting band (unlike US-5.4); the
server-403-render requirement comes only from the NFR list.

| Test Function | Level |
|---|---|
| `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_forced_403_renders_a_not_permitted_state_never_blank_or_spinner` | Integration |
| `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_forced_403_renders_a_not_permitted_state_never_blank_or_spinner` | Integration |

## Plain-text rendering (Enforcement Matrix `[gate]` row; not itself a numbered AC)

| Test Function | Level |
|---|---|
| `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_html_bearing_reply_body_renders_as_escaped_text_and_never_executes` | Integration |

## `useReplyToTicket.ts`/`useTicketDetail.ts`/`TicketDetailScreen.tsx` existing-file test-surface impact (Risk 1; not itself a numbered AC)

Fixture-parity only (Task T9/T10) — no new behavioral assertion; both
production files (`useTicketDetail.ts`, `TicketDetailScreen.tsx`) must show
zero diff per the task breakdown's own verification commands.

| Test Function | Level |
|---|---|
| `hooks/useTicketDetail.test.ts` — existing `ReplyRead` fixtures gain an explicit `visibility` value (no new function; existing tests re-verified against the widened type) | Unit |
| `screens/TicketDetailScreen.test.tsx` — existing reply fixtures gain an explicit `visibility` value (no new function; existing tests re-verified against the widened type) | Integration |

## a11y bar (Enforcement Matrix `[gate]` row — exactly the two screens named)

| Row | Test Function | Level |
|---|---|---|
| a11y bar — `AgentTicketQueueScreen` | `screens/AgentTicketQueueScreen.test.tsx::test_agent_ticket_queue_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `AgentTicketDetailScreen` | `screens/AgentTicketDetailScreen.test.tsx::test_agent_ticket_detail_screen_has_no_detectable_accessibility_violations` | Integration |

## Gaps Not Covered

None. Every AC (AG-AC1 through AG-AC9) has at least one prescribed test
asserting its stated behavior, and every endpoint this Story's spec names is
already shipped (US-4.4), so no AC is deferred for that reason. See
`docs/tests/US-5.5-test-strategy.md` for the one item this pass explicitly
records as out of Vitest's reach rather than silently skipped
(responsive/viewport behavior), and for the collaborator-shape decisions this
matrix's rows implement (the shared `agentTicketAssigneeQueryKey` cache
mechanism, the `agentOfferedActionsForStatus` pure function, and the
navigation-state-handoff test mechanism).
