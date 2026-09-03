# Security Review: US-2.1 Login

**Story ID:** US-2.1 (spec's own field; backlog story is US-2.1)
**Reviewed:** 2026-08-31
**Overall Verdict:** Pass

## Summary

All six AGENTS.md §7 non-negotiable invariants hold for this story's login implementation. Password verification (both real and the dummy anti-enumeration path) is Argon2id-only with settings-driven cost parameters; no credential, token, or hash appears in any log call; every inbound schema is `extra="forbid"` with no privilege field; every query is a parameterized SQLAlchemy construct; and the anti-enumeration ordering (credential check always precedes every state/existence branch) guarantees a uniform failure response, confirmed by both a unit test (`test_authenticate_user_deactivated_wrong_password_returns_generic_401`) and an integration test asserting byte-for-byte identical response bodies (`test_login_unknown_email_returns_401_same_shape_as_wrong_password`).

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | Pass | `app/core/security.py:15-22` (`_hash_password_sync`) — `PasswordHasher(time_cost=settings.argon2_time_cost, memory_cost=settings.argon2_memory_cost_kb, parallelism=settings.argon2_parallelism)`, all three from `get_settings()`. This story's own new dummy-verification path (`verify_password_dummy`, `security.py:45-56`) hashes its fixed dummy string through this exact same `hash_password()`/`PasswordHasher` call, so it inherits the same settings-driven cost — no separate, potentially-drifted parameter set was introduced. |
| No plaintext/reversible encryption for credentials | Pass | No credential field anywhere in this story's diff uses anything but the Argon2id path above. `RefreshToken.token_hash` (`app/modules/users/models.py:62-70`) stores a SHA-256 digest, not the raw token — SHA-256 here is a lookup-key hash for an opaque bearer token (matching `EmailVerificationToken.token_hash`/`EmailChangeToken.token_hash`'s existing project-wide precedent), not a password-equivalent credential requiring Argon2id; the raw value is a high-entropy random token (`secrets.token_urlsafe(32)`, `security.py:64`), not a user-chosen secret. |
| No tokens/hashes/PII in logs; no `print()` | Pass | This story adds zero new `logger.*`/`print()` calls anywhere in `app/modules/users/service.py`, `router.py`, `repository.py`, `cache.py`, or `app/modules/account/service.py`/`repository.py` (confirmed via grep — zero hits in the new/changed code). The two `logger.exception(...)` calls present in `users/service.py` (lines 217, 377) are pre-existing, unrelated to this story, and log only static messages, never a credential, token, or hash value. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | Pass | `app/modules/users/schemas.py:32` — `LoginRequest` sets `extra="forbid"`; its two fields (`email`, `password`) are the entirety of the schema — no privilege/system field (`id`, `status`, `email_verified`, `hashed_password`, etc.) is present to exclude. |
| Parameterized SQL only, no string interpolation | Pass | Every new/changed repository method (`users/repository.py`'s `update_last_login_at`, `create_auth_audit_log_entry`, `create_refresh_token`; `account/repository.py`'s `reactivate_if_within_grace`) uses SQLAlchemy `select()`/`update()`/`session.add()` constructs exclusively — grep for f-string/`.format()`/`%`-style SQL interpolation across both files returns zero hits. The new migration (`1cdc08e88be9_add_login_audit_and_refresh_tokens.py`) contains zero `op.execute()` calls — it is pure `op.create_table`/`op.create_index`/`op.add_column`, no hand-written SQL at all. |
| Uniform auth-failure response, no differentiation leaked | Pass | `users/service.py`'s `authenticate_user` runs the real-or-dummy credential check (lines 246-283) strictly before every account-existence/state branch (deactivated-past-grace, deactivated-within-grace/reactivation, unverified — lines 285-320): an attacker without the correct password only ever observes `InvalidCredentialsError`/401, regardless of whether the account exists, is deactivated, or is unverified. Verified end-to-end by `tests/integration/modules/users/test_users_router.py::test_login_unknown_email_returns_401_same_shape_as_wrong_password` (asserts identical JSON body between the two cases, not just matching status) and `::test_login_deactivated_wrong_password_returns_401_not_403`. |

## Verdict Rationale

Pass: all six §7 rows hold with cited, specific evidence — no credential, token, or hash is ever logged, stored insecurely, or leaked through a differentiated failure response, and every query in scope is parameterized.
