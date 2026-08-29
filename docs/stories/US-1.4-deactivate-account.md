# Epic 1 — Users: Deactivate Account

**Story ID:** US-1.3
**Project:** Customer Portal

## User Story
As an authenticated customer,
I want to deactivate my account,
So that I stop being able to use the service and my active sessions are revoked, while retaining the option to reactivate within a grace period.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Deactivation type | Soft delete: `status = deactivated` (analogous to SCIM `active=false`), never a hard DELETE | Reversibility, auditability |
| 2 | Confirmation required | Current password (or MFA, if supported) re-entry | Prevents accidental/malicious deactivation |
| 3 | Session/token revocation | Per-user `revoke_before` timestamp stored in Valkey, checked on every authenticated request | JWTs are stateless; this is the standard pattern to invalidate all existing tokens at once |
| 4 | Grace period | 30 days; logging in during this window reactivates the account | Common industry pattern |
| 5 | Post-grace-period action | Scheduled job permanently deletes/anonymizes the account | Matches "deactivation ≠ erasure" distinction; final anonymization policy needs legal review |
| 6 | Login status code for a deactivated account with correct credentials | 403, returned only after credential verification succeeds | Avoids leaking deactivation status to someone who doesn't already know the password |

## In Scope
- `POST /v1/account/deactivate` — self-service deactivation
- Login-time enforcement: block authentication for deactivated accounts, with reactivation on successful login within the grace period
- Session/token revocation on deactivation
- Scheduled job for permanent deletion after grace period expiry
- Audit trail for deactivation, reactivation, and permanent deletion events

## Out of Scope
- Full admin-initiated deactivation API contract (a separate story; this story only requires that admin deactivation triggers the same revocation invariant defined here)
- Final data-retention/anonymization policy for permanently deleted accounts (legal/DPO review required — see Open Questions)
- Data export ("download your data before deactivating") — potential follow-up story

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/account/deactivate` | Required (self) | `{"current_password": str}` | 200, `{"status": "deactivated"}` |
| POST | `/v1/auth/login` (extended) | None | existing login payload | 200 with reactivation notice if within grace period; 403 if past grace period is not applicable (account no longer exists) |

## Data Model Notes
- `users.status: enum("active", "deactivated")`
- `users.deactivated_at: datetime | null`
- Valkey key: `revoke_before:{user_id} -> timestamp` — read on every authenticated request; any token issued before this timestamp is rejected
- `account_lifecycle_audit_log`: append-only; records `user_id`, `event` (`deactivated` / `reactivated` / `permanently_deleted`), `actor` (`self` / `admin:{admin_id}` / `system`), `timestamp`

## Acceptance Criteria

### Happy path
**DA-AC1 — Successful self-service deactivation**
```gherkin
Given an authenticated, active user
When POST /v1/account/deactivate is called with the correct current_password
Then respond 200
And users.status is set to "deactivated"; users.deactivated_at is set to now
And revoke_before:{user_id} is set to now in Valkey
And an account_lifecycle_audit_log entry is written (event=deactivated, actor=self)
```

### Confirmation / negative
**DA-AC2 — Incorrect password**
```gherkin
Given an authenticated, active user
When POST /v1/account/deactivate is called with an incorrect current_password
Then respond 401
And the account remains active; no revoke_before timestamp is set
```

**DA-AC3 — Deactivating an already-deactivated account**
```gherkin
Given a user whose status is already "deactivated"
When POST /v1/account/deactivate is called again
Then respond 409 with problem+json type ".../errors/already-deactivated"
```

### Session/token revocation
**DA-AC4 — Existing tokens are rejected immediately after deactivation**
```gherkin
Given a user with an active access token issued before deactivation
When that user is deactivated (DA-AC1)
And a request is subsequently made to any authenticated endpoint using the pre-existing token
Then respond 401
Because the token's issued-at time is before the account's revoke_before timestamp
```

**DA-AC5 — Refresh tokens are also revoked**
```gherkin
Given a user with a valid refresh token issued before deactivation
When that user is deactivated
And the refresh token is subsequently used to request a new access token
Then respond 401
And no new access token is issued
```

### Login-time gating
**DA-AC6 — Deactivated account cannot authenticate normally**
```gherkin
Given a deactivated user, and correct login credentials are supplied
When POST /v1/auth/login is called
Then respond 403 with problem+json type ".../errors/account-deactivated"
And no session or token is issued
```

**DA-AC7 — Incorrect credentials on a deactivated account do not leak deactivation status**
```gherkin
Given a deactivated user
When POST /v1/auth/login is called with incorrect credentials
Then respond 401 (the same generic credentials error as for an active account), not 403
```

### Reactivation
**DA-AC8 — Reactivation within the grace period**
```gherkin
Given a user deactivated less than 30 days ago
When POST /v1/auth/login is called with correct credentials
Then the account's status is set back to "active"; deactivated_at is cleared
And a new session/token is issued (respond 200)
And an account_lifecycle_audit_log entry is written (event=reactivated, actor=self)
```

### Background invariant
**DA-AC9 — Permanent deletion after grace period expiry**
```gherkin
Given a user deactivated more than 30 days ago with no login in the interim
When the scheduled permanent-deletion job runs
Then the account is permanently deleted or anonymized per the data-retention policy
And an account_lifecycle_audit_log entry is written (event=permanently_deleted, actor=system) before the corresponding user row is removed
```

### Admin path (invariant only — full contract out of scope)
**DA-AC10 — Admin-initiated deactivation applies the same revocation invariant**
```gherkin
Given an admin deactivates a user through the (separately specified) admin endpoint
Then DA-AC1's revocation side effects (status change, revoke_before timestamp, audit entry with actor=admin:{admin_id}) apply identically to the self-service path
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/account-deactivated",
  "title": "Account Deactivated",
  "status": 403,
  "detail": "This account has been deactivated. Log in again to reactivate it within the grace period.",
  "instance": "/v1/auth/login"
}
```
Error `type` slugs introduced by this story: `already-deactivated`, `account-deactivated`.

## Non-Functional / Security Requirements
- The `revoke_before` check MUST run on every authenticated request (middleware/dependency, not opt-in per-endpoint) so no route can accidentally skip it.
- Credential verification in DA-AC6/DA-AC7 MUST happen before the deactivated-status check, so timing does not distinguish "wrong password" from "correct password, deactivated account" for an attacker who does not already know the password.
- Permanent deletion (DA-AC9) MUST write its audit entry before the row is removed, since the log is the only surviving record of the event.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| DA-AC1–3 | Integration test suite | `[gate]` |
| DA-AC4–5 | Integration test suite asserting `revoke_before` middleware rejects pre-existing tokens | `[gate]` |
| DA-AC6–7 | Integration test suite, including a timing/behavior check that DA-AC7 returns 401 not 403 | `[gate]` |
| DA-AC8 | Integration test suite | `[gate]` |
| DA-AC9 | Unit test on the deletion job; scheduled execution verified in staging | `[manual]` (cron/scheduler config not covered by unit tests) |
| DA-AC10 | Integration test once the admin endpoint exists; until then, tracked as a backlog item | `[manual]` pending admin-endpoint story |
| `revoke_before` applied globally via middleware, not per-route | Architecture/import-linter rule preventing authenticated routes from bypassing the shared auth dependency | `[gate]` if enforceable via import-linter or a custom AST check; otherwise `[manual]` |

## Open Questions
1. What is the final anonymization vs. hard-deletion policy for DA-AC9? Needs legal/DPO sign-off — affects what "permanently deleted" actually writes/removes (e.g. anonymized row retained for audit purposes vs. full row deletion).
2. Should reactivation (DA-AC8) require re-verification of email if the grace period exceeds some threshold, or is login alone sufficient regardless of elapsed time within the 30 days?
3. Confirm whether admin-initiated deactivation needs its own confirmation step (e.g. reason code, second-admin approval) — currently out of scope but flagged for the follow-up admin story.
