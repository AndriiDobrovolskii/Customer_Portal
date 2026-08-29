# Spec Review: Deactivate Account

**Original Story:** docs/stories/US-1.4-deactivate-account.md
**Spec Reviewed:** docs/specifications/US-004-deactivate-account-spec.md
**Story ID:** US-004
**Reviewed:** 2026-08-15
**Overall Verdict:** Pass

## Summary

The spec was re-reviewed after the two prior Missing Edge Case findings and the source's own three Open Questions were resolved via an explicit "Clarifications & Decisions" section (the reactivation/permanent-deletion race, concurrent deactivation requests, the anonymization policy, reactivation re-verification, and the admin confirmation step). All 10 ACs remain fully covered, no contradictions were found, and no requirement is left non-verifiable. The spec now carries two resolutions that go beyond what the source story literally states — these are disclosed and traceable to documented stakeholder decisions rather than silently invented, so they are noted below as disclosed scope additions rather than defects.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| DA-AC1 | "Given an authenticated, active user When POST /v1/account/deactivate is called with the correct current_password Then respond 200 And users.status is set to \"deactivated\"; users.deactivated_at is set to now And revoke_before:{user_id} is set to now in Valkey And an account_lifecycle_audit_log entry is written (event=deactivated, actor=self)" | Covered | FR-1 | Concurrency now addressed — see Clarification #2 |
| DA-AC2 | "Given an authenticated, active user When POST /v1/account/deactivate is called with an incorrect current_password Then respond 401 And the account remains active; no revoke_before timestamp is set" | Covered | FR-2 | — |
| DA-AC3 | "Given a user whose status is already \"deactivated\" When POST /v1/account/deactivate is called again Then respond 409 with problem+json type '.../errors/already-deactivated'" | Covered | FR-3 | — |
| DA-AC4 | "Given a user with an active access token issued before deactivation When that user is deactivated (DA-AC1) And a request is subsequently made to any authenticated endpoint using the pre-existing token Then respond 401 Because the token's issued-at time is before the account's revoke_before timestamp" | Covered | FR-4 | — |
| DA-AC5 | "Given a user with a valid refresh token issued before deactivation When that user is deactivated And the refresh token is subsequently used to request a new access token Then respond 401 And no new access token is issued" | Covered | FR-5 | — |
| DA-AC6 | "Given a deactivated user, and correct login credentials are supplied When POST /v1/auth/login is called Then respond 403 with problem+json type '.../errors/account-deactivated' And no session or token is issued" | Covered | FR-6 | — |
| DA-AC7 | "Given a deactivated user When POST /v1/auth/login is called with incorrect credentials Then respond 401 (the same generic credentials error as for an active account), not 403" | Covered | FR-7 | — |
| DA-AC8 | "Given a user deactivated less than 30 days ago When POST /v1/auth/login is called with correct credentials Then the account's status is set back to \"active\"; deactivated_at is cleared And a new session/token is issued (respond 200) And an account_lifecycle_audit_log entry is written (event=reactivated, actor=self)" | Covered | FR-8 | Boundary race and re-verification now addressed — see Clarifications #1, #4 |
| DA-AC9 | "Given a user deactivated more than 30 days ago with no login in the interim When the scheduled permanent-deletion job runs Then the account is permanently deleted or anonymized per the data-retention policy And an account_lifecycle_audit_log entry is written (event=permanently_deleted, actor=system) before the corresponding user row is removed" | Covered | FR-9 | Boundary race now addressed — see Clarification #1 |
| DA-AC10 | "Given an admin deactivates a user through the (separately specified) admin endpoint Then DA-AC1's revocation side effects (status change, revoke_before timestamp, audit entry with actor=admin:{admin_id}) apply identically to the self-service path" | Covered | FR-10 | — |

## Ambiguities & Non-Verifiable Statements

None found.

## Contradictions With Original Story

None found.

## Scope Additions (Disclosed)

The spec's "Clarifications & Decisions" section adds behavior not stated in the source story's ACs. These are explicitly disclosed as stakeholder decisions (not presented as if derived from the ACs), so they are noted here for visibility rather than as defects:

- **Reactivation/deletion race ordering (FR-8, FR-9)** — Not addressed by DA-AC8/DA-AC9; the spec now specifies a conditional-operation ordering rule so the two paths cannot both apply to the same account. Disclosed in Clarification #1.
- **Data-layer atomicity for concurrent deactivation (FR-1)** — Not addressed by DA-AC1/DA-AC3; the spec now requires a conditional update so only one concurrent request succeeds. Disclosed in Clarification #2.

None of these contradict the story; they fill gaps the story left open. Recommend confirming with the original story author/product owner that these decisions are acceptable, since they were made outside the story document itself. Clarifications #3, #4, and #5 confirm existing source defaults or explicitly defer out-of-scope items rather than adding new behavior, so they are not scope additions.

## Missing Edge Cases, Boundary Conditions & Error Handling

None remaining. The two edge cases flagged in the prior review (reactivation/deletion boundary race, concurrent deactivation requests) are now addressed in FR-8/FR-9 and FR-1 respectively.

## Verdict Rationale

Pass: AC coverage is complete (10/10 Covered), no contradictions were found, and no ambiguous or non-verifiable statements remain — the two previously open Missing Edge Case findings, plus the source's own Open Questions, are now resolved with concrete, testable definitions. The disclosed scope additions are transparently documented as stakeholder decisions rather than silent invention, so they do not block the verdict, though confirming them with the story owner before implementation is advisable.
