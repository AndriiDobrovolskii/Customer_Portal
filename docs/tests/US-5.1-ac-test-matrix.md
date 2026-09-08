---
artifact_type: ac_test_matrix
story: US-5.1
version: 1
status: ARCHIVED
created_at: "2026-09-07T20:00:00Z"
updated_at: "2026-09-07T20:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.1-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.1-plan-review.md
    version: 1
supersedes: null
---

# AC → Test Matrix: Authentication & Session Management — Frontend (US-5.1)

All test functions named below exist as `it("test_...")` cases in the working
tree at the file path given (verified by direct grep — see
`docs/evidence/US-5.1-test-generation-report.md`). Every test is written
against symbols (`authApi.ts`, `errorNormalization.ts`, `refreshCoordinator.ts`,
`authStore.tsx`, every hook, every screen/route/layout/component, and the
Task T4 test infrastructure — `mswServer.ts`, `mswHandlers.ts`,
`test-utils.tsx`) that do not exist yet — `frontend/` has no scaffold at all
(Task T1 has not run). This is the intended pre-`IMPLEMENTATION` state,
consistent with this project's `US-4.3` test-writer precedent one level
further out (there, symbols were missing; here, the whole project is
missing).

| AC ID | Acceptance Criterion (from spec Traceability Matrix) | Test Function(s) | Level |
|---|---|---|---|
| FE-AC1 | Register: 201 → land on /login with success message | `screens/RegisterScreen.test.tsx::test_register_screen_submits_valid_data_and_redirects_to_login_with_success_message` | Integration |
| | | `hooks/useRegister.test.ts::test_use_register_calls_register_endpoint_and_returns_created_user` | Unit |
| | | `hooks/useRegister.test.ts::test_use_register_duplicate_email_surfaces_normalized_409_error` (OD-4 at the hook level) | Unit |
| FE-AC2 | Login without MFA: LoginResponse, in-memory token, redirect home, refresh cookie untouched by client code | `screens/LoginScreen.test.tsx::test_login_screen_valid_credentials_without_mfa_stores_token_in_memory_and_redirects_to_home` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_unauthenticated_navigation_to_protected_route_redirects_to_login_and_back_after_successful_login` (full FR-2 flow, closes plan_review's Test-Strategy Realism finding) | Integration |
| | | `hooks/useLogin.test.ts::test_use_login_success_without_mfa_updates_session_and_returns_login_response` | Unit |
| FE-AC3 | Login with MFA: MfaRequiredResponse, mfa_token transient only, verify completes login | `screens/LoginScreen.test.tsx::test_login_screen_mfa_required_response_navigates_to_mfa_verify_screen_holding_mfa_token_in_transient_state` | Integration |
| | | `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_valid_totp_code_completes_login_same_as_login_without_mfa` | Integration |
| | | `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_valid_recovery_code_completes_login_same_as_login_without_mfa` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_placeholder_home` (full FR-3 flow, closes plan_review's Test-Strategy Realism finding) | Integration |
| | | `hooks/useLogin.test.ts::test_use_login_mfa_required_response_does_not_update_session_and_returns_mfa_token` | Unit |
| | | `hooks/useMfaVerify.test.ts::test_use_mfa_verify_success_with_totp_code_updates_session_same_as_login_without_mfa` | Unit |
| | | `hooks/useMfaVerify.test.ts::test_use_mfa_verify_success_with_recovery_code_updates_session_same_as_login_without_mfa` | Unit |
| FE-AC4 | Silent refresh: exactly one `/auth/refresh` on 401, retry on success, clear+redirect on failure | `hooks/refreshCoordinator.integration.test.tsx::test_two_concurrent_authenticated_requests_both_401_trigger_exactly_one_refresh_call_and_both_retry_succeed` | Integration |
| | | `hooks/refreshCoordinator.integration.test.tsx::test_refresh_failure_clears_session_and_redirects_to_login_once_not_once_per_waiter` | Integration |
| | | `api/refreshCoordinator.test.ts::test_refresh_coordinator_concurrent_callers_share_one_in_flight_refresh_promise` | Unit |
| | | `api/refreshCoordinator.test.ts::test_refresh_coordinator_serial_calls_after_settle_each_trigger_a_new_refresh` | Unit |
| | | `api/refreshCoordinator.test.ts::test_refresh_coordinator_rejects_all_waiters_when_the_shared_refresh_fails` | Unit |
| FE-AC5 | Logout / logout-all: same client-side effect (clear + land on /login) | `layouts/AppShell.test.tsx::test_app_shell_log_out_calls_logout_endpoint_clears_session_and_lands_on_login` | Integration |
| | | `layouts/AppShell.test.tsx::test_app_shell_log_out_everywhere_calls_logout_all_endpoint_with_same_client_effect` | Integration |
| | | `hooks/useLogout.test.ts::test_use_logout_calls_logout_endpoint_and_clears_session_on_success` | Unit |
| | | `hooks/useLogoutAll.test.ts::test_use_logout_all_calls_logout_all_endpoint_and_clears_session_on_success` | Unit |
| FE-AC6 | Sessions: list renders device/location/last-used + current marker; revoke non-current removes row only | `screens/SessionsScreen.test.tsx::test_sessions_screen_renders_device_label_location_last_used_and_marks_current_session` | Integration |
| | | `screens/SessionsScreen.test.tsx::test_sessions_screen_revoke_non_current_session_removes_row_without_affecting_current_session` | Integration |
| | | `screens/SessionsScreen.test.tsx::test_sessions_screen_current_session_row_revoke_control_is_disabled_per_od_6_default` (OD-6 default recorded by this pass — see test-strategy) | Integration |
| | | `hooks/useSessions.test.ts::test_use_sessions_returns_session_list_on_success` | Unit |
| | | `hooks/useRevokeSession.test.ts::test_use_revoke_session_calls_delete_endpoint_for_the_given_family_id` | Unit |
| | | `hooks/useRevokeSession.test.ts::test_use_revoke_session_current_session_surfaces_normalized_409_current_session_error` | Unit |
| FE-AC7 | Password reset: request → generic message regardless of account existence; confirm (valid token+policy) → land on /login with success message | `screens/ForgotPasswordScreen.test.tsx::test_forgot_password_screen_submits_email_and_shows_generic_message_regardless_of_account_existence` | Integration |
| | | `screens/ResetPasswordScreen.test.tsx::test_reset_password_screen_valid_token_and_policy_compliant_password_succeeds_and_lands_on_login_with_success_message` | Integration |
| | | `hooks/useRequestPasswordReset.test.ts::test_use_request_password_reset_returns_generic_message_regardless_of_account_existence` | Unit |
| | | `hooks/useConfirmPasswordReset.test.ts::test_use_confirm_password_reset_valid_token_and_password_succeeds_with_empty_body` | Unit |
| FE-AC8 | Client-side validation: empty/malformed required fields block submission, no API call | `screens/RegisterScreen.test.tsx::test_register_screen_blocks_submission_on_empty_fields_without_calling_api` | Integration |
| | | `screens/RegisterScreen.test.tsx::test_register_screen_blocks_submission_on_malformed_email_without_calling_api` | Integration |
| | | `screens/RegisterScreen.test.tsx::test_register_screen_blocks_submission_on_password_missing_required_character_classes_without_calling_api` | Integration |
| | | `screens/LoginScreen.test.tsx::test_login_screen_blocks_submission_on_empty_fields_without_calling_api` | Integration |
| | | `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_blocks_submission_on_empty_code_without_calling_api` | Integration |
| | | `screens/ForgotPasswordScreen.test.tsx::test_forgot_password_screen_blocks_submission_on_malformed_email_without_calling_api` | Integration |
| | | `screens/ResetPasswordScreen.test.tsx::test_reset_password_screen_blocks_submission_below_12_char_minimum_without_calling_api` | Integration |
| | | `screens/ResetPasswordScreen.test.tsx::test_reset_password_screen_does_not_simulate_breach_check_client_side_and_falls_through_to_server_error` (proves the server-only check is NOT pre-empted) | Integration |
| | | `screens/ResetPasswordScreen.test.tsx::test_reset_password_screen_does_not_simulate_differs_from_current_check_client_side_and_falls_through_to_server_error` (same) | Integration |
| FE-AC9 | 4xx `application/problem+json` renders `detail`/mapped message, never raw JSON/stack trace; 422 `errors[]` maps to fields | `api/errorNormalization.test.ts::test_normalize_api_error_maps_rfc7807_problem_json_detail_to_message` | Unit |
| | | `api/errorNormalization.test.ts::test_normalize_api_error_maps_422_errors_array_to_field_errors` | Unit |
| | | `api/errorNormalization.test.ts::test_normalize_api_error_maps_register_400_validation_error_shape_without_problem_json_envelope` (OD-4) | Unit |
| | | `api/errorNormalization.test.ts::test_normalize_api_error_maps_register_409_duplicate_email_shape_without_problem_json_envelope` (OD-4) | Unit |
| | | `api/errorNormalization.test.ts::test_normalize_api_error_never_renders_raw_json_or_stack_trace_for_an_unrecognized_shape` | Unit |
| | | `screens/RegisterScreen.test.tsx::test_register_screen_renders_mapped_message_for_register_400_validation_error_shape` | Integration |
| | | `screens/RegisterScreen.test.tsx::test_register_screen_renders_mapped_message_for_register_409_duplicate_email_shape` | Integration |
| | | `screens/LoginScreen.test.tsx::test_login_screen_renders_uniform_401_message_without_leaking_account_existence` | Integration |
| | | `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_renders_mapped_message_for_invalid_code` | Integration |
| | | `screens/ResetPasswordScreen.test.tsx::test_reset_password_screen_invalid_or_expired_token_renders_mapped_error` | Integration |
| | | `hooks/useRevokeSession.test.ts::test_use_revoke_session_current_session_surfaces_normalized_409_current_session_error` | Unit |
| | | `hooks/useLogin.test.ts::test_use_login_invalid_credentials_surfaces_normalized_401_error_without_leaking_account_existence` | Unit |
| | | `hooks/useConfirmPasswordReset.test.ts::test_use_confirm_password_reset_invalid_token_surfaces_normalized_error` | Unit |
| FE-AC10 | Unauthenticated → /login → back to original route after login; authenticated visiting /login or /register → placeholder home | `routes/ProtectedRoute.test.tsx::test_protected_route_unauthenticated_visitor_is_redirected_to_login` | Integration |
| | | `routes/ProtectedRoute.test.tsx::test_protected_route_remembers_the_originally_requested_route_for_post_login_return` | Integration |
| | | `routes/ProtectedRoute.test.tsx::test_protected_route_authenticated_visitor_renders_the_protected_children` | Integration |
| | | `routes/GuestOnlyRoute.test.tsx::test_guest_only_route_authenticated_user_is_redirected_to_placeholder_home` | Integration |
| | | `routes/GuestOnlyRoute.test.tsx::test_guest_only_route_unauthenticated_visitor_renders_the_guest_children` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_unauthenticated_navigation_to_protected_route_redirects_to_login_and_back_after_successful_login` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_authenticated_user_visiting_login_is_redirected_to_placeholder_home` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_authenticated_user_visiting_register_is_redirected_to_placeholder_home` | Integration |
| FE-AC11 | Network error / 5xx → generic retry-capable error state, never blank screen or unhandled exception | `components/ErrorState.test.tsx::test_error_state_renders_a_generic_retry_capable_message_for_a_network_error` | Integration |
| | | `components/ErrorState.test.tsx::test_error_state_renders_a_generic_retry_capable_message_for_a_5xx_response` | Integration |
| | | `components/ErrorState.test.tsx::test_error_state_retry_button_invokes_the_provided_callback` | Integration |
| | | `screens/RegisterScreen.test.tsx::test_register_screen_network_error_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/RegisterScreen.test.tsx::test_register_screen_5xx_response_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/LoginScreen.test.tsx::test_login_screen_network_error_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/LoginScreen.test.tsx::test_login_screen_5xx_response_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_network_error_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/ForgotPasswordScreen.test.tsx::test_forgot_password_screen_network_error_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/ResetPasswordScreen.test.tsx::test_reset_password_screen_network_error_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/SessionsScreen.test.tsx::test_sessions_screen_network_error_shows_generic_retry_capable_error_state` | Integration |
| | | `screens/SessionsScreen.test.tsx::test_sessions_screen_5xx_response_shows_generic_retry_capable_error_state` | Integration |

## Non-AC Enforcement Matrix row: a11y bar

The story's own Enforcement Matrix names an "automated a11y check (e.g. axe)"
`[gate]` row with no corresponding FE-AC/FR (traces instead to the spec's own
NFR "full keyboard navigation and visible focus states"). Per
`implementation-plan` Risk 1 / Architectural Change 9, the automated-check
library itself (`vitest-axe` or equivalent) is a new dependency pending
`AGENTS.md` §7.8 sign-off and is **not** used here. The dependency-free floor
this pass can assert is covered instead:

| Row | Test Function | Level |
|---|---|---|
| a11y bar (keyboard/focus floor only; automated axe check pending dependency sign-off) | `screens/RegisterScreen.test.tsx::test_register_screen_supports_full_keyboard_navigation_across_its_fields_and_submit_control` | Integration |

## Supporting tests not directly named by an AC row

These exist to prove collaborator-level behavior the AC rows above depend on,
but are not themselves an AC's primary evidence:

- `components/FieldError.test.tsx::test_field_error_renders_the_mapped_message_for_its_field_when_present`, `test_field_error_renders_nothing_when_its_field_has_no_mapped_error` — the shared 422-field renderer FE-AC9 depends on.
- `components/MfaEnrollmentBanner.test.tsx::test_mfa_enrollment_banner_renders_the_deadline_when_present`, `test_mfa_enrollment_banner_renders_nothing_when_deadline_is_absent`, `test_mfa_enrollment_banner_dismiss_control_hides_the_banner_and_persists_via_session_storage` — story Assumption #6 / OD-7-gated banner; not itself a numbered FE-AC.
- `screens/PlaceholderHomeScreen.test.tsx::test_placeholder_home_screen_renders_for_an_authenticated_user`, `test_placeholder_home_screen_surfaces_mfa_enrollment_banner_when_deadline_present`, `test_placeholder_home_screen_omits_mfa_enrollment_banner_when_deadline_absent` — the FE-AC2/FE-AC3 redirect target's own render, including the same banner (OD-8-gated content).
- `hooks/useMfaVerify.test.ts::test_use_mfa_verify_invalid_code_surfaces_normalized_error_and_leaves_session_unauthenticated` — negative-path collaborator proof for FE-AC3/FE-AC9's combination.

## Gaps Not Covered

See `docs/evidence/US-5.1-test-generation-report.md` for the full list. In
summary: nothing runnable exists yet (no `frontend/` scaffold — Task T1 has
not run), so no test here has actually been executed; every OD-gated screen
(OD-5, OD-6, OD-7, OD-8) is tested against this pass's own recorded default,
not a resolved OD; and the a11y bar's automated-check portion is intentionally
not implemented pending dependency sign-off.
