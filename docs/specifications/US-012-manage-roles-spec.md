# Specification: Manage Roles

**Source:** docs/backlog/US-3.2-manage-roles.md
**Story ID:** US-012
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/US-012-spec-review.md)

## Summary

This spec covers administrator management of a user's role assignments: replacing a user's full role set through a fixed, seeded role catalogue; immediate propagation of the resulting permission change to live sessions via access-token-only invalidation; reading the role catalogue and the scopes each role grants; and rejection of unknown roles, self-modification, privilege escalation, and removal of the last administrator.

## Background

As an administrator, I want to assign and revoke roles for a user, so that each person has exactly the access their job requires and no more.

The role catalogue is fixed and seeded with four roles: `customer`, `support_agent`, `admin`, `auditor` — custom or tenant-defined roles are not supported. The permission scopes referenced by roles are: `users:read`, `users:write`, `roles:write`, `audit:read`, `tickets:read`, `tickets:write`. Application code checks scopes only, read from the JWT's `scopes` claim, never role names directly. Role assignment (`PUT`) replaces the full role set for a user rather than applying incremental grants/revokes, so the operation is idempotent on repeat. The underlying data model is `roles`, `permissions`, `role_permissions`, and `user_roles`.

## Functional Requirements

### FR-1: Replacing a User's Role Set

Given an authenticated admin with the `roles:write` scope and a current ETag for the target user, when `PUT /v1/admin/users/{id}/roles` is called with an `If-Match` header and a body of `{"roles": [...]}`, the system responds `200` with the resulting role set. The operation is a full replacement, so it is idempotent on repeat. `perm_epoch:{target_id}` is set to now in Valkey, and an `admin_audit_log` entry is written with the old and new role sets and the actor.

**Derived from:** MR-AC1

### FR-2: New Permissions Take Effect Without Forcing a Re-Login

Given a target user with a live session whose access token was issued before the role change, when that user calls any authenticated endpoint, the system responds `401` with type `.../errors/token-stale`. When the client then calls `POST /v1/auth/refresh`, a new access token is issued carrying the updated scopes, because `perm_epoch` invalidates access tokens only, leaving the refresh family intact.

**Derived from:** MR-AC2

### FR-3: Reading the Role Catalogue

Given an authenticated admin with the `users:read` scope, when `GET /v1/admin/roles` is called, the system responds `200` with each role and the permission scopes it grants, as a body of the shape:

```json
{"roles": [{"name": "string", "permissions": ["string"]}]}
```

**Derived from:** MR-AC3; auth scope and response shape per the source's API Contract table

### FR-4: Unknown Role Is Rejected

Given a request containing a role name that is not in the catalogue, when `PUT /v1/admin/users/{id}/roles` is called, the system responds `422` with type `.../errors/validation-failed`. The entire request is rejected — no role in the list is applied.

**Derived from:** MR-AC4

### FR-5: Self-Modification Is Forbidden

Given an admin whose id equals the target id, when `PUT /v1/admin/users/{id}/roles` is called, the system responds `403` with type `.../errors/cannot-target-self`, because an admin must not be able to grant themselves permissions unilaterally.

**Derived from:** MR-AC5

### FR-6: Privilege Escalation Is Forbidden

Given an admin attempting to grant a role containing a permission they do not themselves hold, when `PUT /v1/admin/users/{id}/roles` is called, the system responds `403` with type `.../errors/privilege-escalation`, and an `admin_audit_log` entry is written (`event=authz_denied`, `severity=high`).

**Derived from:** MR-AC6

### FR-7: Removing the Last Administrator Is Blocked

Given the target is the only active account holding the `admin` role, when `PUT /v1/admin/users/{id}/roles` is called with a set that excludes `admin`, the system responds `409` with type `.../errors/last-admin`. The check and the update run in one transaction, so two concurrent requests cannot together remove both remaining admins.

**Derived from:** MR-AC7

## Non-Functional Requirements

- `perm_epoch:{user_id}` and `revoke_before:{user_id}` (US-1.4) are two separate Valkey keys by design: `revoke_before` kills the whole session including refresh, which is correct for deactivation; `perm_epoch` invalidates access tokens only, so a permission change refreshes transparently. Both are checked in the same shared middleware.
- MR-AC5 and MR-AC6 together close both self-elevation paths; the emergency route is an out-of-band runbook, not an API endpoint.
- An Alembic hook in `env.py` MUST fail the migration if any scope referenced in code is missing from `permissions`, or if a `role_permissions` row references an unknown scope.
- Permission checks resolve from the JWT `scopes` claim — no database round trip on the hot path; only `perm_epoch` is read from Valkey.
- Error responses use the RFC 7807 `application/problem+json` envelope (`type`, `title`, `status`, `detail`, `instance`), with `type` values rooted at `https://portal.internal/errors/...`.
- The `token-stale` error type slug is introduced by this story.

**Derived from:** Non-Functional / Security Requirements section and Error Envelope section of the source.

## Out of Scope

- Custom/tenant-defined roles
- Per-resource (row-level) permissions
- Break-glass admin recovery — a CI/CD-gated Alembic command, not an API

**Derived from:** Out of Scope section of the source.

## Open Questions

- Which permission scopes does each of the four seeded roles (`customer`, `support_agent`, `admin`, `auditor`) grant? The source names the four roles and the six scopes but never states the mapping between them, which MR-AC3's response body (FR-3) and MR-AC6's privilege-escalation check (FR-6) both require to be implementable.
- Do the MR-AC4 (unknown role, 422), MR-AC5 (self-modification, 403), and MR-AC7 (last-admin, 409) rejection paths also write an `admin_audit_log` entry? MR-AC1 and MR-AC6 each specify an audit log entry on that path; the other three negative paths are silent on it.
- The source's own Open Questions note that the break-glass runbook for zero-admin recovery needs a named owner and a rehearsal date before go-live — who owns it and when is it rehearsed?
- MR-AC1 requires an `If-Match` header, but the source doesn't state what happens when it doesn't match the target user's current ETag (a stale/failed precondition). What response (status and error type) should that produce?
- When more than one negative condition applies to a single `PUT` request at once (e.g., an admin targets themselves with a role list that also contains an unknown role name), the source doesn't state which check takes precedence. What is the required validation/check order?
- The source doesn't state how a `roles` array containing duplicate role names should be handled — rejected, deduplicated, or accepted as-is?
- Neither the story nor this spec states what `PUT /v1/admin/users/{id}/roles` returns when `{id}` does not correspond to an existing user — all seven ACs/FRs implicitly assume the target exists. Does this warrant a `404`, and if so what error `type`?
- The source's Assumptions table states `PUT` replaces the full role set ("removals are explicit rather than implied"), and FR-1 describes it as "a full replacement," but neither document states whether `{"roles": []}` is a valid request leaving a user with zero roles, or is rejected — and if accepted, how it interacts with FR-7's last-admin check when the target is not currently an admin.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| MR-AC1 | "Given an authenticated admin with roles:write and a current ETag for the target user When PUT /v1/admin/users/{id}/roles is called with If-Match and {\"roles\": [\"support_agent\"]} Then respond 200 with the resulting role set And the operation is a full replacement, so it is idempotent on repeat And perm_epoch:{target_id} is set to now in Valkey And an admin_audit_log entry is written with the old and new role sets and the actor" | FR-1 |
| MR-AC2 | "Given a target user with a live session whose access token was issued before the role change When that user calls any authenticated endpoint Then respond 401 with type \".../errors/token-stale\" And when the client then calls POST /v1/auth/refresh, a new access token is issued carrying the updated scopes Because perm_epoch invalidates access tokens only, leaving the refresh family intact" | FR-2 |
| MR-AC3 | "Given an authenticated admin When GET /v1/admin/roles is called Then respond 200 with each role and the permission scopes it grants" | FR-3 |
| MR-AC4 | "Given a request containing a role name that is not in the catalogue When PUT /v1/admin/users/{id}/roles is called Then respond 422 with type \".../errors/validation-failed\" And the entire request is rejected — no role in the list is applied" | FR-4 |
| MR-AC5 | "Given an admin whose id equals the target id When PUT /v1/admin/users/{id}/roles is called Then respond 403 with type \".../errors/cannot-target-self\" Because an admin must not be able to grant themselves permissions unilaterally" | FR-5 |
| MR-AC6 | "Given an admin attempting to grant a role containing a permission they do not themselves hold When PUT /v1/admin/users/{id}/roles is called Then respond 403 with type \".../errors/privilege-escalation\" And an admin_audit_log entry is written (event=authz_denied, severity=high)" | FR-6 |
| MR-AC7 | "Given the target is the only active account holding the admin role When PUT /v1/admin/users/{id}/roles is called with a set that excludes admin Then respond 409 with type \".../errors/last-admin\" And the check and the update run in one transaction, so two concurrent requests cannot together remove both remaining admins" | FR-7 |
