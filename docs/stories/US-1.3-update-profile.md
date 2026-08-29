# Epic 1 — Users: Update Profile

**Story ID:** US-1.2
**Project:** Customer Portal

## User Story
As an authenticated customer,
I want to update my profile information,
So that my account details stay accurate and current.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Editable fields | `display_name`, `locale`, `timezone`, `avatar_url` (placeholder set) | Confirm against actual `users` schema |
| 2 | Immutable fields | `id`, `created_at`, `role`, `email_verified` | Identity/system fields must never be client-writable |
| 3 | Sensitive field requiring re-verification | `email` | Pattern is extensible to any future sensitive field (e.g. phone) |
| 4 | Concurrency control | `If-Match` header with resource ETag is **required** on every PATCH | Prevents lost-update races |
| 5 | Schema strictness | Unknown/extra fields in the request body are rejected, not silently ignored (Pydantic v2 `model_config extra="forbid"`) | Makes violations impossible rather than merely prohibited |
| 6 | Sensitive-change authentication | Current password required in the request body when changing email | Prevents account-takeover via a hijacked session |

## In Scope
- `PATCH /v1/profile` — partial update of non-sensitive fields, and initiation of an email change
- `POST /v1/profile/confirm-email-change` — consume the confirmation token sent to the new address
- Audit logging of every accepted profile change

## Out of Scope
- `GET /v1/profile` (assumed to already exist)
- Avatar file upload/storage handling (only the `avatar_url` string field is in scope here)
- Phone number field (not present in the current schema; apply the same sensitive-field pattern if/when added)
- Admin-initiated profile edits (separate story; the field whitelist and audit requirements below still apply)

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| PATCH | `/v1/profile` | Required (self) | Partial fields; `If-Match` header required; `current_password` required if `email` is present | 200 (non-sensitive fields) with new ETag, or 202 (email change initiated) |
| POST | `/v1/profile/confirm-email-change` | None (token is the credential) | `{"token": str}` | 200, primary email updated |

## Data Model Notes
- `users.pending_email: str | null`
- `email_change_tokens`: `token_hash` (SHA-256, unique), `user_id`, `issued_at`, `expires_at`, `consumed_at` (nullable) — same design as `email_verification_tokens` in US-1.1
- `profile_audit_log`: append-only, insert-only at the storage layer (no UPDATE/DELETE grants); records `actor_id`, `field`, `old_value`, `new_value`, `request_id`, `timestamp`

## Acceptance Criteria

### Happy path
**UP-AC1 — Successful partial update**
```gherkin
Given an authenticated user and a current ETag for their profile
When PATCH /v1/profile is called with If-Match: <etag> and {"display_name": "New Name"}
Then respond 200 with the updated resource and a new ETag
And a profile_audit_log entry is written with old/new value, actor, and timestamp
```

### Concurrency
**UP-AC2 — Missing If-Match header**
```gherkin
Given an authenticated user
When PATCH /v1/profile is called without an If-Match header
Then respond 400 with problem+json type ".../errors/precondition-required"
And no fields are changed
```

**UP-AC3 — Stale If-Match (lost-update prevention)**
```gherkin
Given the profile resource changed since the client last read its ETag
When PATCH /v1/profile is called with the stale If-Match value
Then respond 412
And no fields are changed
```

### Validation / schema strictness
**UP-AC4 — Field-level validation failure**
```gherkin
Given an authenticated user and a valid ETag
When PATCH /v1/profile is called with an invalid value (e.g. locale not in the supported list)
Then respond 422 with problem+json type ".../errors/validation-failed"
And the errors array names the offending field(s)
```

**UP-AC5 — Immutable field in payload**
```gherkin
When PATCH /v1/profile is called with {"role": "admin"} or any other immutable field
Then respond 422 with problem+json type ".../errors/immutable-field"
And no fields are changed
```

**UP-AC6 — Unknown/extra field in payload**
```gherkin
When PATCH /v1/profile is called with a field not in the editable whitelist (e.g. {"is_super_user": true})
Then respond 422 with problem+json type ".../errors/validation-failed"
And no fields are changed
```

### Authorization
**UP-AC7 — Cannot update another user's profile**
```gherkin
Given user A is authenticated
When PATCH /v1/profile is scoped/targeted at user B's resource (e.g. via a mismatched path or resource id)
Then respond 403
```

**UP-AC8 — Unauthenticated request**
```gherkin
When PATCH /v1/profile is called without a valid session/JWT
Then respond 401
```

### Sensitive field change: email
**UP-AC9 — Email change without or with incorrect current_password**
```gherkin
Given an authenticated user and a valid ETag
When PATCH /v1/profile is called with {"email": "new@example.com"} and a missing or incorrect current_password
Then respond 401 with problem+json type ".../errors/reauthentication-required"
And the primary email and pending_email remain unchanged
```

**UP-AC10 — Email change initiated successfully**
```gherkin
Given an authenticated user, a valid ETag, and the correct current_password
When PATCH /v1/profile is called with {"email": "new@example.com", "current_password": "..."}
Then respond 202
And users.email remains unchanged; users.pending_email is set to "new@example.com"
And a confirmation link is sent to new@example.com
And a notification (not a confirmation link) is sent to the current, still-active email address
And a profile_audit_log entry records the change request
```

**UP-AC11 — Confirming a pending email change**
```gherkin
Given a valid, unconsumed, unexpired email_change_token
When POST /v1/profile/confirm-email-change is called with the raw token
Then respond 200
And users.email is set to the value of pending_email; pending_email is cleared
And all active sessions/tokens for this user except the confirming one are revoked (requires re-login elsewhere)
And a profile_audit_log entry records the completed change
```

**UP-AC12 — Expired or invalid email-change token**
```gherkin
Given an expired, already-consumed, or unknown token
When POST /v1/profile/confirm-email-change is called with that token
Then respond 400 with problem+json type ".../errors/token-expired" or ".../errors/token-invalid" as appropriate
And users.email and pending_email remain unchanged
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/validation-failed",
  "title": "Validation Failed",
  "status": 422,
  "detail": "One or more fields failed validation.",
  "instance": "/v1/profile",
  "errors": [
    {"field": "locale", "code": "invalid_choice", "message": "Locale 'xx' is not supported"}
  ]
}
```
Error `type` slugs introduced by this story: `precondition-required`, `immutable-field`, `validation-failed`, `reauthentication-required`, `token-expired`, `token-invalid` (last two reuse the shape defined in US-1.1).

## Non-Functional / Security Requirements
- The editable-field whitelist MUST be enforced server-side via the Pydantic model (`extra="forbid"`), not by client-side omission alone.
- `pending_email` MUST NOT be exposed to any party other than the account owner until confirmed.
- Session revocation on UP-AC11 MUST cover both access and refresh tokens (see US-1.3 Deactivate Account for the underlying revocation mechanism, which this story reuses).

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| UP-AC1 | Integration test suite | `[gate]` |
| UP-AC2–3 | Integration test suite (ETag/If-Match handling) | `[gate]` |
| UP-AC4–6 | Integration test suite + Pydantic model strictness (`extra="forbid"`) | `[gate]` |
| UP-AC7–8 | Integration test suite (authz) | `[gate]` |
| UP-AC9–10 | Integration test suite | `[gate]` |
| UP-AC11 | Integration test suite, including assertion that other sessions are revoked | `[gate]` |
| UP-AC12 | Integration test suite | `[gate]` |
| Audit log append-only / no UPDATE-DELETE grants | DB migration defines restrictive grants; verified by a dedicated negative test attempting UPDATE/DELETE | `[gate]` for the negative test; `[manual]` for confirming production grants match migration intent |

## Open Questions
1. Confirm the final editable-field list against the actual `users` table — the set above is a placeholder.
2. Should UP-AC7's cross-user check return 403 or 404 (to avoid confirming the target resource exists)? 403 is assumed here since the endpoint is self-scoped (no target id in the path) — flag if the actual routing design differs.
3. Confirm whether MFA (if/when supported) may substitute for the dual-email-confirmation flow on email change, per OWASP guidance.
