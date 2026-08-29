# Specification: Login

**Source:** docs/stories/US-2.1-login.md
**Story ID:** US-005
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/specifications/US-005-spec-review.md)

## Summary

This spec covers the `POST /v1/auth/login` endpoint: credential verification and token issuance for the happy path, anti-enumeration behavior for wrong passwords and unknown emails, account-state gating for unverified and deactivated accounts, brute-force throttling per account and per IP, audit logging of login attempts, and request validation.

## Background

As a registered customer, I want to exchange my email and password for a session, so that I can use the authenticated parts of the portal without re-entering my credentials on every request.

## Functional Requirements

### FR-1: Successful Login

Given an active user whose email is verified, when `POST /v1/auth/login` is called with the correct email and password, the system responds `200` with a body of the shape defined in [Success Response Schema](#success-response-schema); sets a refresh token as an HttpOnly, Secure, SameSite=Strict cookie scoped to `Path=/v1/auth`; writes an `auth_audit_log` entry (`event=login_succeeded`) populated per [Audit Log Schema](#audit-log-schema); and updates `users.last_login_at`.

**Derived from:** LI-AC1; response and audit schemas per source API Contract and Data Model Notes

### FR-2: Wrong Password

Given an active, verified user, when `POST /v1/auth/login` is called with an incorrect password, the system responds `401` with a `problem+json` body of the shape defined in [Error Envelope Schema](#error-envelope-schema), of type `.../errors/invalid-credentials`; no token of any kind is issued; and an `auth_audit_log` entry is written (`event=login_failed`, `reason=bad_password`) populated per [Audit Log Schema](#audit-log-schema).

**Derived from:** LI-AC2; error and audit schemas per source Error Envelope and Data Model Notes

### FR-3: Unknown Email (Anti-Enumeration)

Given an email address that is not registered, when `POST /v1/auth/login` is called with that email and any password, the system responds `401` with the same body (per [Error Envelope Schema](#error-envelope-schema)), status, and comparable timing as the wrong-password case (FR-2), because a dummy Argon2id verification is performed so response time does not reveal account existence.

**Derived from:** LI-AC3

### FR-4: Account-State Gating for Unverified and Deactivated Accounts

Given correct credentials are supplied: when the account is unverified, the system responds `403` with a `problem+json` body (per [Error Envelope Schema](#error-envelope-schema)) of type `.../errors/email-not-verified`; when the account is deactivated, the system responds `403` with a `problem+json` body of type `.../errors/account-deactivated`. In both cases, credential verification runs first, so an attacker who does not already know the password only ever observes a `401` response.

**Derived from:** LI-AC4

### FR-5: Brute-Force Throttling

Given 10 failed login attempts for the same account within 15 minutes, when `POST /v1/auth/login` is called again for that account, the system responds `429` with a `Retry-After` header and a `problem+json` body (per [Error Envelope Schema](#error-envelope-schema)) of type `.../errors/too-many-attempts`. The same limit applies independently per source IP, at 20 attempts per 15 minutes. A successful login resets the account counter.

**Derived from:** LI-AC5

### FR-6: Malformed Request

Given a request body missing `password`, or containing an unknown field, when `POST /v1/auth/login` is called, the system responds `422` with a `problem+json` body (per [Error Envelope Schema](#error-envelope-schema)) of type `.../errors/validation-failed`; the errors array names the offending field(s); and no login attempt is recorded against the rate-limit counter.

**Derived from:** LI-AC6

## Response Schemas

### Success Response Schema

Applies to the `200` response referenced by FR-1:

```json
{
  "access_token": "string (JWT)",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Derived from:** source API Contract table (`/v1/auth/login` success shape).

### Error Envelope Schema

Applies to all `problem+json` responses referenced by FR-2–FR-6 (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/invalid-credentials",
  "title": "Invalid Credentials",
  "status": 401,
  "detail": "The email or password is incorrect.",
  "instance": "/v1/auth/login"
}
```

- `type` for FR-2 (`invalid-credentials`) and FR-5 (`too-many-attempts`) is defined by this story's Error `type` slugs. `type` for FR-4's `email-not-verified` and `account-deactivated` is defined by US-1.2 and US-1.4 respectively; `type` for FR-6's `validation-failed` is shared convention — none of these three is introduced by this story.
- The `422` validation-failed response additionally includes an `errors` array naming the offending field(s), per LI-AC6.

**Derived from:** source Error Envelope section.

### Audit Log Schema

Applies to every `auth_audit_log` entry referenced by FR-1 and FR-2:

| Field | Description |
|---|---|
| `event` | `login_succeeded` or `login_failed` |
| `reason` | e.g. `bad_password` for `login_failed` |
| `actor_id` | |
| `ip` | |
| `user_agent` | |
| `request_id` | |
| `occurred_at` | |

**Derived from:** source Data Model Notes (`auth_audit_log` field list). Whether the unknown-email (FR-3), account-state-gating (FR-4), throttled (FR-5), and malformed-request (FR-6) cases also write an `auth_audit_log` entry is not stated by the source; see [Open Questions](#open-questions).

## Non-Functional Requirements

- The response MUST NOT distinguish "no such user" from "wrong password" in body, status, or timing.
- Passwords MUST NOT appear in logs, traces, or APM payloads — a scrubbing rule is required for `password` / `current_password` keys.
- Argon2id verification MUST run in a thread pool so it does not block the event loop.
- The login endpoint is CSRF-exempt, but every cookie-authenticated state-changing endpoint requires a CSRF token.
- **Performance:** p95 response time ≤ 400 ms, including the deliberate ≈100 ms hashing cost.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Refresh and rotation mechanics (US-2.3)
- Session termination (US-2.2)
- MFA challenge branch (US-2.5 — this story's success path is what US-2.5 later intercepts)
- Registration and email verification (US-1.1, US-1.2)

**Derived from:** Out of Scope section of the source.

## Open Questions

The source's own Open Questions section states "None. Transport selection is settled by Decision #1 in the epic-level document." The items below are gaps and inconsistencies identified while drafting the Functional Requirements against the AC text (LI-AC1–LI-AC6) and the surrounding source sections; they were not raised by the source itself.

- Assumption #2 in the Assumptions & Defaults table states the refresh token is delivered as a JSON body field "when `X-Client-Type: mobile`," in addition to the cookie transport — but no AC covers this branch, and the API Contract table (line 36) lists only `Set-Cookie: refresh_token` as the success response shape. Does the mobile JSON-body transport belong in this story, and if so, what is its expected response shape and which AC governs it?
- Assumption #3 states access tokens use "RS256 with JWKS key rotation," but LI-AC1 only specifies "access token (JWT, 15-minute TTL)" without stating a signing algorithm or key-rotation mechanism. Is RS256/JWKS a hard requirement of this story's implementation, or informative context with no AC coverage?
- Does the unknown-email case (LI-AC3) write an `auth_audit_log` entry, and if so, what `reason` value should be recorded? LI-AC2 specifies `reason=bad_password` for the wrong-password case, but LI-AC3 does not specify an equivalent value for the anti-enumeration path.
- Does a blocked-login response under LI-AC4 (unverified or deactivated account) write an `auth_audit_log` entry, and if so with what `reason` value? The Data Model Notes define `auth_audit_log` events as `login_succeeded` / `login_failed`, but LI-AC4 does not state whether the `403` responses are logged.
- LI-AC5 states that "a successful login resets the account counter" but says nothing about the per-IP counter — please confirm whether the per-IP counter is deliberately left unreset on a successful login, or should also be reset.
- Are `429` (throttled, LI-AC5) or `422` (validation-failed, LI-AC6) responses recorded in `auth_audit_log`? Neither AC states this, and the Data Model Notes' event enum (`login_succeeded`, `login_failed`) has no obvious matching value for either case.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| LI-AC1 | "Given an active user whose email is verified When POST /v1/auth/login is called with the correct email and password Then respond 200 with an access token (JWT, 15-minute TTL) in the body And set a refresh token as an HttpOnly, Secure, SameSite=Strict cookie (Path=/v1/auth) And an auth_audit_log entry is written (event=login_succeeded) And users.last_login_at is updated" | FR-1 |
| LI-AC2 | "Given an active, verified user When POST /v1/auth/login is called with an incorrect password Then respond 401 with problem+json type \".../errors/invalid-credentials\" And no token of any kind is issued And an auth_audit_log entry is written (event=login_failed, reason=bad_password)" | FR-2 |
| LI-AC3 | "Given an email address that is not registered When POST /v1/auth/login is called with that email and any password Then respond 401 with the same body, status and comparable timing as LI-AC2 Because a dummy Argon2id verification is performed so response time does not reveal account existence" | FR-3 |
| LI-AC4 | "Given correct credentials are supplied When the account is unverified Then respond 403 with type \".../errors/email-not-verified\" # per US-1.2 VE-AC5 When the account is deactivated Then respond 403 with type \".../errors/account-deactivated\" # per US-1.4 DA-AC6 And in both cases credential verification runs first, so an attacker without the password only ever sees 401" | FR-4 |
| LI-AC5 | "Given 10 failed login attempts for the same account within 15 minutes When POST /v1/auth/login is called again for that account Then respond 429 with a Retry-After header and type \".../errors/too-many-attempts\" And the same limit applies independently per source IP (20 attempts / 15 minutes) And a successful login resets the account counter" | FR-5 |
| LI-AC6 | "Given a request body missing \"password\", or containing an unknown field When POST /v1/auth/login is called Then respond 422 with type \".../errors/validation-failed\" And the errors array names the offending field(s) And no login attempt is recorded against the rate-limit counter" | FR-6 |
