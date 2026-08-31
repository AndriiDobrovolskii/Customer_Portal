# Verification Report: Deactivate Account

**Story ID:** US-004
**gate-enforcer Result Relied On:** Pass (2026-08-30 re-run, post-Docker) — 145/145 tests, 96.84% coverage, 6/6 import-linter contracts, migration cycle verified via test fixtures.
**Reviewed:** 2026-08-30
**Overall Verdict:** Pass

## Summary

Verified the human-judgment half of the Definition of Done that `gate-enforcer` doesn't mechanically check. No ORM leaks, no missing TTLs, no cross-module discipline violations, and all §6.7 contract/security items and §5 security test cases are present with cited evidence. One item is N/A rather than Pass/Fail: this story touches no relationship, so eager-loading doesn't apply.

## §6.5 — Migration Human Half

- Generated file read: Yes — hand-authored by `migration-manager` (no autogenerate target available), read in full during authoring, `migrations/versions/7e371ad49a0a_add_account_deactivation.py`.
- Rewriter-unreachable statements guarded: Pass — the hand-written `op.add_column("users", ...)` is guarded by `sa.inspect(op.get_bind())` at `7e371ad49a0a_add_account_deactivation.py:58-63`; `op.create_table`/`op.create_index` calls use `if_not_exists=True` (Rewriter-reachable, but confirmed present).
- `downgrade()` real, not `pass`: Pass — `downgrade()` at `7e371ad49a0a_add_account_deactivation.py:67-79` performs guarded `op.drop_column`, then `op.drop_index(if_exists=True)`, then `op.drop_table(if_exists=True)` — genuine inverse, verified to actually execute via the test suite's session-teardown downgrade (captured in `gate-enforcer`'s run).

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/account/service.py:36-38` — `deactivate_account` returns `-> DeactivateAccountResponse` (schema), never the `User` ORM instance. `app/modules/account/router.py` imports only `AccountServiceDep`, `DeactivateAccountRequest`/`Response`, `CurrentUserDep` — no `models`/`repository`/`sqlalchemy` import (also mechanically confirmed by `lint-imports`' "Routers must not touch persistence infrastructure" contract). |
| All nested data eager-loaded | N/A | No relationship is touched by this story — `AccountLifecycleAuditLog` (`app/modules/account/models.py`) has no FK/relationship by design (must survive account deletion), and no query in `account/repository.py` or the `users` changes loads a collection. |
| Every cache write has a TTL | Pass | `app/core/revocation_cache.py:30-32` — the sole cache write, `set_revoke_before`, calls `self._client.set(revoke_before_key(user_id), ..., ex=ttl_seconds)`; `ttl_seconds` is always supplied by the caller (`account/service.py:57-58`, `settings.access_token_ttl_seconds`), never omitted. |
| Cross-module calls go service→service | Pass | `account/service.py` never imports from `app.modules.users` (only `users.models.User` is imported for typing the repository Protocol's return, not a cross-service call — matches the existing `profile/repository.py` precedent of a repository directly touching the shared `users` table). `users/service.py`'s new `RevocationCacheReaderProtocol` collaborator is satisfied by `app.core.revocation_cache.RevocationCache` (`users/dependencies.py:8,20`) — core infrastructure, not another module's service or router. No `service.py` file in this diff imports any `*.router`. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `account/router.py:11` — `response_model=DeactivateAccountResponse, status_code=status.HTTP_200_OK`, the only new route. |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `account/schemas.py:7-10` — `DeactivateAccountRequest` sets `model_config = ConfigDict(extra="forbid")`; its only field is `current_password: SecretStr`, no privilege/system field present to exclude. |
| `.env.example` updated (if applicable) | Pass | `.env.example:12` — `VALKEY_URL=redis://localhost:6379/0` added alongside `app/core/config.py`'s new `valkey_url` setting. |
| No sensitive field in any `*Read` | Pass | `DeactivateAccountResponse` (`account/schemas.py:17-19`) exposes only `status` and `deactivated_at` — no password, token, or hash field. |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `POST /v1/account/deactivate` | `test_deactivate_no_token_returns_401` | `test_deactivate_expired_token_returns_401` | `test_deactivate_malformed_token_returns_401` | N/A — self-service only, no role/scope gating on this endpoint (documented in `docs/tests/US-004-traceability-matrix.md`) | `test_deactivate_revoked_session_token_returns_401` |

All four in `tests/integration/modules/account/test_account_router.py`, confirmed passing in `gate-enforcer`'s 145/145 result.

## Verdict Rationale

Every §6.6 item is Pass or a justified N/A, every §6.7 item is Pass with cited file:line evidence, and all four applicable §5 security cases exist and pass (the fifth, insufficient-permissions, is N/A for a route with no authorization layer beyond authentication). No ORM leak, no TTL-less write, no cross-module violation, and no missing contract/security item was found — **Pass**.
