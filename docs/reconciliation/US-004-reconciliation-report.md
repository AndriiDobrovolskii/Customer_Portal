# Reconciliation Report: Deactivate Account

**Story ID:** US-004
**Reviewed:** 2026-08-30
**Overall Verdict:** Pass

## Summary

Every AC has a traceability matrix row, and DA-AC1–DA-AC4 (the ACs this story actually implements) each have real, existing tests that assert the AC's stated behavior — verified by reading test bodies, not just names, confirmed passing 145/145 via `gate-enforcer`. One issue was found during this review — the traceability matrix's planned test function names didn't match what was actually written (a naming-convention difference, not a coverage gap) — and corrected in `docs/tests/US-004-traceability-matrix.md` as part of this same review, so the delivered matrix accurately reflects the code. No spec drift was found in the shipped behavior itself.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| DA-AC1 | "Given an authenticated, active user When POST /v1/account/deactivate is called with the correct current_password Then respond 200 And users.status is set to \"deactivated\"; users.deactivated_at is set to now And revoke_before:{user_id} is set to now in Valkey And an account_lifecycle_audit_log entry is written (event=deactivated, actor=self)" | Yes | `test_deactivate_correct_password_returns_200` | Yes (`tests/integration/modules/account/test_account_router.py:57-91`) | Yes | Asserts all five clauses individually: 200, `status="deactivated"`, `deactivated_at is not None`, one audit row with `event=deactivated, actor=self`, `revoke_before` key present in Valkey. |
| DA-AC1 (Clarification #2, concurrency) | Data-layer conditional update; "the other observes the account already deactivated" | Yes | `test_deactivate_concurrent_requests_only_one_succeeds` | Yes (`test_account_router.py:253-...`) | Yes | Asserts `sorted(status_codes) == [200, 409]` from two genuinely concurrent requests (`real_client`, independent connections) plus final persisted `status == "deactivated"`. |
| DA-AC2 | "...When POST /v1/account/deactivate is called with an incorrect current_password Then respond 401 And the account remains active; no revoke_before timestamp is set" | Yes | `test_deactivate_wrong_password_returns_401` | Yes (`test_account_router.py:94-...`) | Yes | Asserts 401, `problem+json` `type=.../errors/invalid-credentials`, and re-queries the DB to confirm `status == "active"` unchanged. |
| DA-AC3 | "Given a user whose status is already \"deactivated\" When POST /v1/account/deactivate is called again Then respond 409 with problem+json type '.../errors/already-deactivated'" | Yes | `test_deactivate_already_deactivated_returns_409` | Yes (`test_account_router.py:117-...`) | Yes | Asserts 409 and the exact `type` string, matching the spec's literal type slug. |
| DA-AC4 | "...a request is subsequently made to any authenticated endpoint using the pre-existing token Then respond 401 Because the token's issued-at time is before the account's revoke_before timestamp" | Yes | `test_deactivate_then_reuse_old_token_returns_401` (integration, end-to-end) + `test_get_authenticated_user_token_before_revoke_before_rejected` (unit, `tests/unit/modules/users/test_users_service.py:407-422`) | Yes | Yes | Integration test proves it against this story's own endpoint (spec's literal wording, "any authenticated endpoint", is necessarily only sampled by one route since US-005/006/007's routes don't exist yet — see Spec Drift note below). Unit test isolates the exact comparison logic with a controlled `issued_at`/`revoke_before` pair. |
| DA-AC5 | Refresh token rejected after deactivation | Yes (N/A) | — | N/A | N/A | Correctly out of scope — owned by US-007, which doesn't exist yet (`US-004-api-design.md`'s FR-ownership table). Not a gap in this story. |
| DA-AC6 | Deactivated account, correct login credentials → 403 | Yes (N/A) | — | N/A | N/A | Owned by US-005 (Login), not yet built. |
| DA-AC7 | Deactivated account, wrong login credentials → 401 (no leak) | Yes (N/A) | — | N/A | N/A | Owned by US-005 (Login), not yet built. |
| DA-AC8 | Reactivation on login within grace period | Yes (N/A) | — | N/A | N/A | Owned by US-005 (Login extension), not yet built. |
| DA-AC9 | Permanent deletion after grace period | Yes (N/A) | — | N/A | N/A | Owned by a future cron story, not yet built. |
| DA-AC10 | Admin-initiated deactivation applies the identical invariant | Yes (N/A) | — | N/A | N/A | Owned by US-011 (`US-3.1.4`), not yet built. Explicitly out of scope per the spec's own Out of Scope section. |

## Documentation Drift (found and corrected within this review, not a coverage gap)

- **[Low] Traceability matrix test-function names didn't match shipped code** — Matrix originally said, e.g., `test_account_service_deactivate_correct_password_deactivates`; the actual function is `test_deactivate_account_correct_password_deactivates` in `tests/unit/modules/account/test_account_service.py`. Same pattern across all `account` and `users` rows — the shipped code omits the redundant module-name prefix the plan assumed, instead matching each file's existing local convention (sibling tests in `test_users_service.py` read `test_register_user_...`, not `test_users_service_register_user_...`). Verified this is a naming difference only, not a missing test, by opening every file and confirming the AC's actual behavior is asserted under the real name. Corrected in `docs/tests/US-004-traceability-matrix.md` as part of this review.

## Spec Drift

- **[Informational, not a defect] DA-AC4's "any authenticated endpoint" is sampled by one route.** The spec's literal wording implies the revocation check should be provable against "any" authenticated endpoint, but `US-005`/`US-006`/`US-007` (login/logout/refresh) don't exist yet, and the only pre-existing authenticated route (`profile`) wasn't touched by this story's test suite. The integration proof (`test_deactivate_then_reuse_old_token_returns_401`) exercises `POST /v1/account/deactivate` itself as the "subsequent authenticated request," which is a valid instance of "any authenticated endpoint" (the check lives in the shared `get_authenticated_user` dependency every route uses), but it's not literally "any" endpoint being tested. This is inherent to the story's sequencing (US-004 ships before the routes that would fully exercise the claim) rather than an implementation shortfall, and the unit test (`test_get_authenticated_user_token_before_revoke_before_rejected`) proves the underlying shared-dependency logic directly, independent of which route calls it. Noted for visibility, not scored against the verdict.

## Verdict Rationale

Every AC has a matrix row (10/10, with DA-AC5–DA-AC10 correctly N/A), every applicable test function was opened and confirmed to exist and assert the AC's actual stated behavior (not just proximity), and no drift was found in the *shipped behavior* against the approved spec. The one issue found — the matrix's planned test names not matching reality — was corrected within this same review, so the delivered `docs/tests/US-004-traceability-matrix.md` is now accurate. **Pass.**
