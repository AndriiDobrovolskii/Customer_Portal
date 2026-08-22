# Epic 2 — Authentication: Login

**Story ID:** US-2.1
**Project:** Customer Portal

## User Story
As a registered customer,
I want to exchange my email and password for a session,
So that I can use the authenticated parts of the portal without re-entering my credentials on every request.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Access token TTL | 15 minutes | Short enough that revocation lag is tolerable, long enough to avoid refresh churn |
| 2 | Refresh token transport | HttpOnly, Secure, SameSite=Strict cookie scoped to `Path=/v1/auth`; JSON body when `X-Client-Type: mobile` | Cookie is unavailable to native clients; the switch keys on an explicit header, never on `User-Agent` |
| 3 | JWT signing | RS256 with JWKS key rotation | Verifiers never need a shared secret |
| 4 | Failed-login limits | 10 / account / 15 min, 20 / IP / 15 min | Standard abuse-prevention range; successful login resets the account counter |
| 5 | Unknown-email handling | Dummy Argon2id verification is performed | Response timing must not reveal account existence |
| 6 | Password hashing cost | Argon2id tuned to ≈100 ms | Balance between brute-force resistance and endpoint latency |

## In Scope
- `POST /v1/auth/login` — credential verification and token issuance
- Account-state gating (unverified, deactivated) at login time
- Brute-force throttling per account and per IP
- Audit entries for successful and failed attempts

## Out of Scope
- Refresh and rotation mechanics (US-2.3)
- Session termination (US-2.2)
- MFA challenge branch (US-2.5 — this story's success path is what US-2.5 later intercepts)
- Registration and email verification (US-1.1, US-1.2)

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/auth/login` | None | `{"email": str, "password": str}` | 200 `{"access_token": str, "token_type": "Bearer", "expires_in": 900}` + `Set-Cookie: refresh_token` |

## Data Model Notes
- `users.last_login_at: datetime | null`
- `auth_audit_log`: append-only; `event` ∈ {`login_succeeded`, `login_failed`}, `reason`, `actor_id`, `ip`, `user_agent`, `request_id`, `occurred_at`
- Rate-limit counters live in Valkey keyed on `login_fail:account:{user_id}` and `login_fail:ip:{ip}`, with TTL so no cleanup job is needed

## Acceptance Criteria

### Happy path
**LI-AC1 — Successful login**
```gherkin
Given an active user whose email is verified
When POST /v1/auth/login is called with the correct email and password
Then respond 200 with an access token (JWT, 15-minute TTL) in the body
And set a refresh token as an HttpOnly, Secure, SameSite=Strict cookie (Path=/v1/auth)
And an auth_audit_log entry is written (event=login_succeeded)
And users.last_login_at is updated
```

### Credential failures
**LI-AC2 — Wrong password**
```gherkin
Given an active, verified user
When POST /v1/auth/login is called with an incorrect password
Then respond 401 with problem+json type ".../errors/invalid-credentials"
And no token of any kind is issued
And an auth_audit_log entry is written (event=login_failed, reason=bad_password)
```

**LI-AC3 — Unknown email (anti-enumeration)**
```gherkin
Given an email address that is not registered
When POST /v1/auth/login is called with that email and any password
Then respond 401 with the same body, status and comparable timing as LI-AC2
Because a dummy Argon2id verification is performed so response time does not reveal account existence
```

### Account-state gating
**LI-AC4 — Account states that block login**
```gherkin
Given correct credentials are supplied
When the account is unverified
Then respond 403 with type ".../errors/email-not-verified"   # per US-1.2 VE-AC5
When the account is deactivated
Then respond 403 with type ".../errors/account-deactivated"  # per US-1.4 DA-AC6
And in both cases credential verification runs first, so an attacker without the password only ever sees 401
```

### Throttling and validation
**LI-AC5 — Brute-force throttling**
```gherkin
Given 10 failed login attempts for the same account within 15 minutes
When POST /v1/auth/login is called again for that account
Then respond 429 with a Retry-After header and type ".../errors/too-many-attempts"
And the same limit applies independently per source IP (20 attempts / 15 minutes)
And a successful login resets the account counter
```

**LI-AC6 — Malformed request**
```gherkin
Given a request body missing "password", or containing an unknown field
When POST /v1/auth/login is called
Then respond 422 with type ".../errors/validation-failed"
And the errors array names the offending field(s)
And no login attempt is recorded against the rate-limit counter
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/invalid-credentials",
  "title": "Invalid Credentials",
  "status": 401,
  "detail": "The email or password is incorrect.",
  "instance": "/v1/auth/login"
}
```
Error `type` slugs introduced by this story: `invalid-credentials`, `too-many-attempts`.

## Non-Functional / Security Requirements
- The response MUST NOT distinguish "no such user" from "wrong password" in body, status **or** timing.
- Passwords MUST NOT appear in logs, traces or APM payloads — add a scrubbing rule for `password` / `current_password` keys.
- Argon2id verification MUST run in a thread pool so it does not block the event loop.
- The login endpoint is CSRF-exempt, but every cookie-authenticated state-changing endpoint requires a CSRF token.
- **Performance:** p95 ≤ 400 ms including the deliberate ≈100 ms hashing cost.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| LI-AC1–2 | Integration test suite (pytest + httpx) | `[gate]` |
| LI-AC3 | Integration test asserting identical response shape, status and comparable timing | `[gate]` |
| LI-AC4 | Integration test asserting credential check precedes the state check | `[gate]` |
| LI-AC5 | Integration test with a fixed Valkey clock / counter | `[gate]` |
| LI-AC6 | Schema test on the Pydantic request model | `[gate]` |
| No password in logs | CI grep + log-scrubbing unit test | `[manual]` until a dedicated lint rule exists |

## Open Questions
None. Transport selection is settled by Decision #1 in the epic-level document.