# Specification: Refresh Token

**Source:** docs/backlog/US-2.3-refresh-token.md
**Story ID:** US-007
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/US-007-spec-review.md)

## Summary

This spec covers silent, in-band renewal of a user's session via `POST /v1/auth/refresh`: single-use refresh token rotation, reuse detection with family-wide revocation and alerting, rejection of expired/unknown/logged-out tokens with an indistinguishable response, idle and absolute lifetime enforcement, denial for deactivated or otherwise revoked accounts, and atomic handling of concurrent refresh requests from the same client.

## Background

As an authenticated user, I want my session to renew silently in the background, so that I stay logged in for a normal working day without re-typing my password, while stolen tokens stay useful for only a short window.

## Functional Requirements

### FR-1: Successful Rotation

Given a valid, unconsumed, unexpired refresh token, when `POST /v1/auth/refresh` is called, the system responds `200` with a new access token; issues a new refresh token and sets it as the cookie (rotation), scoped to `Path=/v1/auth` — the refresh endpoint is the only route that accepts the refresh cookie, limiting its exposure surface; marks the presented refresh token consumed so it can never be used again; and the new token keeps the same `family_id` and the same absolute expiry as the original.

**Derived from:** RT-AC1; cookie path scoping per source Data Model Notes

### FR-2: Reuse Detection Triggers Family-Wide Revocation and Alerting

Given a refresh token that was already consumed by a previous rotation, when `POST /v1/auth/refresh` is called with it, the system responds `401` with type `.../errors/token-invalid`; every token in that family is revoked immediately (the whole session chain is destroyed); an `auth_audit_log` entry is written (`event=refresh_reuse_detected`, `severity=high`); and a security notification email is sent to the account owner.

**Derived from:** RT-AC2

### FR-3: Expired, Unknown, or Logged-Out Tokens Are Rejected Indistinguishably

Given a refresh token that is expired, unknown, or was revoked by logout, when `POST /v1/auth/refresh` is called, the system responds `401` with type `.../errors/token-invalid`, no access token is issued, and the response is indistinguishable between the three cases (expired, unknown, revoked-by-logout).

**Derived from:** RT-AC3

### FR-4: Idle Timeout Forces Re-Authentication

Given a refresh token last used more than 14 days ago (idle timeout), when `POST /v1/auth/refresh` is called, the system responds `401` and full re-authentication is required.

**Derived from:** RT-AC4

### FR-5: Absolute Lifetime Cap Enforced Regardless of Recent Activity

Given a token family created more than 30 days ago (absolute cap), when `POST /v1/auth/refresh` is called with any token in that family, the system responds `401` regardless of recent activity.

**Derived from:** RT-AC4

### FR-6: Refresh Denied for Deactivated or Revoked Accounts

Given the account was deactivated, or `revoke_before:{user_id}` is later than the token's issued-at, when `POST /v1/auth/refresh` is called, the system responds `401` and no new access token is issued (per US-1.4 DA-AC5).

**Derived from:** RT-AC5

### FR-7: Concurrent Refresh Requests Are Resolved Atomically

Given two parallel refresh requests carrying the same token (e.g. two browser tabs), when both reach the server, exactly one succeeds; the check-and-consume runs as one atomic operation (a Valkey Lua script, or a conditional `UPDATE ... WHERE consumed_at IS NULL RETURNING`); the losing request receives `401` within a 10-second grace window without the family being revoked, because a same-family retry inside the grace window is a race, not an attack.

**Derived from:** RT-AC6

## Response Schemas

### Error Envelope Schema

Applies to the `401` `problem+json` responses referenced by FR-2, FR-3, and FR-6, all of type `.../errors/token-invalid` (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/token-invalid",
  "title": "Refresh Token Invalid",
  "status": 401,
  "detail": "This session can no longer be refreshed. Sign in again.",
  "instance": "/v1/auth/refresh"
}
```

This story introduces no new error `type` slugs; `token-invalid` is reused from US-1.2.

**Derived from:** source Error Envelope section.

## Non-Functional Requirements

- The check-and-consume operation behind FR-7 (RT-AC6) must be atomic as a hard requirement, not an implementation detail: a read-then-write pair is a TOCTOU bug in which both requests would observe `consumed_at IS NULL`, both would rotate, and the second rotation would then trip reuse detection (FR-2) and destroy a legitimate session.
- Raw refresh tokens must not be logged, and must not appear in URLs.
- Reuse detection (FR-2 / RT-AC2) must alert, not merely fail: a detected reuse is a probable token theft.
- Performance: p95 latency for `POST /v1/auth/refresh` must be ≤ 120 ms, since this call sits in the critical path of every user action after token expiry.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Initial token issuance (US-2.1).
- Session listing (US-2.6), which reads the metadata this story writes.

**Derived from:** Out of Scope section of the source.

## Open Questions

- The source's own Open Questions section asks: the 10-second grace window (RT-AC6 / FR-7) needs to be confirmed against real frontend behaviour once the SPA's refresh interceptor exists — too short causes spurious family revocations, too long weakens reuse detection. Should the grace window value be validated (and potentially adjusted) once that interceptor is available?
- The source's Assumptions & Defaults table (decision #6) specifies a refresh rate limit of 60 requests/family/hour, but no Acceptance Criterion defines the expected response (status code, error type, or other behavior) when a client exceeds this limit. What should happen when the rate limit is exceeded?
- The source's API Contract states the endpoint accepts the refresh token via cookie "(or body for `X-Client-Type: mobile`)", but no Acceptance Criterion covers the mobile path — RT-AC1 specifies only that the rotated token "is issued and set as the cookie". How is the rotated refresh token returned to an `X-Client-Type: mobile` client (e.g. in the response body rather than a `Set-Cookie` header)?
- RT-AC3/FR-3 requires the response to be "indistinguishable between the three cases" (expired, unknown, revoked-by-logout) but neither the story nor this spec states which dimensions must match — status code and body only, or also response latency (to close a timing side-channel, as FR-3's sibling anti-enumeration requirement in US-2.1 does explicitly)? Please clarify what "indistinguishable" is scoped to cover.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| RT-AC1 | "Given a valid, unconsumed, unexpired refresh token When POST /v1/auth/refresh is called Then respond 200 with a new access token And a new refresh token is issued and set as the cookie (rotation) And the presented refresh token is marked consumed and can never be used again And the new token keeps the same family_id and the same absolute expiry as the original" | FR-1 |
| RT-AC2 | "Given a refresh token that was already consumed by a previous rotation When POST /v1/auth/refresh is called with it Then respond 401 with type \".../errors/token-invalid\" And every token in that family is revoked immediately (the whole session chain is destroyed) And an auth_audit_log entry is written (event=refresh_reuse_detected, severity=high) And a security notification email is sent to the account owner" | FR-2 |
| RT-AC3 | "Given a refresh token that is expired, unknown, or was revoked by logout When POST /v1/auth/refresh is called Then respond 401 with type \".../errors/token-invalid\" And no access token is issued And the response is indistinguishable between the three cases" | FR-3 |
| RT-AC4 | "Given a refresh token last used more than 14 days ago (idle timeout) When POST /v1/auth/refresh is called Then respond 401 and full re-authentication is required Given a token family created more than 30 days ago (absolute cap) When POST /v1/auth/refresh is called with any token in that family Then respond 401 regardless of recent activity" | FR-4, FR-5 |
| RT-AC5 | "Given the account was deactivated, or revoke_before:{user_id} is later than the token's issued-at When POST /v1/auth/refresh is called Then respond 401 and no new access token is issued   # per US-1.4 DA-AC5" | FR-6 |
| RT-AC6 | "Given two parallel refresh requests carrying the same token (e.g. two browser tabs) When both reach the server Then exactly one succeeds; the check-and-consume runs as ONE atomic operation (a Valkey Lua script, or a conditional UPDATE ... WHERE consumed_at IS NULL RETURNING) And the loser receives 401 within a 10-second grace window WITHOUT the family being revoked Because a same-family retry inside the grace window is a race, not an attack" | FR-7 |
