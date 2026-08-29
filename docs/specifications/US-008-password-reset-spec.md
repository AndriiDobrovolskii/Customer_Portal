# Specification: Password Reset

**Source:** docs/stories/US-2.4-password-reset.md
**Story ID:** US-008
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/specifications/US-008-spec-review.md)

## Summary

This spec covers self-service password reset: token issuance and email delivery via `POST /v1/auth/password-reset/request`, token consumption and password change via `POST /v1/auth/password-reset/confirm`, anti-enumeration for unknown or deactivated accounts, rejection of expired/consumed/invalid tokens and policy-violating passwords, full session and refresh-token revocation on a successful reset, and per-account and per-IP request throttling.

## Background

As a user who has forgotten their password, I want to set a new one via a link emailed to my registered address, so that I can regain access to my account without contacting support.

## Functional Requirements

### FR-1: Requesting a Reset

Given a registered, active account, when `POST /v1/auth/password-reset/request` is called with that account's email, the system responds `202` with a generic body ("If an account exists, an email has been sent"). A single-use reset token with a 30-minute TTL is created, generated as 32 bytes via `secrets.token_urlsafe(32)`, with only its SHA-256 hash stored (token record: `token_hash`, `user_id`, `issued_at`, `expires_at`, `consumed_at` — the same shape as `email_verification_tokens` in US-1.2). Any previously issued, unconsumed reset token for that account is invalidated. An email is sent containing the token in the URL fragment, not the query string.

**Derived from:** PR-AC1; token generation method per source Assumptions & Defaults table

### FR-2: Completing the Reset

Given a valid, unconsumed, unexpired reset token and a new password meeting policy, when `POST /v1/auth/password-reset/confirm` is called with `{token, new_password}`, the system responds `200`; replaces the password hash (Argon2id); sets the token's `consumed_at`; sets `revoke_before:{user_id}` to now, terminating every existing session and refresh family; sends a "your password was changed" notification to the account's email; and writes an `auth_audit_log` entry (`event=password_reset_completed`).

**Derived from:** PR-AC2

### FR-3: Unknown or Deactivated Account Does Not Leak Existence

Given an email address that is not registered, or that belongs to a deactivated account, when `POST /v1/auth/password-reset/request` is called, the system responds `202` with the same body, status, and comparable timing as a request for a registered, active account (FR-1). No email is sent, and this fact is not observable from the response.

**Derived from:** PR-AC3

### FR-4: Expired, Consumed, or Unknown Token Rejected

Given a reset token that is expired, already consumed, or matches no stored hash, when `POST /v1/auth/password-reset/confirm` is called with it, the system responds `400` with a `problem+json` body of type `.../errors/token-expired` or `.../errors/token-invalid`. The existing password remains unchanged, and the response offers the option to request a new link.

**Derived from:** PR-AC4

### FR-5: Weak or Reused Password Rejected Without Consuming the Token

Given a valid reset token, when the submitted new password is shorter than 12 characters, appears in the breached-password list, or equals the current password, the system responds `422` with a `problem+json` body of type `.../errors/password-policy`, and the errors array states which rule failed. The token is NOT consumed by this rejection, so the user can retry with the same link.

**Derived from:** PR-AC5

### FR-6: Request Flooding Is Throttled

Given a reset was requested for the same account less than 60 seconds ago, when `POST /v1/auth/password-reset/request` is called again, the system responds `429` with a `Retry-After` header. The per-account limit is 5 requests/hour and the per-IP limit is 10 requests/hour.

**Derived from:** PR-AC6

## Response Schemas

### Error Envelope Schema

Applies to the `problem+json` responses referenced by FR-4 and FR-5 (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/password-policy",
  "title": "Password Does Not Meet Policy",
  "status": 422,
  "detail": "Choose a password of at least 12 characters that you have not used before.",
  "instance": "/v1/auth/password-reset/confirm"
}
```

Error `type` slugs introduced by this story: `password-policy`. FR-4's `token-expired`/`token-invalid` slugs follow the same envelope shape.

**Derived from:** source Error Envelope section.

## Non-Functional Requirements

- The reset token must never reach the server via a URL: it is delivered in the URL fragment, which browsers do not send to the server, so it cannot land in access logs, proxies, or `Referer` headers; the SPA reads the fragment and POSTs the token in the request body.
- A successful reset must invalidate all sessions (FR-2) — otherwise an attacker who reset the password would keep the victim's session, or vice versa.
- A policy-violating password submission (FR-5) deliberately does not consume the reset token, since consuming it would force a second email round trip for what may be a typo.
- The breached-password check must use k-anonymity (a 5-character SHA-1 prefix) or a local bloom filter, and must never transmit the password or its full hash.
- The request endpoint returns within 300 ms regardless of SMTP latency, because email dispatch is queued asynchronously; response timing must not vary with whether an email was actually queued.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Password change by an already-authenticated user (belongs with profile management, US-1.3).
- Admin-initiated password reset — admins never set another person's password (US-3.1.2 MU-AC7).

**Derived from:** Out of Scope section of the source.

## Open Questions

- PR-AC4 allows a `400` response of either `.../errors/token-expired` or `.../errors/token-invalid` for three distinct token states (expired, already consumed, or matching no stored hash), but the source does not specify which state maps to which error type. Which of the three conditions should return `token-expired`, and which should return `token-invalid`?
- The API Contract defines the request body for `POST /v1/auth/password-reset/request` as `{"email": str}`, but neither the source's ACs nor this spec state what happens when the field is missing, empty, or not a validly formed email address. Is this a `400` handled by this story, or basic field validation assumed to be handled elsewhere?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| PR-AC1 | "Given a registered, active account When POST /v1/auth/password-reset/request is called with that email Then respond 202 with a generic body (\"If an account exists, an email has been sent\") And a single-use reset token with a 30-minute TTL is created (SHA-256 hash stored only) And any previously issued, unconsumed reset token for that account is invalidated And an email is sent containing the token in the URL fragment, not the query string" | FR-1 |
| PR-AC2 | "Given a valid, unconsumed, unexpired reset token and a new password meeting policy When POST /v1/auth/password-reset/confirm is called with {token, new_password} Then respond 200 And the password hash is replaced (Argon2id) And the token's consumed_at is set And revoke_before:{user_id} is set to now, terminating every existing session and refresh family And a \"your password was changed\" notification is sent to the account's email And an auth_audit_log entry is written (event=password_reset_completed)" | FR-2 |
| PR-AC3 | "Given an email address that is not registered, or belongs to a deactivated account When POST /v1/auth/password-reset/request is called Then respond 202 with the same body, status and comparable timing as PR-AC1 And no email is sent, and this fact is not observable from the response" | FR-3 |
| PR-AC4 | "Given a reset token that is expired, already consumed, or matches no stored hash When POST /v1/auth/password-reset/confirm is called with it Then respond 400 with type \".../errors/token-expired\" or \".../errors/token-invalid\" And the existing password remains unchanged And the response offers the option to request a new link" | FR-4, Open Question |
| PR-AC5 | "Given a valid reset token When the new password is shorter than 12 characters, appears in the breached-password list, or equals the current password Then respond 422 with type \".../errors/password-policy\" And the errors array states which rule failed And the token is NOT consumed, so the user can retry with the same link" | FR-5 |
| PR-AC6 | "Given a reset was requested for the same account less than 60 seconds ago When POST /v1/auth/password-reset/request is called again Then respond 429 with a Retry-After header And the per-account limit is 5 requests/hour and the per-IP limit is 10 requests/hour" | FR-6 |
