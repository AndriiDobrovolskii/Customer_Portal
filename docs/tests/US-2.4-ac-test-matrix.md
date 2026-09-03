# Traceability Matrix: Password Reset (US-2.4 / spec US-2.4)

**Spec:** `docs/specifications/US-2.4-spec.md`
**Task breakdown:** `docs/plans/US-2.4-task-breakdown.md` (T6 unit, T7 integration — test code itself deferred to IMPLEMENTATION, matrix only at this stage, same sequencing as US-2.1/US-2.2/US-2.3)
**Written:** 2026-09-01

Both endpoints are unauthenticated by design (source story's API Contract: `Auth: None`), so the standard `AGENTS.md` §5 "four security cases per protected route" (missing/invalid/expired token, wrong scope) does not apply here — there is no bearer token to be missing or invalid. The equivalent security surface for this story is anti-enumeration (NFR-002) and rate limiting (NFR-003), covered below.

## `POST /v1/auth/password-reset/request`

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| PR-AC1 / FR-1 | Happy path: known active account gets a token, email, audit entry | Unit | `test_request_password_reset_known_account_creates_token_and_sends_email` |
| PR-AC1 / FR-1 | Prior unconsumed token for the account is invalidated | Unit | `test_request_password_reset_invalidates_prior_unconsumed_token` |
| PR-AC1 / FR-1, OD-3 | `auth_audit_log(event=password_reset_requested)` written | Unit | `test_request_password_reset_writes_audit_log_entry` |
| PR-AC1 | 202 status, generic body, integration round-trip | Integration | `test_password_reset_request_returns_202_with_generic_body` |
| PR-AC3 / FR-3 | Unknown email: 202 generic body, no email sent | Unit | `test_request_password_reset_unknown_email_returns_generic_response_no_email_sent` |
| PR-AC3 / FR-3 | Deactivated account: 202 generic body, no email sent | Unit | `test_request_password_reset_deactivated_returns_generic_no_email` (renamed during T6 for line-length) |
| PR-AC3 / FR-3, OD-3 | Unknown/deactivated still writes `password_reset_requested` audit entry (server-side only, doesn't affect response) | Unit | `test_request_password_reset_unknown_email_still_writes_audit_log_entry` |
| PR-AC3 / FR-3 (implementation-time addition, not a source AC — see below) | Unverified account also treated as ineligible, mirroring login's own eligibility notion | Unit | `test_request_password_reset_unverified_returns_generic_no_email` |
| PR-AC3 | Integration: unknown-email response is byte-identical in status/body to a known-account response | Integration | `test_password_reset_request_unknown_email_returns_202_identical_body` |
| PR-AC6 / FR-6 | Second request within 60 s cooldown → 429 | Unit | `test_request_password_reset_second_call_within_cooldown_returns_429` |
| PR-AC6 / FR-6 | 6th request within an hour (per-account) → 429 | Unit | `test_request_password_reset_sixth_call_within_hour_returns_429` |
| PR-AC6 / FR-6 | 11th request within an hour from one IP → 429 | Unit | `test_request_password_reset_eleventh_call_from_ip_within_hour_returns_429` |
| PR-AC6 / FR-6, OD-2 | Check order: cooldown trips before either hourly limit is even evaluated | Unit | `test_request_password_reset_check_order_cooldown_before_hourly_limits` |
| PR-AC6 | Integration: flooding returns 429 with `Retry-After` header | Integration | `test_password_reset_request_flooding_returns_429_with_retry_after` |

## `POST /v1/auth/password-reset/confirm`

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| PR-AC2 / FR-2 | Happy path: password replaced (Argon2id), token consumed | Unit | `test_confirm_password_reset_valid_token_replaces_password_and_revokes_sessions` |
| PR-AC2 / FR-2 | `revoke_before:{user_id}` set, terminating sessions and refresh families | Unit | (asserted within the above; same test) |
| PR-AC2 / FR-2 | "Password changed" notification email sent | Unit | `test_confirm_password_reset_sends_notification_email` |
| PR-AC2 / FR-2 | `auth_audit_log(event=password_reset_completed)` written | Unit | `test_confirm_password_reset_writes_audit_log_completed_event` |
| PR-AC2 | Integration: 200, `users.hashed_password` actually changed in DB | Integration | `test_password_reset_confirm_returns_200_and_persists_new_password_hash` |
| PR-AC2 | Integration: prior session/refresh-family tokens rejected after reset | Integration | `test_password_reset_confirm_revokes_all_sessions_and_refresh_families` |
| PR-AC4 / FR-4 | Unknown token hash → 400 `token-invalid` | Unit | `test_confirm_password_reset_unknown_token_hash_raises_token_invalid` |
| PR-AC4 / FR-4 | Already-consumed token → 400 `token-invalid` | Unit | `test_confirm_password_reset_already_consumed_token_raises_token_invalid` |
| PR-AC4 / FR-4 | Expired token → 400 `token-expired` | Unit | `test_confirm_password_reset_expired_token_raises_token_expired` |
| PR-AC4 | Integration: each of the three states, real DB rows | Integration | `test_password_reset_confirm_expired_token_returns_400_token_expired`, `test_password_reset_confirm_unknown_token_returns_400_token_invalid`, `test_password_reset_confirm_consumed_token_returns_400_token_invalid` |
| PR-AC5 / FR-5 | Password < 12 chars → 422 `password-policy`, token not consumed | Unit | `test_confirm_password_reset_too_short_raises_policy_keeps_token` (renamed during T6 for line-length) |
| PR-AC5 / FR-5, OD-1 | Breached password (local list) → 422, token not consumed | Unit | `test_confirm_password_reset_breached_raises_policy_keeps_token` (renamed during T6 for line-length) |
| PR-AC5 / FR-5 | Password equals current → 422, token not consumed | Unit | `test_confirm_password_reset_reused_raises_policy_keeps_token` (renamed during T6 for line-length) |
| PR-AC5 | Integration: 422, token still valid/reusable after rejection | Integration | `test_password_reset_confirm_weak_password_returns_422_token_not_consumed` |
| Spec-review resolution (accepted 2026-09-01) — atomic consumption | Two concurrent confirm calls against the same token: fake exercises the repository's race branch | Unit | `test_confirm_password_reset_concurrent_requests_only_one_succeeds` |
| Spec-review resolution — atomic consumption | Real concurrent `asyncio.gather` confirm calls against real Postgres: exactly one 200, the other a genuine 400 `token-invalid` | Integration | `test_password_reset_confirm_concurrent_same_token_exactly_one_succeeds` |

## Coverage Check

All six source ACs (PR-AC1–PR-AC6) have at least one unit and one integration test. All three resolved Open Decisions (OD-1 breach mechanism, OD-2 check order, OD-3 request-side audit) and the spec-review-accepted atomic-consumption requirement each have a dedicated test. No AC is left with only a single test level where a state assertion (DB/audit-log row) genuinely requires the integration level to prove.
