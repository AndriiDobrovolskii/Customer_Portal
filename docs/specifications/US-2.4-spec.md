# Specification: Password Reset

**Source:** docs/stories/US-2.4-password-reset.md
**Story ID:** US-2.4
**Generated:** 2026-08-22
**Revised:** 2026-09-01 — incorporates OD-1–OD-3 (`docs/decisions/US-2.4-open-decisions.md`), the 2 precedent-resolved items from `docs/evidence/US-2.4-clarification-report.md`, and the 3 carried-forward findings from `docs/reviews/specifications/US-2.4-spec-review.md` (token-generation method, error-envelope field shape, malformed-email question).
**Status:** Draft (revised)

## Summary

This spec covers self-service password reset: token issuance and email delivery via `POST /v1/auth/password-reset/request`, token consumption and password change via `POST /v1/auth/password-reset/confirm`, anti-enumeration for unknown or deactivated accounts, rejection of expired/consumed/invalid tokens and policy-violating passwords, full session and refresh-token revocation on a successful reset, and per-account and per-IP request throttling.

## Background

As a user who has forgotten their password, I want to set a new one via a link emailed to my registered address, so that I can regain access to my account without contacting support.

## Open Decision Resolutions (2026-09-01)

- **OD-1 (breached-password check mechanism):** A local static breached-password list (or a bloom filter built from one), bundled with the application. No live network call to a third-party service — this remains the project's first and only external check to run entirely offline, consistent with every other check in this codebase (rate limits, revocation, audit) being self-contained against Postgres/Valkey.
- **OD-2 (request-throttle check order):** When more than one of the three limits on `POST /v1/auth/password-reset/request` is tripped at once, checks run in this order: the 60-second per-account cooldown, then the 5/hour per-account limit, then the 10/hour per-IP limit. The response uses the `Retry-After` of the first limit tripped.
- **OD-3 (request-side audit logging):** `POST /v1/auth/password-reset/request` writes an `auth_audit_log` entry (`event=password_reset_requested`) on every call, including calls for an unknown email or a deactivated account. This audit write is server-side only and does not alter PR-AC3's anti-enumeration response.
- **Precedent (PR-AC4's token-state mapping):** unknown token hash and already-consumed token both map to `token-invalid`; an expired token maps to `token-expired`. Resolved by direct precedent in `app/modules/email_verification/service.py`, which handles the identical token shape this story is explicitly modeled on.
- **Precedent (malformed/missing email on the request endpoint):** no dedicated email-format validation; the field is a plain string, matching `LoginRequest.email` in `app/modules/users/schemas.py` (no endpoint in this codebase validates email format at the schema layer).
- **Spec-review gap (concurrent confirm requests on the same token), accepted by user 2026-09-01:** token consumption in FR-2 must be atomic (`UPDATE...WHERE consumed_at IS NULL RETURNING`), guaranteeing single-use under concurrent `confirm` calls with the same token — mirroring US-2.3's refresh-token race handling (RT-AC6). Not stated by the source story; resolved per `docs/reviews/specifications/US-2.4-spec-review.md`'s Missing Edge Cases finding.

## Functional Requirements

### FR-1: Requesting a Reset

Given a registered, active account, when `POST /v1/auth/password-reset/request` is called with that account's email, the system responds `202` with a generic body ("If an account exists, an email has been sent"). A single-use reset token is generated as 32 bytes via `secrets.token_urlsafe(32)`, with a 30-minute TTL and only its SHA-256 hash persisted (token record: `token_hash`, `user_id`, `issued_at`, `expires_at`, `consumed_at` — the same shape as `email_verification_tokens` in US-1.2). Any previously issued, unconsumed reset token for that account is invalidated. An email is sent containing the token in the URL fragment, not the query string. An `auth_audit_log` entry is written (`event=password_reset_requested`).

**Derived from:** PR-AC1; token generation method per source Assumptions & Defaults table; audit entry per OD-3.

### FR-2: Completing the Reset

Given a valid, unconsumed, unexpired reset token and a new password meeting policy, when `POST /v1/auth/password-reset/confirm` is called with `{token, new_password}`, the system responds `200`; replaces the password hash (Argon2id); sets the token's `consumed_at` atomically (guarding against a concurrent request consuming the same token twice — see spec-review resolution below); sets `revoke_before:{user_id}` to now, terminating every existing session and refresh family; sends a "your password was changed" notification to the account's email; and writes an `auth_audit_log` entry (`event=password_reset_completed`).

**Derived from:** PR-AC2; atomic consumption per spec-review Missing Edge Cases finding, accepted 2026-09-01.

### FR-3: Unknown or Deactivated Account Does Not Leak Existence

Given an email address that is not registered, or that belongs to a deactivated account, when `POST /v1/auth/password-reset/request` is called, the system responds `202` with the same body, status, and comparable timing as a request for a registered, active account (FR-1). No email is sent, and this fact is not observable from the response. The `auth_audit_log` write required by FR-1/OD-3 still occurs for this case — it is server-side only and does not affect the response.

**Derived from:** PR-AC3; audit-write applicability per OD-3.

### FR-4: Expired, Consumed, or Unknown Token Rejected

Given a reset token that is expired, already consumed, or matches no stored hash, when `POST /v1/auth/password-reset/confirm` is called with it, the system responds `400` with a `problem+json` body. An unknown token hash or an already-consumed token both respond with type `.../errors/token-invalid`; an expired token responds with type `.../errors/token-expired`. The existing password remains unchanged, and the response offers the option to request a new link.

**Derived from:** PR-AC4; token-state mapping per precedent (Open Decision Resolutions).

### FR-5: Weak or Reused Password Rejected Without Consuming the Token

Given a valid reset token, when the submitted new password is shorter than 12 characters, appears in the breached-password list, or equals the current password, the system responds `422` with a `problem+json` body of type `.../errors/password-policy`, and the errors array states which rule failed. The breached-password check is performed against a local static list/bloom filter (OD-1) — no password or hash of it is ever transmitted off-host. The token is NOT consumed by this rejection, so the user can retry with the same link.

**Derived from:** PR-AC5; breach-check mechanism per OD-1.

### FR-6: Request Flooding Is Throttled

Given a reset was requested for the same account less than 60 seconds ago, when `POST /v1/auth/password-reset/request` is called again, the system responds `429` with a `Retry-After` header. Three limits apply to this endpoint: a 60-second per-account cooldown, a 5-requests/hour per-account limit, and a 10-requests/hour per-IP limit. Checks run in that order (cooldown, then per-account/hour, then per-IP/hour); the response uses the `Retry-After` value of the first limit tripped.

**Derived from:** PR-AC6; check order per OD-2.

## Response Schemas

### Error Envelope Schema

Applies to every `problem+json` response referenced by FR-4 and FR-5 (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/password-policy",
  "title": "Password Does Not Meet Policy",
  "status": 422,
  "detail": "Choose a password of at least 12 characters that you have not used before.",
  "instance": "/v1/auth/password-reset/confirm"
}
```

Every `problem+json` response from this story's endpoints (`token-expired`, `token-invalid`, `password-policy`, and the `429` from FR-6) carries the same five fields: `type`, `title`, `status`, `detail`, `instance`. Error `type` slugs introduced by this story: `password-policy`. FR-4's `token-expired`/`token-invalid` slugs and FR-6's `429` follow the same envelope shape.

**Derived from:** source Error Envelope section.

## Non-Functional Requirements

- The reset token must never reach the server via a URL: it is delivered in the URL fragment, which browsers do not send to the server, so it cannot land in access logs, proxies, or `Referer` headers; the SPA reads the fragment and POSTs the token in the request body.
- A successful reset must invalidate all sessions (FR-2) — otherwise an attacker who reset the password would keep the victim's session, or vice versa.
- A policy-violating password submission (FR-5) deliberately does not consume the reset token, since consuming it would force a second email round trip for what may be a typo.
- The breached-password check (FR-5, OD-1) is a local static list/bloom filter and must never transmit the password or its full hash off-host.
- The request endpoint returns within 300 ms regardless of SMTP latency, because email dispatch is queued asynchronously; response timing must not vary with whether an email was actually queued.

**Derived from:** Non-Functional / Security Requirements section of the source; breach-check mechanism per OD-1.

## Out of Scope

- Password change by an already-authenticated user (belongs with profile management, US-1.3).
- Admin-initiated password reset — admins never set another person's password (US-3.1.2 MU-AC7).

**Derived from:** Out of Scope section of the source.

## Open Questions

None — both open questions from the prior draft (PR-AC4's token-state mapping; malformed/missing email handling) are resolved by precedent, and all 3 Open Decisions raised by `us-clarifier` are resolved above.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| PR-AC1 | "Given a registered, active account When POST /v1/auth/password-reset/request is called with that email Then respond 202 with a generic body (\"If an account exists, an email has been sent\") And a single-use reset token with a 30-minute TTL is created (SHA-256 hash stored only) And any previously issued, unconsumed reset token for that account is invalidated And an email is sent containing the token in the URL fragment, not the query string" | FR-1 |
| PR-AC2 | "Given a valid, unconsumed, unexpired reset token and a new password meeting policy When POST /v1/auth/password-reset/confirm is called with {token, new_password} Then respond 200 And the password hash is replaced (Argon2id) And the token's consumed_at is set And revoke_before:{user_id} is set to now, terminating every existing session and refresh family And a \"your password was changed\" notification is sent to the account's email And an auth_audit_log entry is written (event=password_reset_completed)" | FR-2 |
| PR-AC3 | "Given an email address that is not registered, or belongs to a deactivated account When POST /v1/auth/password-reset/request is called Then respond 202 with the same body, status and comparable timing as PR-AC1 And no email is sent, and this fact is not observable from the response" | FR-3 |
| PR-AC4 | "Given a reset token that is expired, already consumed, or matches no stored hash When POST /v1/auth/password-reset/confirm is called with it Then respond 400 with type \".../errors/token-expired\" or \".../errors/token-invalid\" And the existing password remains unchanged And the response offers the option to request a new link" | FR-4 |
| PR-AC5 | "Given a valid reset token When the new password is shorter than 12 characters, appears in the breached-password list, or equals the current password Then respond 422 with type \".../errors/password-policy\" And the errors array states which rule failed And the token is NOT consumed, so the user can retry with the same link" | FR-5 |
| PR-AC6 | "Given a reset was requested for the same account less than 60 seconds ago When POST /v1/auth/password-reset/request is called again Then respond 429 with a Retry-After header And the per-account limit is 5 requests/hour and the per-IP limit is 10 requests/hour" | FR-6 |
