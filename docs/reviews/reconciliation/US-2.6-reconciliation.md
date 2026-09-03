# Reconciliation Report: Active Session Management (US-2.6 / spec US-2.6)

**Story ID:** US-2.6
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass

## Summary

All 5 source Acceptance Criteria (SM-AC1–SM-AC5) have matrix rows, existing test functions, and each test was opened and confirmed to assert the AC's actual stated behavior (status, body shape, and persisted state — not just "reaches the endpoint"). FR-6/FR-7 (no source AC, per resolved OD-1/OD-2) are likewise fully covered. No drift was found between the approved, spec-review-amended spec and the shipped implementation — every mechanism the spec-review resolutions committed to (cookie-based current-session identification, row-locked cap eviction) shipped exactly as described.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| SM-AC1 | "...respond 200 with one entry per family: family_id, created_at, last_used_at, approximate location..., a parsed device/browser label, and is_current And exactly one entry is flagged is_current... And no token value, hash or full IP address is returned" | Yes | `test_get_sessions_returns_200_and_correct_family_shapes` (integration); `test_list_sessions_returns_one_entry_per_live_family`, `test_list_sessions_is_current_matches_cookie_family`, `test_list_sessions_response_excludes_token_and_full_ip` (unit) | Yes | Yes | Integration test asserts 200, exact field set, exactly-one `is_current`; unit tests independently assert the field-set exhaustiveness and the current-family match. |
| SM-AC2 | "...respond 204 and every token in that family is revoked... And the caller's own session is unaffected And an auth_audit_log entry is written (event=session_revoked, target_family=…)" | Yes | `test_delete_session_returns_204_and_persists_revocation` (integration) | Yes | Yes | Asserts 204, `target.revoked_at is not None`, caller's own family's `revoked_at is None`, and the exact audit row (`event`, `target_family`, `actor_id`). |
| SM-AC3 | "...respond 404 with type \".../errors/not-found\" Because 403 would confirm that the family_id exists" | Yes | `test_delete_other_users_session_returns_404_and_leaves_untouched` (integration); `test_revoke_session_other_users_family_returns_404` (unit) | Yes | Yes | Integration test asserts `response.status_code == 404` and `response.json()["type"].endswith("/not-found")`, plus that the victim's family is left unrevoked. |
| SM-AC4 | "...respond 204 — the operation is idempotent, mirroring LO-AC4" | Yes | `test_revoke_session_already_revoked_returns_204_idempotent`, `test_revoke_session_expired_family_returns_204_idempotent` (unit) | Yes | Yes | Both assert the call completes without raising (the router's single, unconditional `204` code path is separately proven live by SM-AC2's integration test — same code path, no branch specific to the idempotent case) and that no audit entry is written for the no-op. |
| SM-AC5 | "...respond 401 and no session metadata is disclosed" | Yes | `test_list_sessions_missing_token_returns_401` (asserts `"sessions" not in response.text`), `test_list_sessions_invalid_token_returns_401`, `test_list_sessions_expired_token_returns_401` (integration) | Yes | Yes | All three assert `401`; the missing-token test additionally asserts no session data leaks into the body. |
| FR-6 (no AC — OD-1) | Own current session → `409`, not revoked | Yes | `test_delete_own_current_session_returns_409_and_persists_nothing` (integration); `test_revoke_session_own_current_family_returns_409`, `test_revoke_session_no_cookie_current_check_never_triggers` (unit) | Yes | Yes | Integration test asserts `409`, `type` ends `/current-session`, and the family's `revoked_at` stays `None`. |
| FR-7 (no AC — OD-2) | 20-family cap eviction, oldest revoked, `event=session_evicted`, no email, row-locked against concurrent logins | Yes | `test_login_creates_21st_family_evicts_oldest_persisted`, `test_concurrent_logins_at_cap_boundary_never_exceed_cap` (integration); `test_login_below_cap_creates_family_without_eviction`, `test_login_at_cap_evicts_oldest_family`, `test_login_new_family_never_evicted_on_same_login`, `test_login_eviction_writes_session_evicted_audit_no_email`, `test_login_eviction_lock_scoped_to_acting_user_only` (unit) | Yes | Yes | The concurrency test genuinely proves the row lock: two real concurrent logins via `real_client`+`asyncio.gather`, final live-family count asserted `== 20` (not 22), exactly 2 `session_evicted` audit rows. |

## Spec Drift

None found. Specifically checked and confirmed matching:

- FR-2's audit-write scope ("writes an `auth_audit_log` entry") applies only to FR-2's own given-clause (a live family) — FR-4's separate given-clause (already-revoked/expired) states no audit requirement. The shipped `revoke_session` (`service.py`) writes the audit entry only when `was_live` is true, which is a precise match to the spec's own scoping between its two separate FRs, not an invention.
- FR-6's `409`/`current-session` slug, FR-7's `session_evicted` event name and no-email behavior, and the cookie-based current-session resolution (with its documented cookie-absent/stale fallback) all match their Open Decision Resolutions verbatim.
- FR-7's "the newly-created family is never itself eligible for eviction" is structurally guaranteed, not just asserted: `_evict_oldest_family_if_at_cap` runs before `create_refresh_token` in both call sites, so the new family doesn't exist in the eviction candidate set at decision time.

## Verdict Rationale

Pass: every AC (source and no-AC/Open-Decision-derived) has a matrix row, an existing test, and that test's assertions were read and confirmed to match the AC's actual stated behavior at the status/body/persisted-state level. No drift was found between the spec-review-amended spec and the shipped code.
