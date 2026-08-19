# Specification: Update Profile

**Source:** docs/backlog/US-1.3-update-profile.md
**Story ID:** US-003
**Generated:** 2026-08-15
**Status:** Draft (Open Questions resolved 2026-08-15)

## Summary

This spec covers authenticated customers updating their own profile: partial updates to non-sensitive fields with optimistic concurrency control (ETag/If-Match), strict field validation and whitelisting, authorization scoping to the requesting user, and a two-step confirmed email-change flow with re-authentication and session revocation.

## Background

As an authenticated customer, I want to update my profile information, so that my account details stay accurate and current.

## Functional Requirements

### FR-1: Successful Partial Update

Given an authenticated user and a current ETag for their profile, when `PATCH /v1/profile` is called with `If-Match: <etag>` and a body such as `{"display_name": "New Name"}`, the system responds `200` with the updated resource and a new ETag, and writes a `profile_audit_log` entry with the old/new value, actor, and timestamp. When a single request changes multiple fields, one `profile_audit_log` row is written per changed field (see [Clarifications & Decisions](#clarifications--decisions) #5). A request combining a whitelisted field with `email` is handled per FR-10 (see [Clarifications & Decisions](#clarifications--decisions) #4).

**Derived from:** UP-AC1

### FR-2: Missing If-Match Header Rejection

Given an authenticated user, when `PATCH /v1/profile` is called without an `If-Match` header, the system responds `400` with a `problem+json` body of type `.../errors/precondition-required`, and no fields are changed.

**Derived from:** UP-AC2

### FR-3: Stale If-Match Rejection

Given the profile resource changed since the client last read its ETag, when `PATCH /v1/profile` is called with the stale `If-Match` value, the system responds `412`, and no fields are changed.

**Derived from:** UP-AC3

### FR-4: Field-Level Validation Failure

Given an authenticated user and a valid ETag, when `PATCH /v1/profile` is called with an invalid field value (e.g. a `locale` not in the supported list), the system responds `422` with a `problem+json` body of type `.../errors/validation-failed`, whose `errors` array names the offending field(s).

**Derived from:** UP-AC4

### FR-5: Immutable Field Rejection

When `PATCH /v1/profile` is called with `{"role": "admin"}` or any other immutable field, the system responds `422` with a `problem+json` body of type `.../errors/immutable-field`, and no fields are changed.

**Derived from:** UP-AC5

### FR-6: Unknown/Extra Field Rejection

When `PATCH /v1/profile` is called with a field not in the editable whitelist (e.g. `{"is_super_user": true}`), the system responds `422` with a `problem+json` body of type `.../errors/validation-failed`, and no fields are changed. `current_password` is accepted only when submitted together with `email`; if `current_password` is present without `email` in the same request, it is treated as an unknown field under this rule (see [Clarifications & Decisions](#clarifications--decisions) #3).

**Derived from:** UP-AC6

### FR-7: Cannot Update Another User's Profile

Given user A is authenticated, when `PATCH /v1/profile` is scoped/targeted at user B's resource (e.g. via a mismatched path or resource id), the system responds `403`.

**Derived from:** UP-AC7

### FR-8: Unauthenticated Request Rejection

When `PATCH /v1/profile` is called without a valid session/JWT, the system responds `401`.

**Derived from:** UP-AC8

### FR-9: Email Change Requires Correct Current Password

Given an authenticated user and a valid ETag, when `PATCH /v1/profile` is called with `{"email": "new@example.com"}` and a missing or incorrect `current_password`, the system responds `401` with a `problem+json` body of type `.../errors/reauthentication-required`, and the primary email and `pending_email` remain unchanged. Password verification happens before the duplicate-email check in FR-10 (see [Clarifications & Decisions](#clarifications--decisions) #1).

**Derived from:** UP-AC9

### FR-10: Email Change Initiated Successfully

Given an authenticated user, a valid ETag, and the correct `current_password`, when `PATCH /v1/profile` is called with `{"email": "new@example.com", "current_password": "..."}`, the system responds `202`; `users.email` remains unchanged while `users.pending_email` is set to `"new@example.com"`; a confirmation link is sent to the new address; a notification (not a confirmation link) is sent to the current, still-active email address; and a `profile_audit_log` entry records the change request. If the requested email is already registered to another account (case-insensitive), the system instead responds `409 Conflict` and `pending_email` is not set (see [Clarifications & Decisions](#clarifications--decisions) #1). If the request body also includes whitelisted non-sensitive fields (e.g. `display_name`) alongside `email`, both the non-sensitive field changes and the email-change initiation are committed atomically in one transaction, and the response is `202` (see [Clarifications & Decisions](#clarifications--decisions) #4).

**Derived from:** UP-AC10

### FR-11: Confirming a Pending Email Change

Given a valid, unconsumed, unexpired `email_change_token`, when `POST /v1/profile/confirm-email-change` is called with the raw token, the system responds `200`; `users.email` is set to the value of `pending_email` and `pending_email` is cleared; all active sessions/tokens for this user except the confirming one are revoked (requiring re-login elsewhere); and a `profile_audit_log` entry records the completed change. This consume operation is enforced atomically at the data layer, so at most one of two concurrent requests for the same token can succeed (see [Clarifications & Decisions](#clarifications--decisions) #2) — the other fails per FR-12.

**Derived from:** UP-AC11

### FR-12: Expired or Invalid Email-Change Token Rejection

Given an expired, already-consumed, or unknown token, when `POST /v1/profile/confirm-email-change` is called with that token, the system responds `400` with a `problem+json` body of type `.../errors/token-expired` or `.../errors/token-invalid` as appropriate, and `users.email` and `pending_email` remain unchanged.

**Derived from:** UP-AC12

## Non-Functional Requirements

- The editable-field whitelist must be enforced server-side via the Pydantic model (`extra="forbid"`), not by client-side omission alone.
- `pending_email` must not be exposed to any party other than the account owner until confirmed.
- Session revocation on FR-11 must cover both access and refresh tokens (the source notes this reuses the revocation mechanism from the Deactivate Account story).

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- `GET /v1/profile` (assumed to already exist).
- Avatar file upload/storage handling (only the `avatar_url` string field is in scope here).
- The phone number field (not present in the current schema; the same sensitive-field pattern applies if/when added).
- Admin-initiated profile edits (separate story; the field whitelist and audit requirements still apply).

**Derived from:** Out of Scope section of the source.

## Clarifications & Decisions

The following points were left undefined by the source story (US-003) or flagged by spec review (`docs/reviews/US-003-spec-review.md`) and were resolved by explicit stakeholder decision on 2026-08-15, rather than derived directly from AC text. They supersede the prior "Open Questions" section.

1. **Duplicate new-email address** — UP-AC9/UP-AC10 don't address a requested new email already registered to another account (review finding). Decision: the check is case-insensitive, consistent with the duplicate-email handling established for registration (`docs/specifications/US-001-register-user-spec.md`, FR-2), runs after `current_password` verification succeeds, and returns `409 Conflict` without setting `pending_email` on a match. See FR-9, FR-10.
2. **Concurrent email-change token consumption** — UP-AC11/UP-AC12 don't address simultaneous confirm requests for the same token (review finding). Decision: consumption is enforced atomically at the data layer, mirroring the equivalent decision for Verify Email (`docs/specifications/US-002-verify-email-spec.md`, Clarification #1). See FR-11.
3. **`current_password` field whitelist status** — UP-AC6 doesn't state whether `current_password` counts as a whitelisted field (review finding). Decision: `current_password` is accepted only when submitted alongside `email`; submitted without `email`, it is rejected as an unknown field under the same rule as UP-AC6. See FR-6.
4. **Combined non-sensitive update + email change in one request** — Not addressed whether a single PATCH containing both a whitelisted field and `email` is permitted (review finding). Decision: permitted; both changes are committed atomically in one transaction, and the response is `202` (since the request includes a pending email change). See FR-1, FR-10.
5. **Audit log entry granularity** — UP-AC1's example only changes one field, leaving multi-field granularity undefined (review finding). Decision: one `profile_audit_log` row is written per changed field, matching the source's Data Model Notes schema (`field`, `old_value`, `new_value` per row). See FR-1.
6. **Editable field list** — The source's own Open Questions flagged `display_name`, `locale`, `timezone`, `avatar_url` as a placeholder pending confirmation against the actual `users` table. Decision: confirmed final as listed; no change.
7. **Cross-user check status code (403 vs. 404)** — The source's own Open Questions asked whether UP-AC7 should return `403` or `404`. Decision: `403` confirmed, per the source's stated assumption that the endpoint is self-scoped with no target id in the path. See FR-7.
8. **MFA substitution for dual-email-confirmation** — The source's own Open Questions raised whether MFA could substitute for the two-step email-change flow. Decision: out of scope for this spec — no MFA support currently exists; flagged for a follow-up story if/when MFA is implemented.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| UP-AC1 | "Given an authenticated user and a current ETag for their profile When PATCH /v1/profile is called with If-Match: <etag> and {\"display_name\": \"New Name\"} Then respond 200 with the updated resource and a new ETag And a profile_audit_log entry is written with old/new value, actor, and timestamp" | FR-1 |
| UP-AC2 | "Given an authenticated user When PATCH /v1/profile is called without an If-Match header Then respond 400 with problem+json type '.../errors/precondition-required' And no fields are changed" | FR-2 |
| UP-AC3 | "Given the profile resource changed since the client last read its ETag When PATCH /v1/profile is called with the stale If-Match value Then respond 412 And no fields are changed" | FR-3 |
| UP-AC4 | "Given an authenticated user and a valid ETag When PATCH /v1/profile is called with an invalid value (e.g. locale not in the supported list) Then respond 422 with problem+json type '.../errors/validation-failed' And the errors array names the offending field(s)" | FR-4 |
| UP-AC5 | "When PATCH /v1/profile is called with {\"role\": \"admin\"} or any other immutable field Then respond 422 with problem+json type '.../errors/immutable-field' And no fields are changed" | FR-5 |
| UP-AC6 | "When PATCH /v1/profile is called with a field not in the editable whitelist (e.g. {\"is_super_user\": true}) Then respond 422 with problem+json type '.../errors/validation-failed' And no fields are changed" | FR-6 |
| UP-AC7 | "Given user A is authenticated When PATCH /v1/profile is scoped/targeted at user B's resource (e.g. via a mismatched path or resource id) Then respond 403" | FR-7 |
| UP-AC8 | "When PATCH /v1/profile is called without a valid session/JWT Then respond 401" | FR-8 |
| UP-AC9 | "Given an authenticated user and a valid ETag When PATCH /v1/profile is called with {\"email\": \"new@example.com\"} and a missing or incorrect current_password Then respond 401 with problem+json type '.../errors/reauthentication-required' And the primary email and pending_email remain unchanged" | FR-9 |
| UP-AC10 | "Given an authenticated user, a valid ETag, and the correct current_password When PATCH /v1/profile is called with {\"email\": \"new@example.com\", \"current_password\": \"...\"} Then respond 202 And users.email remains unchanged; users.pending_email is set to \"new@example.com\" And a confirmation link is sent to new@example.com And a notification (not a confirmation link) is sent to the current, still-active email address And a profile_audit_log entry records the change request" | FR-10 |
| UP-AC11 | "Given a valid, unconsumed, unexpired email_change_token When POST /v1/profile/confirm-email-change is called with the raw token Then respond 200 And users.email is set to the value of pending_email; pending_email is cleared And all active sessions/tokens for this user except the confirming one are revoked (requires re-login elsewhere) And a profile_audit_log entry records the completed change" | FR-11 |
| UP-AC12 | "Given an expired, already-consumed, or unknown token When POST /v1/profile/confirm-email-change is called with that token Then respond 400 with problem+json type '.../errors/token-expired' or '.../errors/token-invalid' as appropriate And users.email and pending_email remain unchanged" | FR-12 |
