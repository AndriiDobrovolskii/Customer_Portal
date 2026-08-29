# Specification: Deactivate Account

**Source:** docs/stories/US-1.4-deactivate-account.md
**Story ID:** US-004
**Generated:** 2026-08-15
**Status:** Draft (Open Questions resolved 2026-08-15)

## Summary

This spec covers self-service account deactivation: password-confirmed soft deletion, immediate revocation of existing access and refresh tokens, login-time gating and anti-enumeration for deactivated accounts, reactivation via login within a 30-day grace period, scheduled permanent deletion after the grace period, and the invariant that admin-initiated deactivation applies the same revocation behavior.

## Background

As an authenticated customer, I want to deactivate my account, so that I stop being able to use the service and my active sessions are revoked, while retaining the option to reactivate within a grace period.

## Functional Requirements

### FR-1: Successful Self-Service Deactivation

Given an authenticated, active user, when `POST /v1/account/deactivate` is called with the correct `current_password`, the system responds `200`; sets `users.status` to `"deactivated"` and `users.deactivated_at` to now; sets `revoke_before:{user_id}` to now in Valkey; and writes an `account_lifecycle_audit_log` entry (`event=deactivated`, `actor=self`). This transition is enforced atomically at the data layer (e.g. a conditional update scoped to `status = 'active'`), so at most one of two concurrent deactivation requests for the same account can succeed; the other observes the account already deactivated and is handled per FR-3 (see [Clarifications & Decisions](#clarifications--decisions) #2).

**Derived from:** DA-AC1

### FR-2: Incorrect Password Rejection

Given an authenticated, active user, when `POST /v1/account/deactivate` is called with an incorrect `current_password`, the system responds `401`, the account remains active, and no `revoke_before` timestamp is set.

**Derived from:** DA-AC2

### FR-3: Deactivating an Already-Deactivated Account

Given a user whose status is already `"deactivated"`, when `POST /v1/account/deactivate` is called again, the system responds `409` with a `problem+json` body of type `.../errors/already-deactivated`.

**Derived from:** DA-AC3

### FR-4: Existing Access Tokens Rejected Immediately After Deactivation

Given a user with an active access token issued before deactivation, when that user is deactivated (FR-1) and a request is subsequently made to any authenticated endpoint using the pre-existing token, the system responds `401`, because the token's issued-at time is before the account's `revoke_before` timestamp.

**Derived from:** DA-AC4

### FR-5: Refresh Tokens Are Also Revoked

Given a user with a valid refresh token issued before deactivation, when that user is deactivated and the refresh token is subsequently used to request a new access token, the system responds `401` and no new access token is issued.

**Derived from:** DA-AC5

### FR-6: Deactivated Account Cannot Authenticate Normally

Given a deactivated user, and correct login credentials are supplied, when `POST /v1/auth/login` is called, the system responds `403` with a `problem+json` body of type `.../errors/account-deactivated`, and no session or token is issued.

**Derived from:** DA-AC6

### FR-7: Incorrect Credentials on a Deactivated Account Do Not Leak Deactivation Status

Given a deactivated user, when `POST /v1/auth/login` is called with incorrect credentials, the system responds `401` — the same generic credentials error as for an active account — not `403`.

**Derived from:** DA-AC7

### FR-8: Reactivation Within the Grace Period

Given a user deactivated less than 30 days ago, when `POST /v1/auth/login` is called with correct credentials, the system sets the account's status back to `"active"`, clears `deactivated_at`, issues a new session/token (responding `200`), and writes an `account_lifecycle_audit_log` entry (`event=reactivated`, `actor=self`). No additional re-verification (e.g. of email) is required regardless of elapsed time within the 30-day window (see [Clarifications & Decisions](#clarifications--decisions) #4). If this reactivation races against the permanent-deletion job in FR-9 for the same account, the ordering rule in Clarification #1 applies.

**Derived from:** DA-AC8

### FR-9: Permanent Deletion After Grace Period Expiry

Given a user deactivated more than 30 days ago with no login in the interim, when the scheduled permanent-deletion job runs, the system permanently deletes or anonymizes the account per the data-retention policy, and writes an `account_lifecycle_audit_log` entry (`event=permanently_deleted`, `actor=system`) before the corresponding user row is removed. The job's delete/anonymize operation is conditioned on the account still being deactivated with `deactivated_at` older than 30 days at transaction time (e.g. a conditional operation scoped to that predicate); if a reactivation login (FR-8) commits first, the job's operation affects no rows and is a no-op. If the job commits first, a concurrent reactivation login attempt no longer finds an active user row and is treated as an unrecognized-account login, receiving the standard invalid-credentials response (see [Clarifications & Decisions](#clarifications--decisions) #1). The exact mechanics of "deleted or anonymized" are pending legal/DPO sign-off (see [Clarifications & Decisions](#clarifications--decisions) #3).

**Derived from:** DA-AC9

### FR-10: Admin-Initiated Deactivation Applies the Same Revocation Invariant

Given an admin deactivates a user through the (separately specified) admin endpoint, FR-1's revocation side effects — status change, `revoke_before` timestamp, and an audit entry with `actor=admin:{admin_id}` — apply identically to the self-service path.

**Derived from:** DA-AC10

## Non-Functional Requirements

- The `revoke_before` check must run on every authenticated request (middleware/dependency, not opt-in per-endpoint) so no route can accidentally skip it.
- Credential verification in FR-6/FR-7 must happen before the deactivated-status check, so timing does not distinguish "wrong password" from "correct password, deactivated account" for an attacker who does not already know the password.
- Permanent deletion (FR-9) must write its audit entry before the row is removed, since the log is the only surviving record of the event.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- The full admin-initiated deactivation API contract (a separate story; this story only requires that admin deactivation triggers the same revocation invariant defined in FR-10).
- The final data-retention/anonymization policy for permanently deleted accounts (legal/DPO review required).
- Data export ("download your data before deactivating") — potential follow-up story.

**Derived from:** Out of Scope section of the source.

## Clarifications & Decisions

The following points were left undefined by the source story (US-004) or flagged by spec review (`docs/reviews/specifications/US-004-spec-review.md`) and were resolved by explicit stakeholder decision on 2026-08-15, rather than derived directly from AC text. They supersede the prior "Open Questions" section.

1. **Reactivation vs. permanent-deletion race at the grace-period boundary** — DA-AC8 and DA-AC9 don't address a reactivation login and the deletion job running concurrently on the same account (review finding). Decision: the deletion job's operation is conditioned on the account still being deactivated with `deactivated_at` older than 30 days at transaction time; if reactivation commits first, the job is a no-op for that row. If the job commits first, a concurrent reactivation attempt no longer finds an active user and is treated as an unrecognized-account login, returning the standard invalid-credentials response (no new response type introduced). See FR-8, FR-9.
2. **Concurrent deactivation requests** — DA-AC1/DA-AC3 describe sequential behavior only (review finding). Decision: deactivation is enforced atomically at the data layer (a conditional update scoped to `status = 'active'`), so at most one of two concurrent requests can succeed; the other receives the `409 already-deactivated` response from FR-3. See FR-1.
3. **Anonymization vs. hard-deletion policy for FR-9** — The source's own Open Questions flagged this as needing legal/DPO sign-off. Decision: remains out of scope for this spec's build requirements; FR-9 requires only that the audit entry precede row removal — the exact deletion/anonymization mechanics are deferred pending legal review, consistent with the source's own framing.
4. **Re-verification on reactivation** — The source's own Open Questions asked whether reactivation needs additional re-verification for a longer elapsed grace period. Decision: no additional re-verification is required; login alone is sufficient regardless of elapsed time within the 30-day window, confirmed per the source's stated default. See FR-8.
5. **Admin-initiated deactivation confirmation step** — The source's own Open Questions raised whether admin deactivation needs its own confirmation step (reason code, second-admin approval). Decision: confirmed out of scope for this spec, deferred to the follow-up admin-endpoint story, consistent with the source's own note.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| DA-AC1 | "Given an authenticated, active user When POST /v1/account/deactivate is called with the correct current_password Then respond 200 And users.status is set to \"deactivated\"; users.deactivated_at is set to now And revoke_before:{user_id} is set to now in Valkey And an account_lifecycle_audit_log entry is written (event=deactivated, actor=self)" | FR-1 |
| DA-AC2 | "Given an authenticated, active user When POST /v1/account/deactivate is called with an incorrect current_password Then respond 401 And the account remains active; no revoke_before timestamp is set" | FR-2 |
| DA-AC3 | "Given a user whose status is already \"deactivated\" When POST /v1/account/deactivate is called again Then respond 409 with problem+json type '.../errors/already-deactivated'" | FR-3 |
| DA-AC4 | "Given a user with an active access token issued before deactivation When that user is deactivated (DA-AC1) And a request is subsequently made to any authenticated endpoint using the pre-existing token Then respond 401 Because the token's issued-at time is before the account's revoke_before timestamp" | FR-4 |
| DA-AC5 | "Given a user with a valid refresh token issued before deactivation When that user is deactivated And the refresh token is subsequently used to request a new access token Then respond 401 And no new access token is issued" | FR-5 |
| DA-AC6 | "Given a deactivated user, and correct login credentials are supplied When POST /v1/auth/login is called Then respond 403 with problem+json type '.../errors/account-deactivated' And no session or token is issued" | FR-6 |
| DA-AC7 | "Given a deactivated user When POST /v1/auth/login is called with incorrect credentials Then respond 401 (the same generic credentials error as for an active account), not 403" | FR-7 |
| DA-AC8 | "Given a user deactivated less than 30 days ago When POST /v1/auth/login is called with correct credentials Then the account's status is set back to \"active\"; deactivated_at is cleared And a new session/token is issued (respond 200) And an account_lifecycle_audit_log entry is written (event=reactivated, actor=self)" | FR-8 |
| DA-AC9 | "Given a user deactivated more than 30 days ago with no login in the interim When the scheduled permanent-deletion job runs Then the account is permanently deleted or anonymized per the data-retention policy And an account_lifecycle_audit_log entry is written (event=permanently_deleted, actor=system) before the corresponding user row is removed" | FR-9 |
| DA-AC10 | "Given an admin deactivates a user through the (separately specified) admin endpoint Then DA-AC1's revocation side effects (status change, revoke_before timestamp, audit entry with actor=admin:{admin_id}) apply identically to the self-service path" | FR-10 |
