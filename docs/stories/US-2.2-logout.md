# Epic 2 — Authentication: Logout

**Story ID:** US-2.2
**Project:** Customer Portal

## User Story
As an authenticated user,
I want to end my session on this device, or on all devices at once,
So that nobody can continue using the portal as me after I walk away or lose a device.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Access-token revocation | `jti` added to a Valkey denylist with TTL = remaining lifetime | Logout must be immediate, not effective only at token expiry |
| 2 | Refresh revocation scope | The whole rotation family, not just the presented token | A single surviving family member would let the session continue |
| 3 | Logout-everywhere mechanism | `revoke_before:{user_id}`, as introduced in US-1.4 | Reuse the existing revocation primitive rather than inventing a second one |
| 4 | Repeat logout | Idempotent — 204 either way | Distinguishing states would leak token status |

## In Scope
- `POST /v1/auth/logout` — end the current session
- `POST /v1/auth/logout-all` — end every session for the account
- Server-side revocation of both token types

## Out of Scope
- Per-device session listing and selective revocation (US-2.6)
- Account deactivation (US-1.4), which has its own revocation trigger

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/auth/logout` | Required | none | 204 + `Set-Cookie` clearing the refresh cookie |
| POST | `/v1/auth/logout-all` | Required | none | 204 |

## Data Model Notes
- Valkey `jti_denylist:{jti}` — value irrelevant, TTL = `exp − now`
- Valkey `revoke_before:{user_id}` — shared with US-1.4
- `auth_audit_log` `event=logout`, `scope` ∈ {`session`, `all_sessions`}

## Acceptance Criteria

### Happy path
**LO-AC1 — Logout on the current device**
```gherkin
Given an authenticated user with a valid access token and refresh cookie
When POST /v1/auth/logout is called
Then respond 204
And the presented refresh token is marked revoked (its whole rotation family, per US-2.3)
And the access token's jti is added to a Valkey denylist with TTL = its remaining lifetime
And the refresh cookie is cleared (Set-Cookie with Max-Age=0)
And an auth_audit_log entry is written (event=logout, scope=session)
```

**LO-AC2 — Logout everywhere**
```gherkin
Given an authenticated user with active sessions on three devices
When POST /v1/auth/logout-all is called
Then respond 204
And revoke_before:{user_id} is set to now in Valkey
And every access and refresh token issued before that moment is rejected on next use (401)
And an auth_audit_log entry is written (event=logout, scope=all_sessions)
```

### Negative paths
**LO-AC3 — Not authenticated**
```gherkin
Given a request with no access token, or an expired/invalid one
When POST /v1/auth/logout is called
Then respond 401
And no session state is modified
```

**LO-AC4 — Idempotent repeat logout**
```gherkin
Given a refresh token that was already revoked by a previous logout
When POST /v1/auth/logout is called again with the same still-valid access token
Then respond 204 (identical to LO-AC1) — the operation is idempotent
And no additional revocation side effects occur
And no error is surfaced that would confirm the token's prior state
```

**LO-AC5 — Revoked token cannot be reused**
```gherkin
Given a user who has just logged out
When any authenticated endpoint is called with the pre-logout access token
Then respond 401
Because the jti is on the denylist, regardless of the token's exp claim
```

## Error Envelope (RFC 7807 `application/problem+json`)
This story introduces no new error `type` slugs; it emits only the shared `401` unauthenticated envelope.

## Non-Functional / Security Requirements
- Clearing the cookie client-side is NOT sufficient; server-side revocation is the acceptance criterion.
- Logout is a state-changing, cookie-authenticated call → CSRF token required.
- Denylist entries MUST expire on their own (TTL = `exp − now`) so the store stays bounded without a cleanup job.
- **Performance:** the denylist lookup adds ≤ 2 ms to the shared auth middleware; combine it with the `revoke_before` check in a single Valkey round trip.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| LO-AC1–2 | Integration test suite | `[gate]` |
| LO-AC3–4 | Integration test suite | `[gate]` |
| LO-AC5 | Integration test asserting the middleware rejects a denylisted jti | `[gate]` |
| Denylist TTL bounded | Unit test on the TTL calculation | `[gate]` |

## Open Questions
None.