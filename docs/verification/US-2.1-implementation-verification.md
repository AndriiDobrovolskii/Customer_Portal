# Verification Report: US-2.1 Login

**Story ID:** US-2.1 (spec's own field; backlog story is US-2.1)
**gate-enforcer Result Relied On:** Pass — 7/7 pre-commit hooks green, mypy strict clean (81 files), lint-imports clean (6/6 contracts), 163/163 tests pass, 97.16% coverage, migration upgrade→downgrade→upgrade cycle proven (2026-08-31)
**Reviewed:** 2026-08-31
**Overall Verdict:** Pass

## Summary

Every §6.5–§6.7 item checked Pass or explicit N/A, with no ORM leaks, no missing eager-loads, no TTL-less cache writes, and correct service→service cross-module discipline for the new reactivation call. The one N/A (login is the story's single deliberately-unauthenticated route, so §5's four security cases don't apply) is a genuine architectural fact, not a gap.

## §6.5 — Migration Human Half

- Generated file read: Yes — `migration-manager` (this session) read `migrations/versions/1cdc08e88be9_add_login_audit_and_refresh_tokens.py` in full before trusting it, and caught a real defect: autogenerate proposed a spurious drop of `account_lifecycle_audit_log` (caused by a pre-existing gap in `migrations/env.py` never importing `app.modules.account.models`), removed by hand rather than accepted.
- Rewriter-unreachable statements guarded: Pass — `add_column`/`drop_column` on `users.last_login_at` (the one statement type the Rewriter's `CreateTableOp`/`CreateIndexOp`/`DropTableOp`/`DropIndexOp` scope doesn't reach) is guarded with `sa.inspect(op.get_bind())` in both `upgrade()` (lines 79–88) and `downgrade()` (lines 95–99), mirroring `2c77dd65027b`'s established pattern exactly.
- `downgrade()` real, not `pass`: Pass — drops `last_login_at` (guarded), `refresh_tokens`, and `auth_audit_log` (both `if_exists=True` via the Rewriter); does not touch `account_lifecycle_audit_log`, correctly matching that it was never dropped by `upgrade()`.
- Cycle actually run: Pass — `migration-manager` ran `upgrade → downgrade → upgrade` against a standalone Postgres container (not just the testcontainer suite) and additionally verified, via a throwaway autogenerate pass after fixing `migrations/env.py`, that the spurious diff is gone for good.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/users/service.py:223,355` — `authenticate_user` returns `tuple[LoginResponse, str]` (a Pydantic schema + a raw string), never the `User`/`RefreshToken`/`UserSession` ORM objects; `app/modules/account/service.py:71` — `reactivate_account` returns `bool`. `router.py` (both `users` and `account`) never imports `models`/`repository`/`sqlalchemy` (confirmed via grep, zero hits). |
| All nested data eager-loaded | N/A | Zero `relationship()` declarations exist anywhere in `app/modules/users/models.py` or `app/modules/account/models.py` (confirmed via grep) — this story follows the codebase's existing universal pattern of separate FK-based queries, not loaded relationships, so no eager-load strategy applies. |
| Every cache write has a TTL | Pass | `app/modules/users/cache.py:52-53` — `pipe.incr(key)` is always paired with `pipe.expire(key, window_seconds)` in the same atomic pipeline (`_incr_with_ttl`), the only write path in the gateway. |
| Cross-module calls go service→service | Pass | `app/modules/users/service.py:291` calls `self._account_service.reactivate_account(user.id)` — a `Protocol`-typed collaborator (`AccountServiceProtocol`, structural typing, no import of `app.modules.account.*` in `service.py` itself). The concrete wiring in `app/modules/users/dependencies.py:11,27` imports `AccountServiceDep` from `app.modules.account.dependencies` (the module's service-layer DI alias), never its `router`. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `app/modules/users/router.py:25` — `@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)`. |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `app/modules/users/schemas.py:32` — `LoginRequest` sets `extra="forbid"`; its only fields are `email`/`password`, neither a privilege/system field. |
| `.env.example` updated (if applicable) | Pass | `.env.example:13-16` — all four new settings (`LOGIN_FAILURE_THRESHOLD_ACCOUNT`, `LOGIN_FAILURE_THRESHOLD_IP`, `LOGIN_THROTTLE_WINDOW_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS`) present, matching `app/core/config.py`'s new `Settings` fields exactly. |
| No sensitive field in any `*Read` | Pass | `LoginResponse` (`app/modules/users/schemas.py:38-41`) carries only `access_token`, `token_type`, `expires_in` — no password/hash field. The raw refresh token is never part of this schema; it's returned out-of-band as a plain `str` for the router to set as a cookie (never persisted in the response body or logged). |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `POST /v1/auth/login` | N/A | N/A | N/A | N/A | N/A |

`POST /v1/auth/login` is this story's one endpoint, and it is deliberately unauthenticated (`security: []` in the OpenAPI contract, `docs/designs/api/US-2.1-openapi.yaml`) — the four protected-route security cases don't apply to it by design, not by omission. This is the same treatment `US-1.4-verification-report.md`-equivalent reasoning would give any genuinely public endpoint.

## Verdict Rationale

Pass: every §6.5/§6.6/§6.7 item is either Pass with cited evidence or a genuine, architecturally-correct N/A (no relationships in scope; login is unauthenticated). No ORM leak, no missing TTL, no service→router cross-module violation, no missing `response_model`/`status_code`, and the one migration defect found (`env.py`'s missing `account` import) was caught, disclosed, and fixed with explicit user sign-off rather than silently worked around.
