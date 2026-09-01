# Verification Report: Password Reset (US-2.4 / spec US-008)

**Story ID:** US-2.4
**gate-enforcer Result Relied On:** PASS — 7/7 pre-commit hooks green, mypy strict clean (82 files), import-linter clean, 244/244 tests, 97.12% coverage (floor 85%; `service.py` 98%, `router.py` 100%), migration cycle proven (`upgrade → downgrade → upgrade` against `customer_portal_pg`).
**Reviewed:** 2026-09-01
**Overall Verdict:** Pass

## Summary

Verified the judgment-level items AGENTS.md §6.6/§6.7 marks as not machine-checkable: no ORM object crosses the service→router boundary, no relationships are touched (so eager-loading is N/A), every new rate-limit cache write carries a TTL, no new cross-module coupling was introduced, every new route declares `response_model`/`status_code`, both inbound schemas set `extra="forbid"` with no privilege fields, and `.env.example` is current. Both new endpoints are unauthenticated by design (the source story's own API Contract states `Auth: None`), so §5's four-security-case table doesn't apply — confirmed neither route depends on `CurrentUserDep`/`CurrentUserAllowRevokedDep`.

## §6.5 — Migration Human Half

- Generated file read: Yes — `migrations/versions/9a4776e19934_add_password_reset_tokens.py`, confirmed during migration-manager's own run this session.
- Rewriter-unreachable statements guarded: N/A — the migration contains only `op.create_table`/`op.create_index` (both already carry `if_not_exists=True` from the Rewriter), no `add_column`/`drop_column`/`AlterColumnOp`/enum edit/hand-written `op.execute()` exists in this diff, so no additional `sa.inspect(op.get_bind())` guard is needed.
- `downgrade()` real, not `pass`: Pass — `op.drop_index(..., if_exists=True)` then `op.drop_table(..., if_exists=True)`, a genuine inverse of `upgrade()`.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/users/service.py:738-745` (`request_password_reset(...) -> PasswordResetRequestResponse`), `:836` (`return PasswordResetRequestResponse()` — a schema instance, never the `User`/`PasswordResetToken` ORM object); `:838-845` (`confirm_password_reset(...) -> None`, returns no data at all). `app/modules/users/router.py:143-154` returns the service's schema result directly; `:157-175` returns `Response(status_code=...)`, no ORM object touches the router. |
| All nested data eager-loaded | N/A | `PasswordResetToken` declares no `relationship()` (per `docs/designs/database/US-008-entity-model.md` and `app/modules/users/models.py`); the repository queries it directly by `token_hash`/`user_id`, never traverses from a loaded `User`. |
| Every cache write has a TTL | Pass | `app/modules/users/cache.py:123-138` (`record_cooldown_attempt`/`record_account_attempt`/`record_ip_attempt`) all delegate to `_incr_with_ttl` (`:143-146`), which pairs `pipe.incr(key)` with `pipe.expire(key, window_seconds)` in one atomic pipeline — no write without an accompanying expiry. |
| Cross-module calls go service→service | Pass (N/A — no new cross-module call) | `app/modules/users/service.py:27,39-40` — every import is from `app.modules.users.*` itself; no `app.modules.<other>.router` or `.service` import was added by this story, confirmed against `impact-analysis.md`'s explicit statement that no cross-module call was needed (unlike login's `AccountService` reactivation path). |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `app/modules/users/router.py:140-141` (`response_model=PasswordResetRequestResponse, status_code=status.HTTP_202_ACCEPTED`), `:157` (`response_model=None, status_code=status.HTTP_200_OK`). |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `app/modules/users/schemas.py:50` (`PasswordResetRequestRequest`), `:62` (`PasswordResetConfirmRequest`) both set `ConfigDict(extra="forbid")`. Field list checked: `email` (request), `token`/`new_password` (confirm) — none of this module's actual privilege/system fields (`id`, `status`, `email_verified`, `hashed_password`, `created_at`, `deactivated_at`, `last_login_at`) appear on either. |
| `.env.example` updated (if applicable) | Pass | `.env.example` gained all 5 new settings (`PASSWORD_RESET_TOKEN_TTL_MINUTES`, `PASSWORD_RESET_COOLDOWN_SECONDS`, `PASSWORD_RESET_ACCOUNT_HOURLY_LIMIT`, `PASSWORD_RESET_IP_HOURLY_LIMIT`, `BREACHED_PASSWORD_LIST_PATH`) — found missing and fixed during T8 (gate-enforcer). |
| No sensitive field in any `*Read` | Pass | `PasswordResetRequestResponse` (`schemas.py:55-59`) carries only the fixed literal `message` string; no `*Read` schema was created for `PasswordResetToken` — the token itself is never returned by any endpoint. |

## §5 — Security Test Cases (per protected route)

N/A — neither `POST /v1/auth/password-reset/request` nor `POST /v1/auth/password-reset/confirm` is a protected route by design (source story's API Contract states `Auth: None` for both — the reset token itself is the credential for `confirm`). Confirmed via `app/modules/users/router.py:143` and `:158`: neither function signature depends on `CurrentUserDep` or `CurrentUserAllowRevokedDep` (both appear only at `:96` and `:125`, on `/logout` and `/logout-all`). The equivalent security surface for these two endpoints — anti-enumeration and rate limiting — is covered by `test_password_reset_request_unknown_email_returns_202_identical_body`, `test_password_reset_request_flooding_returns_429_with_retry_after`, and the token-state tests (`test_password_reset_confirm_expired_token_returns_400_token_expired`, `_unknown_token_returns_400_token_invalid`, `_consumed_token_returns_400_token_invalid`) in `tests/integration/modules/users/test_users_router.py`.

## Verdict Rationale

Pass: every §6.6/§6.7 item is Pass or an explicitly justified N/A with cited evidence, and §5's table doesn't apply to this story's two intentionally-unauthenticated endpoints — nothing here blocks advancing to SECURITY_REVIEW.
