# Impact Analysis: Password Reset (US-2.4 / spec US-2.4)

**Spec:** `docs/specifications/US-2.4-spec.md`
**API design:** `docs/designs/api/US-2.4-openapi.yaml`, `docs/designs/api/US-2.4-api-design.md`
**DB design:** `docs/designs/database/US-2.4-db-design.md`, `docs/designs/database/US-2.4-entity-model.md`
**Written:** 2026-09-01

## Affected Files, by Layer

All changes are confined to the existing `app/modules/users/` module — no new module directory is needed, matching how US-2.1/2.2/2.3 all extended this same module rather than creating `password_reset/`.

| Layer | File | Reason |
|---|---|---|
| Models | `app/modules/users/models.py` | New `PasswordResetToken` entity (column-for-column per `db-design.md`). |
| Schemas | `app/modules/users/schemas.py` | New `PasswordResetRequestRequest`, `PasswordResetRequestResponse`, `PasswordResetConfirmRequest` (per `US-2.4-openapi.yaml`). |
| Repository | `app/modules/users/repository.py` | New methods: `create_password_reset_token`, `get_password_reset_token_by_hash`, `invalidate_password_reset_tokens_for_user` (FR-1's prior-token invalidation), `consume_password_reset_token` (atomic `UPDATE...WHERE consumed_at IS NULL RETURNING`, spec-review resolution). Existing `create_auth_audit_log_entry` is reused as-is (no signature change — `event`/`scope`/`severity` are already parameters, per `entity-model.md`'s note that this story's two new events use `scope=None`/`severity=None`). |
| Cache | `app/modules/users/cache.py` | New `PasswordResetRateLimitCache` (or equivalent — exact shape is OQ-2, deferred to `implementation-planner`) implementing the three-limit throttle (cooldown, per-account/hour, per-IP/hour) resolved by OD-2. New key(s) in `app/core/cache_keys.py` alongside `refresh_rate_limit_key`. |
| Service | `app/modules/users/service.py` | New `request_password_reset()` and `confirm_password_reset()` methods on `UserService`. `request_password_reset()` needs a breached-password-independent path (breach check only applies in `confirm`); `confirm_password_reset()` needs the new breach-check call (see new module below), the atomic-consume repository call, `revocation_cache.set_revoke_before` (existing method, reused — same call `logout_all`/`deactivate` already make), and a new `email_sender.send_password_reset_notice` call. |
| Exceptions | `app/modules/users/exceptions.py` | New `TokenExpiredError` (400, `token-expired`) and `PasswordPolicyError` (422, `password-policy`) — `TokenInvalidError` already exists (reused from US-2.3, same slug, same 401→ but this story needs 400; **flag:** the existing `TokenInvalidError.status = 401` cannot be reused as-is for this story's `400 token-invalid` responses — either a new users-module-local exception class or a status override is needed, a decision for `planner`, not invented here). |
| Router | `app/modules/users/router.py` | Two new routes: `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm` — both unauthenticated (no `CurrentUserDep`/`CurrentUserAllowRevokedDep`), following the same unauthenticated pattern as `/login`. |
| Dependencies | `app/modules/users/dependencies.py` | `get_user_service` gains a `PasswordResetRateLimitCache` (or equivalent) instantiation, following the exact pattern by which `RefreshRateLimitCache` was added for US-2.3; `UserService.__init__` signature grows one parameter. |
| Core | `app/core/email.py` | `EmailSender` Protocol and `LoggingEmailSender` both gain `send_password_reset_email(*, to: str, raw_token: str)` and `send_password_reset_notice(*, to: str)` — same additive pattern as US-2.3's `send_refresh_reuse_alert` (which required updating `RecordingEmailSender` fakes in `email_verification` and `profile` modules' own tests, per US-2.3's own gate-enforcer notes — expect the identical ripple here). |
| Core | `app/core/config.py` | New settings: reset-token TTL (30 min), rate-limit windows/thresholds (60 s / 5 per hour / 10 per hour), breached-password-list path or equivalent (OQ-1). |
| Core (new) | A breach-check helper — either a new function in `app/core/security.py` (alongside `hash_password`/`verify_password`, since it's password-related and used only from `users/service.py`) or a small new module, depending on OQ-1's resolution. Not decided here (out of this analysis's scope per its own constraints) — flagged for `planner`. | New capability, no existing equivalent anywhere in the codebase. |

## Cross-Module Ripple

- **None new.** `request_password_reset`/`confirm_password_reset` are both self-contained within `UserService` — no call out to `AccountService` (unlike login's reactivation path, OD-10/US-2.1), since the spec's PR-AC3 only requires deactivated accounts to be treated identically to unknown ones (no reactivation semantics apply to a password-reset request).
- **email_verification / profile modules:** their `RecordingEmailSender` test fakes will need the two new `EmailSender` Protocol methods added (mirroring the exact ripple US-2.3's `send_refresh_reuse_alert` caused), even though neither module's production code changes.

## Migration/Schema Impact

**Yes, one migration required.** Adds `password_reset_tokens` (new table, all columns non-nullable except `consumed_at`) per `db-design.md`/`entity-model.md`. No `ALTER` on any existing table — `auth_audit_log`'s existing `event: String(32)` column already fits this story's two new event-name values without a length change. No existing repository query is affected by this migration (it's a wholly new table with no FK inbound from any existing table other than the new one's own outbound FK to `users.id`).

## Test-Surface Impact

**New test files:** none — both existing files are extended, matching every prior Epic 2 story's pattern.

**Existing files changed:**
- `tests/unit/modules/users/test_users_service.py` — new `FakePasswordResetToken`-equivalent seeding helpers (or extend the existing `FakeUserRepository`), new fake breach-check collaborator, new tests for FR-1/FR-2/FR-3/FR-4/FR-5/FR-6 plus the atomic-consumption race (mirroring US-2.3's `simulate_race_on_consume` flag pattern on `FakeUserRepository`).
- `tests/integration/modules/users/test_users_router.py` — new integration tests against real Postgres+Valkey for both endpoints, including a genuine concurrent-`confirm` test via `asyncio.gather` (mirroring US-2.3's RT-AC6 integration test).
- `tests/unit/modules/email_verification/*` and `tests/unit/modules/profile/*` (wherever `RecordingEmailSender` fakes live) — extended with the two new `EmailSender` Protocol methods, same ripple class as US-2.3's gate-enforcer finding.
- `tests/conftest.py` — only if a new shared fixture (e.g. a seeded reset token) is needed; not certain until `implementation-planner` sequences the tasks.
