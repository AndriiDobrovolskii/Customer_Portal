# Verification Report: Manage Users (US-3.1 / spec US-3.1)

**Story ID:** US-3.1
**gate-enforcer Result Relied On:** Pass — 7/7 pre-commit hooks (ruff lint+format, mypy strict on 113 files, import-linter 6/6, unit tests, no-mock-in-integration, detect-secrets), 509/509 tests, 96.64% coverage (floor 85%)
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass

## Summary

Verified the human-judgment half of the Definition of Done for US-3.1's new `admin_users` module and its cross-cutting changes to `roles`/`account`/`users`. One real gap was found during this pass — most protected routes had only a `missing_token` case at the integration level, not the full §5 five-case set — and fixed same-day (24 new integration tests added, gate re-confirmed green at 509/509). Everything else — ORM containment, cache TTL, service→service discipline, and §6.7 contract/security items — checked out clean on the first read.

## §6.5 — Migration Human Half

- Generated file read: Yes — both `a5edc35c8e96_admin_users_invitation_tokens_and_audit_.py` and `1b2b1d52dd71_admin_users_email_display_name_trgm_.py` were read in full by `migration-manager` before the upgrade/downgrade/upgrade cycle was run (this session's own T3/T3b execution).
- Rewriter-unreachable statements guarded: Pass — `a5edc35c8e96` lines 65-79 wrap all 5 `add_column` calls in `if "<column>" not in {c["name"] for c in inspector.get_columns(...)}:` guards (`account_lifecycle_audit_log.reason`; `admin_audit_log.field`/`old_value`/`new_value`/`reason`), mirroring `2c77dd65027b`'s exemplar pattern exactly. `create_table`/`create_index` calls (lines 30-56) carry `if_not_exists=True`, added by the Rewriter automatically.
- `downgrade()` real, not `pass`: Pass — `a5edc35c8e96` lines 82-102 perform the real inverse (drop the 5 columns under the same guard pattern, drop the index, drop the table); `1b2b1d52dd71` lines 66-79 drop both concurrent indexes and the extension. Both migrations' `upgrade → downgrade → upgrade` cycles were actually run against real PostgreSQL (this session's T3/T3b output), not merely asserted.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/admin_users/service.py`: every one of the 6 public methods has a `-> UserRead`/`-> tuple[UserRead, str]`/`-> UserListResponse`/`-> ResendInviteResponse` return annotation (lines 184, 211, 226, 273, 322, 357) and returns via the `_to_user_read()` helper (line 149) or a schema constructor — never the raw `User` ORM object. `router.py` imports only `schemas`/`dependencies`/`fastapi`/stdlib (confirmed by grep: zero `sqlalchemy`/`models`/`repository` matches). |
| All nested data eager-loaded | N/A | No SQLAlchemy `relationship()` is introduced or touched by this story — `admin_users/repository.py`'s `_role_names_for_users` reads role names via an explicit `select(UserRole.user_id, Role.name).join(...)` query (repository.py lines 51-61), not an ORM relationship traversal, so the eager-loading rule doesn't apply. |
| Every cache write has a TTL | Pass | `admin_users/service.py` line ~345 (`deactivate_user`): `await self._revocation_cache.set_revoke_before(target_id, ttl_seconds=settings.refresh_token_ttl_seconds)` — reuses the existing `RevocationCache` gateway, same TTL rationale `AccountService.deactivate_account` already established. This is the only cache write this story introduces. |
| Cross-module calls go service→service | Pass | `admin_users/dependencies.py` line 17 injects `RoleServiceDep` (from `app.modules.roles.dependencies`, which itself composes `roles.service.RoleService`) into `AdminUserService.__init__` — `admin_users/service.py` calls `self._role_service.resolve_role_ids_for_grant(...)` (line 236) and `self._role_service.raise_if_last_admin(...)` (line 341), never touching `roles.repository` or `roles.router`. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `admin_users/router.py`: all 7 routes (`list_users`, `get_user`, `create_user`, `update_user`, `deactivate_user`, `delete_user_not_allowed`, `resend_invite`) declare both — including `delete_user_not_allowed`'s explicit `response_model=None, status_code=status.HTTP_405_METHOD_NOT_ALLOWED`, matching the `users/router.py` `response_model=None` precedent for no-body routes. |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `admin_users/schemas.py`: `CreateUserRequest`, `UpdateUserRequest`, `DeactivateUserRequest` all set `model_config = ConfigDict(extra="forbid")`. None declares `id`, `created_at`, `email_verified`, `status`, or `hashed_password`; `UpdateUserRequest` additionally excludes `roles` and `email` by omission (checked against the raw body pre-validation for the immutable set, per `update_user`'s implementation). |
| `.env.example` updated (if applicable) | Pass | `INVITATION_TOKEN_TTL_HOURS=24` and `INVITATION_RESEND_HOURLY_LIMIT=5` both added, 1:1 with `app/core/config.py`'s two new settings. |
| No sensitive field in any `*Read` | Pass | `UserRead` (`admin_users/schemas.py`) declares exactly `id`, `email`, `display_name`, `status`, `roles`, `created_at`, `last_login_at` — no `hashed_password`, token, or MFA field. |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `GET /admin/users` | `test_list_users_missing_token_returns_401` | `test_list_users_expired_token_returns_401` | `test_list_users_invalid_token_returns_401` | `test_list_users_insufficient_permission_returns_403` | `test_list_users_revoked_session_returns_401` |
| `GET /admin/users/{id}` | `test_get_user_missing_token_returns_401` | `test_get_user_expired_token_returns_401` | `test_get_user_invalid_token_returns_401` | `test_get_user_insufficient_permission_returns_403` | `test_get_user_revoked_session_returns_401` |
| `POST /admin/users` | `test_create_user_missing_token_returns_401` | `test_create_user_expired_token_returns_401` | `test_create_user_invalid_token_returns_401` | `test_create_user_insufficient_permission_returns_403` | `test_create_user_revoked_session_returns_401` |
| `PATCH /admin/users/{id}` | `test_patch_user_missing_token_returns_401` | `test_patch_user_expired_token_returns_401` | `test_patch_user_invalid_token_returns_401` | `test_patch_user_insufficient_permission_returns_403` | `test_patch_user_revoked_session_returns_401` |
| `POST /admin/users/{id}/deactivate` | `test_deactivate_user_missing_token_returns_401` | `test_deactivate_user_expired_token_returns_401` | `test_deactivate_user_invalid_token_returns_401` | `test_deactivate_user_insufficient_permission_returns_403` | `test_deactivate_user_revoked_session_returns_401` |
| `DELETE /admin/users/{id}` | `test_delete_user_missing_token_returns_401_not_405` | `test_delete_user_expired_token_returns_401_not_405` | `test_delete_user_invalid_token_returns_401_not_405` | N/A — FR-17 has no permission scope (any authenticated caller gets 405, per resolved reading) | `test_delete_user_revoked_session_returns_401_not_405` |
| `POST /admin/users/{id}/resend-invite` | `test_resend_invite_missing_token_returns_401` | `test_resend_invite_expired_token_returns_401` | `test_resend_invite_invalid_token_returns_401` | `test_resend_invite_insufficient_permission_returns_403_and_audits` | `test_resend_invite_revoked_session_returns_401` |

**Gap found and fixed same-day:** the initial T7/T8 pass only had `missing_token` covered for 5 of the 7 routes (the exception was `GET /admin/users`, which already had the full set). 24 new integration tests were added to close this — table above reflects the final, complete state; full suite re-confirmed green (509/509) after the fix.

## Verdict Rationale

Pass: every §6.6 runtime rule and §6.7 contract/security item checks out with cited evidence, the migration's human-judgment half is confirmed, and — after the same-day fix — every protected route now has the complete §5 five-case security test set (or an explicit N/A for the one inapplicable case, `DELETE`'s insufficient-permission, which has no scope check by design).
