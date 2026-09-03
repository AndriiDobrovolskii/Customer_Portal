# Verification Report: Multi-Factor Authentication / TOTP (US-2.5 / spec US-2.5)

**Story ID:** US-2.5
**gate-enforcer Result Relied On:** PASS — 7/7 pre-commit hooks green, mypy strict clean, import-linter 6/6 contracts kept, 360/360 tests, 97.43% coverage (floor 85%; `users/service.py` 98%, `users/router.py` 100%, `users/dependencies.py` 100%), migration `cef55228a927` upgrade→downgrade→upgrade proven against `customer_portal_pg`.
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass

## Summary

Verified the judgment-level items AGENTS.md §6.6/§6.7 marks as not machine-checkable: no ORM object crosses the service→router boundary anywhere in this story's 4 new endpoints or its login/refresh extensions, no relationship was introduced (the story's own DB design deliberately uses FK-filtered queries instead, per `US-2.5-entity-model.md`), every new cache write (`MfaTokenCache`, `MfaReplayCache`) carries a TTL, and the one new cross-module coupling (`users.service` → `roles.service.get_role_grants_for_user`) targets a service class, never a router. All 4 new routes declare `response_model`/`status_code`, every new inbound schema sets `extra="forbid"`, and `.env.example` is current. §5's initial pass found a real gap — 13 of the story's 4 new bearer-protected routes' security-case tests were missing (activate/disable had none at all; enroll was missing 3 of 4) — closed same-day: 13 tests added, all passing, full suite now 360/360.

## §6.5 — Migration Human Half

- Generated file read: Yes — `migrations/versions/cef55228a927_add_mfa_columns_and_recovery_codes.py`, read in full and hand-rewritten (not left as bare autogenerate output) during `migration-manager`'s T3 run this session.
- Rewriter-unreachable statements guarded: Pass — `mfa_recovery_codes`' `op.create_table`/`op.create_index` are Rewriter-covered (`if_not_exists=True` present, lines 24-40). The 5 `add_column` statements (4 on `users`, 1 on `user_roles`) are not Rewriter-reachable and are each individually guarded with `sa.inspect(op.get_bind())` column-existence checks (lines 55-84), mirroring `2c77dd65027b`'s established pattern exactly.
- `downgrade()` real, not `pass`: Pass — drops the 5 columns (each guarded, lines 90-105) then the table/index (`if_exists=True`, lines 107-111), a genuine inverse of `upgrade()`. Verified by the actual captured `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` output (migration-manager's report) plus a direct `psql \d` schema check confirming the resulting columns/table matched the design exactly.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/users/service.py:1118` (`enroll_mfa`) returns a newly-constructed `MfaEnrollResponse`; `:1141` (`activate_mfa`) returns `MfaActivateResponse`; `:1253` (`verify_mfa`) returns `tuple[MfaVerifyResponse, str]`; `:1334` (`disable_mfa`) returns `None`. None return the `User`/`MfaRecoveryCode` ORM objects. `app/modules/users/router.py` confirmed zero `models`/`repository`/`sqlalchemy`/`AsyncSession` imports (`grep -nE "sqlalchemy|AsyncSession|models|repository" app/modules/users/router.py` → no matches). |
| All nested data eager-loaded | N/A | No relationship was introduced by this story — `docs/designs/database/US-2.5-entity-model.md` deliberately chose a plain FK column plus a separate repository query (`list_unconsumed_recovery_codes`, `app/modules/users/repository.py`) over a `relationship()`, since nothing in this story's flows needs a `User` object returned together with its recovery codes in one call. Confirmed no new `relationship(` in `app/modules/users/models.py`'s diff. |
| Every cache write has a TTL | Pass | `app/modules/users/cache.py:178` (`MfaTokenCache.issue`) — `self._client.set(..., ex=ttl_seconds)`; `:198` (`record_failed_attempt`, via `_incr_with_ttl`) — `pipe.expire(key, window_seconds)`; `:226` (`MfaReplayCache.mark_step_used`) — `self._client.set(..., ex=ttl_seconds)`. All three TTLs are sourced from settings (`mfa_token_ttl_seconds`) at their call sites in `service.py`. |
| Cross-module calls go service→service | Pass | `app/modules/users/service.py` declares `RoleServiceProtocol.get_role_grants_for_user` (a `Protocol`, not a concrete import) and calls `self._role_service.get_role_grants_for_user(...)` in `_resolve_enrollment_scoping` and `disable_mfa` — never `app.modules.roles.router`. Confirmed: `grep -n "from app.modules.roles.router" app/modules/users/service.py` → no matches. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `app/modules/users/router.py:173` (enroll: `MfaEnrollResponse`/200), `:182` (activate: `MfaActivateResponse`/200), `:199` (verify: `MfaVerifyResponse`/200), `:229` (disable: `None`/204). Login's route also updated to `response_model=LoginResponse \| MfaRequiredResponse` (confirmed reflected as `anyOf` in `app.openapi()`). |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `app/modules/users/schemas.py` — `MfaEnrollRequest` (`current_password` only), `MfaActivateRequest` (`code` only), `MfaVerifyRequest` (`mfa_token`, `code`), `MfaDisableRequest` (`current_password`, `code`) all set `ConfigDict(extra="forbid")`. None exposes `id`, `mfa_enabled`, `status`, or any other privilege/system field — field lists checked directly against the class bodies, not assumed. |
| `.env.example` updated (if applicable) | Pass | `.env.example` gained `MFA_SECRET_ENCRYPTION_KEY`, `MFA_TOKEN_TTL_SECONDS`, `MFA_VERIFY_LOCKOUT_THRESHOLD`, `MFA_GRACE_PERIOD_DAYS`, matching all 4 new `app/core/config.py` settings. |
| No sensitive field in any `*Read` | Pass | `MfaEnrollResponse` (`secret`, `otpauth_uri`) is a one-time-disclosure response the spec itself requires (MF-AC1) — not a `*Read` re-exposing a stored value on a later call (the secret is never returned again after enrolment, confirmed no other endpoint returns it). `MfaActivateResponse.recovery_codes` is the same one-time-disclosure case (MF-AC2). Neither is stored back out in plaintext anywhere else. |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `POST /v1/auth/mfa/enroll` | `test_enroll_mfa_missing_token_returns_401` | `test_enroll_mfa_expired_token_returns_401` | `test_enroll_mfa_malformed_token_returns_401` | N/A — self-service, no scope check | `test_enroll_mfa_revoked_session_returns_401` |
| `POST /v1/auth/mfa/activate` | `test_activate_mfa_missing_token_returns_401` | `test_activate_mfa_expired_token_returns_401` | `test_activate_mfa_malformed_token_returns_401` | N/A — self-service, no scope check | `test_activate_mfa_revoked_session_returns_401` |
| `DELETE /v1/auth/mfa` | `test_mfa_disable_missing_token_returns_401` | `test_mfa_disable_expired_token_returns_401` | `test_mfa_disable_malformed_token_returns_401` | N/A — self-service, no scope check | `test_mfa_disable_revoked_session_returns_401` |
| `POST /v1/auth/mfa/verify` (distinct `mfa_token` scheme, not bearer) | `test_verify_mfa_missing_token_returns_401` | N/A — `mfa_token` has no separate expiry test beyond "invalid" (its TTL is unit-tested via `MfaTokenCache`); `test_verify_mfa_already_consumed_token_returns_401` covers the equivalent "token no longer valid" case | `test_verify_mfa_rejects_normal_access_token_as_mfa_token` (the scheme-specific malformed-equivalent: a well-formed but wrong-type token) | N/A — no scope check | `test_verify_mfa_already_consumed_token_returns_401` (the scheme's equivalent of "revoked" — a token already used) |

**N/A rationale:** None of this story's 4 new endpoints check a permission scope (`require_scope`-style dependency) — they are self-service actions gated only by proving identity (bearer auth) plus, for enroll/activate/disable, the current password and/or a valid code. This matches the existing pattern for other self-service endpoints in this codebase (e.g. profile update, password-reset confirm), which likewise have no "insufficient permission" security case.

## Verdict Rationale

Pass: every §6.5/§6.6/§6.7 item is Pass, Pass-with-cited-N/A, or a correctly-justified N/A with evidence. §5's initially-found gap (13 missing security-case tests across `enroll`/`activate`/`disable`, plus 2 of `verify`'s scheme-specific equivalents) was closed same-day — all 13 new tests added and passing, full suite now 360/360, gate re-confirmed green (`pre-commit run --all-files`, 7/7). Nothing outstanding blocks advancing to SECURITY_REVIEW.
