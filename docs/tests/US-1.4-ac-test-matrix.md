# Traceability Matrix: US-1.4 Deactivate Account

**Status:** Verified — all rows below reflect actual test code, confirmed passing (145/145, `gate-enforcer` 2026-08-30). **Corrected during `reconciliation-reviewer`** (2026-08-30): the "Planned test function" names below originally used a redundant `test_account_service_...`/`test_account_router_...`/`test_users_service_...` prefix; the actual test files omit it (matching each file's existing naming convention — e.g. sibling tests in the same file read `test_register_user_...`, not `test_users_service_register_user_...`). Names corrected to match reality; no coverage gap, drift was documentation-only.

**Scope note:** only DA-AC1/2/3 (this story's own endpoint) and DA-AC4 (the read-side check this story also implements, per `US-1.4-api-design.md`'s FR-ownership table) get real tests here. DA-AC5–DA-AC10 are explicitly owned by other stories (US-2.1/006/007/011, a future cron story) and are marked N/A — not a gap, per that table.

| AC ID | Case | Level | Test function | File | Task |
|---|---|---|---|---|---|
| DA-AC1 | Happy path: correct password → 200, status/deactivated_at set, revoke_before cache write with TTL, audit log entry (`event=deactivated, actor=self`) | Unit | `test_deactivate_account_correct_password_deactivates` | `tests/unit/modules/account/test_account_service.py` | T11 |
| DA-AC1 | Happy path, HTTP round trip: status code, body shape, persisted DB row, persisted cache key | Integration | `test_deactivate_correct_password_returns_200` | `tests/integration/modules/account/test_account_router.py` | T13 |
| DA-AC1 (Clarification #2) | Two concurrent requests for the same account: exactly one succeeds (200), the other observes already-deactivated (409) | Integration | `test_deactivate_concurrent_requests_only_one_succeeds` | same | T13 |
| DA-AC2 | Wrong password → 401 `invalid-credentials`, account remains active, no revoke_before set | Unit | `test_deactivate_account_wrong_password_raises_invalid_password` | `tests/unit/modules/account/test_account_service.py` | T11 |
| DA-AC2 | Wrong password, HTTP round trip: 401 body shape (`application/problem+json`, `type=.../errors/invalid-credentials`), account still active in DB | Integration | `test_deactivate_wrong_password_returns_401` | `tests/integration/modules/account/test_account_router.py` | T13 |
| DA-AC3 | Already-deactivated account → 409 `already-deactivated` | Unit | `test_deactivate_account_already_deactivated_raises_already_deactivated` | `tests/unit/modules/account/test_account_service.py` | T11 |
| DA-AC3 | Already-deactivated, HTTP round trip: 409 body shape | Integration | `test_deactivate_already_deactivated_returns_409` | `tests/integration/modules/account/test_account_router.py` | T13 |
| DA-AC4 | Token issued before `revoke_before` timestamp → rejected (`None` returned from `get_authenticated_user`) | Unit | `test_get_authenticated_user_token_before_revoke_before_rejected` | `tests/unit/modules/users/test_users_service.py` | T12 |
| DA-AC4 | Token issued after / no `revoke_before` set → accepted | Unit | `test_get_authenticated_user_revoke_before_absent_accepted` + `test_get_authenticated_user_token_issued_after_revoke_before_accepted` (extra case added beyond the original plan) | `tests/unit/modules/users/test_users_service.py` | T12 |
| DA-AC4 (fail-closed, `AGENTS.md` §3 denylist rule) | Cache read raises (Valkey outage) → rejected, not accepted | Unit | `test_get_authenticated_user_cache_read_error_rejected` | `tests/unit/modules/users/test_users_service.py` | T12 |
| DA-AC4 | End-to-end: deactivate, then reuse the pre-deactivation access token against a protected route → 401 | Integration | `test_deactivate_then_reuse_old_token_returns_401` | `tests/integration/modules/account/test_account_router.py` | T13 |
| — (AGENTS.md §5 security baseline for every protected route) | No token | Integration | `test_deactivate_no_token_returns_401` | `tests/integration/modules/account/test_account_router.py` | T13 |
| — | Expired token | Integration | `test_deactivate_expired_token_returns_401` | same | T13 |
| — | Malformed token | Integration | `test_deactivate_malformed_token_returns_401` | same | T13 |
| — | Already-revoked session's token | Integration | `test_deactivate_revoked_session_token_returns_401` | same | T13 |
| — | Insufficient role/scope | N/A | — | `POST /v1/account/deactivate` is self-service only, not permission-gated beyond authentication — no role/scope case applies. |
| DA-AC5 | Refresh token rejected after deactivation | N/A | — | Owned by US-2.3 (Refresh Token) |
| DA-AC6 | Login with correct credentials on deactivated account → 403 | N/A | — | Owned by US-2.1 (Login) |
| DA-AC7 | Login with wrong credentials on deactivated account → 401 (no leak) | N/A | — | Owned by US-2.1 (Login) |
| DA-AC8 | Reactivation on login within grace period | N/A | — | Owned by US-2.1 (Login, extension) |
| DA-AC9 | Permanent deletion after grace period | N/A | — | Owned by a future cron story (pattern: `purge_unverified_accounts`) |
| DA-AC10 | Admin-initiated deactivation applies the same invariant | N/A | — | Owned by US-3.1 (Manage Users, `US-3.1.4`) |

## Note on TESTS-before-IMPLEMENTATION sequencing

`docs/workflow/stage-map.yaml` places `TESTS` before `IMPLEMENTATION`. This story's task breakdown (`docs/plans/US-1.4-task-breakdown.md`) instead sequences test tasks (T11-T13) *after* their corresponding service/router tasks (T6-T8), because the unit tests import `AccountService`, `AccountRepositoryProtocol`, and the new cache-gateway `Protocol` by name — these types don't exist until `service-and-router-builder`/`data-layer-builder` create them, so test code written earlier would fail at collection, not at assertion. This matrix — the AC→test-function mapping — is this stage's actual deliverable; the test *files* are produced per the task breakdown's ordering instead. Flagged explicitly here rather than silently deviating from the stage map.
