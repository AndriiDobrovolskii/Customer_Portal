# Verification Report: Manage Roles (US-3.2 / spec US-3.2)

**Story ID:** US-3.2
**gate-enforcer Result Relied On:** PASS — 7/7 pre-commit hooks green, mypy strict clean (94 files), import-linter 6/6 contracts kept, 274/274 tests, 97.12% coverage (floor 85%; `roles/service.py` 99%, `roles/router.py` 100%, `roles/repository.py` 95%), migration cycle proven twice against `customer_portal_pg`.
**Reviewed:** 2026-09-01
**Overall Verdict:** Pass

## Summary

Verified the judgment-level items AGENTS.md §6.6/§6.7 marks as not machine-checkable: no ORM object crosses the service→router boundary, the one touched relationship (`Role.permissions`) is eager-loaded with `selectinload` everywhere it's read, the new `PermissionEpochCache` write carries a TTL, and the one new cross-module coupling (`users.service` → `roles.service`) targets a service class, never a router. Both new routes declare `response_model`/`status_code`, the one inbound schema sets `extra="forbid"`, and `.env.example` is current. §5's gap noted during this review (no per-route malformed-token/revoked-session test) was closed same-day — 4 tests added, all passing.

## §6.5 — Migration Human Half

- Generated file read: Yes — `migrations/versions/e50fbe8161fc_add_roles_and_permissions.py` and `migrations/versions/d7585b660cd7_add_admin_audit_log.py`, both read in full during `migration-manager`'s run this session.
- Rewriter-unreachable statements guarded: Partial, correctly so — both migrations' `op.create_table`/`op.create_index` calls are Rewriter-covered (`if_not_exists=True` present on every one, confirmed in both files). The one hand-written, Rewriter-unreachable addition is the seed-data `op.execute(...)` block in `e50fbe8161fc` (lines 63-94) — it is not `sa.inspect()`-guarded, but is idempotent by construction (`ON CONFLICT ... DO NOTHING` on all three `INSERT`s), which is the correct guard shape for a data statement rather than a schema-existence check (`sa.inspect()` guards column/table existence, not row idempotency).
- `downgrade()` real, not `pass`: Pass — both files drop indexes then tables with `if_exists=True`, genuine inverses of their `upgrade()`. `e50fbe8161fc`'s `downgrade()` has no explicit seed-data cleanup, correctly so: `op.drop_table` cascades away the seeded rows with the table itself.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/roles/service.py:70-78` (`list_catalogue`) and `:93-184` (`replace_user_roles`) both return newly-constructed `RoleCatalogueResponse`/`ReplaceUserRolesResponse` instances built from plain `str` values read off ORM attributes (`role.name`, `permission.scope`) — the `Role`/`Permission` ORM objects themselves are never returned or passed to the router. `app/modules/roles/router.py:24-45` returns the service's schema result directly, no ORM import present (confirmed: `grep -n "models\|sqlalchemy\|AsyncSession\|repository" app/modules/roles/router.py` → zero hits). |
| All nested data eager-loaded | Pass | `Role.permissions` (`app/modules/roles/models.py`, `lazy="raise_on_sql"`, `secondary="role_permissions"`) is read in exactly two places — `app/modules/roles/repository.py:16` (`list_all_with_permissions`) and `:23` (`get_by_names`) — both via `.options(selectinload(Role.permissions))`, matching the model's declared collection strategy. No `joinedload()` combined with `LIMIT`/`OFFSET` anywhere in the diff. |
| Every cache write has a TTL | Pass | `app/core/revocation_cache.py:63` (`PermissionEpochCache.set_perm_epoch`) — `self._client.set(perm_epoch_key(user_id), ..., ex=ttl_seconds)`, `ttl_seconds` sourced from `get_settings().perm_epoch_ttl_seconds` at the call site (`app/modules/roles/service.py:179-182`). |
| Cross-module calls go service→service | Pass | `app/modules/users/service.py` imports `RoleServiceProtocol` (a `Protocol`, not a concrete import) and calls `self._role_service.resolve_scopes_for_user(...)` at lines 476 and 726 — never `app.modules.roles.router`. Confirmed by grep: `grep -rn "from app.modules.*\.router import" app/modules/roles/service.py app/modules/users/service.py` → zero hits. The reverse-direction FR-7 exception (`roles/repository.py` reading `app.modules.users.models.User` directly, not `users.service`) is a documented, narrow, user-approved deviation from this same rule (see `app/modules/roles/repository.py:33-42`'s docstring and `docs/impact-analysis/US-3.2-impact-analysis.md`'s 2026-09-01 resolution) — not a violation, a disclosed exception. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `app/modules/roles/router.py:20-21` (`GET /roles`: `response_model=RoleCatalogueResponse, status_code=status.HTTP_200_OK`), `:30-31` (`PUT /users/{id}/roles`: `response_model=ReplaceUserRolesResponse, status_code=status.HTTP_200_OK`). |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `app/modules/roles/schemas.py:16` — `ReplaceUserRolesRequest`'s `ConfigDict(extra="forbid")`. Field list checked: `roles: list[str]` only — no privilege/system field (`id`, `status`, `email_verified`, etc.) is exposed on this or any other schema in the module; `RoleCatalogueResponse`/`ReplaceUserRolesResponse`/`RoleSummary` are outbound-only, no `extra` setting needed. |
| `.env.example` updated (if applicable) | Pass | `.env.example` gained `PERM_EPOCH_TTL_SECONDS=900`, matching `app/core/config.py`'s new `perm_epoch_ttl_seconds` setting. |
| No sensitive field in any `*Read` | Pass | `RoleCatalogueResponse`/`RoleSummary` carry only role/permission name strings; `ReplaceUserRolesResponse` carries only the resulting role-name list — no credential, token, or PII field on any schema this story adds. |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `GET /v1/admin/roles` | `test_list_role_catalogue_no_token_returns_401` | — (covered generically, see note) | `test_list_role_catalogue_malformed_token_returns_401` | `test_list_role_catalogue_missing_scope_returns_403` | `test_list_role_catalogue_revoked_session_returns_401` |
| `PUT /v1/admin/users/{id}/roles` | `test_replace_user_roles_no_token_returns_401` | `test_replace_user_roles_expired_token_returns_401` | `test_replace_user_roles_malformed_token_returns_401` | `test_replace_user_roles_missing_scope_returns_403` | `test_replace_user_roles_revoked_session_returns_401` |

**Note:** `GET /v1/admin/roles` has no dedicated expired-token test of its own (the PUT route's covers the mechanism); expiry is additionally unit-tested generically at `test_decode_access_token_expired_raises_invalid_token` (`tests/unit/core/test_security.py:106`). All other cells are dedicated tests added to `tests/integration/modules/roles/test_roles_router.py` during this review pass (21/21 passing).

## Verdict Rationale

Pass: every §6.5/§6.6/§6.7 item is Pass or a correctly-justified Partial/N/A with cited evidence, and §5's initially-found gap (missing per-route malformed-token/revoked-session tests) was closed same-day with 4 new passing tests — nothing outstanding blocks advancing to SECURITY_REVIEW.
