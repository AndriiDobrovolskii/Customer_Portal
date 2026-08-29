# Epic 2 — Authentication: Multi-Factor Authentication (TOTP)

**Story ID:** US-2.5
**Project:** Customer Portal

## User Story
As an administrator or support agent,
I want to protect my account with a time-based one-time code,
So that a stolen or phished password alone is not enough to reach the admin console or other customers' data.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Algorithm | RFC 6238 TOTP, SHA-1, 6 digits, 30-second step | The interoperable baseline every authenticator app supports |
| 2 | Skew tolerance | ±1 time step | Wider windows multiply the guessable code space |
| 3 | Recovery codes | 10 single-use codes, Argon2id-hashed, shown once | Device loss must not mean account loss |
| 4 | Secret storage | Envelope encryption with a KMS-managed key | A leaked database must not yield working second factors |
| 5 | MFA token TTL | 5 minutes, single-use, scoped to verification only | Bounds the value of an intercepted challenge token |
| 6 | Privileged-role enforcement | Mandatory for `admin`, `auditor`, `support_agent` | MFA a privileged user can disable is not a control |
| 7 | Rollout | 14-day grace period with warnings, then enrolment-scoped tokens | Nobody is locked out; they are funnelled into enrolment |

## In Scope
- Enrolment, activation and recovery-code issuance
- The login challenge branch and its verification endpoint
- Mandatory enforcement for privileged roles, including the rollout grace period

## Out of Scope
- WebAuthn / passkeys (the natural follow-up story)
- SMS codes — deliberately excluded (SIM-swap risk)
- "Remember this device"

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/auth/mfa/enroll` | Required (self) | `{"current_password": str}` | 200 `{"secret": str, "otpauth_uri": str}` (pending) |
| POST | `/v1/auth/mfa/activate` | Required (self) | `{"code": str}` | 200 `{"recovery_codes": [str]}` |
| POST | `/v1/auth/mfa/verify` | MFA token | `{"mfa_token": str, "code": str}` | 200, same payload as US-2.1 LI-AC1 |
| DELETE | `/v1/auth/mfa` | Required (self) | `{"current_password": str, "code": str}` | 204 |

## Data Model Notes
- `users.mfa_enabled: bool`, `users.mfa_secret_encrypted: bytes | null`, `users.mfa_activated_at`
- `mfa_recovery_codes`: `code_hash` (Argon2id), `user_id`, `consumed_at` (nullable)
- Valkey `mfa_used_step:{user_id}:{step}` for replay protection, TTL one time step
- `auth_audit_log` events: `mfa_enabled`, `mfa_disabled`, `mfa_verify_failed`, `mfa_recovery_used`

## Acceptance Criteria

### Enrolment
**MF-AC1 — Enrolment**
```gherkin
Given an authenticated user without MFA enrolled
When POST /v1/auth/mfa/enroll is called with the correct current_password
Then respond 200 with a TOTP secret (otpauth:// URI + QR payload) in a PENDING state
And the secret is stored encrypted at rest (envelope encryption, KMS-managed key), never in plaintext
And MFA is NOT yet active — an unfinished enrolment can never lock the user out
```

**MF-AC2 — Activation and recovery codes**
```gherkin
Given a pending enrolment
When POST /v1/auth/mfa/activate is called with a valid 6-digit code
Then respond 200 with 10 single-use recovery codes, shown exactly once
And recovery codes are stored as Argon2id hashes, never in plaintext
And users.mfa_enabled becomes true
And an auth_audit_log entry is written (event=mfa_enabled)
```

### Login challenge
**MF-AC3 — Login challenge**
```gherkin
Given a user with mfa_enabled = true who submits correct credentials
When POST /v1/auth/login is called
Then respond 200 with {"mfa_required": true, "mfa_token": "..."} and NO access or refresh token
And the mfa_token is single-use, scoped to MFA verification only, with a 5-minute TTL
And POST /v1/auth/mfa/verify with a valid code then completes the login exactly as LI-AC1
```

**MF-AC4 — Wrong or replayed code**
```gherkin
Given a valid mfa_token
When POST /v1/auth/mfa/verify is called with an incorrect code
Then respond 401 with type ".../errors/mfa-invalid-code"
Given a code that was already accepted within its time step
Then respond 401 as well, because each code is single-use (replay protection)
And a ±1 time-step (30 s) skew window is accepted, no wider
```

**MF-AC5 — Code brute force**
```gherkin
Given 5 failed verification attempts against the same mfa_token
When POST /v1/auth/mfa/verify is called again
Then respond 429, the mfa_token is invalidated, and full re-authentication is required
Because a 6-digit code has only 10^6 possibilities and must not be guessable online
```

### Enforcement and recovery
**MF-AC6 — Privileged roles cannot opt out**
```gherkin
Given a user holding the admin, auditor or support_agent role
When DELETE /v1/auth/mfa is called
Then respond 409 with type ".../errors/mfa-required-for-role"
And when such a role is granted to a user without MFA (US-3.2 MR-AC1),
    that user's next login issues a token scoped only to the enrolment endpoints until enrolment completes
And during the 14-day rollout grace period login still succeeds,
    but each login warns the user and records the outstanding enrolment
```

**MF-AC7 — Recovery code use**
```gherkin
Given a user who has lost their authenticator device
When POST /v1/auth/mfa/verify is called with a valid recovery code instead of a TOTP code
Then login completes, that recovery code is consumed and can never be reused
And the user is emailed a security notification and prompted to re-enrol
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/mfa-required-for-role",
  "title": "MFA Required For This Role",
  "status": 409,
  "detail": "Accounts with administrative access must keep multi-factor authentication enabled.",
  "instance": "/v1/auth/mfa"
}
```
Error `type` slugs introduced by this story: `mfa-invalid-code`, `mfa-required-for-role`.

## Non-Functional / Security Requirements
- Enforcement for privileged roles lives in the shared permission middleware (the same one US-3.2 uses), never in the UI.
- Disabling MFA for a non-privileged user requires the current password **and** a valid code, so a hijacked session cannot strip the second factor.
- Code comparison MUST be constant-time; the secret MUST never be returned again after enrolment.
- The rollout deadline is a configuration value, and its expiry is itself an audited event.
- **Performance:** verification is a local HMAC computation — p95 ≤ 50 ms, no external service on the login path.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| MF-AC1–3 | Integration test suite | `[gate]` |
| MF-AC4 | Integration test with a fixed TOTP clock, covering skew and replay | `[gate]` |
| MF-AC5 | Integration test with a fixed Valkey counter | `[gate]` |
| MF-AC6 | Integration test per privileged role, plus a test of the enrolment-scoped token | `[gate]` |
| MF-AC7 | Integration test asserting single use | `[gate]` |
| Secret encrypted at rest | Code review + a test asserting the stored column is not the plaintext secret | `[gate]` |

## Open Questions
1. Communication plan for the 14-day rollout (who sends the warning emails, and on what schedule within the window).