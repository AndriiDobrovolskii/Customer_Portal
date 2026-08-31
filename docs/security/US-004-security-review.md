# Security Review: Deactivate Account

**Story ID:** US-004
**Reviewed:** 2026-08-30
**Overall Verdict:** Pass

## Summary

Reviewed `app/modules/account/`, `app/core/revocation_cache.py`, `app/core/cache_keys.py`, and the `users/service.py`/`users/dependencies.py` changes against `AGENTS.md` §7's six non-negotiable rules. All six pass. This story introduces no new password-storage or SQL-construction code of its own — it reuses `app.core.security`'s existing Argon2id verification and SQLAlchemy Core constructs — so most rows are satisfied by inheriting already-compliant shared infrastructure rather than new logic.

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | Pass | `account/service.py:45` calls the existing `app.core.security.verify_password`, which uses `argon2.PasswordHasher` (`app/core/security.py:7,28`); this story adds no new hashing code and stores no new password. |
| No plaintext/reversible encryption for credentials | Pass | `DeactivateAccountRequest.current_password` (`account/schemas.py:10`) is `SecretStr`, unwrapped once via `.get_secret_value()` (`account/service.py:40`) only to pass to `verify_password`, never persisted, never returned, never logged — no row/column anywhere in this diff stores a raw or reversibly-encrypted credential. |
| No tokens/hashes/PII in logs; no `print()` | Pass | Only new log call in the diff: `logger.exception("revoke_before check failed; rejecting token")` (`users/service.py:206`) — a static message with no interpolated token/user-id/PII; `logger.exception` here logs whatever the underlying cache-read exception carries, which is an infrastructure connection error, not a secret. Zero `print()` calls in any touched file (`grep -rn "print(" app/modules/account/ app/core/revocation_cache.py app/core/cache_keys.py`: no matches). |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | Pass | `DeactivateAccountRequest` (`account/schemas.py:7-10`) — the only new inbound schema — sets `extra="forbid"` and its sole field is `current_password`; no privilege/system field (`id`, `status`, `role`, etc.) is present to exclude. |
| Parameterized SQL only, no string interpolation | Pass | `account/repository.py`'s `deactivate_if_not_already` and `get_user_by_id` use SQLAlchemy Core `select()`/`update()` with bound `.where()` predicates — no f-string/`.format()`/`%` SQL construction anywhere in the file. The migration (`migrations/versions/7e371ad49a0a_add_account_deactivation.py`) contains zero `op.execute()` calls — only `op.create_table`/`op.create_index`/`op.add_column`/`op.drop_column`, all parameter-driven DDL, no raw string SQL at all. |
| Uniform auth-failure response, no differentiation leaked | Pass | `account/service.py:39-46` — password verification (`user is None or not await verify_password(...)`) happens in one branch, before the `deactivate_if_not_already` state check, so a defensive "user not found" case (unreachable in practice since the caller is already authenticated) and a genuine wrong-password case both raise the identical `InvalidPasswordError` (401, `type=invalid-credentials`), mirroring `UserService.authenticate_user`'s existing ordering. |

## Advisory Findings

None.

## Verdict Rationale

All six §7 rows are Pass with cited evidence, no credential is stored insecurely or logged, no SQL is string-built, and the auth-failure path is uniform — **Pass**.
