# Traceability Matrix: Active Session Management (US-2.6 / spec US-010)

**Spec:** `docs/specifications/US-010-active-session-management-spec.md`
**Task breakdown:** `docs/plans/US-010-task-breakdown.md` (T7 unit, T8 integration — test code itself deferred to IMPLEMENTATION, matrix only at this stage, same sequencing as US-2.1–US-2.5/US-3.2)
**Written:** 2026-09-02

Both new routes (`GET /v1/auth/sessions`, `DELETE /v1/auth/sessions/{family_id}`) use the standard bearer scheme via the existing `CurrentUserDep`, so each gets the full `AGENTS.md` §5 three-case security set (missing/invalid/expired token — there is no scope/role restriction on either route, since both are self-service). `POST /v1/auth/login` (existing route, US-2.1) is extended for FR-7 — only its new eviction branch is listed here, not its pre-existing coverage.

## `GET /v1/auth/sessions` — FR-1

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| SM-AC1 / FR-1 | Happy path: three live families → 200, one entry each, correct fields (`family_id`, `created_at`, `last_used_at`, `location`, `device_label`, `is_current`) | Unit | `test_list_sessions_returns_one_entry_per_live_family` |
| SM-AC1 / FR-1 | `created_at` is the family's `MIN(issued_at)` across its rotation chain, not the current row's own `issued_at` | Unit | `test_list_sessions_created_at_is_earliest_issued_at_in_family` |
| SM-AC1 / FR-1 | `is_current` is `true` exactly once, matching the family the `refresh_token` cookie resolves to | Unit | `test_list_sessions_is_current_matches_cookie_family` |
| SM-AC1 / FR-1, spec-review resolution | No `refresh_token` cookie present → every entry's `is_current` is `false` | Unit | `test_list_sessions_no_cookie_all_entries_not_current` |
| SM-AC1 / FR-1 | Cookie present but matches no live family (stale/expired) → every entry's `is_current` is `false` | Unit | `test_list_sessions_stale_cookie_all_entries_not_current` |
| SM-AC1 / FR-1 | Response contains no token value, token hash, or full IP address | Unit | `test_list_sessions_response_excludes_token_and_full_ip` |
| SM-AC1 / FR-1, OD-4 | Private/loopback/unresolvable IP → `location` is `null`, request still succeeds | Unit | `test_list_sessions_unresolvable_ip_returns_null_location` |
| SM-AC1 / FR-1, OD-3 | Missing/unparseable `User-Agent` → `device_label` is `"Unknown device"` | Unit | `test_list_sessions_unparseable_user_agent_returns_unknown_device` |
| SM-AC5 / FR-5 | No user (family has no live rows) → empty `sessions` list, not an error | Unit | `test_list_sessions_no_live_families_returns_empty_list` |
| Security | Missing token → 401 | Integration | `test_list_sessions_missing_token_returns_401` |
| Security | Invalid/malformed token → 401 | Integration | `test_list_sessions_invalid_token_returns_401` |
| Security | Expired token → 401 | Integration | `test_list_sessions_expired_token_returns_401` |
| SM-AC5 / FR-5 | Integration: 401 body discloses no session metadata | Integration | `test_list_sessions_unauthenticated_discloses_no_metadata` |
| SM-AC1 | Integration: 200 body shape, real DB rows across 3 rotated families, correct `is_current` via a real cookie | Integration | `test_get_sessions_returns_200_and_correct_family_shapes` |
| NFR (p95 ≤ 200 ms) | Integration: real timing assertion with 20 live families (the cap) | Integration | `test_get_sessions_p95_latency_within_budget_at_cap` |

## `DELETE /v1/auth/sessions/{family_id}` — FR-2, FR-3, FR-4, FR-6

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| SM-AC2 / FR-2 | Happy path: another of the caller's own families → 204, every token in that family revoked, caller's own session unaffected | Unit | `test_revoke_session_own_other_family_returns_204_and_revokes` |
| SM-AC2 / FR-2 | `auth_audit_log(event=session_revoked, target_family=...)` written on an actual revoke | Unit | `test_revoke_session_writes_session_revoked_audit_entry` |
| SM-AC3 / FR-3 | `family_id` belongs to a different user → 404 `not-found` (never 403) | Unit | `test_revoke_session_other_users_family_returns_404` |
| Spec-review resolution / FR-3 | Malformed/nonexistent `family_id` → 404, same path as "belongs to a different user" | Unit | `test_revoke_session_malformed_family_id_returns_404` |
| SM-AC4 / FR-4 | Already-revoked family → 204, idempotent, no audit entry written on the no-op path | Unit | `test_revoke_session_already_revoked_returns_204_idempotent` |
| SM-AC4 / FR-4 | Expired family → 204, idempotent | Unit | `test_revoke_session_expired_family_returns_204_idempotent` |
| OD-1 / FR-6 | `family_id` matches the caller's own current family (per cookie) → 409 `current-session`, nothing revoked | Unit | `test_revoke_session_own_current_family_returns_409` |
| OD-1 / FR-6, spec-review resolution | No `refresh_token` cookie present → 409 never triggers, falls through to FR-2's ordinary revoke | Unit | `test_revoke_session_no_cookie_current_check_never_triggers` |
| Security | Missing token → 401 | Integration | `test_revoke_session_missing_token_returns_401` |
| Security | Invalid/malformed token → 401 | Integration | `test_revoke_session_invalid_token_returns_401` |
| Security | Expired token → 401 | Integration | `test_revoke_session_expired_token_returns_401` |
| SM-AC2 | Integration: 204, DB confirms every token in the target family has `revoked_at` set, caller's own family's tokens unaffected | Integration | `test_delete_session_returns_204_and_persists_revocation` |
| SM-AC3 | Integration: cross-user attempt returns 404, target family's tokens remain unrevoked | Integration | `test_delete_other_users_session_returns_404_and_leaves_untouched` |
| OD-1 | Integration: real cookie identifying the caller's own current family → 409, DB confirms nothing revoked | Integration | `test_delete_own_current_session_returns_409_and_persists_nothing` |

## `POST /v1/auth/login` (existing route, new branch) — FR-7

| AC / FR | Case | Level | Test Function |
|---|---|---|---|
| FR-7 | Below the cap (fewer than 20 live families) → login creates the new family, no eviction | Unit | `test_login_below_cap_creates_family_without_eviction` |
| FR-7 | At the cap (exactly 20 live families) → new login evicts the single oldest pre-existing family | Unit | `test_login_at_cap_evicts_oldest_family` |
| FR-7 | The newly-created (21st) family is never itself eligible for eviction on the same login | Unit | `test_login_new_family_never_evicted_on_same_login` |
| FR-7 | `auth_audit_log(event=session_evicted, target_family=...)` written on eviction; no notification email sent | Unit | `test_login_eviction_writes_session_evicted_audit_no_email` |
| FR-7, spec-review resolution | Row lock scoped to `WHERE user_id = :user_id`, not the whole table — a login by a different user is never blocked by this lock | Unit | `test_login_eviction_lock_scoped_to_acting_user_only` |
| FR-7 | Integration: login as the 21st family with 20 already live → oldest revoked, DB confirms `session_evicted` audit row | Integration | `test_login_creates_21st_family_evicts_oldest_persisted` |
| FR-7, spec-review resolution (concurrency) | Integration: two logins for the same user racing concurrently at the cap boundary (`asyncio.gather`) → exactly one eviction occurs, final live-family count never exceeds 20 | Integration | `test_concurrent_logins_at_cap_boundary_never_exceed_cap` |

## Supporting Units — `app/core/geoip.py`, `app/core/device.py` (not directly AC-driven, required by OD-3/OD-4)

| Source | Case | Level | Test Function |
|---|---|---|---|
| OD-4 | Public, resolvable IP → returns `(city, country)` | Unit | `test_geoip_lookup_resolvable_ip_returns_city_country` |
| OD-4 | Private/loopback IP → returns `None` | Unit | `test_geoip_lookup_private_ip_returns_none` |
| OD-4 | IP with no database entry → returns `None`, does not raise | Unit | `test_geoip_lookup_unresolvable_ip_returns_none_not_raise` |
| OD-4, plan Risks | GeoLite2 database file absent (e.g. local dev without a fetched `.mmdb`) → returns `None`, does not raise, does not fail app startup | Unit | `test_geoip_lookup_missing_database_file_returns_none` |
| OD-3 | Well-formed `User-Agent` → `"{browser} on {OS}"` | Unit | `test_device_label_parses_known_user_agent` |
| OD-3 | Missing `User-Agent` → `"Unknown device"` | Unit | `test_device_label_missing_header_returns_unknown` |
| OD-3 | Unparseable/garbage `User-Agent` → `"Unknown device"` | Unit | `test_device_label_unparseable_header_returns_unknown` |

## Coverage Check

All 5 source ACs (SM-AC1–SM-AC5) have at least one unit and one integration test. FR-6/FR-7 (no source AC, per OD-1/OD-2) have full coverage despite having no AC to trace to — their origin is documented in each row. Both spec-review resolutions (current-session cookie mechanism, concurrent cap-eviction row lock) have dedicated tests: the cookie mechanism in both directions (present/absent/stale) across both endpoints, and the row lock with a genuine concurrent-request integration test mirroring US-3.2's own FR-7 concurrency proof technique. The two new `app/core/` primitives (`geoip.py`, `device.py`) are tested independently of the endpoints that consume them, covering every fallback path OD-3/OD-4 and the plan's Risks section commit to. No AC is left with only a single test level where a persisted-state assertion genuinely requires the integration level to prove it.
