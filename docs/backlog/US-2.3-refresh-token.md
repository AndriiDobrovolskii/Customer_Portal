# Epic 2 — Authentication: Refresh Token

**Story ID:** US-2.3
**Project:** Customer Portal

## User Story
As an authenticated user,
I want my session to renew silently in the background,
So that I stay logged in for a normal working day without re-typing my password, while stolen tokens stay useful for only a short window.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Rotation policy | Single-use tokens with reuse detection per family | OAuth 2.0 Security BCP |
| 2 | Idle timeout | 14 days since last use | Common vendor default |
| 3 | Absolute cap | 30 days from family creation | Bounds the damage of a long-lived stolen chain |
| 4 | Concurrent-refresh grace window | 10 seconds | Absorbs double renders and flaky networks without giving an attacker a usable window |
| 5 | Token design | 32 bytes via `secrets.token_urlsafe(32)`, SHA-256 hash stored only | Matches US-1.2 token design |
| 6 | Refresh rate limit | 60 requests / family / hour | A client above this is looping |

## In Scope
- `POST /v1/auth/refresh` — rotate a refresh token and issue a new access token
- Reuse detection and family-wide revocation
- Idle and absolute lifetime enforcement

## Out of Scope
- Initial token issuance (US-2.1)
- Session listing (US-2.6), which reads the metadata this story writes

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/auth/refresh` | Refresh cookie (or body for `X-Client-Type: mobile`) | none | 200 `{"access_token": str, "expires_in": 900}` + rotated refresh cookie |

## Data Model Notes
- `refresh_tokens`: `token_hash` (SHA-256, unique), `family_id`, `user_id`, `issued_at`, `consumed_at` (nullable), `expires_at`, plus `ip`, `user_agent`, `last_used_at` for US-2.6
- The refresh endpoint is the only route that accepts the refresh cookie (`Path=/v1/auth`), limiting its exposure surface

## Acceptance Criteria

### Happy path
**RT-AC1 — Successful rotation**
```gherkin
Given a valid, unconsumed, unexpired refresh token
When POST /v1/auth/refresh is called
Then respond 200 with a new access token
And a new refresh token is issued and set as the cookie (rotation)
And the presented refresh token is marked consumed and can never be used again
And the new token keeps the same family_id and the same absolute expiry as the original
```

### Reuse and lifetime
**RT-AC2 — Reuse detection**
```gherkin
Given a refresh token that was already consumed by a previous rotation
When POST /v1/auth/refresh is called with it
Then respond 401 with type ".../errors/token-invalid"
And every token in that family is revoked immediately (the whole session chain is destroyed)
And an auth_audit_log entry is written (event=refresh_reuse_detected, severity=high)
And a security notification email is sent to the account owner
```

**RT-AC3 — Expired or unknown token**
```gherkin
Given a refresh token that is expired, unknown, or was revoked by logout
When POST /v1/auth/refresh is called
Then respond 401 with type ".../errors/token-invalid"
And no access token is issued
And the response is indistinguishable between the three cases
```

**RT-AC4 — Idle and absolute lifetime limits**
```gherkin
Given a refresh token last used more than 14 days ago (idle timeout)
When POST /v1/auth/refresh is called
Then respond 401 and full re-authentication is required
Given a token family created more than 30 days ago (absolute cap)
When POST /v1/auth/refresh is called with any token in that family
Then respond 401 regardless of recent activity
```

**RT-AC5 — Account no longer eligible**
```gherkin
Given the account was deactivated, or revoke_before:{user_id} is later than the token's issued-at
When POST /v1/auth/refresh is called
Then respond 401 and no new access token is issued   # per US-1.4 DA-AC5
```

### Concurrency
**RT-AC6 — Concurrent refresh from one client**
```gherkin
Given two parallel refresh requests carrying the same token (e.g. two browser tabs)
When both reach the server
Then exactly one succeeds; the check-and-consume runs as ONE atomic operation
    (a Valkey Lua script, or a conditional UPDATE ... WHERE consumed_at IS NULL RETURNING)
And the loser receives 401 within a 10-second grace window WITHOUT the family being revoked
Because a same-family retry inside the grace window is a race, not an attack
```
> A read-then-write pair here is the classic TOCTOU bug: both requests would see `consumed_at IS NULL`, both would rotate, and the second rotation would then trip RT-AC2 and destroy a legitimate session. The atomicity is the requirement, not an implementation detail.

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/token-invalid",
  "title": "Refresh Token Invalid",
  "status": 401,
  "detail": "This session can no longer be refreshed. Sign in again.",
  "instance": "/v1/auth/refresh"
}
```
Error `type` slugs introduced by this story: none new — reuses `token-invalid` from US-1.2.

## Non-Functional / Security Requirements
- RT-AC6's atomicity is a **requirement, not an implementation detail**: a read-then-write pair is a TOCTOU bug in which both requests observe `consumed_at IS NULL`, both rotate, and the second rotation then trips RT-AC2 and destroys a legitimate session.
- Raw refresh tokens MUST NOT be logged, and MUST NOT appear in URLs.
- Reuse detection (RT-AC2) MUST alert, not merely fail: a detected reuse is a probable token theft.
- **Performance:** p95 ≤ 120 ms — this call sits in the critical path of every user action after token expiry.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| RT-AC1 | Integration test suite | `[gate]` |
| RT-AC2 | Integration test asserting family-wide revocation and the audit entry | `[gate]` |
| RT-AC3–5 | Integration test suite | `[gate]` |
| RT-AC6 | Concurrency test issuing two simultaneous refreshes; asserts one 200, one 401, family intact | `[gate]` |
| Atomicity of check-and-consume | Code review checklist + the RT-AC6 concurrency test | `[gate]` |

## Open Questions
1. Confirm the 10-second grace window (RT-AC6) against real frontend behaviour once the SPA's refresh interceptor exists — too short causes spurious family revocations, too long weakens reuse detection.