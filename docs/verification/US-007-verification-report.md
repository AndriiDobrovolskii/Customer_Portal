# Verification Report: US-2.3 Refresh Token

**Story ID:** US-007
**gate-enforcer Result Relied On:** Pass — 7/7 pre-commit hooks, mypy strict clean (81 files), import-linter clean, 212/212 tests, 97.24% coverage (floor 85%), migration cycle proven (see `docs/catalog/US-2.3-pipeline-status.md`, IMPLEMENTATION/Gate row)
**Reviewed:** 2026-09-01
**Overall Verdict:** Pass

## Summary

Verified US-2.3's implementation against AGENTS.md §6.5–§6.7 and §5's per-route security-case requirement. All runtime rules and contract items check out clean. One gap was found and fixed during this review: this project's established per-protected-route "no token" security case (set by every other route's own tests) had no dedicated integration test for `POST /v1/auth/refresh` — the existing test only covered a garbage/never-issued cookie value, not the literal absence of any cookie. `test_refresh_no_cookie_returns_401` was added; full suite (213 tests) reverified green.

## §6.5 — Migration Human Half

- Generated file read: Yes — `migration-manager`'s T3 report (`docs/catalog/US-2.3-pipeline-status.md`) confirms the file was read in full before trusting it; independently re-confirmed here by reading `migrations/versions/c8eeaa6b5ff6_add_refresh_rotation_columns.py`.
- Rewriter-unreachable statements guarded: Pass — evidence: `migrations/versions/c8eeaa6b5ff6_add_refresh_rotation_columns.py:23-44` (`upgrade()`) and `:48-65` (`downgrade()`) both wrap all five `add_column`/`drop_column` calls (`auth_audit_log.severity`, `refresh_tokens.{consumed_at,last_used_at,ip,user_agent}`) in `sa.inspect(op.get_bind())` column-existence checks, mirroring the `9f9d9263bdfc` exemplar's pattern exactly. No `create_index`/`drop_index` is in this diff (no new index was needed, per `US-007-db-design.md`).
- `downgrade()` real, not `pass`: Pass — evidence: `migrations/versions/c8eeaa6b5ff6_add_refresh_rotation_columns.py:48-65` performs the real inverse (five conditional `drop_column` calls), and `migration-manager`'s captured `upgrade → downgrade → upgrade` output (quoted in the T3 pipeline-status row, independently re-run in the gate-enforcer pass) proves it round-trips cleanly.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/users/service.py:635-639` builds `response = RefreshResponse(access_token=..., expires_in=...)` and `return response, new_raw_token` — never the `RefreshToken`/`User` ORM objects. `rotate_refresh_token`'s return annotation (`service.py:532-534`) is `-> tuple[RefreshResponse, str]`, never `Any`/a model. `router.py`'s `refresh_token` function (`router.py:63-86`) never imports `app.modules.users.models` (confirmed via grep). |
| All nested data eager-loaded | N/A | No `relationship()` exists in `app/modules/users/models.py` (confirmed via grep: zero matches) and this story adds none — every new query (`consume_refresh_token`, `get_by_id` in `repository.py`) is a plain single-table `select`/`update`, no joins. |
| Every cache write has a TTL | Pass | `RefreshRateLimitCache.record_request` (`app/modules/users/cache.py:79-85`) calls `pipe.expire(key, window_seconds)` inside the same atomic pipeline as the `incr` — no bare write, same pattern as the pre-existing `LoginThrottleCache`. |
| Cross-module calls go service→service | N/A | Confirmed via `docs/impact-analysis/US-007-impact-analysis.md`'s "Cross-module ripple: None" finding — independently re-confirmed by grepping `app/modules/users/service.py` for `from app.modules.` imports outside its own module: zero matches (only `app.modules.users.exceptions`/`.models`/`.schemas`). This story makes no cross-module call at all. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `router.py:63` — `@router.post("/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)`. |
| `extra="forbid"` + privilege exclusion on inbound schemas | N/A | `POST /v1/auth/refresh` accepts no request body (cookie-only credential, per the story's own API Contract) — no inbound schema exists for this story to check. `RefreshResponse` (`schemas.py:44-46`) is outbound-only: `access_token: str`, `expires_in: int`, no privilege/system field. |
| `.env.example` updated (if applicable) | N/A | No new setting was introduced — the rate limit (60/family/hour), grace window (10s), and idle timeout (14 days) are module-level constants in `service.py:43-46`, not `Settings` fields, matching the plan's stated Validation Strategy. Confirmed via `git diff --name-only`: `.env.example`/`app/core/config.py` absent from this story's diff. |
| No sensitive field in any `*Read` | Pass | `RefreshResponse` returns only `access_token` (the bearer credential this endpoint's entire purpose is to issue, same class of field as `LoginResponse.access_token`) and `expires_in` — no password, hash, or raw refresh-token value is ever included in the response body. |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `POST /v1/auth/refresh` | `test_refresh_no_cookie_returns_401` *(added during this review)* | `test_refresh_absolute_cap_returns_401`, `test_refresh_idle_timeout_returns_401`, and the "expired" case in `test_refresh_unknown_expired_revoked_return_identical_401_body` | the "unknown" case in `test_refresh_unknown_expired_revoked_return_identical_401_body` (a garbage/never-issued cookie value) | N/A — this route has no role/scope-gated authorization to check; its sole "credential" is the refresh cookie itself, and a wrong/garbage value already falls under "malformed" | the "revoked" case in `test_refresh_unknown_expired_revoked_return_identical_401_body`, plus `test_refresh_reuse_returns_401_and_revokes_family` for the reuse-specific revocation path |

**Note on route-specific security-case mapping:** unlike every prior story's Bearer-token routes, `/refresh` is not behind `CurrentUserDep` — its own credential is the cookie, so this table's columns map onto FR-3's three explicitly-indistinguishable cases (unknown/expired/revoked) plus the newly-added no-cookie case, rather than onto `get_current_user`'s decode/lookup branches. This is a deliberate, documented divergence (`US-007-api-design.md`'s `refreshCookieAuth` scheme), not a gap.

## Verdict Rationale

Pass: every §6.5/§6.6/§6.7 item is Pass or a genuinely-applicable N/A. The one gap found during this review (missing dedicated no-cookie security-case test, against this project's own established per-route pattern) was fixed in-session — `test_refresh_no_cookie_returns_401` was added, and the full suite (213 tests) was reverified green. Nothing remains outstanding.
