# Traceability Matrix: Manage Roles (US-3.2 / spec US-3.2)

**Spec:** docs/specifications/US-3.2-spec.md
**Task breakdown:** docs/plans/US-3.2-task-breakdown.md (T7 unit, T8 integration)
**Status:** Updated 2026-09-01 post-IMPLEMENTATION to reflect actual shipped test function names (several renamed during T7/T8; a handful added during VERIFICATION to close a §5 security-case gap — see notes).

| AC / FR | Case | Level | Test function | File |
|---|---|---|---|---|
| MR-AC1 / FR-1 | Happy path: replace role set, 200, resulting set returned, `perm_epoch` set, `admin_audit_log` written | Integration | `test_replace_user_roles_valid_set_returns_200_and_updates_scopes` — strengthened during RECONCILIATION to assert `perm_epoch` was actually written to Valkey (`app.core.cache_keys.perm_epoch_key`), not just implied by a later, different test | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC1 / FR-1 | Idempotent on repeat (same set applied twice) | Integration | `test_replace_user_roles_repeat_call_idempotent` | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC1 / FR-1 | Service-layer guard/orchestration logic (old/new set, audit write) in isolation | Unit | `test_replace_user_roles_valid_set_returns_200_and_updates_scopes` (renamed from planned `test_replace_user_roles_writes_audit_and_perm_epoch` — same case, folded into the happy-path unit test) | `tests/unit/modules/roles/test_roles_service.py` |
| MR-AC2 / FR-2 | Stale access token (issued before role change) → `401 token-stale`; `POST /v1/auth/refresh` then returns new scopes | Integration | `test_stale_access_token_after_role_change_returns_401_then_refresh_carries_new_scopes` | `tests/integration/modules/users/test_users_router.py` |
| MR-AC2 / FR-2 | Login/refresh response carries the current `scopes` claim | Integration | `test_login_response_access_token_carries_current_scopes` (added — supports MR-AC2's premise, not separately planned) | `tests/integration/modules/users/test_users_router.py` |
| MR-AC2 / FR-2 | `perm_epoch` comparison logic in isolation, fake cache — stale-raise branch | Unit | `test_get_authenticated_user_token_before_perm_epoch_raises_token_stale` (renamed from planned `test_token_validation_rejects_session_issued_before_perm_epoch`) | `tests/unit/modules/users/test_users_service.py` |
| MR-AC2 / FR-2 | `perm_epoch` absent (no role change yet) → accepted | Unit | `test_get_authenticated_user_perm_epoch_absent_accepted` (added during RECONCILIATION — mirrors the existing `revoke_before`-absent case) | `tests/unit/modules/users/test_users_service.py` |
| MR-AC2 / FR-2 | `perm_epoch` cache-read error → fail closed | Unit | `test_get_authenticated_user_perm_epoch_cache_read_error_rejected` (added during RECONCILIATION — found+fixed: this branch, `app/modules/users/service.py:522-525`, was uncovered) | `tests/unit/modules/users/test_users_service.py` |
| MR-AC3 / FR-3 | `GET /v1/admin/roles` returns catalogue with correct shape | Integration | `test_list_role_catalogue_returns_all_four_roles_with_permissions` | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC3 / FR-3 | Catalogue-read service logic in isolation | Unit | `test_list_catalogue_maps_roles_to_permissions` | `tests/unit/modules/roles/test_roles_service.py` |
| MR-AC4 / FR-4 | Unknown role name in request → `422 validation-failed`, no role applied | Integration | `test_replace_user_roles_unknown_role_returns_422_and_applies_nothing` | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC4 / FR-4 | Guard logic in isolation | Unit | `test_replace_user_roles_unknown_role_rejected` (renamed from planned `test_replace_user_roles_rejects_unknown_role`) | `tests/unit/modules/roles/test_roles_service.py` |
| MR-AC5 / FR-5 | Admin targets own id → `403 cannot-target-self` | Integration | `test_replace_user_roles_self_target_returns_403` | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC5 / FR-5 | Guard logic in isolation | Unit | `test_replace_user_roles_self_target_rejected` (renamed from planned `test_replace_user_roles_rejects_self_target`) | `tests/unit/modules/roles/test_roles_service.py` |
| MR-AC6 / FR-6 | Admin grants a role containing a permission they don't hold → `403 privilege-escalation`, `admin_audit_log` `event=authz_denied severity=high` | Integration | `test_replace_user_roles_privilege_escalation_returns_403_and_audits` | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC6 / FR-6 | Guard logic in isolation | Unit | `test_replace_user_roles_privilege_escalation_rejected_and_audited` (renamed from planned `test_replace_user_roles_rejects_privilege_escalation`) | `tests/unit/modules/roles/test_roles_service.py` |
| MR-AC7 / FR-7 | Last admin: excluding `admin` from the sole remaining admin's set → `409 last-admin` | Integration | `test_replace_user_roles_sole_admin_returns_409` (renamed from planned `test_replace_user_roles_last_admin_returns_409`) | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC7 / FR-7 | Removing `admin` from one of two admins, the other remains → 200, not blocked (companion negative-of-negative case) | Integration | `test_replace_user_roles_removes_admin_when_another_admin_remains` (added) | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC7 / FR-7 | **Concurrency** — two simultaneous requests removing `admin` from the last two admins; exactly one succeeds, one gets `409` (`[gate]` per spec's Enforcement Matrix) | Integration | `test_replace_user_roles_concurrent_last_admin_removal_only_one_succeeds` | `tests/integration/modules/roles/test_roles_router.py` |
| MR-AC7 / FR-7 | Last-admin count-query logic in isolation, fake repository | Unit | `test_replace_user_roles_rejects_removing_last_admin` | `tests/unit/modules/roles/test_roles_service.py` |
| MR-AC7 / FR-7 | Removing admin with another admin present, in isolation | Unit | `test_replace_user_roles_allows_removing_admin_when_another_admin_remains` (added) | `tests/unit/modules/roles/test_roles_service.py` |
| — (cross-cutting, `AGENTS.md` §5) | `GET /v1/admin/roles` with no token → `401` | Integration | `test_list_role_catalogue_no_token_returns_401` | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `GET /v1/admin/roles` with token lacking `users:read` → `403 insufficient-permission` | Integration | `test_list_role_catalogue_missing_scope_returns_403` | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `GET /v1/admin/roles` with a malformed token → `401` | Integration | `test_list_role_catalogue_malformed_token_returns_401` (added during VERIFICATION — closed a §5 gap) | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `GET /v1/admin/roles` with a revoked session → `401` | Integration | `test_list_role_catalogue_revoked_session_returns_401` (added during VERIFICATION) | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `PUT .../roles` with no token → `401` | Integration | `test_replace_user_roles_no_token_returns_401` | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `PUT .../roles` with token lacking `roles:write` → `403 insufficient-permission` | Integration | `test_replace_user_roles_missing_scope_returns_403` | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `PUT .../roles` with expired access token → `401` | Integration | `test_replace_user_roles_expired_token_returns_401` | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `PUT .../roles` with a malformed token → `401` | Integration | `test_replace_user_roles_malformed_token_returns_401` (added during VERIFICATION) | `tests/integration/modules/roles/test_roles_router.py` |
| — (cross-cutting) | `PUT .../roles` with a revoked session → `401` | Integration | `test_replace_user_roles_revoked_session_returns_401` (added during VERIFICATION) | `tests/integration/modules/roles/test_roles_router.py` |
| Plan-review resolution (empty/duplicate array) | Empty `{"roles": []}` → `422 validation-failed` | Integration | `test_replace_user_roles_empty_array_returns_422` | `tests/integration/modules/roles/test_roles_router.py` |
| Plan-review resolution | Empty array, in isolation | Unit | `test_replace_user_roles_empty_array_rejected` (added) | `tests/unit/modules/roles/test_roles_service.py` |
| Plan-review resolution | Duplicate role name in array → `422 validation-failed` | Integration | `test_replace_user_roles_duplicate_role_returns_422` | `tests/integration/modules/roles/test_roles_router.py` |
| Plan-review resolution | Duplicate role name, in isolation | Unit | `test_replace_user_roles_duplicate_role_rejected` (added) | `tests/unit/modules/roles/test_roles_service.py` |
| OD-1 resolution (permission-catalogue completeness, standalone CI check, not an `env.py` hook) | Every scope referenced in `roles/dependencies.py` and every `role_permissions` seed row has a matching `permissions` row | Integration | `test_permission_catalogue_completeness` | `tests/integration/modules/roles/test_roles_router.py` |
| Supporting (not directly AC-mapped) | `resolve_scopes_for_user` flattens and dedupes across multiple roles | Unit | `test_resolve_scopes_for_user_flattens_and_dedupes_across_roles` (added — the mechanism MR-AC2's login/refresh scopes depend on) | `tests/unit/modules/roles/test_roles_service.py` |

## Gaps Not Covered (carried forward, not invented here)

Per this project's convention of disclosing rather than inventing scope, the following spec/API-design Open Questions have **no** test row above because no behavior is yet decided to test against — adding tests for them now would assert an invented requirement:

- 404 behavior for a non-existent `{id}` target user.
- Missing/stale `If-Match` header response (no `400`/`412` defined).
- Check-precedence order when multiple negative conditions apply to one request.
- Initial-ETag acquisition (no `GET /v1/admin/users/{id}` exists yet — US-3.1).

If any of these gain a decision in a future story, add the corresponding test row then.
