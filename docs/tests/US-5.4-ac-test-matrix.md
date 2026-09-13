---
artifact_type: ac_test_matrix
story: US-5.4
version: 1
status: DRAFT
created_at: "2026-09-13T20:00:00Z"
updated_at: "2026-09-13T20:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.4-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.4-plan-review.md
    version: 2
supersedes: null
---

# AC → Test Matrix: Admin Console — Frontend (US-5.4)

**Every test function named below is prescriptive, not as-built.** Per
`docs/tests/US-5.4-test-strategy.md`'s "This stage's division of labor"
section, `test-writer` writes no test source file for this Story —
`frontend-builder` creates each file/function named here verbatim, paired
with the production file it tests, during `IMPLEMENTATION`
(`docs/plans/US-5.4-task-breakdown.md` v2, Tasks T2–T22). None of these
symbols exist in the working tree yet. `RECONCILIATION` is where "does the
named function exist and actually assert this AC" gets checked against the
real files, once they exist.

| AC ID | Acceptance Criterion (summary) | Test Function(s) | Level |
|---|---|---|---|
| AD-AC1 | User list renders `email`/`display_name`/`status`/`roles`/`created_at`/`last_login_at`; `q`/`status`/`role` filters re-request and reset the cursor; "Load more" on `next_cursor`; no total count/page number anywhere | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_renders_email_display_name_status_roles_created_at_and_last_login_at_per_row` | Integration |
| | | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_q_status_role_filters_re_request_the_list_and_reset_the_cursor` | Integration |
| | | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_load_more_appends_the_next_page_and_disappears_when_next_cursor_is_null` | Integration |
| | | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_never_renders_a_total_count_or_page_number` | Integration |
| | | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_renders_an_unrecognized_status_or_roles_value_verbatim` (Risk 7) | Integration |
| | | `hooks/useAdminUsers.test.ts::test_use_admin_users_first_page_has_next_page_true_when_next_cursor_is_present` | Unit |
| | | `hooks/useAdminUsers.test.ts::test_use_admin_users_has_next_page_false_when_next_cursor_is_null` | Unit |
| | | `hooks/useAdminUsers.test.ts::test_use_admin_users_q_status_role_filters_are_sent_as_query_parameters` | Unit |
| | | `hooks/useAdminUsers.test.ts::test_use_admin_users_changing_a_filter_resets_pagination_to_a_single_page` | Unit |
| AD-AC2 `[gate]` | `GET /admin/users/{id}` captures the `ETag` response header; echoed as `If-Match` on the next `PATCH` for the *same* user, never for a different user | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_get_captures_the_etag_and_echoes_it_as_if_match_on_the_next_patch` | Integration |
| | | `hooks/useAdminUser.test.ts::test_use_admin_user_captures_the_etag_response_header_into_the_per_user_cache_key` | Unit |
| | | `hooks/useAdminUser.test.ts::test_use_admin_user_etag_for_user_a_is_never_read_under_user_bs_cache_key` (Risk 4) | Unit |
| | | `hooks/useAdminUser.test.ts::test_use_admin_user_missing_etag_header_leaves_the_cache_key_unset` | Unit |
| AD-AC3 `[gate]` | Create sends exactly `email`/`display_name`/`roles`, no password field anywhere; roles catalogue-sourced (OD-4); `201` lands on new user's detail screen | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_submits_exactly_email_display_name_and_roles` | Integration |
| | | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_never_renders_a_password_field_anywhere_in_the_dom` | Integration |
| | | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_roles_options_are_sourced_only_from_get_admin_roles_no_free_text_entry` (OD-4) | Integration |
| | | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_on_201_navigates_to_the_new_users_detail_screen` | Integration |
| | | `hooks/useCreateAdminUser.test.ts::test_use_create_admin_user_sends_exactly_email_display_name_and_roles` | Unit |
| | | `hooks/useCreateAdminUser.test.ts::test_use_create_admin_user_never_sends_a_password_field` | Unit |
| | | `hooks/useCreateAdminUser.test.ts::test_use_create_admin_user_on_success_resolves_with_the_new_users_id_for_navigation` | Unit |
| AD-AC4 `[gate]` | Edit requires non-empty `reason`; `PATCH` carries `If-Match` + `reason`; `412` shows a conflict state; `immutable-field` problem renders its detail | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_requires_a_non_empty_reason_before_a_field_edit_can_be_submitted` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_412_renders_a_conflict_state` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_immutable_field_problem_renders_its_own_detail` | Integration |
| | | `hooks/useUpdateAdminUser.test.ts::test_use_update_admin_user_sends_if_match_using_the_cached_etag_for_that_user` | Unit |
| | | `hooks/useUpdateAdminUser.test.ts::test_use_update_admin_user_412_sets_conflict_true` | Unit |
| | | `hooks/useUpdateAdminUser.test.ts::test_use_update_admin_user_immutable_field_error_surfaces_the_problems_detail` | Unit |
| AD-AC5 `[gate]` | `roles` never in `PATCH` body; `GET /admin/roles` supplies the catalogue; `PUT .../roles` carries the full replacement list; role control disabled without `roles:write` (server 403 still renders); confirmation names Gained/Lost (OD-3) | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_patch_never_includes_a_roles_field` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_role_save_hits_put_users_id_roles_with_the_full_replacement_list` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_role_control_is_disabled_without_roles_write` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_forced_403_on_a_role_save_attempt_still_renders_correctly` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_confirmation_computes_gained_and_lost_role_sets_with_a_reordered_seed` (Risk 6/OD-3) | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_save_is_disabled_when_the_selected_role_set_equals_the_current_set` (OD-3) | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_save_becomes_enabled_the_moment_either_set_differs` (OD-3) | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_blocks_an_empty_role_selection_as_a_separate_always_blocking_case` | Integration |
| | | `hooks/useAdminRoles.test.ts::test_use_admin_roles_fetches_the_role_catalogue_once_and_is_not_paginated` | Unit |
| | | `hooks/useAdminRoles.test.ts::test_use_admin_roles_is_the_same_query_key_consumed_by_create_and_replace_paths` | Unit |
| | | `hooks/useReplaceUserRoles.test.ts::test_use_replace_user_roles_sends_the_full_replacement_list_via_put` | Unit |
| | | `hooks/useReplaceUserRoles.test.ts::test_use_replace_user_roles_on_success_invalidates_use_admin_users_query_key_for_that_id` (Risk 3) | Unit |
| | | `hooks/useUpdateAdminUser.test.ts::test_use_update_admin_user_never_includes_roles_in_the_patch_body` | Unit |
| AD-AC6 `[gate]` | Deactivate with non-empty reason calls the deactivate endpoint, reflects returned status; resend-invite calls the resend endpoint, shows generic confirmation | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_deactivate_requires_a_non_empty_reason_and_sits_behind_confirmation` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_deactivate_success_reflects_the_returned_status` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_resend_invite_shows_a_generic_confirmation_and_never_displays_the_202_body` | Integration |
| | | `hooks/useDeactivateAdminUser.test.ts::test_use_deactivate_admin_user_sends_the_required_reason` | Unit |
| | | `hooks/useDeactivateAdminUser.test.ts::test_use_deactivate_admin_user_on_success_updates_the_cached_status_without_a_full_refetch` (Risk 3) | Unit |
| | | `hooks/useResendInvite.test.ts::test_use_resend_invite_calls_the_resend_endpoint_and_never_surfaces_the_202_body` | Unit |
| AD-AC7 `[gate]` | No control anywhere issues `DELETE /admin/users/{id}` | `api/adminApi.test.ts::test_no_frontend_source_file_calls_http_delete_against_the_admin_users_path` (static, source-wide — the only mechanism proving "anywhere") | Unit |
| | | `api/adminApi.test.ts::test_admin_api_ts_does_not_export_a_delete_user_function` (structural backstop) | Unit |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_never_renders_a_delete_control` (screen-level backstop, not a proof of "anywhere") | Integration |
| AD-AC8 `[gate]` | Audit log renders all nine fields; nullable columns show an explicit placeholder; `actor_id`/`event`/`target_id`/`from`/`to` sent as query params with the literal `from` key; default 7-day window pre-filled visibly (OD-1); `event` is free text (OD-2); "Load more" on `next_cursor`; no total count/page number | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_renders_all_nine_columns_per_entry` | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_renders_an_explicit_placeholder_for_each_nullable_column` | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_from_and_to_inputs_are_visibly_prefilled_with_the_last_7_days_default_on_first_render_clock_frozen` (OD-1, Risk 5) | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_event_filter_is_a_free_text_input_with_an_illustrative_placeholder_never_a_select` (OD-2) | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_actor_id_event_target_id_from_and_to_are_sent_as_query_parameters_with_the_literal_from_key` | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_load_more_appends_using_a_stable_synthetic_row_key_across_pages` (Risk 7) | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_never_renders_a_total_count_or_page_number` | Integration |
| | | `hooks/useAuditLogs.test.ts::test_use_audit_logs_default_window_is_the_last_7_days_in_iso_8601_utc_with_the_clock_frozen` (OD-1, Risk 5) | Unit |
| | | `hooks/useAuditLogs.test.ts::test_use_audit_logs_computes_the_default_window_exactly_once_per_mount` | Unit |
| | | `hooks/useAuditLogs.test.ts::test_use_audit_logs_actor_id_event_target_id_from_and_to_are_sent_as_query_parameters_with_the_literal_from_key` | Unit |
| | | `hooks/useAuditLogs.test.ts::test_use_audit_logs_has_next_page_false_when_next_cursor_is_null` | Unit |
| | | `api/adminApi.test.ts::test_list_audit_logs_sends_the_start_of_window_parameter_key_literally_as_from_not_from_` | Unit |
| XC-AC1 `[gate]` | No admin nav entry without an admin scope; a direct-navigating scope-less user sees the server's 403, never blank/spinner; `users:read`-only renders reads normally with every write control disabled | `layouts/AppShell.test.tsx::test_app_shell_renders_the_users_and_audit_log_nav_entries_when_scopes_include_users_read_and_audit_read` | Integration |
| | | `layouts/AppShell.test.tsx::test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope` | Integration |
| | | `layouts/AppShell.test.tsx::test_app_shell_clears_admin_nav_entries_after_a_clear_session_dispatch` (closes plan_review's authStore Medium finding) | Integration |
| | | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_forced_403_from_the_server_renders_the_not_permitted_state_not_a_blank_screen_or_spinner` | Integration |
| | | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_users_write_less_seed_disables_or_hides_the_create_user_control` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_users_read_only_seed_disables_every_write_control` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_forced_403_on_a_scope_less_direct_navigation_renders_not_permitted_never_blank_or_spinner` | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_forced_403_renders_not_permitted_never_blank_or_spinner` | Integration |
| XC-AC2 `[gate]` | 4xx `application/problem+json` renders `detail`/mapped message, never raw JSON; `422` `errors[]` maps onto matching fields | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_4xx_problem_json_renders_the_mapped_detail_with_no_raw_json` | Integration |
| | | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_422_validation_error_maps_the_errors_array_onto_the_matching_fields` | Integration |
| XC-AC3 `[gate]` | Empty/malformed required field (invalid email, empty reason, empty role list) blocks submission with a field-level error and no API call | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_blocks_submission_on_invalid_email_shape_without_calling_the_api` | Integration |
| | | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_blocks_submission_on_an_empty_role_selection_without_calling_the_api` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_requires_a_non_empty_reason_before_a_field_edit_can_be_submitted` (shared row with AD-AC4) | Integration |
| XC-AC4 `[gate]` | Network error or 5xx from any endpoint shows a retry-capable error state, never blank/spinner/unhandled exception | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_network_error_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_5xx_response_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_network_error_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_network_error_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_network_error_shows_a_retry_capable_error_state` | Integration |
| | | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_5xx_response_shows_a_retry_capable_error_state` | Integration |

## `httpPut` wrapper (implementation_plan v2 Architectural Change 2; underlies AD-AC5, not itself a numbered AC)

| Test Function | Level |
|---|---|
| `api/httpClient.test.ts::test_http_put_sends_a_put_request_with_the_json_body_and_returns_the_parsed_response` | Unit |

## `decodeTokenScopes` (implementation_plan v2 Architectural Change 1; underlies FR-9/XC-AC1, not itself a numbered AC)

| Test Function | Level |
|---|---|
| `store/decodeTokenScopes.test.ts::test_decode_token_scopes_returns_the_scopes_claim_from_a_well_formed_token` | Unit |
| `store/decodeTokenScopes.test.ts::test_decode_token_scopes_returns_an_empty_array_when_the_scopes_claim_is_absent` | Unit |
| `store/decodeTokenScopes.test.ts::test_decode_token_scopes_returns_an_empty_array_and_does_not_throw_on_a_malformed_payload` | Unit |

## Routing (Files To Modify; underlies every screen being reachable, not itself a numbered AC)

| Test Function | Level |
|---|---|
| `routes/AppRoutes.test.tsx::test_app_routes_admin_users_renders_admin_user_list_screen` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_admin_users_redirects_unauthenticated_visitor_to_login` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_admin_users_new_renders_admin_user_create_screen` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_admin_users_new_redirects_unauthenticated_visitor_to_login` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_admin_users_id_renders_admin_user_detail_screen` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_admin_users_id_redirects_unauthenticated_visitor_to_login` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_admin_audit_logs_renders_admin_audit_log_screen` | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_admin_audit_logs_redirects_unauthenticated_visitor_to_login` | Integration |

## Explicit loading state per screen (spec NFR; underlies all four screens, not itself a numbered AC)

| Test Function | Level |
|---|---|
| `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_renders_a_distinct_loading_state_before_the_query_resolves` | Integration |
| `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_renders_a_distinct_loading_state_before_the_role_catalogue_resolves` | Integration |
| `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_renders_a_distinct_loading_state_before_the_user_query_resolves` | Integration |
| `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_renders_a_distinct_loading_state_before_the_query_resolves` | Integration |

## Console hygiene (spec NFR; underlies AdminAuditLogScreen, not itself a numbered AC)

| Test Function | Level |
|---|---|
| `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_console_spy_records_no_call_containing_ip_user_agent_or_request_id` | Integration |

## a11y bar (Enforcement Matrix `[gate]` row — exactly the three screens named)

| Row | Test Function | Level |
|---|---|---|
| a11y bar — `AdminUserListScreen` | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `AdminUserDetailScreen` (story's "user-edit" screen) | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `AdminAuditLogScreen` | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_has_no_detectable_accessibility_violations` | Integration |

## Gaps Not Covered

None. Every AC (AD-AC1 through AD-AC8, XC-AC1 through XC-AC4) has at least one
prescribed test asserting its stated behavior. Unlike `US-5.2` (one AC
untestable pending a missing backend endpoint), every endpoint this Story's
spec names is already shipped (US-3.1/US-3.2/US-3.3), so no AC is deferred for
that reason. See `docs/tests/US-5.4-test-strategy.md` for the three items this
pass explicitly records as out of Vitest's reach rather than silently
skipped (production-build-specific console hygiene; responsive/viewport
behavior) and for the AD-AC7 mechanism decision this matrix's three rows
implement.
