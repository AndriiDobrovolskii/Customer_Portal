# Traceability Matrix: Multi-Factor Authentication / TOTP (US-2.5 / spec US-009)

**Spec:** `docs/specifications/US-009-mfa-totp-spec.md`
**Task breakdown:** `docs/plans/US-009-task-breakdown.md` (T7 unit, T8 integration — test code itself deferred to IMPLEMENTATION, matrix only at this stage, same sequencing as US-2.1–US-2.4/US-3.2)
**Written:** 2026-09-01
**Reconciliation note (2026-09-02):** `docs/reconciliation/US-009-reconciliation-report.md` found this matrix's proposed test names drifted from what T7/T8 actually shipped in several places (renamed for consistency, e.g. the `test_login_*` family below shipped as `test_authenticate_user_*` — each renamed test was individually verified to still cover its row) and found 7 genuinely missing tests, all closed same-day: `test_replace_user_roles_sets_granted_at_to_recent_value` (integration, roles), `test_enroll_mfa_accepts_enrollment_scoped_token`, `test_mfa_disable_rejects_enrollment_scoped_token`, `test_verify_mfa_replayed_code_rejected_against_real_valkey` (integration, users), `test_verify_mfa_wrong_recovery_code_counts_toward_totp_lockout`, `test_rotate_refresh_token_both_scoping_triggers_true_issues_single_scoped_token` (unit, users). See that report for the full accounting; the rows below are left as originally written by `test-writer`, not retroactively renamed.

`POST /v1/auth/mfa/enroll`, `/activate`, and `DELETE /v1/auth/mfa` are protected by the standard bearer scheme, so each gets the full `AGENTS.md` §5 four-case security set (missing/invalid/expired token, insufficient scope-equivalent). `POST /v1/auth/mfa/verify` uses the distinct `mfaTokenAuth` scheme instead — its equivalent security surface is missing/invalid/expired/already-consumed `mfa_token`, plus the specific negative case of a normal bearer access token being rejected there. `POST /v1/auth/login`/`POST /v1/auth/refresh` are existing, already-covered routes (US-2.1/US-2.3) extended by this story — only their new branches are listed here, not their pre-existing coverage.

## `POST /v1/auth/mfa/enroll` — FR-1

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MF-AC1 / FR-1 | Happy path: 200, PENDING secret created, encrypted at rest (not plaintext in the stored column) | Unit | `test_enroll_mfa_creates_pending_secret_encrypted_at_rest` |
| MF-AC1 / FR-1 | `otpauth_uri` encodes SHA1/6-digit/30s params correctly | Unit | `test_enroll_mfa_otpauth_uri_encodes_rfc6238_params` |
| MF-AC1 / FR-1 | MFA not yet active (`mfa_enabled` stays false) after enroll | Unit | `test_enroll_mfa_does_not_set_mfa_enabled` |
| MF-AC1 / FR-1, OD-11 | Re-enroll while a PENDING enrolment exists overwrites the secret | Unit | `test_enroll_mfa_reenroll_while_pending_overwrites_secret` |
| MF-AC1 | Wrong `current_password` → 401 | Unit | `test_enroll_mfa_wrong_password_returns_401` |
| Security | Missing token → 401 | Integration | `test_enroll_mfa_missing_token_returns_401` |
| Security | Invalid/malformed token → 401 | Integration | `test_enroll_mfa_invalid_token_returns_401` |
| Security | Expired token → 401 | Integration | `test_enroll_mfa_expired_token_returns_401` |
| Security (positive case) | An enrolment-scoped token IS accepted here (the one endpoint category it's valid for) | Integration | `test_enroll_mfa_accepts_enrollment_scoped_token` |
| MF-AC1 | Integration: 200 body shape, DB row confirms `mfa_secret_encrypted` differs from the raw secret returned | Integration | `test_mfa_enroll_returns_200_and_persists_encrypted_secret` |

## `POST /v1/auth/mfa/activate` — FR-2

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MF-AC2 / FR-2 | Happy path: 200, 10 recovery codes returned, `mfa_enabled` becomes true, `auth_audit_log(event=mfa_enabled)` written | Unit | `test_activate_mfa_valid_code_issues_recovery_codes_and_enables_mfa` |
| MF-AC2 / FR-2 | Recovery codes stored as Argon2id hashes, never plaintext | Unit | `test_activate_mfa_recovery_codes_stored_as_argon2id_hashes` |
| MF-AC2 | Wrong code → 401 | Unit | `test_activate_mfa_wrong_code_returns_401` |
| MF-AC2 (Open Question, resolved as generic 401) | No PENDING enrolment exists → 401 | Unit | `test_activate_mfa_no_pending_enrollment_returns_401` |
| FR-2 / FR-6 exit condition | Clears `mfa_reenrollment_required` and sets `perm_epoch` when the account was recovery-code-scoped | Unit | `test_activate_mfa_clears_reenrollment_required_and_sets_perm_epoch` |
| FR-2 / FR-6 exit condition | Sets `perm_epoch` when the account was privileged-role-scoped (no `mfa_reenrollment_required` involved) | Unit | `test_activate_mfa_privileged_scoped_account_sets_perm_epoch` |
| Security | Missing/invalid/expired token → 401 | Integration | `test_activate_mfa_missing_token_returns_401`, `test_activate_mfa_invalid_token_returns_401`, `test_activate_mfa_expired_token_returns_401` |
| Security (positive case) | Enrolment-scoped token IS accepted here | Integration | `test_activate_mfa_accepts_enrollment_scoped_token` |
| MF-AC2 | Integration: 200, DB confirms `mfa_enabled=true`, 10 rows in `mfa_recovery_codes` | Integration | `test_mfa_activate_returns_200_and_persists_enabled_state` |

## `POST /v1/auth/login` (existing route, new branches) — FR-3, FR-6

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MF-AC3 / FR-3 | `mfa_enabled=true` account, correct credentials → 200 `{mfa_required: true, mfa_token}`, no access/refresh token issued | Unit | `test_login_mfa_enabled_returns_challenge_no_tokens` |
| FR-6 | Privileged role, `mfa_enabled=false`, past grace period → login issues an enrolment-scoped access token | Unit | `test_login_privileged_role_past_grace_period_issues_scoped_token` |
| FR-6 / OD-4 | Privileged role, `mfa_enabled=false`, within grace period → normal token + grace-period-deadline field | Unit | `test_login_privileged_role_within_grace_period_returns_deadline_field` |
| FR-6 / OD-5 | `mfa_reenrollment_required=true` → scoped token issued regardless of role, no grace period | Unit | `test_login_reenrollment_required_issues_scoped_token_no_grace` |
| FR-6 (regression) | Non-privileged, `mfa_enabled=false`, no reenrollment flag → ordinary login, unaffected | Unit | `test_login_ordinary_user_unaffected_by_mfa_scoping` |
| FR-6 (`_resolve_enrollment_scoping` OR-combination) | Both triggers true simultaneously → still exactly one scoped token, not double-handling | Unit | `test_login_both_scoping_triggers_true_issues_single_scoped_token` |
| MF-AC3 | Integration: full login → challenge → `POST /mfa/verify` completes login exactly as LI-AC1 | Integration | `test_login_then_mfa_verify_completes_as_standard_login` |

## `POST /v1/auth/refresh` (existing route, new branch) — FR-6 spec-review resolution

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| FR-6 resolution | Refresh re-evaluates the scoping condition: still holds → re-issues an equally scoped token | Unit | `test_refresh_reissues_scoped_token_when_condition_still_holds` |
| FR-6 resolution | Refresh re-evaluates: condition resolved (enrolled since last check) → issues a normal token | Unit | `test_refresh_reissues_normal_token_when_condition_resolved` |
| FR-6 resolution | Integration: enrolment-scoped account calls `/refresh` instead of logging in again — new access token still scoped | Integration | `test_refresh_while_enrollment_scoped_returns_scoped_access_token` |

## `POST /v1/auth/mfa/verify` — FR-3, FR-4, FR-5, FR-7

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MF-AC3 / FR-3 | Valid TOTP code completes login (LI-AC1 shape) | Unit | `test_verify_mfa_valid_totp_completes_login` |
| MF-AC4 / FR-4 | Incorrect code → 401 `mfa-invalid-code` | Unit | `test_verify_mfa_incorrect_code_returns_401` |
| MF-AC4 / FR-4 | Replayed code (already accepted this step) → 401 | Unit | `test_verify_mfa_replayed_code_returns_401` |
| MF-AC4 / FR-4 | ±1 step skew accepted; ±2 steps rejected | Unit (parametrized) | `test_verify_mfa_skew_tolerance[-1-True]`, `[0-True]`, `[1-True]`, `[2-False]`, `[-2-False]` |
| MF-AC5 / FR-5 | 5th failed attempt → 429, `mfa_token` invalidated, full re-auth required | Unit | `test_verify_mfa_fifth_failure_returns_429_invalidates_token` |
| MF-AC5 / FR-5, OD-10 | A wrong recovery code counts toward the same lockout counter as a wrong TOTP code | Unit | `test_verify_mfa_wrong_recovery_code_counts_toward_totp_lockout` |
| MF-AC7 / FR-7 | Valid recovery code completes login, code consumed (single-use) | Unit | `test_verify_mfa_valid_recovery_code_completes_login_and_consumes_it` |
| MF-AC7 / FR-7 | Already-consumed recovery code rejected | Unit | `test_verify_mfa_already_consumed_recovery_code_returns_401` |
| MF-AC7 / FR-7, OD-5 | Recovery-code use sets `mfa_reenrollment_required=true`, writes `auth_audit_log(event=mfa_recovery_used)`, sends security-notification email | Unit | `test_verify_mfa_recovery_code_sets_reenrollment_flag_and_notifies` |
| Security | Missing `mfa_token` → 401 | Integration | `test_verify_mfa_missing_token_returns_401` |
| Security | Invalid/expired/already-consumed `mfa_token` → 401 | Integration | `test_verify_mfa_invalid_or_expired_token_returns_401`, `test_verify_mfa_already_consumed_token_returns_401` |
| Security | A normal bearer access token presented as `mfa_token` is rejected | Integration | `test_verify_mfa_rejects_normal_access_token_as_mfa_token` |
| MF-AC4 | Integration: fixed TOTP clock, skew and replay cases end-to-end | Integration | `test_mfa_verify_skew_and_replay_with_fixed_clock` |
| MF-AC5 | Integration: fixed Valkey counter, 5th attempt returns 429 | Integration | `test_mfa_verify_fifth_failure_returns_429_fixed_counter` |
| MF-AC7 | Integration: recovery-code login end-to-end, code consumed in DB | Integration | `test_mfa_verify_recovery_code_login_persists_consumption` |

## `DELETE /v1/auth/mfa` — FR-6, FR-8

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MF-AC6 / FR-6 | Privileged role (`admin`/`auditor`/`support_agent`) → 409 `mfa-required-for-role` | Unit (parametrized over the 3 roles) | `test_disable_mfa_privileged_role_returns_409[admin]`, `[auditor]`, `[support_agent]` |
| FR-8 (not covered by any source AC — OD-6/OD-8) | Non-privileged, correct password + code → 204, `mfa_enabled=false`, secret nulled, all recovery codes deleted, `auth_audit_log(event=mfa_disabled)`, `revoke_before` set | Unit | `test_disable_mfa_non_privileged_success_purges_state_and_revokes_sessions` |
| FR-8 | Wrong `current_password` → 401 | Unit | `test_disable_mfa_wrong_password_returns_401` |
| FR-8 | Wrong code → 401 | Unit | `test_disable_mfa_wrong_code_returns_401` |
| Security | Missing/invalid/expired token → 401 | Integration | `test_disable_mfa_missing_token_returns_401`, `test_disable_mfa_invalid_token_returns_401`, `test_disable_mfa_expired_token_returns_401` |
| Security (negative case, distinct from enroll/activate) | An enrolment-scoped token attempting `DELETE /v1/auth/mfa` → 403 `mfa-enrollment-required` (this route is NOT in the enrollment allow-list) | Integration | `test_disable_mfa_rejects_enrollment_scoped_token` |
| FR-8 | Integration: 204, DB confirms full purge and other sessions revoked | Integration | `test_mfa_disable_returns_204_and_persists_full_purge` |
| MF-AC6 | Integration: privileged-role 409 end-to-end | Integration | `test_mfa_disable_privileged_role_returns_409` |

## Cross-Cutting: Enrolment-Scoped-Token Default-Deny (the single most important test in this story — see `US-009-implementation-plan.md` Risks)

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| FR-6/FR-7 mechanism | `get_authenticated_user` rejects an `mfa_enrollment_required=true` token on a representative sample of existing protected routes (`GET /v1/profile`, `GET /v1/admin/roles`, `DELETE /v1/auth/mfa`) with `403 mfa-enrollment-required` | Unit (parametrized) | `test_get_authenticated_user_rejects_enrollment_scoped_token_on_other_routes` |
| FR-6/FR-7 mechanism | `get_current_user_allow_enrollment_scoped` accepts the same token unchanged | Unit | `test_get_current_user_allow_enrollment_scoped_accepts_scoped_token` |
| FR-6/FR-7 mechanism | Every other route in the app still resolves via the default, unchanged `CurrentUserDep` (no route was silently switched to the lenient dependency) | Integration | `test_only_enroll_and_activate_routes_use_enrollment_scoped_dependency` |
| Full flow | Privileged grant → scoped login → blocked non-enrollment call (403) → activate → old token now `401 token-stale` → refresh → normal token → previously-blocked call now succeeds | Integration | `test_full_enrollment_scoping_flow_role_grant_to_resolution` |
| Full flow (second trigger) | Recovery-code use → scoped login → activate → resolution, same shape as the role-grant flow | Integration | `test_full_enrollment_scoping_flow_recovery_code_to_resolution` |

## Supporting Units (not directly AC-driven, but required by the plan's resolutions)

| Source | Case | Level | Test Function |
|---|---|---|---|
| OD-2 / `app/core/crypto.py` | Round-trip encrypt/decrypt returns the original plaintext | Unit | `test_encrypt_decrypt_mfa_secret_round_trip` |
| OD-2 / `app/core/crypto.py` | Wrong key fails to decrypt | Unit | `test_decrypt_mfa_secret_wrong_key_raises` |
| OD-2 / `app/core/crypto.py` | Tampered ciphertext fails to decrypt (AES-GCM authentication) | Unit | `test_decrypt_mfa_secret_tampered_ciphertext_raises` |
| Plan Architectural Change #5 | `RoleService.get_role_grants_for_user` returns name+`granted_at` pairs correctly | Unit | `test_get_role_grants_for_user_returns_names_and_timestamps` |
| Plan Architectural Change #5 | `UserRoleRepository.replace_for_user` sets `granted_at` explicitly on every inserted row | Unit | `test_replace_for_user_sets_granted_at_explicitly` |

## Coverage Check

All 7 source ACs (MF-AC1–MF-AC7) have at least one unit and one integration test. FR-8 (the disable-success path with no source AC, per OD-6/OD-8) has full coverage despite having no AC to trace to — its origin is documented in the row itself. Both enrolment-scoped-token triggers (FR-6's privileged-role grant, FR-7/OD-5's recovery-code use) and their shared exit condition (FR-2) are each covered independently and as one combined end-to-end flow. The default-deny mechanism itself — flagged in the plan as the single highest-risk line in the story — has dedicated tests in both directions (rejects elsewhere, accepts on the two enrollment routes) plus a full-flow integration test per trigger. No AC is left with only a single test level where a persisted-state assertion genuinely requires the integration level to prove it.
