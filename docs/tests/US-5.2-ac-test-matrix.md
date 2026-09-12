---
artifact_type: ac_test_matrix
story: US-5.2
version: 1
status: ARCHIVED
created_at: "2026-09-08T10:00:00Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.2-plan-review.md
    version: 1
supersedes: null
---

# AC → Test Matrix: Account & Profile Self-Service — Frontend (US-5.2)

All test functions named below exist as `it("test_...")` cases in the working
tree at the file path given (verified by direct grep — see
`docs/evidence/US-5.2-test-generation-report.md`). Every test is written
against symbols (`profileApi.ts`, `mfaApi.ts`, `accountApi.ts`, the eight new
hooks, five new/modified screens, `RecoveryCodesDisplay.tsx`, `QrCode.tsx`,
and the `httpPatch`/`getErrorStatus`/`authStore.mfaEnabled`/`AppRoutes.tsx`/
`MfaEnrollmentBanner.tsx` additions) that `IMPLEMENTATION` (Tasks T1–T12) has
not yet created — the intended TDD-red state, per
`docs/tests/US-5.2-test-strategy.md`.

| AC ID | Acceptance Criterion (from spec Traceability Matrix) | Test Function(s) | Level |
|---|---|---|---|
| PS-AC1 | Profile view — **deferred, `[blocked]`**: no `GET /profile`/`GET /users/me` exists (FR-1, Dependencies & Blockers #1) | *(no test — untestable this Story; see the "PS-AC1" section below)* | — |
| PS-AC2 | Field edit: `PATCH /profile` with only changed fields; `If-Match` echoes a known ETag or sends `*`; `200` reflects `ProfileRead` and caches the returned `ETag`; `412` renders "changed elsewhere, reload" | `screens/ProfileScreen.test.tsx::test_profile_screen_submits_only_changed_fields_on_save` | Integration |
| | | `screens/ProfileScreen.test.tsx::test_profile_screen_first_write_in_session_sends_if_match_asterisk` | Integration |
| | | `screens/ProfileScreen.test.tsx::test_profile_screen_second_write_in_session_echoes_captured_etag` | Integration |
| | | `screens/ProfileScreen.test.tsx::test_profile_screen_412_response_renders_changed_elsewhere_reload_conflict_state` | Integration |
| | | `hooks/useProfileUpdate.test.ts::test_use_profile_update_first_write_in_session_sends_if_match_asterisk_and_caches_returned_etag` | Unit |
| | | `hooks/useProfileUpdate.test.ts::test_use_profile_update_subsequent_write_in_same_session_echoes_previously_cached_etag_as_if_match` | Unit |
| | | `hooks/useProfileUpdate.test.ts::test_use_profile_update_412_response_sets_conflict_flag_without_updating_cached_etag` | Unit |
| | | `hooks/useProfileUpdate.test.ts::test_use_profile_update_reset_conflict_clears_the_conflict_flag` | Unit |
| | | `api/httpClient.test.ts::test_http_patch_resolves_with_data_status_and_headers_on_200` | Unit |
| | | `api/httpClient.test.ts::test_http_patch_threads_if_match_header_when_option_supplied` | Unit |
| | | `api/httpClient.test.ts::test_http_patch_omits_if_match_header_when_option_not_supplied` | Unit |
| | | `api/httpClient.test.ts::test_http_patch_412_response_rejects_with_api_error_status_412` | Unit |
| PS-AC3 | Email change: `PATCH /profile` with `email`+`current_password` → `202` and pending-email state; primary email unchanged until confirmed; `POST /profile/confirm-email-change` works signed-in and signed-out | `screens/ProfileScreen.test.tsx::test_profile_screen_email_change_submission_shows_pending_confirmation_state_on_202` | Integration |
| | | `screens/ConfirmEmailChangeScreen.test.tsx::test_confirm_email_change_screen_succeeds_when_rendered_unauthenticated` | Integration |
| | | `screens/ConfirmEmailChangeScreen.test.tsx::test_confirm_email_change_screen_succeeds_when_rendered_authenticated` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_confirm_email_change_renders_for_an_unauthenticated_visitor` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_confirm_email_change_renders_for_an_authenticated_visitor` | Integration |
| | | `hooks/useProfileUpdate.test.ts::test_use_profile_update_202_email_change_pending_removes_cached_etag_and_resolves_with_pending_email` | Unit |
| | | `hooks/useConfirmEmailChange.test.ts::test_use_confirm_email_change_success_resolves_confirm_email_change_response` | Unit |
| | | `hooks/useConfirmEmailChange.test.ts::test_use_confirm_email_change_succeeds_identically_when_rendered_authenticated` | Unit |
| | | `api/httpClient.test.ts::test_http_patch_resolves_with_202_status_and_no_etag_header_for_email_change_pending` | Unit |
| PS-AC4 | Email verification: `POST /auth/verify-email` — success/expired/invalid render distinctly; resend gives a generic confirmation regardless of address existence | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_valid_token_renders_success_outcome` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_expired_token_renders_expired_outcome` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_invalid_token_renders_invalid_outcome` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_resend_control_shows_generic_confirmation_when_address_exists` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_resend_control_shows_the_same_generic_confirmation_when_address_does_not_exist` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_verify_email_renders_for_an_unauthenticated_visitor` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_verify_email_renders_for_an_authenticated_visitor` | Integration |
| | | `hooks/useVerifyEmail.test.ts::test_use_verify_email_success_resolves_verify_email_response` | Unit |
| | | `hooks/useVerifyEmail.test.ts::test_use_verify_email_expired_token_surfaces_the_servers_normalized_expired_message` | Unit |
| | | `hooks/useVerifyEmail.test.ts::test_use_verify_email_invalid_token_surfaces_the_servers_normalized_invalid_message` | Unit |
| | | `hooks/useResendVerificationEmail.test.ts::test_use_resend_verification_email_resolves_generic_confirmation_for_any_submitted_address` | Unit |
| PS-AC5 | MFA enrollment: `POST /auth/mfa/enroll` → local QR + manual secret; `POST /auth/mfa/activate` → one-time `recovery_codes`; save-confirmation gate; secret/URI/codes never reach storage/console/third party <!-- pragma: allowlist secret --> | `screens/SecurityScreen.test.tsx::test_security_screen_mfa_disabled_session_shows_enroll_flow` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_start_calls_mfa_enroll_with_current_password_and_renders_qr_and_manual_secret` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_blocks_submission_when_current_password_empty_without_calling_api` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_activate_with_valid_6_digit_code_displays_recovery_codes_exactly_once` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_blocks_submission_with_non_6_digit_code_without_calling_api` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_flow_cannot_complete_until_save_confirmation_checked` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_secret_otpauth_uri_and_recovery_codes_never_reach_storage_console_or_third_party` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_completing_enrollment_flips_the_screen_to_the_disable_flow` | Integration |
| | | `components/RecoveryCodesDisplay.test.tsx::test_recovery_codes_display_renders_every_code_in_a_keyboard_selectable_list` | Integration |
| | | `components/RecoveryCodesDisplay.test.tsx::test_recovery_codes_display_copy_control_writes_codes_to_the_clipboard_api` | Integration |
| | | `components/RecoveryCodesDisplay.test.tsx::test_recovery_codes_display_continue_control_is_disabled_until_save_confirmation_is_checked` | Integration |
| | | `components/RecoveryCodesDisplay.test.tsx::test_recovery_codes_display_never_writes_codes_to_local_storage_session_storage_or_console` | Integration |
| | | `components/QrCode.test.tsx::test_qr_code_renders_an_svg_representation_of_the_provided_value` | Integration |
| | | `components/QrCode.test.tsx::test_qr_code_fires_no_network_request_while_rendering` | Integration |
| | | `components/QrCode.test.tsx::test_qr_code_never_logs_the_provided_value_to_the_console` | Integration |
| | | `hooks/useMfaEnroll.test.ts::test_use_mfa_enroll_success_resolves_secret_and_otpauth_uri` | Unit |
| | | `hooks/useMfaActivate.test.ts::test_use_mfa_activate_success_resolves_recovery_codes_and_sets_auth_store_mfa_enabled_true` | Unit |
| PS-AC6 | MFA disable: `DELETE /auth/mfa` → security screen reflects MFA disabled | `screens/SecurityScreen.test.tsx::test_security_screen_mfa_enabled_session_shows_disable_flow_directly_not_defaulting_to_enroll` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_disable_requires_current_password_and_code` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_disable_confirmation_names_session_revocation_consequence` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_successful_disable_calls_mfa_disable_and_the_screen_reflects_mfa_as_disabled` | Integration |
| | | `hooks/useMfaDisable.test.ts::test_use_mfa_disable_success_sends_current_password_and_code_and_sets_auth_store_mfa_enabled_false` | Unit |
| | | `hooks/useMfaDisable.test.ts::test_use_mfa_disable_incorrect_password_or_code_surfaces_normalized_error_and_leaves_mfa_enabled_unchanged` | Unit |
| | | `hooks/useLogin.test.ts::test_use_login_success_without_mfa_sets_auth_store_mfa_enabled_false` (Change 6 signal, additive) | Unit |
| | | `hooks/useMfaVerify.test.ts::test_use_mfa_verify_success_sets_auth_store_mfa_enabled_true` (Change 6 signal, additive) | Unit |
| PS-AC7 | Account deactivation: `POST /account/deactivate` (unconditional `current_password`) → clears auth state, lands on `/login` with confirmation; explicit non-accidental confirmation naming the consequence | `screens/DeactivateAccountScreen.test.tsx::test_deactivate_account_screen_requires_current_password_unconditionally_and_blocks_submission_when_empty` | Integration |
| | | `screens/DeactivateAccountScreen.test.tsx::test_deactivate_account_screen_confirmation_step_names_the_consequence_before_final_submit` | Integration |
| | | `screens/DeactivateAccountScreen.test.tsx::test_deactivate_account_screen_successful_deactivation_clears_auth_state_and_lands_on_login_with_confirmation_message` | Integration |
| | | `routes/AppRoutes.test.tsx::test_app_routes_settings_deactivate_redirects_unauthenticated_visitor_to_login` | Integration |
| | | `hooks/useAccountDeactivate.test.ts::test_use_account_deactivate_success_clears_auth_session_state` | Unit |
| XC-AC1 | 4xx `application/problem+json` renders `detail`/mapped message, never raw JSON/stack trace; `422` `errors[]` maps to fields | `screens/ProfileScreen.test.tsx::test_profile_screen_422_validation_error_maps_errors_array_onto_matching_fields` | Integration |
| | | `screens/ProfileScreen.test.tsx::test_profile_screen_4xx_problem_json_renders_mapped_detail_message_with_no_raw_json` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_expired_token_renders_expired_outcome` | Integration |
| | | `screens/ConfirmEmailChangeScreen.test.tsx::test_confirm_email_change_screen_invalid_or_expired_token_renders_mapped_error` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_422_validation_error_maps_errors_onto_matching_fields` | Integration |
| | | `screens/DeactivateAccountScreen.test.tsx::test_deactivate_account_screen_incorrect_password_renders_mapped_error` | Integration |
| | | `components/apiErrorHelpers.test.ts::test_get_error_status_returns_the_numeric_status_from_a_structural_error` | Unit |
| | | `components/apiErrorHelpers.test.ts::test_get_field_errors_returns_the_field_errors_record_when_present` | Unit |
| XC-AC2 | Client-side validation: empty/malformed required fields block submission, no API call | `screens/ProfileScreen.test.tsx::test_profile_screen_blocks_submission_with_invalid_email_shape_without_calling_api` | Integration |
| | | `screens/ProfileScreen.test.tsx::test_profile_screen_blocks_submission_with_unrecognized_timezone_without_calling_api` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_resend_blocks_invalid_email_shape_without_calling_api` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_blocks_submission_when_current_password_empty_without_calling_api` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_enroll_blocks_submission_with_non_6_digit_code_without_calling_api` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_disable_requires_current_password_and_code` | Integration |
| | | `screens/DeactivateAccountScreen.test.tsx::test_deactivate_account_screen_requires_current_password_unconditionally_and_blocks_submission_when_empty` | Integration |
| XC-AC3 | Network error / 5xx → retry-capable error state, never blank screen or unhandled exception | `screens/ProfileScreen.test.tsx::test_profile_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `screens/ProfileScreen.test.tsx::test_profile_screen_5xx_response_shows_retry_capable_error_state` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_5xx_response_shows_retry_capable_error_state` | Integration |
| | | `screens/ConfirmEmailChangeScreen.test.tsx::test_confirm_email_change_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `screens/SecurityScreen.test.tsx::test_security_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `screens/DeactivateAccountScreen.test.tsx::test_deactivate_account_screen_network_error_shows_retry_capable_error_state` | Integration |
| | | `hooks/useResendVerificationEmail.test.ts::test_use_resend_verification_email_network_error_surfaces_normalized_network_error` | Unit |

## PS-AC1 — no test exists (untestable this Story)

PS-AC1 requires reading the current profile (`display_name`, `locale`,
`timezone`, `avatar_url`, `email`, `pending_email`, `email_verified`) from
`/settings/profile`. No `GET /profile` or `GET /users/me` endpoint exists on
the backend (FR-1, story Dependencies & Blockers #1, Enforcement Matrix's own
`[blocked]` marker). No test can assert a read that has nothing to read from.
This is not a gap this pass introduced or is hiding: `[blocked]` and FR-1's
own text both mark this a spec-sanctioned deferral to a future backend
Story. `screens/ProfileScreen.test.tsx::test_profile_screen_starts_blank_write_only_interim_with_no_prefilled_values`
pins the write-only interim (FR-2/Assumption #3) as a positive assertion so
the deferral is not left as a silent hole — see
`docs/evidence/US-5.2-test-generation-report.md` and the Result Envelope's
`non_blocking_findings`.

## a11y bar (Enforcement Matrix `[gate]` row)

Unlike `US-5.1`, `vitest-axe` was already an approved, in-use dependency
(confirmed by direct read of `package.json` and six existing screen test
files) — the automated check is written directly, not left as a
dependency-pending gap:

| Row | Test Function | Level |
|---|---|---|
| a11y bar — `ProfileScreen` | `screens/ProfileScreen.test.tsx::test_profile_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `SecurityScreen` | `screens/SecurityScreen.test.tsx::test_security_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `DeactivateAccountScreen` | `screens/DeactivateAccountScreen.test.tsx::test_deactivate_account_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `EmailVerificationScreen` (beyond the Enforcement Matrix's three named screens; added since this screen also carries a form) | `screens/EmailVerificationScreen.test.tsx::test_email_verification_screen_has_no_detectable_accessibility_violations` | Integration |
| a11y bar — `ConfirmEmailChangeScreen` (same reasoning) | `screens/ConfirmEmailChangeScreen.test.tsx::test_confirm_email_change_screen_has_no_detectable_accessibility_violations` | Integration |

## Supporting tests not directly named by an AC row

- `components/apiErrorHelpers.test.ts` — the remaining `getErrorStatus`/`getErrorKind`/`getErrorMessage`/`getFieldErrors` branch coverage (undefined/absent cases) underlying every screen's error rendering above, not itself a numbered AC.
- `api/httpClient.test.ts::test_http_patch_resolves_with_data_status_and_headers_on_200` — the base shape every PS-AC2/PS-AC3 assertion depends on.
- `hooks/useProfileUpdate.test.ts::test_use_profile_update_reset_conflict_clears_the_conflict_flag` — collaborator-level proof for the "reload" action ProfileScreen's 412 state exposes.
- `components/MfaEnrollmentBanner.test.tsx::test_mfa_enrollment_banner_link_targets_settings_security` — spec Assumption #6's link target; not itself a numbered AC.
- `hooks/useConfirmEmailChange.test.ts::test_use_confirm_email_change_invalid_or_expired_token_surfaces_normalized_error`, `hooks/useMfaEnroll.test.ts::test_use_mfa_enroll_incorrect_password_surfaces_normalized_error`, `hooks/useMfaActivate.test.ts::test_use_mfa_activate_invalid_code_surfaces_normalized_error_and_leaves_mfa_enabled_unchanged`, `hooks/useAccountDeactivate.test.ts::test_use_account_deactivate_incorrect_password_surfaces_normalized_error_and_leaves_session_intact` — hook-level negative-path collaborator proofs underlying the XC-AC1 screen rows above.

## Gaps Not Covered

See `docs/evidence/US-5.2-test-generation-report.md` for the full list. In
summary: PS-AC1 has no test (untestable, spec-sanctioned deferral, see
above); `screens/SecurityScreen.test.tsx` and `components/QrCode.test.tsx`
fail at module-resolution until `qrcode.react` (Task T5, human-approved) is
added to `frontend/package.json`; every OD-gated field (OD-6 locale set,
OD-7 timezone set) is tested against this pass's own recorded default per
`docs/tests/US-5.2-test-strategy.md`, not a resolved OD; OD-3
(enrollment-scoped-token navigation) has no test, matching the spec's own
"banner link only" scope.
