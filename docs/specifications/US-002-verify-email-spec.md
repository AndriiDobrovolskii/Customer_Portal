# Specification: Verify Email

**Source:** docs/backlog/US-1.2-verify-email.md
**Story ID:** US-002
**Generated:** 2026-08-15
**Status:** Draft (Open Questions resolved 2026-08-15)

## Summary

This spec covers email verification for newly registered customers: consuming a verification token to activate an account, rejecting expired/consumed/unknown tokens, gating login for unverified accounts, a resend flow with rate limiting and anti-enumeration protection, and scheduled purge of unverified accounts.

## Background

As a newly registered customer, I want to verify ownership of the email address I registered with, so that my account is activated and I can access authenticated features.

## Functional Requirements

### FR-1: Successful Verification

Given an unverified user with a valid, unconsumed, unexpired token, when `POST /v1/auth/verify-email` is called with the raw token, the system responds `200`, sets `users.email_verified` to `true`, and marks the token's `consumed_at`. This consume operation is enforced atomically at the data layer, so at most one of two concurrent requests for the same token can succeed (see [Clarifications & Decisions](#clarifications--decisions) #1) — reuse fails per FR-3.

**Derived from:** VE-AC1

### FR-2: Expired Token Rejection

Given a token whose `expires_at` has passed, when `POST /v1/auth/verify-email` is called with that token, the system responds `400` with a `problem+json` body of type `.../errors/token-expired`, and `email_verified` remains `false`. This response is kept distinct from the invalid-token response in FR-3/FR-4, confirmed by decision (see [Clarifications & Decisions](#clarifications--decisions) #4).

**Derived from:** VE-AC2

### FR-3: Already-Consumed Token Rejection

Given a token that was already consumed, when `POST /v1/auth/verify-email` is called with that token again, the system responds `400` with a `problem+json` body of type `.../errors/token-invalid`.

**Derived from:** VE-AC3

### FR-4: Unknown or Malformed Token Rejection

Given a token string that does not match any stored hash, when `POST /v1/auth/verify-email` is called with that token, the system responds `400` with a `problem+json` body of type `.../errors/token-invalid`.

**Derived from:** VE-AC4

### FR-5: Unverified Account Cannot Log In

Given a user whose `email_verified` is `false`, when `POST /v1/auth/login` is called with correct credentials, the system responds `403` with a `problem+json` body of type `.../errors/email-not-verified`, and no session or JWT is issued.

**Derived from:** VE-AC5

### FR-6: Verified Account Logs In Normally

Given a user whose `email_verified` is `true`, when `POST /v1/auth/login` is called with correct credentials, the system responds `200` with a valid session/JWT.

**Derived from:** VE-AC6

### FR-7: Resend Rate Limit

Given a user requested a verification email less than 60 seconds ago, when `POST /v1/auth/verify-email/resend` is called for the same account, the system responds `429` with a `Retry-After` header. The account lookup for cooldown tracking is case-insensitive on email (see [Clarifications & Decisions](#clarifications--decisions) #3).

**Derived from:** VE-AC7

### FR-8: Resend Anti-Enumeration for Unregistered Email

Given an email address that is not registered, when `POST /v1/auth/verify-email/resend` is called, the system responds `200` with the same generic body (see [Clarifications & Decisions](#clarifications--decisions) #7), status code, and comparable timing as for a registered, unverified account. The email lookup is case-insensitive (see [Clarifications & Decisions](#clarifications--decisions) #3). If the submitted `email` is missing or not a syntactically valid email address, the system instead responds `HTTP 400` with a `problem+json` body of type `.../errors/invalid-request`, since this check occurs before any account lookup and therefore does not leak account-existence information (see [Clarifications & Decisions](#clarifications--decisions) #2).

**Derived from:** VE-AC8

### FR-9: Resend for Already-Verified Account

Given an email address belonging to an already-verified account, when `POST /v1/auth/verify-email/resend` is called, the system responds `200` with the same generic body as FR-8 (see [Clarifications & Decisions](#clarifications--decisions) #7) — no email is sent, but the response does not reveal this.

**Derived from:** VE-AC9

### FR-10: Unverified Account Purge

Given a user account created more than 7 days ago with `email_verified = false`, when the scheduled purge job runs, the system deletes the account and its verification tokens, and writes a record to the audit log noting an automatic purge. The 7-day window is confirmed final (see [Clarifications & Decisions](#clarifications--decisions) #5).

**Derived from:** VE-AC10

## Non-Functional Requirements

- Token comparison must use constant-time comparison (`hmac.compare_digest`) against the stored hash.
- Raw tokens must not appear in application logs or error traces.
- The token must be delivered in the request body, never in a URL query string, to avoid leaking it via access logs, browser history, or referrer headers.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- The initial registration endpoint (assumed to already issue the first token on signup).
- CAPTCHA / bot mitigation on resend (tracked separately if abuse is observed).
- Email **change** re-verification for existing accounts (tracked under the Update Profile story).

**Derived from:** Out of Scope section of the source.

## Clarifications & Decisions

The following points were left undefined by the source story (US-002) or flagged by spec review (`docs/reviews/US-002-spec-review.md`) and were resolved by explicit stakeholder decision on 2026-08-15, rather than derived directly from AC text. They supersede the prior "Open Questions" section.

1. **Concurrent token consumption** — VE-AC1/VE-AC3 don't address simultaneous requests consuming the same token (review finding). Decision: token consumption is enforced atomically at the data layer (e.g. a single conditional update that both checks `consumed_at IS NULL` and sets it), so at most one concurrent request for the same token can succeed; any other concurrent request receives the invalid-token response. See FR-1, FR-3.
2. **Malformed or missing email on resend** — VE-AC7–VE-AC9 assume a well-formed email is submitted (review finding). Decision: if the `email` field is missing or not a syntactically valid email address, the resend endpoint returns `HTTP 400` with a `problem+json` body of type `.../errors/invalid-request`, using the Error Envelope shape defined in the source story. Because this check happens before any account lookup, it does not leak account-existence information and remains compatible with the anti-enumeration requirement in VE-AC8/VE-AC9. See FR-8.
3. **Email case sensitivity on resend** — Not addressed by any AC (review finding). Decision: email lookups for the resend cooldown (VE-AC7) and existence check (VE-AC8) are case-insensitive, consistent with the case-insensitive email handling already established for registration (`docs/specifications/US-001-register-user-spec.md`, FR-2). See FR-7, FR-8.
4. **Distinct expired vs. invalid/unknown token responses** — The source's own Open Questions asked whether VE-AC2–VE-AC4 should collapse into one generic response for stricter anti-enumeration. Decision: keep the three responses distinct, exactly as VE-AC2–VE-AC4 literally specify; confirmed final, not changed. See FR-2, FR-3, FR-4.
5. **7-day unverified-account purge window** — The source's own Open Questions asked whether this needs product/compliance confirmation. Decision: 7 days is confirmed final per the source's Assumptions & Defaults table; no change. See FR-10.
6. **Hourly / per-IP resend rate limits** — The source's Assumptions & Defaults table lists "5 requests / account / hour, 10 / IP / hour" as a default, but no Acceptance Criterion covers it — only the 60-second cooldown (VE-AC7) has an AC. Decision: out of scope for this spec until a dedicated AC is written; only the 60-second cooldown (FR-7) is a build requirement for this spec. Flagged for a follow-up story/AC.
7. **Generic resend response body shape** — VE-AC8/VE-AC9 require an identical body across the unregistered/verified/unverified cases but don't specify its contents. Decision: the body is `{"message": "If this email is registered and unverified, a verification email has been sent."}`, returned unchanged across all three `HTTP 200` cases. See FR-8, FR-9.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| VE-AC1 | "Given an unverified user with a valid, unconsumed, unexpired token When POST /v1/auth/verify-email is called with the raw token Then respond 200 And users.email_verified is set to true And the token's consumed_at is set (single-use enforced; reuse fails per VE-AC3)" | FR-1 |
| VE-AC2 | "Given a token whose expires_at has passed When POST /v1/auth/verify-email is called with that token Then respond 400 with problem+json type '.../errors/token-expired' And email_verified remains false" | FR-2 |
| VE-AC3 | "Given a token that was already consumed When POST /v1/auth/verify-email is called with that token again Then respond 400 with problem+json type '.../errors/token-invalid'" | FR-3 |
| VE-AC4 | "Given a token string that does not match any stored hash When POST /v1/auth/verify-email is called with that token Then respond 400 with problem+json type '.../errors/token-invalid'" | FR-4 |
| VE-AC5 | "Given a user whose email_verified is false When POST /v1/auth/login is called with correct credentials Then respond 403 with problem+json type '.../errors/email-not-verified' And no session or JWT is issued" | FR-5 |
| VE-AC6 | "Given a user whose email_verified is true When POST /v1/auth/login is called with correct credentials Then respond 200 with a valid session/JWT" | FR-6 |
| VE-AC7 | "Given a user requested a verification email less than 60 seconds ago When POST /v1/auth/verify-email/resend is called for the same account Then respond 429 with a Retry-After header" | FR-7 |
| VE-AC8 | "Given an email address that is not registered When POST /v1/auth/verify-email/resend is called Then respond 200 with the same generic body, status code, and comparable timing as for a registered, unverified account" | FR-8 |
| VE-AC9 | "Given an email address belonging to an already-verified account When POST /v1/auth/verify-email/resend is called Then respond 200 with the same generic body as VE-AC8 (no email is sent, but the response does not reveal this)" | FR-9 |
| VE-AC10 | "Given a user account created more than 7 days ago with email_verified = false When the scheduled purge job runs Then the account and its verification tokens are deleted And a record is written to the audit log noting an automatic purge" | FR-10 |
