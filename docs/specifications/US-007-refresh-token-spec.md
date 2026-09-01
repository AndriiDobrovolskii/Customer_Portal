# Specification: Refresh Token

**Source:** docs/stories/US-2.3-refresh-token.md
**Story ID:** US-007
**Generated:** 2026-08-22
**Revised:** 2026-09-01 (incorporates resolved Open Decisions OD-1–OD-6, `docs/decisions/US-2.3-open-decisions.md`, following us-clarifier's clarification pass against the now-implemented US-2.1/US-2.2 codebase; also addresses the two findings carried forward, unresolved, from the 2026-08-22 spec review — the RFC 7807 error envelope shape and the refresh cookie's `Path=/v1/auth` scoping)
**Status:** Draft (SPEC_REVIEW Pass with Issues, accepted by user 2026-09-01 — see `docs/reviews/specifications/US-007-spec-review.md`; all 3 findings resolved same-day)

## Summary

This spec covers silent, in-band renewal of a user's session via `POST /v1/auth/refresh`: single-use refresh token rotation, reuse detection with family-wide revocation and alerting, rejection of expired/unknown/logged-out tokens with an indistinguishable response, idle and absolute lifetime enforcement, denial for deactivated or otherwise revoked accounts, atomic handling of concurrent refresh requests from the same client, and a per-family rate limit.

## Background

As an authenticated user, I want my session to renew silently in the background, so that I stay logged in for a normal working day without re-typing my password, while stolen tokens stay useful for only a short window.

## Open Decision Resolutions (OD-1–OD-6)

The 2026-08-22 version of this spec left three gaps as unresolved Open Questions (rate-limit response, mobile-client delivery, the scope of RT-AC3's "indistinguishable") and didn't address two schema gaps or a check-ordering ambiguity the story never states. Clarification against the now-implemented US-2.1/US-2.2 codebase resolved all of these; all six apply to the FRs and NFRs below:

- **Rate-limit response:** a client exceeding 60 requests/family/hour receives `429` with a `Retry-After` header, reusing the existing `TooManyAttemptsError` pattern login throttling already established (`app/modules/users/exceptions.py`), keyed by `family_id` instead of IP/account. **Resolution source:** OD-1.
- **Mobile client (`X-Client-Type: mobile`) body-delivery:** descoped. No mobile client exists yet to consume a second, non-`HttpOnly` token-delivery channel; this story implements cookie-based rotation only. Tracked as a follow-up. **Resolution source:** OD-2.
- **RT-AC3's "indistinguishable" response:** scoped to status code and response body only. Unlike login (which fakes a variable-cost Argon2id hash to close a timing side-channel per `BR-005`), none of the three refresh-invalid cases involves a comparably expensive operation, so there is no timing cost to fake. **Resolution source:** OD-3.
- **`auth_audit_log.severity`:** the existing table has no `severity` column. This story adds a dedicated nullable `severity: String(16)` column, set to `"high"` on `refresh_reuse_detected` rows only and left `null` on every other event type. **Resolution source:** OD-4.
- **Check ordering (reuse vs. account eligibility):** a presented token is evaluated (1) exists and not expired, (2) already consumed → reuse, always alerts regardless of account status, (3) account eligibility (deactivated / `revoke_before`), (4) idle timeout, (5) atomic consume. Reuse detection and its alerting fire even against an already-deactivated account, since a replayed stolen token is evidence of compromise independent of the account's current status. **Resolution source:** OD-5.
- **Family revocation's blast radius on reuse:** scoped to `refresh_tokens` rows only. `RefreshToken` and `UserSession` (the access-token table) have no link to each other today, and none is added by this story; a currently-valid access token tied to a reused family remains usable for its remaining ≤15-minute lifetime (`access_token_ttl_seconds = 900`). Accepted as a bounded tradeoff rather than a schema change to a table this story doesn't otherwise touch. **Resolution source:** OD-6.

Two additional findings from the 2026-08-22 spec review, never resolved, are addressed directly in FR-1/FR-2/FR-3/FR-6 below rather than via an Open Decision (they required no ambiguity resolution, only restating detail the source story already specified): the RFC 7807 error envelope's required conformance, and the refresh cookie's `Path=/v1/auth` scoping.

## Functional Requirements

### FR-1: Successful Rotation

Given a valid, unconsumed, unexpired refresh token, when `POST /v1/auth/refresh` is called, the system responds `200` with a new access token; issues a new refresh token and sets it as the cookie (rotation), scoped to `Path=/v1/auth` — the refresh endpoint is the only route that accepts the refresh cookie, limiting its exposure surface; marks the presented refresh token's `consumed_at` so it can never be used again; and the new token keeps the same `family_id` and the same `expires_at` (absolute cap) as the original — `expires_at` is set once at family creation and copied forward unchanged on every rotation, which is also how the 30-day absolute cap (FR-5) is enforced without a separate family-creation timestamp.

**Derived from:** RT-AC1; cookie `Path=/v1/auth` scoping per source Data Model Notes (carried-forward spec-review finding, now stated explicitly here)

### FR-2: Reuse Detection Triggers Family-Wide Revocation and Alerting

Given a refresh token that was already consumed by a previous rotation, when `POST /v1/auth/refresh` is called with it, the system responds `401`, conforming to the Error Envelope Schema below (type `.../errors/token-invalid`); every token in that family has `revoked_at` set immediately (the whole refresh-token chain is destroyed; per resolved OD-6, a currently-valid access token tied to this family is not separately revoked and remains usable for its remaining ≤15-minute lifetime); an `auth_audit_log` entry is written (`event=refresh_reuse_detected`, `severity=high`, per resolved OD-4); and a security notification email is sent to the account owner — this requires a new `EmailSender` protocol method (`app/core/email.py` currently has `send_verification_email`, `send_email_change_confirmation`, `send_email_change_notice`; none fits a security-alert notice) plus an implementation. This check runs before the account-eligibility check (FR-6): reuse is detected and alerted on even if the account is already deactivated, per resolved OD-5.

**Derived from:** RT-AC2; envelope conformance per carried-forward spec-review finding; `severity` column per resolved OD-4; check order and residual access-token window per resolved OD-5, OD-6

### FR-3: Expired, Unknown, or Logged-Out Tokens Are Rejected Indistinguishably

Given a refresh token that is expired, unknown, or was revoked by logout, when `POST /v1/auth/refresh` is called, the system responds `401`, conforming to the Error Envelope Schema below (type `.../errors/token-invalid`); no access token is issued; and the response is identical in status code and body across all three cases (expired, unknown, revoked-by-logout) — per resolved OD-3, this does not extend to response timing, since none of the three cases involves a variable-cost operation to fake the cost of. This is the first check performed on a presented token (per resolved OD-5's check order), before reuse, eligibility, or idle-timeout checks.

**Derived from:** RT-AC3; envelope conformance per carried-forward spec-review finding; "indistinguishable" scope per resolved OD-3; check order per resolved OD-5

### FR-4: Idle Timeout Forces Re-Authentication

Given a refresh token whose `last_used_at` is more than 14 days in the past, when `POST /v1/auth/refresh` is called, the system responds `401` and full re-authentication is required. This check runs after account-eligibility (FR-6), per resolved OD-5's check order.

**Derived from:** RT-AC4 (idle-timeout clause); check order per resolved OD-5

### FR-5: Absolute Lifetime Cap Enforced Regardless of Recent Activity

Given a token family created more than 30 days ago, when `POST /v1/auth/refresh` is called with any token in that family, the system responds `401` regardless of recent activity. This is enforced via the same `expires_at` check as FR-3's "expired" case (FR-1 fixes `expires_at` at family creation and copies it forward unchanged on every rotation), so an absolute-cap rejection is indistinguishable from any other FR-3 rejection without needing a separate family-creation timestamp column.

**Derived from:** RT-AC4 (absolute-cap clause); mechanism per FR-1's `expires_at` handling

### FR-6: Refresh Denied for Deactivated or Revoked Accounts

Given the account was deactivated, or `revoke_before:{user_id}` is later than the token's issued-at, when `POST /v1/auth/refresh` is called, the system responds `401`, conforming to the Error Envelope Schema below (type `.../errors/token-invalid`), and no new access token is issued (per US-1.4 DA-AC5). This check runs after reuse detection (FR-2) but before the idle-timeout check (FR-4), per resolved OD-5's check order.

**Derived from:** RT-AC5; envelope conformance per carried-forward spec-review finding; check order per resolved OD-5

### FR-7: Concurrent Refresh Requests Are Resolved Atomically

Given two parallel refresh requests carrying the same token (e.g. two browser tabs), when both reach the server, exactly one succeeds; the check-and-consume runs as one atomic operation (a Valkey Lua script, or a conditional `UPDATE ... WHERE consumed_at IS NULL RETURNING`); the losing request receives `401` within a 10-second grace window without the family being revoked, because a same-family retry inside the grace window is a race, not an attack. This is the final check in the processing order (per resolved OD-5), applied only once a token has already passed FR-3/FR-2/FR-6/FR-4.

**Derived from:** RT-AC6; check order per resolved OD-5

## Response Schemas

### Error Envelope Schema

Applies to every `401` `problem+json` response referenced by FR-2, FR-3, and FR-6, all of type `.../errors/token-invalid` (`application/problem+json`, RFC 7807). Every field below is required in the response body — this was the carried-forward spec-review finding (the 2026-08-22 version defined this schema but never required FR-2/FR-3/FR-6 to conform to it; this revision closes that gap):

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

**Derived from:** source Error Envelope section; conformance requirement is the carried-forward spec-review finding, resolved 2026-09-01.

## Non-Functional Requirements

- The check-and-consume operation behind FR-7 (RT-AC6) must be atomic as a hard requirement, not an implementation detail: a read-then-write pair is a TOCTOU bug in which both requests would observe `consumed_at IS NULL`, both would rotate, and the second rotation would then trip reuse detection (FR-2) and destroy a legitimate session.
- Raw refresh tokens must not be logged, and must not appear in URLs.
- Reuse detection (FR-2 / RT-AC2) must alert, not merely fail: a detected reuse is a probable token theft.
- Performance: p95 latency for `POST /v1/auth/refresh` must be ≤ 120 ms, since this call sits in the critical path of every user action after token expiry.
- The rotated refresh cookie is scoped `Path=/v1/auth`; no other route accepts it. Per the carried-forward spec-review finding, this is a stated requirement, not left implicit (see FR-1).
- Refresh requests are rate-limited to 60/family/hour; exceeding it returns `429` with `Retry-After`, per resolved OD-1. Checked immediately after the presented token resolves to a `family_id` (i.e., right after the hash lookup succeeds, before the expiry/reuse/eligibility/idle-timeout/atomic-consume checks) — a client hammering a real family counts toward the limit regardless of whether the specific call would otherwise 401, so an unknown/unresolvable token (no `family_id` to key on) cannot itself be rate-limited by this mechanism. Resolved 2026-09-01 per the spec review's ambiguity finding.
- A security-notification email (FR-2) is sent fire-and-forget: the `401` response, family revocation, and audit-log write do not wait on or depend on the email send succeeding, matching this codebase's existing pattern for the registration verification email (`app/modules/users/service.py`, "must succeed regardless of whether the verification email goes out"). Resolved 2026-09-01 per the spec review's missing-edge-case finding.
- A refresh token that is both already-consumed and past its `expires_at` is rejected by FR-3 (expired) rather than FR-2 (reuse): no family revocation, `severity=high` audit entry, or security email fires for that specific replay. Accepted: the family is already unusable via the absolute-cap expiry regardless, so the additional alerting is not required once that boundary has passed. Resolved 2026-09-01 per the spec review's missing-edge-case finding.
- A refresh token family reused after being consumed is not treated as fully contained: the paired access token (if still valid) remains usable for its own remaining ≤15-minute lifetime, since `user_sessions` carries no link back to `refresh_tokens.family_id`. Accepted tradeoff per resolved OD-6.

**Derived from:** Non-Functional / Security Requirements section of the source; cookie scoping per carried-forward spec-review finding; rate-limit and residual-access-window items per resolved OD-1, OD-6; rate-limit check ordering, email-delivery fire-and-forget, and expired-vs-reused precedence per the 2026-09-01 spec review's findings, resolved same-day.

## Out of Scope

- Initial token issuance (US-2.1).
- Session listing (US-2.6), which reads the metadata this story writes.
- `X-Client-Type: mobile` refresh-token delivery in the response body — no mobile client exists yet to consume it, and it is a materially different security posture (no `HttpOnly` protection) from cookie delivery; tracked as a follow-up story. Per resolved OD-2.
- Linking `user_sessions` to `refresh_tokens.family_id` so reuse detection can also revoke a live access token — accepted as a bounded ≤15-minute residual-access tradeoff instead. Per resolved OD-6.

**Derived from:** Out of Scope section of the source; mobile-delivery and access-token-link exclusions per resolved OD-2, OD-6.

## Open Questions

- The source's own Open Questions section asks: the 10-second grace window (RT-AC6 / FR-7) needs to be confirmed against real frontend behaviour once the SPA's refresh interceptor exists — too short causes spurious family revocations, too long weakens reuse detection. This remains open as a future check-in once that interceptor exists; it does not block this spec, since the story itself frames it as a post-launch validation step rather than a pre-implementation gap.

**Derived from:** source's Open Questions section. The three other Open Questions previously listed here (rate-limit response, mobile-client delivery, "indistinguishable" scope) are now resolved — see Open Decision Resolutions above.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| RT-AC1 | "Given a valid, unconsumed, unexpired refresh token When POST /v1/auth/refresh is called Then respond 200 with a new access token And a new refresh token is issued and set as the cookie (rotation) And the presented refresh token is marked consumed and can never be used again And the new token keeps the same family_id and the same absolute expiry as the original" | FR-1 |
| RT-AC2 | "Given a refresh token that was already consumed by a previous rotation When POST /v1/auth/refresh is called with it Then respond 401 with type \".../errors/token-invalid\" And every token in that family is revoked immediately (the whole session chain is destroyed) And an auth_audit_log entry is written (event=refresh_reuse_detected, severity=high) And a security notification email is sent to the account owner" | FR-2 |
| RT-AC3 | "Given a refresh token that is expired, unknown, or was revoked by logout When POST /v1/auth/refresh is called Then respond 401 with type \".../errors/token-invalid\" And no access token is issued And the response is indistinguishable between the three cases" | FR-3 |
| RT-AC4 | "Given a refresh token last used more than 14 days ago (idle timeout) When POST /v1/auth/refresh is called Then respond 401 and full re-authentication is required Given a token family created more than 30 days ago (absolute cap) When POST /v1/auth/refresh is called with any token in that family Then respond 401 regardless of recent activity" | FR-4, FR-5 |
| RT-AC5 | "Given the account was deactivated, or revoke_before:{user_id} is later than the token's issued-at When POST /v1/auth/refresh is called Then respond 401 and no new access token is issued   # per US-1.4 DA-AC5" | FR-6 |
| RT-AC6 | "Given two parallel refresh requests carrying the same token (e.g. two browser tabs) When both reach the server Then exactly one succeeds; the check-and-consume runs as ONE atomic operation (a Valkey Lua script, or a conditional UPDATE ... WHERE consumed_at IS NULL RETURNING) And the loser receives 401 within a 10-second grace window WITHOUT the family being revoked Because a same-family retry inside the grace window is a race, not an attack" | FR-7 |
