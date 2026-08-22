# Epic 3 — Administration: Manage Roles

**Story ID:** US-3.2
**Project:** Customer Portal

## User Story
As an administrator,
I want to assign and revoke roles for a user,
So that each person has exactly the access their job requires and no more.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Role catalogue | Fixed and seeded: `customer`, `support_agent`, `admin`, `auditor` | Custom roles need a management UI and a much larger authorisation test matrix; build them when a business requirement demands it |
| 2 | Assignment semantics | `PUT` replaces the full set | Idempotent, and removals are explicit rather than implied |
| 3 | Propagation to live sessions | `perm_epoch:{user_id}` invalidates access tokens only | A permission change should refresh transparently, not log the user out mid-task |
| 4 | Self-modification | Forbidden | An admin must not grant themselves permissions unilaterally |
| 5 | Granting what you lack | Forbidden | Closes the second self-elevation path |
| 6 | Zero-admin state | Unreachable through the API | Recovery is a documented break-glass runbook |

## In Scope
- `GET /v1/admin/roles` — the catalogue and the scopes each role grants
- `PUT /v1/admin/users/{id}/roles` — replace a user's role set
- Immediate propagation of permission changes to live sessions

## Out of Scope
- Custom/tenant-defined roles
- Per-resource (row-level) permissions
- Break-glass admin recovery — a CI/CD-gated Alembic command, not an API

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| GET | `/v1/admin/roles` | `users:read` | — | 200 `{"roles": [{"name", "permissions": [...]}]}` |
| PUT | `/v1/admin/users/{id}/roles` | `roles:write` | `{"roles": [str]}`; `If-Match` required | 200 with the resulting set |

## Data Model Notes
- `roles`, `permissions`, `role_permissions`, `user_roles`
- Permission scopes: `users:read`, `users:write`, `roles:write`, `audit:read`, `tickets:read`, `tickets:write`
- Valkey `perm_epoch:{user_id}` — deliberately separate from `revoke_before:{user_id}` (US-1.4)
- Application code checks **scopes only**, read from the JWT's `scopes` claim

## Acceptance Criteria

### Happy path
**MR-AC1 — Replacing a user's role set**
```gherkin
Given an authenticated admin with roles:write and a current ETag for the target user
When PUT /v1/admin/users/{id}/roles is called with If-Match and {"roles": ["support_agent"]}
Then respond 200 with the resulting role set
And the operation is a full replacement, so it is idempotent on repeat
And perm_epoch:{target_id} is set to now in Valkey
And an admin_audit_log entry is written with the old and new role sets and the actor
```

**MR-AC2 — New permissions take effect without forcing a re-login**
```gherkin
Given a target user with a live session whose access token was issued before the role change
When that user calls any authenticated endpoint
Then respond 401 with type ".../errors/token-stale"
And when the client then calls POST /v1/auth/refresh, a new access token is issued carrying the updated scopes
Because perm_epoch invalidates access tokens only, leaving the refresh family intact
```

**MR-AC3 — Reading the role catalogue**
```gherkin
Given an authenticated admin
When GET /v1/admin/roles is called
Then respond 200 with each role and the permission scopes it grants
```

### Negative paths
**MR-AC4 — Unknown role**
```gherkin
Given a request containing a role name that is not in the catalogue
When PUT /v1/admin/users/{id}/roles is called
Then respond 422 with type ".../errors/validation-failed"
And the entire request is rejected — no role in the list is applied
```

**MR-AC5 — Self-modification**
```gherkin
Given an admin whose id equals the target id
When PUT /v1/admin/users/{id}/roles is called
Then respond 403 with type ".../errors/cannot-target-self"
Because an admin must not be able to grant themselves permissions unilaterally
```

**MR-AC6 — Privilege escalation**
```gherkin
Given an admin attempting to grant a role containing a permission they do not themselves hold
When PUT /v1/admin/users/{id}/roles is called
Then respond 403 with type ".../errors/privilege-escalation"
And an admin_audit_log entry is written (event=authz_denied, severity=high)
```

**MR-AC7 — Removing the last administrator**
```gherkin
Given the target is the only active account holding the admin role
When PUT /v1/admin/users/{id}/roles is called with a set that excludes admin
Then respond 409 with type ".../errors/last-admin"
And the check and the update run in one transaction, so two concurrent requests cannot together remove both remaining admins
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/token-stale",
  "title": "Token Predates a Permission Change",
  "status": 401,
  "detail": "Your permissions changed. Refresh the session to continue.",
  "instance": "/v1/admin/users"
}
```
Error `type` slugs introduced by this story: `token-stale`.

## Non-Functional / Security Requirements
- **`perm_epoch` vs `revoke_before`:** two separate keys by design. `revoke_before` (US-1.4) kills the whole session including refresh — correct for deactivation. `perm_epoch` invalidates access tokens only, so a permission change refreshes transparently. Both are checked in the same shared middleware.
- MR-AC5 and MR-AC6 together close both self-elevation paths; the emergency route is an out-of-band runbook, not an endpoint.
- **Migration guardrail:** an Alembic hook in `env.py` MUST fail the migration if any scope referenced in code is missing from `permissions`, or if a `role_permissions` row references an unknown scope. A missing permission row silently turns every guarded endpoint into a 403 at runtime; this catches it at deploy time.
- **Performance:** permission checks resolve from the JWT `scopes` claim — no database round trip on the hot path; only `perm_epoch` is read from Valkey.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| MR-AC1, 3 | Integration test suite | `[gate]` |
| MR-AC2 | Integration test asserting the refresh family survives and new scopes appear | `[gate]` |
| MR-AC4–6 | Integration test suite | `[gate]` |
| MR-AC7 | Concurrency test: two simultaneous requests removing the admin role from the last two admins | `[gate]` |
| Permission catalogue completeness | Alembic `env.py` hook, executed in CI | `[gate]` |

## Open Questions
1. The break-glass runbook (Decision #8 in the epic document) needs a named owner and a rehearsal date before go-live.