# Specification: Login

**Source:** docs/stories/US-2.1-login.md
**Story ID:** US-005
**Generated:** 2026-08-22
**Revised:** 2026-08-31 (incorporates resolved Open Decisions OD-1–OD-8, `docs/decisions/US-2.1-open-decisions.md`, following us-clarifier's retroactive clarification pass); further revised 2026-08-31 for OD-10 (FR-4 reactivation branch, found during PLANNING→IMPLEMENTATION handoff)
**Status:** Draft (spec-review pending re-run against this revision; prior review at `docs/reviews/specifications/US-005-spec-review.md` applies to the 2026-08-22 version)

## Summary

This spec covers the `POST /v1/auth/login` endpoint: credential verification and token issuance for the happy path, anti-enumeration behavior for wrong passwords and unknown emails, account-state gating for unverified and deactivated accounts, brute-force throttling per account and per IP, audit logging of login attempts, and request validation.

## Background

As a registered customer, I want to exchange my email and password for a session, so that I can use the authenticated parts of the portal without re-entering my credentials on every request.

## Assumption Resolutions (OD-1, OD-2)

Two of the story's Assumptions & Defaults entries were found, during clarification, to conflict with or go beyond what any Acceptance Criterion requires. Both were resolved by the user on 2026-08-31 and apply to every FR below:

- **Token signing (story Assumption #3, "RS256 with JWKS key rotation"):** superseded. LI-AC1 requires only "an access token (JWT, 15-minute TTL)" with no algorithm named. The already-shipped auth code (`app/core/config.py`, `app/core/security.py`) signs with HS256 via a shared secret, and no JWKS infrastructure exists in the codebase. This spec's login endpoint issues tokens through that existing HS256 path; building RS256 signing or a JWKS publishing endpoint is out of scope for this story. **Resolution source:** OD-1.
- **Refresh-token mobile transport (story Assumption #2, JSON body when `X-Client-Type: mobile`):** out of scope. No AC covers this branch, and the API Contract table's success shape lists only `Set-Cookie: refresh_token`. Login always sets the cookie; the mobile JSON-body variant is deferred to US-2.3 (Refresh Token), which already documents it for its own endpoint. **Resolution source:** OD-2.

## Functional Requirements

### FR-1: Successful Login

Given an active user whose email is verified, when `POST /v1/auth/login` is called with the correct email and password, the system responds `200` with a body of the shape defined in [Success Response Schema](#success-response-schema); sets a refresh token as an HttpOnly, Secure, SameSite=Strict cookie scoped to `Path=/v1/auth`; writes an `auth_audit_log` entry (`event=login_succeeded`) populated per [Audit Log Schema](#audit-log-schema); and updates `users.last_login_at`.

**Derived from:** LI-AC1; response and audit schemas per source API Contract and Data Model Notes

### FR-2: Wrong Password

Given an active, verified user, when `POST /v1/auth/login` is called with an incorrect password, the system responds `401` with a body of the shape defined in [Error Envelope Schema](#error-envelope-schema), of type `.../errors/invalid-credentials`; no token of any kind is issued; and an `auth_audit_log` entry is written (`event=login_failed`, `reason=bad_password`) populated per [Audit Log Schema](#audit-log-schema).

**Derived from:** LI-AC2; error and audit schemas per source Error Envelope and Data Model Notes

### FR-3: Unknown Email (Anti-Enumeration)

Given an email address that is not registered, when `POST /v1/auth/login` is called with that email and any password, the system responds `401` with the same body (per [Error Envelope Schema](#error-envelope-schema)), status, and comparable timing as the wrong-password case (FR-2), because a dummy Argon2id verification is performed so response time does not reveal account existence. An `auth_audit_log` entry is written (`event=login_failed`, `reason=unknown_email`) populated per [Audit Log Schema](#audit-log-schema) — the audit log is staff-only and never exposed to the caller, so recording the true reason internally does not weaken the response-level anti-enumeration guarantee.

**Derived from:** LI-AC3; audit behavior per resolved OD-3

### FR-4: Account-State Gating for Unverified and Deactivated Accounts

Given correct credentials are supplied: when the account is unverified, the system responds `403` with a body (per [Error Envelope Schema](#error-envelope-schema)) of type `.../errors/email-not-verified`, and writes an `auth_audit_log` entry (`event=login_failed`, `reason=email_not_verified`). In both branches below, credential verification runs first, so an attacker who does not already know the password only ever observes a `401` response.

When the account is deactivated and **past** its 30-day grace period (`now - users.deactivated_at > 30 days`), the system responds `403` with a body of type `.../errors/account-deactivated`, and writes an `auth_audit_log` entry (`event=login_failed`, `reason=account_deactivated`).

When the account is deactivated and **within** its 30-day grace period, the system reactivates it instead of blocking the login: `users.status` is set back to `"active"` and `users.deactivated_at` is cleared, an `account_lifecycle_audit_log` entry is written (`event=reactivated`, `actor=self`), and the request proceeds through FR-1's normal success path (`200`, access token, refresh-token cookie, `auth_audit_log` entry `event=login_succeeded`, `users.last_login_at` updated).

**Derived from:** LI-AC4 (403 branches); resolved OD-10 (reactivation branch — assigned to this story by `US-004-deactivate-account-spec.md` FR-8 / `docs/stories/US-1.4-deactivate-account.md` DA-AC8, not stated by LI-AC4's own text); audit behavior per resolved OD-4

### FR-5: Brute-Force Throttling

Given 10 failed login attempts for the same account within 15 minutes, when `POST /v1/auth/login` is called again for that account, the system responds `429` with a `Retry-After` header and a body (per [Error Envelope Schema](#error-envelope-schema)) of type `.../errors/too-many-attempts`. The same limit applies independently per source IP, at 20 attempts per 15 minutes. A successful login resets the account counter (`login_fail:account:{user_id}`); the per-IP counter (`login_fail:ip:{ip}`) is deliberately left unreset, since one IP may serve multiple accounts and a success on one account should not clear failure history that may reflect a different attacker sharing that IP. A `429` response does not write an `auth_audit_log` entry — the Valkey rate-limit counters already record the throttling state.

**Derived from:** LI-AC5; reset asymmetry per resolved OD-5; audit behavior per resolved OD-6

### FR-6: Malformed Request

Given a request body missing `password`, containing an unknown field, or containing an empty-string `password`, when `POST /v1/auth/login` is called, the system responds `422` with a body (per [Error Envelope Schema](#error-envelope-schema)) of type `.../errors/validation-failed`; the errors array names the offending field(s); no login attempt is recorded against the rate-limit counter; and no `auth_audit_log` entry is written, since the request never reaches credential verification. An empty-string `password` is rejected at request-schema validation, before credential verification — it is not treated as a wrong-password attempt.

**Derived from:** LI-AC6; audit behavior per resolved OD-6; empty-string-password handling per resolved OD-8 (docs/decisions/US-2.1-open-decisions.md)

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

Every response of this shape carries all five fields: `type`, `title`, `status`, `detail`, `instance`. The `422` validation-failed response additionally includes an `errors` array naming the offending field(s), per LI-AC6.

- `type` for FR-2 (`invalid-credentials`), FR-3 (`invalid-credentials`, reused per LI-AC3's "same body" requirement), and FR-5 (`too-many-attempts`) is defined by this story's Error `type` slugs. `type` for FR-4's `email-not-verified` and `account-deactivated` is defined by US-1.2 and US-1.4 respectively; `type` for FR-6's `validation-failed` is shared convention — none of these three is introduced by this story.

**Derived from:** source Error Envelope section.

### Audit Log Schema

Applies to every `auth_audit_log` entry referenced by FR-1, FR-2, FR-3, and FR-4. Every entry, regardless of `event`/`reason`, is populated with the full field set below:

| Field | Description |
|---|---|
| `event` | `login_succeeded` or `login_failed` |
| `reason` | Present only when `event=login_failed`: `bad_password` (FR-2), `unknown_email` (FR-3), `email_not_verified` or `account_deactivated` (FR-4) |
| `actor_id` | The matched user's id when one exists (FR-2, FR-4, FR-1); absent/null for FR-3, since no account matched |
| `ip` | Source IP of the request |
| `user_agent` | Request's `User-Agent` header |
| `request_id` | Correlation id for the request |
| `occurred_at` | Timestamp of the attempt |

FR-5 (`429`) and FR-6 (`422`) do not write an `auth_audit_log` entry — see those FRs for the rationale.

**Derived from:** source Data Model Notes (`auth_audit_log` field list); event/reason vocabulary and per-FR applicability per resolved OD-3, OD-4, OD-6.

## Non-Functional Requirements

- The response MUST NOT distinguish "no such user" from "wrong password" in body, status, or timing.
- Passwords MUST NOT appear in logs, traces, or APM payloads — a scrubbing rule is required for `password` / `current_password` keys.
- Argon2id verification MUST run in a thread pool so it does not block the event loop.
- The login endpoint is CSRF-exempt, but every cookie-authenticated state-changing endpoint requires a CSRF token.
- **Performance:** p95 response time ≤ 400 ms, including the deliberate ≈100 ms hashing cost.
- Access tokens are signed with the project's existing HS256 shared-secret scheme (`app/core/config.py`'s `jwt_algorithm`); this story does not introduce RS256 signing or a JWKS endpoint. Per resolved OD-1.

**Derived from:** Non-Functional / Security Requirements section of the source; token-signing note per resolved OD-1.

## Out of Scope

- Refresh and rotation mechanics (US-2.3)
- Session termination (US-2.2)
- MFA challenge branch (US-2.5 — this story's success path is what US-2.5 later intercepts)
- Registration and email verification (US-1.1, US-1.2)
- RS256/JWKS token signing and key rotation (per resolved OD-1)
- Mobile JSON-body refresh-token transport (`X-Client-Type: mobile`) — deferred to US-2.3 (per resolved OD-2)

**Derived from:** Out of Scope section of the source; two additional exclusions per resolved OD-1 and OD-2.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| LI-AC1 | "Given an active user whose email is verified When POST /v1/auth/login is called with the correct email and password Then respond 200 with an access token (JWT, 15-minute TTL) in the body And set a refresh token as an HttpOnly, Secure, SameSite=Strict cookie (Path=/v1/auth) And an auth_audit_log entry is written (event=login_succeeded) And users.last_login_at is updated" | FR-1 |
| LI-AC2 | "Given an active, verified user When POST /v1/auth/login is called with an incorrect password Then respond 401 with problem+json type \".../errors/invalid-credentials\" And no token of any kind is issued And an auth_audit_log entry is written (event=login_failed, reason=bad_password)" | FR-2 |
| LI-AC3 | "Given an email address that is not registered When POST /v1/auth/login is called with that email and any password Then respond 401 with the same body, status and comparable timing as LI-AC2 Because a dummy Argon2id verification is performed so response time does not reveal account existence" | FR-3 |
| LI-AC4 | "Given correct credentials are supplied When the account is unverified Then respond 403 with type \".../errors/email-not-verified\" # per US-1.2 VE-AC5 When the account is deactivated Then respond 403 with type \".../errors/account-deactivated\" # per US-1.4 DA-AC6 And in both cases credential verification runs first, so an attacker without the password only ever sees 401" | FR-4 (403 branches only — the deactivated case is now qualified by resolved OD-10's grace-period distinction; the reactivation branch is not covered by this AC's text at all, only by OD-10 citing DA-AC8) |
| LI-AC5 | "Given 10 failed login attempts for the same account within 15 minutes When POST /v1/auth/login is called again for that account Then respond 429 with a Retry-After header and type \".../errors/too-many-attempts\" And the same limit applies independently per source IP (20 attempts / 15 minutes) And a successful login resets the account counter" | FR-5 |
| LI-AC6 | "Given a request body missing \"password\", or containing an unknown field When POST /v1/auth/login is called Then respond 422 with type \".../errors/validation-failed\" And the errors array names the offending field(s) And no login attempt is recorded against the rate-limit counter" | FR-6 |
