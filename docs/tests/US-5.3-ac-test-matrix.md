---
artifact_type: ac_test_matrix
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-09T09:30:00Z"
updated_at: "2026-09-09T09:30:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.3-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.3-plan-review.md
    version: 2
supersedes: null
---

# AC → Test Matrix: Support Tickets — Frontend (US-5.3)

All test functions named below exist as `it("test_...")` (or an `it.each(...)`
parameterization, noted where used) in the working tree at the file path
given. Every reference in this matrix was independently re-grepped against the
files as written after this pass finished — see
`docs/evidence/US-5.3-test-generation-report.md`'s self-check section for the
count. Every test is written against symbols (`api/supportApi.ts`, the six new
`hooks/`, `TicketListScreen.tsx`/`NewTicketScreen.tsx`/`TicketDetailScreen.tsx`,
`ApiError.retryAfterSeconds`/`httpPost`'s `idempotencyKey` option on
`api/httpClient.ts`, `getRetryAfterSeconds` on `components/apiErrorHelpers.ts`)
that `IMPLEMENTATION` has not yet created — the intended TDD-red state, per
`docs/tests/US-5.3-test-strategy.md`.

| AC ID | Acceptance Criterion (summary) | Test Function(s) | Level |
|---|---|---|---|
| TK-AC1 | Ticket list renders fields; "Load more" on `next_cursor`; empty state shows "New ticket" CTA | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_renders_ticket_number_subject_category_status_and_updated_at_per_row` | Integration |
| | | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_renders_an_unrecognized_status_value_verbatim_with_neutral_styling` | Integration |
| | | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_load_more_appends_the_next_page_using_next_cursor_and_disappears_when_null` | Integration |
| | | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_empty_items_shows_new_ticket_cta_instead_of_a_blank_screen` | Integration |
| | | `hooks/useTickets.test.ts::test_use_tickets_first_page_has_next_page_true_when_next_cursor_is_present` | Unit |
| | | `hooks/useTickets.test.ts::test_use_tickets_has_next_page_false_when_next_cursor_is_null` | Unit |
| | | `hooks/useTickets.test.ts::test_use_tickets_fetch_next_page_appends_using_the_previous_pages_next_cursor` | Unit |
| TK-AC2 | Status filter re-issues the list request with the selected status and a reset cursor; clearing re-requests unfiltered | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_selecting_status_%s_re_issues_the_request_with_that_status_and_a_reset_cursor` (`it.each` over all five statuses — 5 cases) | Integration |
| | | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_clearing_the_filter_re_requests_the_unfiltered_list` | Integration |
| | | `hooks/useTickets.test.ts::test_use_tickets_status_filter_is_sent_as_the_status_query_parameter` | Unit |
| | | `hooks/useTickets.test.ts::test_use_tickets_changing_the_status_filter_resets_pagination_to_a_single_unfiltered_page` | Unit |
| TK-AC3 | Create-ticket submission sends `Idempotency-Key` + `attachment_ids: []`; `201` lands on the ticket's detail screen | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_valid_submission_sends_idempotency_key_and_attachment_ids_empty_and_lands_on_detail_on_201` | Integration |
| | | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_category_field_is_a_plain_text_input_not_a_select` (OD-2) | Integration |
| | | `hooks/useCreateTicket.test.ts::test_use_create_ticket_mints_a_key_on_first_submission_and_sends_attachment_ids_empty` | Unit |
| | | `hooks/useCreateTicket.test.ts::test_use_create_ticket_never_sends_a_visibility_field` | Unit |
| TK-AC4 | Verbatim retry after a network/5xx failure reuses the identical `Idempotency-Key`; a new composition mints a different one | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_verbatim_retry_after_5xx_sends_the_identical_idempotency_key` | Integration |
| | | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_editing_a_field_after_a_failure_and_resubmitting_sends_a_different_key` (OD-6) | Integration |
| | | `hooks/useCreateTicket.test.ts::test_use_create_ticket_reuses_the_identical_key_on_a_verbatim_retry_after_failure` | Unit |
| | | `hooks/useCreateTicket.test.ts::test_use_create_ticket_mints_a_new_key_on_an_edited_then_resubmitted_payload` (OD-6) | Unit |
| | | `hooks/useCreateTicket.test.ts::test_use_create_ticket_fresh_mount_mints_a_different_key_than_a_previous_composition` | Unit |
| TK-AC5 | Ticket detail renders header + reply thread; "Load older replies" uses its own cursor, independent of the list's | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_renders_header_fields_and_reply_thread` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_renders_first_response_at_with_a_plain_label_and_no_sla_styling_when_present` (OD-4) | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_omits_first_response_label_when_absent` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_load_older_replies_fetches_using_its_own_cursor_independent_of_the_list` | Integration |
| | | `hooks/useTicketDetail.test.ts::test_ticket_detail_and_ticket_replies_query_keys_share_no_common_prefix` | Unit |
| | | `hooks/useTicketDetail.test.ts::test_use_ticket_detail_ticket_query_renders_header_fields_from_the_first_page` | Unit |
| | | `hooks/useTicketDetail.test.ts::test_use_ticket_detail_replies_query_has_next_page_true_when_replies_next_cursor_is_present` | Unit |
| | | `hooks/useTicketDetail.test.ts::test_use_ticket_detail_replies_pagination_uses_its_own_cursor_independent_of_any_list_cursor` | Unit |
| TK-AC6 | Reply submission sends no `visibility`, `attachment_ids: []`; on `201` the reply appears, composer clears, ticket detail refetches | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reply_submission_sends_no_visibility_and_attachment_ids_empty_appends_and_clears` | Integration |
| | | `hooks/useReplyToTicket.test.ts::test_use_reply_to_ticket_on_success_invalidates_both_ticket_detail_and_ticket_replies_queries` | Unit |
| | | `hooks/useReplyToTicket.test.ts::test_use_reply_to_ticket_sends_no_visibility_field_and_attachment_ids_empty` | Unit |
| TK-AC7 | "Close ticket" from any eligible status calls the close endpoint; screen reflects `closed`; composer becomes unavailable | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_close_ticket_from_%s_calls_close_endpoint_and_reflects_closed` (`it.each` over `open`/`waiting_on_support`/`waiting_on_customer`/`resolved` — 4 cases) | Integration |
| | | `hooks/useCloseTicket.test.ts::test_use_close_ticket_on_success_invalidates_ticket_detail_query_only` | Unit |
| | | `hooks/useCloseTicket.test.ts::test_use_close_ticket_calls_close_endpoint_and_resolves_with_status_closed` | Unit |
| TK-AC8 | "Reopen" from `resolved` is clickable (never pre-disabled, OD-3), calls reopen; screen reflects `waiting_on_support`; a `409` renders `detail` | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reopen_from_resolved_is_clickable_calls_endpoint_and_reflects_waiting_on_support` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reopen_409_outside_window_renders_detail_and_button_stays_clickable` | Integration |
| | | `hooks/useReopenTicket.test.ts::test_use_reopen_ticket_on_success_invalidates_ticket_detail_query_only` | Unit |
| | | `hooks/useReopenTicket.test.ts::test_use_reopen_ticket_calls_reopen_endpoint_and_resolves_with_status_waiting_on_support` | Unit |
| | | `hooks/useReopenTicket.test.ts::test_use_reopen_ticket_409_outside_reopen_window_reaches_caller_unmodified_with_detail_intact` | Unit |
| TK-AC9 | Only actions valid for the current status are offered; "Resolve" is never offered under any status | `screens/TicketDetailScreen.test.tsx::test_offered_actions_for_status_%s_returns_the_exact_offered_set` (`it.each` over all five known statuses — 5 cases) | Unit |
| | | `screens/TicketDetailScreen.test.tsx::test_offered_actions_for_status_an_unrecognized_status_offers_no_actions_fail_closed` | Unit |
| | | `screens/TicketDetailScreen.test.tsx::test_offered_actions_for_status_never_has_a_resolve_key_for_any_input` | Unit |
| | | `screens/TicketDetailScreen.test.tsx::test_offered_actions_for_status_resolved_always_includes_reopen_true_regardless_of_any_date_input` (OD-3) | Unit |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_status_%s_wires_offered_actions_to_what_is_actually_rendered` (`it.each` over all five known statuses — 5 cases) | Integration |
| TK-AC10 | Empty or over-length subject (150)/body (5000)/category (50) blocks submission with a field-level error, no API call | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_blocks_submission_on_empty_required_fields_without_calling_api` | Integration |
| | | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_blocks_submission_on_over_length_subject_body_category_without_calling_api` | Integration |
| TK-AC11 | 4xx `application/problem+json` renders `detail`/mapped message, never raw JSON; `422` `errors[]` maps to fields; `404` shows a "not found" state | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_4xx_problem_json_renders_mapped_detail_message_with_no_raw_json` | Integration |
| | | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_422_validation_error_maps_errors_array_onto_matching_fields` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_404_renders_a_dedicated_not_found_state` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_4xx_problem_json_renders_mapped_detail_with_no_raw_json` | Integration |
| TK-AC12 | `429` on ticket-create or reply shows a message naming the retry time and disables submit; no auto-retry loop | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_429_response_shows_retry_time_disables_submit_and_fires_exactly_once` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reply_429_shows_retry_time_disables_submit_and_fires_exactly_once` | Integration |
| | | `api/httpClient.test.ts::test_parse_response_429_with_retry_after_header_populates_api_error_retry_after_seconds` | Unit |
| | | `api/httpClient.test.ts::test_parse_response_429_without_a_retry_after_header_leaves_retry_after_seconds_undefined` | Unit |
| | | `api/httpClient.test.ts::test_parse_response_non_429_4xx_never_populates_retry_after_seconds_even_when_header_present` | Unit |
| | | `api/httpClient.test.ts::test_parse_response_429_with_a_non_numeric_retry_after_header_leaves_retry_after_seconds_undefined` | Unit |
| | | `api/httpClient.test.ts::test_parse_response_429_threading_applies_to_httpget_not_only_httppost` | Unit |
| | | `components/apiErrorHelpers.test.ts::test_get_retry_after_seconds_returns_the_numeric_value_from_a_structural_error` | Unit |
| | | `components/apiErrorHelpers.test.ts::test_get_retry_after_seconds_returns_undefined_when_field_is_absent` | Unit |
| | | `hooks/useRetryAfterCountdown.test.ts::test_use_retry_after_countdown_starts_blocked_with_the_supplied_seconds_remaining` | Unit |
| | | `hooks/useRetryAfterCountdown.test.ts::test_use_retry_after_countdown_ticks_down_to_zero_and_isblocked_flips_false` | Unit |
| | | `hooks/useRetryAfterCountdown.test.ts::test_use_retry_after_countdown_clears_its_interval_on_unmount` | Unit |
| | | `hooks/useRetryAfterCountdown.test.ts::test_use_retry_after_countdown_reinitializes_when_a_new_retry_after_seconds_value_arrives` | Unit |
| TK-AC13 | Network error or 5xx from any endpoint in this Story shows a retry-capable error state, never a blank screen or unhandled exception | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_5xx_response_shows_retry_capable_error_state` | Integration |
| | | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_5xx_response_shows_retry_capable_error_state` | Integration |
| TK-AC14 | A `401` triggers US-5.1's existing silent-refresh coordinator; a deactivated account's `403` on ticket create renders its `detail` | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_401_triggers_the_existing_silent_refresh_coordinator_and_retries` | Integration |
| | | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_403_deactivated_account_renders_problem_json_detail` | Integration |

## FR-15 — Post-Login Redirect and Navigation Entry (not a numbered TK-AC; derived from the spec's "In Scope" section, Assumption #7)

| Test Function | Level |
|---|---|
| `screens/LoginScreen.test.tsx::test_login_screen_valid_credentials_without_mfa_stores_token_in_memory_and_redirects_to_tickets` (renamed from the pre-US-5.3 `..._redirects_to_home`; assertion target changed from `/` to `/tickets`) | Integration |
| `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_valid_totp_code_completes_login_and_lands_on_tickets` (renamed, retargeted) | Integration |
| `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_valid_recovery_code_completes_login_and_lands_on_tickets` (renamed, retargeted) | Integration |
| `routes/GuestOnlyRoute.test.tsx::test_guest_only_route_authenticated_user_is_redirected_to_tickets` (renamed, retargeted) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_authenticated_user_visiting_login_is_redirected_to_tickets` (renamed, retargeted) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_authenticated_user_visiting_register_is_redirected_to_tickets` (renamed, retargeted) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_tickets` (renamed, retargeted) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_root_redirects_authenticated_visitor_to_tickets` (new) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_tickets_renders_ticket_list_screen` (new) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_tickets_redirects_unauthenticated_visitor_to_login` (new) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_tickets_new_renders_new_ticket_screen_not_ticket_detail_screen` (new — Risk 9 route-ranking regression check) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_tickets_new_redirects_unauthenticated_visitor_to_login` (new) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_tickets_id_renders_ticket_detail_screen` (new) | Integration |
| `routes/AppRoutes.test.tsx::test_app_routes_tickets_id_redirects_unauthenticated_visitor_to_login` (new) | Integration |
| `layouts/AppShell.test.tsx::test_app_shell_renders_a_tickets_nav_link` (new) | Integration |
| `layouts/AppShell.test.tsx::test_app_shell_renders_the_mfa_enrollment_banner_when_a_deadline_is_present` (new — banner's relocated render site) | Integration |
| `layouts/AppShell.test.tsx::test_app_shell_renders_no_banner_when_no_deadline_is_present` (new) | Integration |

## `httpPost` `idempotencyKey` option (implementation_plan v2 Change 1; underlies TK-AC3/TK-AC4, not itself a numbered AC)

| Test Function | Level |
|---|---|
| `api/httpClient.test.ts::test_http_post_threads_idempotency_key_header_when_option_supplied` | Unit |
| `api/httpClient.test.ts::test_http_post_omits_idempotency_key_header_when_option_not_supplied` | Unit |

## Plain-text rendering (story's own Enforcement Matrix; underlies the NFR bar, not a numbered TK-AC)

| Test Function | Level |
|---|---|
| `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_html_bearing_reply_body_renders_as_escaped_text_and_never_executes` | Integration |

## a11y bar (Enforcement Matrix `[gate]` row)

| Row | Test Function | Level |
|---|---|---|
| a11y bar — `TicketListScreen` | `screens/TicketListScreen.test.tsx::test_ticket_list_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `NewTicketScreen` | `screens/NewTicketScreen.test.tsx::test_new_ticket_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `TicketDetailScreen` | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_has_no_detectable_accessibility_violations` | Integration |

## Supporting tests not directly named by an AC row

- `hooks/useTicketDetail.test.ts::test_ticket_detail_and_ticket_replies_query_keys_share_no_common_prefix` — the structural guarantee (disjoint top-level query keys) TK-AC5's and TK-AC6's invalidation-scoping rows depend on.
- `hooks/useReplyToTicket.test.ts`, `hooks/useCloseTicket.test.ts`, `hooks/useReopenTicket.test.ts`'s own-scope invalidation rows (`..._invalidates_..._only` / `..._invalidates_both_...`) — collaborator-level proof underlying each screen row's cache-refresh behavior above.
- `api/httpClient.test.ts::test_http_patch_*` (5 pre-existing US-5.2 cases) — unmodified by this Story; not re-listed here, confirmed only by the diff-read verification `task_breakdown` v2 T1 names.

## Gaps Not Covered

None — every TK-AC (TK-AC1 through TK-AC14) has at least one test asserting its
stated behavior. See `docs/evidence/US-5.3-test-generation-report.md` for
methodology notes (fake-timer confinement, route-ranking assertion-by-content
rather than by pathname, and the `offeredActionsForStatus` export
collaborator-shape decision) and for the full self-check evidence.
