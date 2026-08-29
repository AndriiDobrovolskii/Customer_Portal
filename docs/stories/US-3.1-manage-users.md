# Epic 3 — Administration: Manage Users

**Story ID:** US-3.1 (five independently shippable slices: US-3.1.1 … US-3.1.5)
**Project:** Customer Portal

> Split per INVEST — a single "CRUD" story is neither *Small* nor independently testable. Slice 3.1.1 (read) is the natural first increment; the others build on it. Each slice may be pulled into its own file if the team prefers one file per sprint item.

## User Story
As an administrator,
I want to provision, find, correct and deactivate user accounts,
So that the directory reflects who should have access, and access can be withdrawn the moment it should be.

Per slice:
- **US-3.1.1 (Read):** …I want to search and page through the user directory, so that I can find the right account quickly when handling a support escalation.
- **US-3.1.2 (Create):** …I want to provision an account for a new colleague by email invitation, so that they can join the portal without me ever handling their password.
- **US-3.1.3 (Update):** …I want to correct a user's profile details, so that the directory stays accurate when someone changes their name or a record was entered wrongly.
- **US-3.1.4 (Deactivate):** …I want to deactivate an account and cut off its active sessions immediately, so that a departing employee or a compromised account loses access the moment I act.
- **US-3.1.5 (Resend invite):** …I want to reissue an invitation to an account that was already created, so that a colleague whose 24-hour link expired can still join without me deleting and recreating their record.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Authorisation model | Permission scopes (`users:read`, `users:write`), not role-string comparison | US-3.2 can reshape roles without touching these endpoints |
| 2 | Status code for a non-admin on an admin route | 403, not 404 | Admin routes are a documented surface; hiding them buys nothing and complicates support |
| 3 | Account creation | Invitation only — an admin never sets a password | Admins must not know another person's credentials |
| 4 | Invitation TTL | 24 hours, reissuable (US-3.1.5) | Matches the verification token TTL in US-1.2 |
| 5 | Deletion | Soft only; `DELETE` is not exposed | Erasure belongs to the retention job in US-1.4 DA-AC9 |
| 6 | Deactivation reason | Mandatory field | It is what auditors actually read |
| 7 | Concurrency control | `If-Match` ETag required on PATCH | Mirrors US-1.3 |

## In Scope
- `GET /v1/admin/users`, `GET /v1/admin/users/{id}` — search, filter, page
- `POST /v1/admin/users` — create by invitation
- `PATCH /v1/admin/users/{id}` — correct whitelisted fields
- `POST /v1/admin/users/{id}/deactivate` — admin-initiated deactivation
- `POST /v1/admin/users/{id}/resend-invite` — reissue an invitation

## Out of Scope
- Role assignment (US-3.2) — `roles` is immutable through this endpoint
- Email change (US-1.3's verified flow applies to admins too)
- Bulk export of the directory — separate story, separately permissioned
- Permanent deletion (US-1.4 DA-AC9)

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| GET | `/v1/admin/users` | `users:read` | — (query: `q`, `status`, `role`, `cursor`, `limit`) | 200, cursor-paginated |
| GET | `/v1/admin/users/{id}` | `users:read` | — | 200 + ETag |
| POST | `/v1/admin/users` | `users:write` | `{"email", "display_name", "roles"}` | 201 + ETag |
| PATCH | `/v1/admin/users/{id}` | `users:write` | Partial; `If-Match` required | 200 + new ETag |
| POST | `/v1/admin/users/{id}/deactivate` | `users:write` | `{"reason": str}` | 200 |
| POST | `/v1/admin/users/{id}/resend-invite` | `users:write` | — | 202 |
| DELETE | `/v1/admin/users/{id}` | — | — | 405 (never implemented) |

## Data Model Notes
- `users.status` ∈ {`invited`, `active`, `deactivated`}
- `invitation_tokens`: `token_hash` (SHA-256), `user_id`, `issued_at`, `expires_at`, `consumed_at` — same shape as US-1.2's tokens
- `admin_audit_log`: one row per changed field, with `actor_id`, `target_id`, `field`, `old_value`, `new_value`, `reason`, `request_id`
- Search requires an index supporting the `q` prefix match (`pg_trgm` or a `tsvector` column) plus `(status, created_at)`

## Acceptance Criteria

### US-3.1.1 — List & search users
**MU-AC1 — Filtered, paginated listing**
```gherkin
Given an authenticated admin
When GET /v1/admin/users?q=smith&status=active&limit=25 is called
Then respond 200 with a cursor-paginated list matching the filters
And each item contains id, email, display_name, status, roles, created_at, last_login_at
And no password hash, token or other credential material is present in the payload
```

**MU-AC2 — Insufficient permission**
```gherkin
Given an authenticated user whose roles do not include the users:read permission
When GET /v1/admin/users is called
Then respond 403 with type ".../errors/insufficient-permission"
And an auth_audit_log entry is written (event=authz_denied)
```

**MU-AC3 — Anonymous access**
```gherkin
Given a request with no valid access token
When any /v1/admin/* endpoint is called
Then respond 401 and the request never reaches the admin handler
```

**MU-AC4 — Invalid paging or filter input**
```gherkin
Given a request with limit=5000, or an unknown status value, or a malformed cursor
When GET /v1/admin/users is called
Then respond 422 with type ".../errors/validation-failed"
And no partial result set is returned
```

### US-3.1.2 — Create a user
**MU-AC5 — Successful creation by invitation**
```gherkin
Given an authenticated admin with users:write
When POST /v1/admin/users is called with {email, display_name, roles}
Then respond 201 with the created resource and its ETag
And users.status is "invited" and email_verified is false; no password is set
And an invitation token (24-hour TTL) is emailed to the address
And an admin_audit_log entry is written (actor=admin:{id}, event=user_created)
```

**MU-AC6 — Duplicate email**
```gherkin
Given an account already exists with that email (case-insensitive)
When POST /v1/admin/users is called
Then respond 409 with type ".../errors/email-already-registered"
And no account is created and no invitation is sent
```

**MU-AC7 — Admin-set password attempt**
```gherkin
Given a request body containing a "password" field
When POST /v1/admin/users is called
Then respond 422 with type ".../errors/validation-failed"
Because admins must never know or choose another person's password
```

**MU-AC8 — Privilege escalation via role assignment**
```gherkin
Given an admin whose own permission set does not include a permission granted by the requested role
When POST /v1/admin/users is called with that role
Then respond 403 with type ".../errors/privilege-escalation"
And no account is created
```

### US-3.1.3 — Update a user
**MU-AC9 — Successful update**
```gherkin
Given an authenticated admin and a current ETag for the target user
When PATCH /v1/admin/users/{id} is called with If-Match and a whitelisted field
Then respond 200 with the updated resource and a new ETag
And one admin_audit_log row is written per changed field (old_value, new_value, actor, reason)
```

**MU-AC10 — Stale or missing ETag**
```gherkin
Given the record changed since the admin last read it
When PATCH /v1/admin/users/{id} is called with the stale If-Match value
Then respond 412 and no field is changed
Given the If-Match header is absent
Then respond 400 with type ".../errors/precondition-required"
```

**MU-AC11 — Immutable or non-whitelisted field**
```gherkin
Given a request body containing id, created_at, email_verified, roles or an unknown field
When PATCH /v1/admin/users/{id} is called
Then respond 422 with type ".../errors/immutable-field" or ".../errors/validation-failed"
And no field is changed
Because role changes go through US-3.2 and email changes through the verified flow in US-1.3
```

**MU-AC12 — Unknown user**
```gherkin
Given a user id that does not exist
When PATCH /v1/admin/users/{id} is called
Then respond 404 with type ".../errors/not-found"
```

### US-3.1.4 — Deactivate a user
**MU-AC13 — Successful deactivation**
```gherkin
Given an authenticated admin with users:write and an active target user
When POST /v1/admin/users/{id}/deactivate is called with a required {reason}
Then respond 200
And users.status becomes "deactivated" and deactivated_at is set
And revoke_before:{target_id} is set to now, killing all access and refresh tokens
And an account_lifecycle_audit_log entry is written (event=deactivated, actor=admin:{admin_id}, reason)
Because these are exactly US-1.4 DA-AC1's side effects, per the DA-AC10 invariant
```

**MU-AC14 — Already deactivated**
```gherkin
Given a target user whose status is already "deactivated"
When POST /v1/admin/users/{id}/deactivate is called
Then respond 409 with type ".../errors/already-deactivated"
```

**MU-AC15 — Self-deactivation via the admin path**
```gherkin
Given an admin whose id equals the target id
When POST /v1/admin/users/{id}/deactivate is called
Then respond 409 with type ".../errors/cannot-target-self"
And the self-service endpoint POST /v1/account/deactivate must be used instead
```

**MU-AC16 — Last administrator protection**
```gherkin
Given the target user is the only remaining active account holding the admin role
When POST /v1/admin/users/{id}/deactivate is called
Then respond 409 with type ".../errors/last-admin"
And the account remains active, so the system can never be locked out of administration
```

**MU-AC17 — No hard delete**
```gherkin
Given any actor
When DELETE /v1/admin/users/{id} is called
Then respond 405 Method Not Allowed
Because erasure is handled only by the retention job in US-1.4 DA-AC9
```

### US-3.1.5 — Resend an invitation
**MU-AC18 — Successful resend**
```gherkin
Given an authenticated admin with users:write and a target user whose status is "invited"
When POST /v1/admin/users/{id}/resend-invite is called
Then respond 202 with a generic body
And any previously issued, unconsumed invitation token for that account is invalidated
And a fresh token with a 24-hour TTL is emailed to the address on file
And an admin_audit_log entry is written (event=invitation_resent, actor=admin:{id})
Because the user id, its roles and its audit history must survive — recreating the record would not
```

**MU-AC19 — Account is not awaiting invitation**
```gherkin
Given a target user whose status is "active" or "deactivated"
When POST /v1/admin/users/{id}/resend-invite is called
Then respond 409 with type ".../errors/invalid-state-transition"
And no email is sent
Because an active user needing access should use password reset (US-2.4), not an invitation
```

**MU-AC20 — Resend flooding**
```gherkin
Given an invitation was resent to the same account less than 60 seconds ago
When POST /v1/admin/users/{id}/resend-invite is called again
Then respond 429 with a Retry-After header
And the per-account limit is 5 resends per hour, mirroring US-1.2 VE-AC7
```

**MU-AC21 — Unknown user or insufficient permission**
```gherkin
Given an unknown user id
Then respond 404
Given an actor without users:write
Then respond 403, and the denied attempt is audited
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/last-admin",
  "title": "Last Administrator",
  "status": 409,
  "detail": "This is the only remaining administrator; the system cannot be left without one.",
  "instance": "/v1/admin/users/{id}/deactivate"
}
```
Error `type` slugs introduced by this story: `insufficient-permission`, `privilege-escalation`, `email-already-registered`, `cannot-target-self`, `last-admin`, `invalid-state-transition`, `not-found`.

## Non-Functional / Security Requirements
- Authorisation MUST be permission-based, never `role == "admin"`.
- List responses MUST be PII-minimised; no credential material in any payload.
- Admin endpoints carry their own rate limit (120 req/min/admin) to bound the damage from a stolen admin token.
- Every mutation is audited **even when it fails authorisation** — denied attempts are the interesting ones.
- **Performance:** MU-AC1 p95 ≤ 300 ms at 100 k users.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| MU-AC1, 4 | Integration test suite | `[gate]` |
| MU-AC2–3 | Integration test per admin route, asserting 401 vs 403 | `[gate]` |
| MU-AC5–8 | Integration test suite | `[gate]` |
| MU-AC9–12 | Integration test suite, including ETag races | `[gate]` |
| MU-AC13 | Integration test asserting all three US-1.4 side effects | `[gate]` |
| MU-AC14–17 | Integration test suite | `[gate]` |
| MU-AC16 | Concurrency test: two simultaneous deactivations of the last two admins | `[gate]` |
| MU-AC18–21 | Integration test suite with a fixed Valkey clock | `[gate]` |

## Open Questions
1. Should an admin-initiated deactivation additionally require a second admin's approval for accounts holding privileged roles? (Raised but deferred in US-1.4 Open Question 3.)