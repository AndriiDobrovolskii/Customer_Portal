# Epic 2 — Authentication: Password Reset

**Story ID:** US-2.4
**Project:** Customer Portal

## User Story
As a user who has forgotten their password,
I want to set a new one via a link emailed to my registered address,
So that I can regain access to my account without contacting support.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Reset token TTL | 30 minutes | Shorter than email verification, because the token grants account takeover |
| 2 | Token design | 32 bytes via `secrets.token_urlsafe(32)`, SHA-256 hash stored, single-use | Matches US-1.2 |
| 3 | Token delivery | In the URL **fragment**, consumed by the SPA and POSTed in the request body | Preserves the project-wide "no tokens in URLs" invariant |
| 4 | Rate limits | 60 s cooldown, 5 / account / hour, 10 / IP / hour | Prevents mail-bombing |
| 5 | Password policy | Minimum 12 characters, rejected if breached or equal to the current password | NIST SP 800-63B guidance |
| 6 | Post-reset session handling | All sessions and refresh families revoked | Neither party should retain a session across a password change |

## In Scope
- `POST /v1/auth/password-reset/request` — issue a reset token
- `POST /v1/auth/password-reset/confirm` — consume it and set a new password
- Anti-enumeration on the request endpoint
- Session revocation and notification on success

## Out of Scope
- Password change by an already-authenticated user (belongs with profile, US-1.3)
- Admin-initiated password reset — admins never set another person's password (US-3.1.2 MU-AC7)

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/auth/password-reset/request` | None | `{"email": str}` | 202, generic body regardless of account existence |
| POST | `/v1/auth/password-reset/confirm` | None (token is the credential) | `{"token": str, "new_password": str}` | 200 |

## Data Model Notes
- `password_reset_tokens`: `token_hash` (SHA-256, unique), `user_id`, `issued_at`, `expires_at`, `consumed_at` (nullable) — same shape as `email_verification_tokens` in US-1.2
- Issuing a new token invalidates any earlier unconsumed one for the same account

## Acceptance Criteria

### Happy path
**PR-AC1 — Requesting a reset**
```gherkin
Given a registered, active account
When POST /v1/auth/password-reset/request is called with that email
Then respond 202 with a generic body ("If an account exists, an email has been sent")
And a single-use reset token with a 30-minute TTL is created (SHA-256 hash stored only)
And any previously issued, unconsumed reset token for that account is invalidated
And an email is sent containing the token in the URL fragment, not the query string
```

**PR-AC2 — Completing the reset**
```gherkin
Given a valid, unconsumed, unexpired reset token and a new password meeting policy
When POST /v1/auth/password-reset/confirm is called with {token, new_password}
Then respond 200
And the password hash is replaced (Argon2id)
And the token's consumed_at is set
And revoke_before:{user_id} is set to now, terminating every existing session and refresh family
And a "your password was changed" notification is sent to the account's email
And an auth_audit_log entry is written (event=password_reset_completed)
```

### Anti-enumeration and token state
**PR-AC3 — Unknown email**
```gherkin
Given an email address that is not registered, or belongs to a deactivated account
When POST /v1/auth/password-reset/request is called
Then respond 202 with the same body, status and comparable timing as PR-AC1
And no email is sent, and this fact is not observable from the response
```

**PR-AC4 — Expired, consumed or unknown token**
```gherkin
Given a reset token that is expired, already consumed, or matches no stored hash
When POST /v1/auth/password-reset/confirm is called with it
Then respond 400 with type ".../errors/token-expired" or ".../errors/token-invalid"
And the existing password remains unchanged
And the response offers the option to request a new link
```

### Validation and throttling
**PR-AC5 — Weak or reused password**
```gherkin
Given a valid reset token
When the new password is shorter than 12 characters, appears in the breached-password list, or equals the current password
Then respond 422 with type ".../errors/password-policy"
And the errors array states which rule failed
And the token is NOT consumed, so the user can retry with the same link
```

**PR-AC6 — Request flooding**
```gherkin
Given a reset was requested for the same account less than 60 seconds ago
When POST /v1/auth/password-reset/request is called again
Then respond 429 with a Retry-After header
And the per-account limit is 5 requests/hour and the per-IP limit is 10 requests/hour
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/password-policy",
  "title": "Password Does Not Meet Policy",
  "status": 422,
  "detail": "Choose a password of at least 12 characters that you have not used before.",
  "instance": "/v1/auth/password-reset/confirm"
}
```
Error `type` slugs introduced by this story: `password-policy`.

## Non-Functional / Security Requirements
- **Why the fragment:** the URL fragment is never sent to the server by the browser, so it cannot land in access logs, proxies or `Referer` headers. The SPA reads it and POSTs the token in the body.
- A successful reset MUST invalidate all sessions (PR-AC2) — otherwise an attacker who reset the password keeps the victim's session, or vice versa.
- PR-AC5 deliberately does NOT consume the token on a policy failure; consuming it would force a second email round trip for a typo.
- The breached-password check MUST use k-anonymity (a 5-character SHA-1 prefix) or a local bloom filter — never transmit the password or its full hash.
- **Performance:** email dispatch is queued asynchronously; the endpoint returns within 300 ms regardless of SMTP latency, and timing must not vary with whether an email was actually queued.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| PR-AC1–2 | Integration test suite | `[gate]` |
| PR-AC3 | Integration test asserting identical status, body and comparable timing | `[gate]` |
| PR-AC4 | Integration test suite | `[gate]` |
| PR-AC5 | Integration test asserting the token survives a policy rejection | `[gate]` |
| PR-AC6 | Integration test with a fixed Valkey clock | `[gate]` |
| No token in any URL query string | CI grep over email templates and route definitions | `[manual]` |

## Open Questions
None.