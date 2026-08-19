# Epic 1 — Users: Verify Email

**Story ID:** US-1.1
**Project:** Customer Portal

## User Story
As a newly registered customer,
I want to verify ownership of the email address I registered with,
So that my account is activated and I can access authenticated features.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Verification token TTL | 24 hours | Common industry default (1–24h range) |
| 2 | Resend cooldown | 60 seconds between sends per account | Prevents mail-bombing |
| 3 | Resend rate limit | 5 requests / account / hour, 10 / IP / hour | Standard abuse-prevention range |
| 4 | Unverified account purge | 7 days after registration | Matches common vendor defaults (e.g. GitLab) |
| 5 | Status code for unverified-account login attempt | 403 | No standard mandates 401 vs 403; 403 = "known but blocked" |
| 6 | Token design | 32 bytes via `secrets.token_urlsafe(32)`, stored as SHA-256 hash only, single-use | Meets standard entropy sufficiency threshold |

## In Scope
- `POST /v1/auth/verify-email` — consume a verification token
- `POST /v1/auth/verify-email/resend` — request a new token
- Enforcement that unverified accounts cannot use authenticated endpoints
- Scheduled purge of unverified accounts past the TTL window

## Out of Scope
- Initial registration endpoint (assumed to already issue the first token on signup)
- CAPTCHA / bot mitigation on resend (tracked separately if abuse is observed)
- Email **change** re-verification for existing accounts (see US-1.2 Update Profile)

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/auth/verify-email` | None (token is the credential) | `{"token": str}` | 200 `{"email_verified": true}` |
| POST | `/v1/auth/verify-email/resend` | None (email identifies target) | `{"email": str}` | 200, generic body regardless of account existence/state |

## Data Model Notes
- `users.email_verified: bool` — default `false`
- `email_verification_tokens`: `token_hash` (SHA-256, unique), `user_id`, `issued_at`, `expires_at`, `consumed_at` (nullable)
- Raw token value is **never** persisted, logged, or included in any URL — only its hash, and only in the request body

## Acceptance Criteria

### Happy path
**VE-AC1 — Successful verification**
```gherkin
Given an unverified user with a valid, unconsumed, unexpired token
When POST /v1/auth/verify-email is called with the raw token
Then respond 200
And users.email_verified is set to true
And the token's consumed_at is set (single-use enforced; reuse fails per VE-AC3)
```

### Validation / token state
**VE-AC2 — Expired token**
```gherkin
Given a token whose expires_at has passed
When POST /v1/auth/verify-email is called with that token
Then respond 400 with problem+json type ".../errors/token-expired"
And email_verified remains false
```

**VE-AC3 — Already-consumed token**
```gherkin
Given a token that was already consumed
When POST /v1/auth/verify-email is called with that token again
Then respond 400 with problem+json type ".../errors/token-invalid"
```

**VE-AC4 — Unknown or malformed token**
```gherkin
Given a token string that does not match any stored hash
When POST /v1/auth/verify-email is called with that token
Then respond 400 with problem+json type ".../errors/token-invalid"
```

### Authorization / access gating
**VE-AC5 — Unverified account cannot log in**
```gherkin
Given a user whose email_verified is false
When POST /v1/auth/login is called with correct credentials
Then respond 403 with problem+json type ".../errors/email-not-verified"
And no session or JWT is issued
```

**VE-AC6 — Verified account logs in normally**
```gherkin
Given a user whose email_verified is true
When POST /v1/auth/login is called with correct credentials
Then respond 200 with a valid session/JWT
```

### Resend flow
**VE-AC7 — Resend rate limit exceeded**
```gherkin
Given a user requested a verification email less than 60 seconds ago
When POST /v1/auth/verify-email/resend is called for the same account
Then respond 429 with a Retry-After header
```

**VE-AC8 — Resend anti-enumeration (unregistered email)**
```gherkin
Given an email address that is not registered
When POST /v1/auth/verify-email/resend is called
Then respond 200 with the same generic body, status code, and comparable timing as for a registered, unverified account
```

**VE-AC9 — Resend for already-verified account**
```gherkin
Given an email address belonging to an already-verified account
When POST /v1/auth/verify-email/resend is called
Then respond 200 with the same generic body as VE-AC8 (no email is sent, but the response does not reveal this)
```

### Background invariant
**VE-AC10 — Unverified account purge**
```gherkin
Given a user account created more than 7 days ago with email_verified = false
When the scheduled purge job runs
Then the account and its verification tokens are deleted
And a record is written to the audit log noting an automatic purge
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/token-expired",
  "title": "Verification Token Expired",
  "status": 400,
  "detail": "The verification token has expired. Request a new one.",
  "instance": "/v1/auth/verify-email"
}
```
Error `type` slugs introduced by this story: `token-expired`, `token-invalid`, `email-not-verified`.

## Non-Functional / Security Requirements
- Token comparison MUST use constant-time comparison (`hmac.compare_digest`) against the stored hash.
- Raw tokens MUST NOT appear in application logs or error traces.
- Token MUST be delivered in the request body, never in a URL query string (avoids leaking it via access logs, browser history, or referrer headers).

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| VE-AC1–4 | Integration test suite (pytest + httpx) | `[gate]` |
| VE-AC5–6 | Integration test suite | `[gate]` |
| VE-AC7 | Integration test with fixed Valkey clock / rate-limit counter | `[gate]` |
| VE-AC8–9 | Integration test asserting identical response shape/status/timing | `[gate]` |
| VE-AC10 | Unit test on purge job; scheduled execution verified in staging | `[manual]` (cron/scheduler config not covered by unit tests) |
| No-plaintext-token-storage | Code review checklist + CI grep for raw-token persistence patterns | `[manual]` until a dedicated lint rule exists |

## Open Questions
1. VE-AC2–4 currently distinguish "expired" from "invalid/unknown." Confirm this is acceptable, or whether all three should collapse into one generic response for stricter anti-enumeration (the token, not an email address, is the enumerable secret here).
2. Confirm the 7-day purge window against any product/compliance requirement.
