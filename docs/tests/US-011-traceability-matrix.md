# Traceability Matrix: Manage Users (US-3.1 / spec US-011)

**Spec:** `docs/specifications/US-011-manage-users-spec.md`
**Task breakdown:** `docs/plans/US-011-task-breakdown.md` (T7 unit, T8 integration — test code itself deferred to IMPLEMENTATION, matrix only at this stage, same sequencing as US-2.1–US-2.6/US-3.2)
**Written:** 2026-09-02
**Note (2026-09-02, post-RECONCILIATION):** this matrix was written before IMPLEMENTATION; several test function names below were renamed during actual coding (e.g. `test_get_admin_users_returns_200_and_paginates` shipped as `test_list_users_returns_200_and_paginates`). `docs/reconciliation/US-011-reconciliation-report.md`'s AC → Test table is the authoritative, verified name mapping — consult it, not this file, for the exact shipped test function per AC.

Every route under `/v1/admin/*` gets the full `AGENTS.md` §5 security case set (missing/invalid/expired token, insufficient permission scope) except `DELETE`, which has no permission check (any authenticated caller gets 405 per FR-17's resolved reading — see `US-011-api-design.md`).

## `GET /v1/admin/users` — FR-1, FR-2, FR-3, FR-4

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MU-AC1 / FR-1 | Happy path: `q`/`status`/`limit` filters applied, cursor-paginated, item shape (`id`, `email`, `display_name`, `status`, `roles`, `created_at`, `last_login_at`) | Unit | `test_list_users_returns_filtered_paginated_page` |
| MU-AC1 / FR-1 | Response contains no password hash, token, or credential material | Unit | `test_list_users_response_excludes_credential_material` |
| MU-AC1 / FR-1 | `q` matches against both `email` and `display_name` | Unit | `test_list_users_q_matches_email_and_display_name` |
| MU-AC4 / FR-4 | `limit=5000` → 422 `validation-failed`, no partial result | Unit | `test_list_users_limit_over_max_returns_422` |
| MU-AC4 / FR-4 | Unknown `status` value → 422 `validation-failed` | Unit | `test_list_users_unknown_status_returns_422` |
| MU-AC4 / FR-4 | Malformed `cursor` → 422 `validation-failed` | Unit | `test_list_users_malformed_cursor_returns_422` |
| MU-AC2 / FR-2 | Missing `users:read` → 403 `insufficient-permission`, `auth_audit_log(event=authz_denied)` written | Unit | `test_list_users_insufficient_permission_returns_403_and_audits` |
| MU-AC3 / FR-3, Security | Missing token → 401 | Integration | `test_list_users_missing_token_returns_401` |
| Security | Invalid/malformed token → 401 | Integration | `test_list_users_invalid_token_returns_401` |
| Security | Expired token → 401 | Integration | `test_list_users_expired_token_returns_401` |
| MU-AC1 | Integration: 200 body shape + real cursor pagination across >1 page with real Postgres rows | Integration | `test_get_admin_users_returns_200_and_paginates` |
| Data-design gap | Integration: `q` search actually returns matches via the `pg_trgm` index (not a sequential scan false-negative) | Integration | `test_get_admin_users_q_search_matches_trigram_index` |

## `GET /v1/admin/users/{id}` — FR-22, FR-23 (Open Decision OD-3, no source AC)

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| FR-22 | Happy path: existing user → 200, same item shape as one list entry, `ETag` header present | Unit | `test_get_user_returns_200_with_etag` |
| FR-23 | Unknown id → 404 `not-found` | Unit | `test_get_user_unknown_id_returns_404` |
| FR-23 | Missing `users:read` → 403 `insufficient-permission`, audited | Unit | `test_get_user_insufficient_permission_returns_403_and_audits` |
| FR-23, Security | Missing/invalid/expired token → 401 | Integration | `test_get_user_missing_token_returns_401`, `test_get_user_invalid_token_returns_401`, `test_get_user_expired_token_returns_401` |
| FR-22 | Integration: 200 body + `ETag` matches the value `PATCH`'s `If-Match` accepts (round-trip proof) | Integration | `test_get_user_etag_accepted_by_subsequent_patch` |

## `POST /v1/admin/users` — FR-5, FR-6, FR-7, FR-8

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MU-AC5 / FR-5 | Happy path: `{email, display_name, roles}` → 201 + ETag, `status="invited"`, `email_verified=false`, no password set, invitation email sent, `admin_audit_log(event=user_created)` written | Unit | `test_create_user_returns_201_and_provisions_invitation` |
| MU-AC6 / FR-6 | Duplicate email (case-insensitive) → 409 `email-already-registered`, no account/invitation created | Unit | `test_create_user_duplicate_email_returns_409` |
| MU-AC7 / FR-7 | Request body containing `"password"` → 422 `validation-failed` (rejected as an unknown field, `extra="forbid"`) | Unit | `test_create_user_password_field_returns_422` |
| MU-AC8 / FR-8 | Requested role grants a permission the actor doesn't hold → 403 `privilege-escalation`, no account created, calls `RoleService.check_no_privilege_escalation` (not a reimplemented check) | Unit | `test_create_user_privilege_escalation_returns_403` |
| FR-2 pattern | Missing `users:write` → 403 `insufficient-permission` | Unit | `test_create_user_insufficient_permission_returns_403` |
| Security | Missing/invalid/expired token → 401 | Integration | `test_create_user_missing_token_returns_401`, `test_create_user_invalid_token_returns_401`, `test_create_user_expired_token_returns_401` |
| MU-AC5 | Integration: 201, DB confirms `users` row + `invitation_tokens` row (24h TTL) + `admin_audit_log` row | Integration | `test_post_admin_users_returns_201_and_persists_invitation` |
| MU-AC6, BR-001 | Integration: two concurrent `POST /v1/admin/users` for the same email (`asyncio.gather`) → exactly one 201, one 409, atomic at the data layer | Integration | `test_concurrent_create_user_same_email_exactly_one_succeeds` |

## `PATCH /v1/admin/users/{id}` — FR-9, FR-10, FR-11, FR-12

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MU-AC9 / FR-9 | Happy path: valid `If-Match` + whitelisted field + required `reason` → 200 + new ETag, one `admin_audit_log` row per changed field (`field`, `old_value`, `new_value`, `reason`, `actor_id`) | Unit | `test_update_user_returns_200_and_writes_one_audit_row_per_field` |
| MU-AC9 / FR-9 | Multiple whitelisted fields changed in one request → one audit row per field, not one row for the whole request | Unit | `test_update_user_multiple_fields_writes_multiple_audit_rows` |
| MU-AC10 / FR-10 | Stale `If-Match` → 412 `precondition-failed`, no field changed | Unit | `test_update_user_stale_etag_returns_412` |
| MU-AC10 / FR-10 | Missing `If-Match` → 400 `precondition-required` | Unit | `test_update_user_missing_if_match_returns_400` |
| MU-AC11 / FR-11 | Body contains `id`/`created_at`/`email_verified`/`roles` → 422 `immutable-field`, checked against the raw body before Pydantic validation, no field changed | Unit | `test_update_user_immutable_field_returns_422` |
| MU-AC11 / FR-11 | Body contains `email` or an unknown field → 422 `validation-failed` (not `immutable-field` — `email` isn't in MU-AC11's immutable list) | Unit | `test_update_user_undeclared_field_returns_422_validation_failed` |
| MU-AC12 / FR-12 | Unknown user id → 404 `not-found` | Unit | `test_update_user_unknown_id_returns_404` |
| FR-2 pattern | Missing `users:write` → 403 `insufficient-permission` | Unit | `test_update_user_insufficient_permission_returns_403` |
| Security | Missing/invalid/expired token → 401 | Integration | `test_update_user_missing_token_returns_401`, `test_update_user_invalid_token_returns_401`, `test_update_user_expired_token_returns_401` |
| MU-AC9 | Integration: 200, DB confirms `users` row updated + `admin_audit_log` rows persisted with correct `old_value`/`new_value` | Integration | `test_patch_admin_user_returns_200_and_persists_audit_rows` |
| MU-AC10 | Integration: real ETag race — two `PATCH` requests with the same stale `If-Match`, one 200 + one 412 | Integration | `test_concurrent_patch_stale_etag_race_one_wins` |

## `POST /v1/admin/users/{id}/deactivate` — FR-13, FR-14, FR-15, FR-16, FR-17b

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MU-AC13 / FR-13 | Happy path: active target + required `{reason}` → 200, `status="deactivated"`, `deactivated_at` set, `revoke_before` set to now, `account_lifecycle_audit_log(event=deactivated, actor="admin:{id}", reason=...)` written | Unit | `test_deactivate_user_returns_200_and_applies_da_ac1_side_effects` |
| MU-AC14 / FR-14 | Already-deactivated target → 409 `already-deactivated` | Unit | `test_deactivate_user_already_deactivated_returns_409` |
| MU-AC15 / FR-15 | Admin id equals target id → 409 `cannot-target-self` | Unit | `test_deactivate_user_self_target_returns_409` |
| MU-AC16 / FR-16 | Target is the only remaining active admin → 409 `last-admin`, account remains active, calls `RoleService.raise_if_last_admin` (additive-only, not via `replace_user_roles`) | Unit | `test_deactivate_user_last_admin_returns_409` |
| MU-AC16 / FR-16 | Target holds admin but is *not* the last one → 200, succeeds | Unit | `test_deactivate_user_admin_not_last_succeeds` |
| MU-AC16 / FR-16 | Target doesn't hold admin at all → `raise_if_last_admin` passes without querying the count | Unit | `test_deactivate_user_non_admin_target_skips_last_admin_check` |
| FR-17b | Unknown user id → 404 `not-found` (no source AC — precedent from FR-12/FR-21) | Unit | `test_deactivate_user_unknown_id_returns_404` |
| FR-2 pattern | Missing `users:write` → 403 `insufficient-permission` | Unit | `test_deactivate_user_insufficient_permission_returns_403` |
| MU-AC13 | `reason` missing/empty → 422 `validation-failed` | Unit | `test_deactivate_user_missing_reason_returns_422` |
| Security | Missing/invalid/expired token → 401 | Integration | `test_deactivate_user_missing_token_returns_401`, `test_deactivate_user_invalid_token_returns_401`, `test_deactivate_user_expired_token_returns_401` |
| MU-AC13 | Integration: 200, DB confirms `users.status`/`deactivated_at`, `revoke_before:{id}` set in Valkey, `account_lifecycle_audit_log` row with `reason` persisted | Integration | `test_post_deactivate_returns_200_and_persists_all_side_effects` |
| MU-AC16 | Integration: genuine concurrency test (`asyncio.gather`) — two simultaneous deactivations of the last two admins → exactly one 200, one 409, never zero admins remain (per the spec's own Enforcement Matrix requirement) | Integration | `test_concurrent_deactivate_last_two_admins_exactly_one_succeeds` |

## `DELETE /v1/admin/users/{id}` — FR-17

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MU-AC17 / FR-17 | Authenticated caller, any role/permission → 405, no handler logic runs beyond the status | Unit | `test_delete_user_any_authenticated_actor_returns_405` |
| MU-AC17 / FR-17, resolved reading | Unauthenticated caller → 401, not 405 (MU-AC3's blanket rule still applies — see `US-011-api-design.md`'s resolution) | Integration | `test_delete_user_missing_token_returns_401_not_405` |
| MU-AC17 | Integration: 405 for an authenticated admin, target user row unchanged | Integration | `test_delete_admin_user_returns_405_and_leaves_row_untouched` |

## `POST /v1/admin/users/{id}/resend-invite` — FR-18, FR-19, FR-20, FR-21

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| MU-AC18 / FR-18 | Happy path: target status `invited` → 202 generic body, prior unconsumed token's `consumed_at` set (invalidated), fresh 24h token emailed, `admin_audit_log(event=invitation_resent)` written | Unit | `test_resend_invite_returns_202_and_reissues_token` |
| MU-AC19 / FR-19 | Target status `active` → 409 `invalid-state-transition`, no email sent | Unit | `test_resend_invite_active_target_returns_409` |
| MU-AC19 / FR-19 | Target status `deactivated` → 409 `invalid-state-transition`, no email sent | Unit | `test_resend_invite_deactivated_target_returns_409` |
| MU-AC20 / FR-20 | Resent within 60s of the last resend → 429 with `Retry-After` (fixed clock) | Unit | `test_resend_invite_within_cooldown_returns_429` |
| MU-AC20 / FR-20 | 6th resend within the same rolling hour → 429, per-account 5/hour cap (fixed clock) | Unit | `test_resend_invite_over_hourly_cap_returns_429` |
| MU-AC21 / FR-21 | Unknown user id → 404 | Unit | `test_resend_invite_unknown_id_returns_404` |
| MU-AC21 / FR-21 | Missing `users:write` → 403, denied attempt audited | Unit | `test_resend_invite_insufficient_permission_returns_403_and_audits` |
| Security | Missing/invalid/expired token → 401 | Integration | `test_resend_invite_missing_token_returns_401`, `test_resend_invite_invalid_token_returns_401`, `test_resend_invite_expired_token_returns_401` |
| MU-AC18 | Integration: 202, DB confirms prior token invalidated + fresh `invitation_tokens` row + `admin_audit_log` row, real Valkey-backed cooldown | Integration | `test_post_resend_invite_returns_202_and_persists_new_token` |
| MU-AC20 | Integration: real fixed-Valkey-clock cooldown and hourly-cap enforcement across repeated calls | Integration | `test_resend_invite_cooldown_and_cap_enforced_against_real_valkey` |

## Supporting Units — `app/modules/roles/service.py`'s two new methods (not directly AC-driven, required by MU-AC8/FR-8, MU-AC16/FR-16)

| Source | Case | Level | Test Function |
|---|---|---|---|
| FR-8 | `check_no_privilege_escalation`: requested permissions ⊆ actor scopes → passes | Unit | `test_check_no_privilege_escalation_subset_passes` |
| FR-8 | `check_no_privilege_escalation`: requested permissions exceed actor scopes → raises `PrivilegeEscalationError` | Unit | `test_check_no_privilege_escalation_superset_raises` |
| Plan-review regression guard | `replace_user_roles`'s existing test cases still pass unchanged after `check_no_privilege_escalation` is extracted into it | Unit | (existing `test_roles_service.py` cases, re-run — no new function, regression check) |
| FR-16 | `raise_if_last_admin`: target holds admin + is the last active one → raises `LastAdminError` | Unit | `test_raise_if_last_admin_sole_admin_raises` |
| FR-16 | `raise_if_last_admin`: target holds admin + is *not* the last one → passes | Unit | `test_raise_if_last_admin_not_sole_admin_passes` |
| FR-16 | `raise_if_last_admin`: target doesn't hold admin at all → passes without querying `count_active_admins_excluding` | Unit | `test_raise_if_last_admin_non_admin_target_skips_query` |
| Plan-review regression guard | `replace_user_roles`'s existing `{admin}` → `{admin, auditor}` case (or equivalent) still succeeds — proves `raise_if_last_admin` is genuinely not wired into it | Unit | `test_replace_user_roles_admin_to_admin_plus_auditor_still_succeeds` |

## Coverage Check

All 21 source ACs (MU-AC1–MU-AC21) have at least one unit and, where a persisted-state or real-concurrency assertion is required, an integration test. FR-17b, FR-22, and FR-23 (no source AC — OD-3 and the Deactivate-slice precedent resolution) have full coverage despite having no AC to trace to, per this project's established convention (US-2.6 FR-6/FR-7). Both `roles/service.py` additions have dedicated unit coverage independent of the two endpoints that consume them (mirroring US-2.6's `geoip.py`/`device.py` pattern), plus two explicit regression-guard tests proving the plan-review-corrected wiring (`check_no_privilege_escalation` extracted and called; `raise_if_last_admin` additive-only, not called) holds in the actual implementation, not just on paper. MU-AC16 and FR-6 (BR-001) both have a genuine concurrency integration test, per the spec's own Enforcement Matrix and the plan's Testing Strategy. No AC is left with only a single test level where a persisted-state assertion genuinely requires the integration level to prove it.
