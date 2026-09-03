# Specification: Manage Users

**Source:** docs/stories/US-3.1-manage-users.md
**Story ID:** US-3.1
**Generated:** 2026-08-22
**Revised:** 2026-09-02 — incorporates OD-1–OD-3 (`docs/decisions/US-3.1-open-decisions.md`) and 6 precedent-resolved items from `docs/evidence/US-3.1-clarification-report.md`, all resolved by the user 2026-09-02.
**Status:** Draft (revised)

## Summary

This spec covers the admin user-management surface: searching and paging the user directory, creating a user by email invitation, correcting a user's whitelisted profile fields, admin-initiated deactivation with immediate session revocation, and reissuing an expired invitation. It spans all five shippable slices of US-3.1 (US-3.1.1 read, US-3.1.2 create, US-3.1.3 update, US-3.1.4 deactivate, US-3.1.5 resend-invite), which share one Acceptance Criteria prefix (`MU-AC`).

## Background

As an administrator, the story is to provision, find, correct, and deactivate user accounts, so that the directory reflects who should have access, and access can be withdrawn the moment it should be. Per slice:

- **List & search (US-3.1.1):** an admin wants to search and page through the user directory, so they can find the right account quickly when handling a support escalation.
- **Create (US-3.1.2):** an admin wants to provision an account for a new colleague by email invitation, so that colleague can join the portal without the admin ever handling their password.
- **Update (US-3.1.3):** an admin wants to correct a user's profile details, so the directory stays accurate when someone changes their name or a record was entered wrongly.
- **Deactivate (US-3.1.4):** an admin wants to deactivate an account and cut off its active sessions immediately, so a departing employee or a compromised account loses access the moment the admin acts.
- **Resend invite (US-3.1.5):** an admin wants to reissue an invitation to an account that was already created, so a colleague whose 24-hour link expired can still join without the admin deleting and recreating their record.

The source establishes the following defaults for this story:

- Authorisation is based on permission scopes (`users:read`, `users:write`), not role-string comparison.
- A non-admin calling an admin route receives `403`, not `404`.
- Account creation is invitation-only — an admin never sets a password.
- Invitation tokens have a 24-hour TTL and are reissuable (US-3.1.5).
- Deletion is soft only; `DELETE` is not exposed (erasure belongs to the retention job in US-1.4 DA-AC9).
- The deactivation `reason` field is mandatory.
- `PATCH` requires an `If-Match` ETag for concurrency control.

In scope are the following endpoints: `GET /v1/admin/users`, `GET /v1/admin/users/{id}`, `POST /v1/admin/users`, `PATCH /v1/admin/users/{id}`, `POST /v1/admin/users/{id}/deactivate`, and `POST /v1/admin/users/{id}/resend-invite`; `DELETE /v1/admin/users/{id}` exists only to return `405`.

## Open Decision Resolutions (2026-09-02)

- **OD-1 (`admin_audit_log` shape for per-field Update rows):** `admin_audit_log` (already built by US-3.2 for role-replacement rows) gains nullable `field`, `old_value`, `new_value`, and `reason` columns, reused by this story's per-field Update audit rows (FR-9) alongside US-3.2's existing `old_roles`/`new_roles` role-replacement rows. Each write populates only the columns relevant to its own `event`.
- **OD-2 (`account_lifecycle_audit_log` reason storage):** `account_lifecycle_audit_log` (already built by US-1.4) gains a nullable `reason` column, populated only by the admin-initiated deactivation path (FR-13); self-service deactivation rows (DA-AC1) leave it `null`, per DA-AC10's "identical side effects" invariant holding for every pre-existing column.
- **OD-3 (`GET /v1/admin/users/{id}` coverage):** the single-resource fetch endpoint, listed in scope by the source but never exercised by an Acceptance Criterion, is now covered by new FR-22/FR-23 below — no source AC, resolved the same way US-2.6's FR-6/FR-7 were (Open-Decision-derived, not source-derived).
- **Precedent (concurrent duplicate-email creation, MU-AC6/FR-6):** already governed by `business-rules.md` BR-001 — email uniqueness "is enforced atomically at the data layer so concurrent registrations for the same email cannot both succeed," reused verbatim for admin-created accounts. No new mechanism; FR-6 below states this explicitly.
- **Precedent (role→permission mapping, MU-AC8/FR-8):** already built by US-3.2. `RoleService`'s existing privilege-escalation check (`requested_permissions.issubset(actor_scopes)`, computed from `Role.permissions` via `RoleRepository.get_by_names()`) is the mechanism this story's create-user check reuses — not a new mapping.
- **Precedent (Deactivate's missing unknown-user case, MU-AC13–17):** resolved by the same 404-on-unknown-id pattern already used by Update (FR-12) and Resend-invite (FR-21) within this same spec.
- **Precedent (invitation-token shape):** confirmed — `email_verification_tokens` and `password_reset_tokens` already exist with exactly the `token_hash`/`user_id`/`issued_at`/`expires_at`/`consumed_at` shape the source describes; `invitation_tokens` follows the identical pattern.
- **Precedent (resend rate-limit mechanism, FR-20):** confirmed — `email_verification`'s resend-cooldown mechanism (a per-account cooldown plus `Retry-After`) is the direct precedent FR-20 adapts, adding the per-hour count FR-20 additionally requires.
- **Precedent (last-admin check, MU-AC16/FR-16):** `RoleService`'s existing `count_active_admins_excluding` query is the mechanism this story's deactivate-check reuses, not a new query.

Data model: `users.status` is one of `invited`, `active`, `deactivated`. `invitation_tokens` stores `token_hash` (SHA-256), `user_id`, `issued_at`, `expires_at`, `consumed_at` — the same shape as US-1.2's tokens, already precedented by `email_verification_tokens`/`password_reset_tokens`. `admin_audit_log` (already built by US-3.2) gains nullable `field`, `old_value`, `new_value`, `reason` columns per OD-1, alongside its existing `id`, `event`, `actor_id`, `target_id`, `old_roles`, `new_roles`, `severity`, `request_id`, `occurred_at`. `account_lifecycle_audit_log` (already built by US-1.4) gains a nullable `reason` column per OD-2, alongside its existing `id`, `user_id`, `event`, `actor`, `occurred_at`. Search requires an index supporting the `q` prefix match (`pg_trgm` or a `tsvector` column) plus `(status, created_at)`.

## Functional Requirements

### Slice 1: List & Search

#### FR-1: Filtered, Paginated Listing

Given an authenticated admin, when `GET /v1/admin/users?q=smith&status=active&limit=25` is called, the system responds `200` with a cursor-paginated list matching the filters; each item contains `id`, `email`, `display_name`, `status`, `roles`, `created_at`, `last_login_at`; no password hash, token, or other credential material is present in the payload.

**Derived from:** MU-AC1

#### FR-2: Insufficient Permission on Read

Given an authenticated user whose roles do not include the `users:read` permission, when `GET /v1/admin/users` is called, the system responds `403` with type `.../errors/insufficient-permission` and writes an `auth_audit_log` entry (`event=authz_denied`).

**Derived from:** MU-AC2

#### FR-3: Anonymous Access to Admin Endpoints

Given a request with no valid access token, when any `/v1/admin/*` endpoint is called, the system responds `401` and the request never reaches the admin handler.

**Derived from:** MU-AC3

#### FR-4: Invalid Paging or Filter Input

Given a request with `limit=5000`, or an unknown `status` value, or a malformed cursor, when `GET /v1/admin/users` is called, the system responds `422` with type `.../errors/validation-failed` and no partial result set is returned.

**Derived from:** MU-AC4

### Slice 2: Create a User

#### FR-5: Successful Creation by Invitation

Given an authenticated admin with `users:write`, when `POST /v1/admin/users` is called with `{email, display_name, roles}`, the system responds `201` with the created resource and its ETag; `users.status` is `"invited"` and `email_verified` is `false`; no password is set; an invitation token (24-hour TTL) is emailed to the address; an `admin_audit_log` entry is written (`actor=admin:{id}`, `event=user_created`).

**Derived from:** MU-AC5

#### FR-6: Duplicate Email Rejected

Given an account already exists with that email (case-insensitive), when `POST /v1/admin/users` is called, the system responds `409` with type `.../errors/email-already-registered`; no account is created and no invitation is sent. Per BR-001, the case-insensitive uniqueness check is enforced atomically at the data layer, so two simultaneous `POST /v1/admin/users` requests for the same email cannot both succeed — the loser receives this same `409`, not a distinct concurrency error.

**Derived from:** MU-AC6; concurrency handling per BR-001 precedent (see Open Decision Resolutions).

#### FR-7: Admin-Set Password Rejected

Given a request body containing a `"password"` field, when `POST /v1/admin/users` is called, the system responds `422` with type `.../errors/validation-failed`, because admins must never know or choose another person's password.

**Derived from:** MU-AC7

#### FR-8: Privilege Escalation via Role Assignment Rejected

Given an admin whose own permission set does not include a permission granted by the requested role, when `POST /v1/admin/users` is called with that role, the system responds `403` with type `.../errors/privilege-escalation`; no account is created. The requested role's permission set is resolved the same way US-3.2's `RoleService` already resolves it for role-replacement requests (a role's flattened `permissions` set compared against the actor's own JWT `scopes`), not a new mapping mechanism.

**Derived from:** MU-AC8; mapping mechanism per US-3.2 `RoleService` precedent (see Open Decision Resolutions).

### Slice 3: Update a User

#### FR-9: Successful Update

Given an authenticated admin and a current ETag for the target user, when `PATCH /v1/admin/users/{id}` is called with `If-Match` and a whitelisted field, the system responds `200` with the updated resource and a new ETag, and writes one `admin_audit_log` row per changed field, using the `field`/`old_value`/`new_value`/`reason` columns added to that table per OD-1 (`actor_id` set to the calling admin).

**Derived from:** MU-AC9; audit-column mapping per OD-1.

#### FR-10: Stale or Missing ETag

Given the record changed since the admin last read it, when `PATCH /v1/admin/users/{id}` is called with the stale `If-Match` value, the system responds `412` and no field is changed. Given the `If-Match` header is absent, the system responds `400` with type `.../errors/precondition-required`.

**Derived from:** MU-AC10

#### FR-11: Immutable or Non-Whitelisted Field Rejected

Given a request body containing `id`, `created_at`, `email_verified`, `roles`, or an unknown field, when `PATCH /v1/admin/users/{id}` is called, the system responds `422` with type `.../errors/immutable-field` or `.../errors/validation-failed`, and no field is changed — role changes go through US-3.2 and email changes through the verified flow in US-1.3.

**Derived from:** MU-AC11

#### FR-12: Unknown User on Update

Given a user id that does not exist, when `PATCH /v1/admin/users/{id}` is called, the system responds `404` with type `.../errors/not-found`.

**Derived from:** MU-AC12

### Slice 4: Deactivate a User

#### FR-13: Successful Admin-Initiated Deactivation

Given an authenticated admin with `users:write` and an active target user, when `POST /v1/admin/users/{id}/deactivate` is called with a required `{reason}`, the system responds `200`; `users.status` becomes `"deactivated"` and `deactivated_at` is set; `revoke_before:{target_id}` is set to now, killing all access and refresh tokens; an `account_lifecycle_audit_log` entry is written (`event=deactivated`, `actor="admin:{admin_id}"`, and `reason` populated in the nullable `reason` column added to that table per OD-2) — these are exactly US-1.4 DA-AC1's side effects plus the admin-only `reason`, per the DA-AC10 invariant.

**Derived from:** MU-AC13; audit-column mapping per OD-2.

#### FR-14: Already-Deactivated Target

Given a target user whose status is already `"deactivated"`, when `POST /v1/admin/users/{id}/deactivate` is called, the system responds `409` with type `.../errors/already-deactivated`.

**Derived from:** MU-AC14

#### FR-15: Self-Deactivation via the Admin Path Rejected

Given an admin whose id equals the target id, when `POST /v1/admin/users/{id}/deactivate` is called, the system responds `409` with type `.../errors/cannot-target-self`; the self-service endpoint `POST /v1/account/deactivate` must be used instead.

**Derived from:** MU-AC15

#### FR-16: Last-Administrator Protection

Given the target user is the only remaining active account holding the admin role, when `POST /v1/admin/users/{id}/deactivate` is called, the system responds `409` with type `.../errors/last-admin`, and the account remains active, so the system can never be locked out of administration. The remaining-admin count is resolved the same way US-3.2's `RoleService` already resolves it for role-removal requests, not a new query.

**Derived from:** MU-AC16; mechanism per US-3.2 `RoleService` precedent (see Open Decision Resolutions).

#### FR-17: No Hard Delete

Given any actor, when `DELETE /v1/admin/users/{id}` is called, the system responds `405 Method Not Allowed`, because erasure is handled only by the retention job in US-1.4 DA-AC9.

**Derived from:** MU-AC17

#### FR-17b: Unknown User on Deactivate

Given a user id that does not exist, when `POST /v1/admin/users/{id}/deactivate` is called, the system responds `404` with type `.../errors/not-found`, matching the identical unknown-id handling already specified for Update (FR-12) and Resend-invite (FR-21).

**Derived from:** Open Decision Resolutions precedent item (no source AC — the Deactivate slice's ACs, MU-AC13–MU-AC17, never state this case; resolved by precedent with Update/Resend-invite rather than left unspecified).

### Slice 5: Resend an Invitation

#### FR-18: Successful Resend

Given an authenticated admin with `users:write` and a target user whose status is `"invited"`, when `POST /v1/admin/users/{id}/resend-invite` is called, the system responds `202` with a generic body; any previously issued, unconsumed invitation token for that account is invalidated; a fresh token with a 24-hour TTL is emailed to the address on file; an `admin_audit_log` entry is written (`event=invitation_resent`, `actor=admin:{id}`) — the user id, its roles, and its audit history must survive, since recreating the record would not.

**Derived from:** MU-AC18

#### FR-19: Account Not Awaiting Invitation

Given a target user whose status is `"active"` or `"deactivated"`, when `POST /v1/admin/users/{id}/resend-invite` is called, the system responds `409` with type `.../errors/invalid-state-transition` and no email is sent, because an active user needing access should use password reset (US-2.4), not an invitation.

**Derived from:** MU-AC19

#### FR-20: Resend Flooding Rate Limit

Given an invitation was resent to the same account less than 60 seconds ago, when `POST /v1/admin/users/{id}/resend-invite` is called again, the system responds `429` with a `Retry-After` header; the per-account limit is 5 resends per hour, mirroring US-1.2 VE-AC7. The 60-second cooldown reuses the same mechanism `email_verification`'s resend-cooldown already implements, extended with the per-hour count.

**Derived from:** MU-AC20; cooldown mechanism per `email_verification` precedent (see Open Decision Resolutions).

#### FR-21: Unknown User or Insufficient Permission on Resend

Given an unknown user id, the system responds `404`. Given an actor without `users:write`, the system responds `403`, and the denied attempt is audited.

**Derived from:** MU-AC21

### Slice 1 (continued): Fetch a Single User

#### FR-22: Successful Single-User Fetch

Given an authenticated admin with `users:read` and an existing user id, when `GET /v1/admin/users/{id}` is called, the system responds `200` with the same item shape FR-1 returns for one list entry (`id`, `email`, `display_name`, `status`, `roles`, `created_at`, `last_login_at`, no credential material) plus an ETag — the same ETag FR-9's `PATCH ... If-Match` flow requires as input.

**Derived from:** Open Decision OD-3 (no AC; the source's In Scope list and API Contract table list this endpoint, but no Acceptance Criterion exercises it).

#### FR-23: Unknown User or Insufficient Permission on Fetch

Given a user id that does not exist, when `GET /v1/admin/users/{id}` is called, the system responds `404` with type `.../errors/not-found`, mirroring FR-12's Update behavior. Given an actor without `users:read`, the system responds `403` with type `.../errors/insufficient-permission` and writes an `auth_audit_log` entry (`event=authz_denied`), mirroring FR-2. Given no valid access token, the system responds `401`, mirroring FR-3.

**Derived from:** Open Decision OD-3 (no AC; derived by mirroring FR-2/FR-3/FR-12's already-specified permission and unknown-id handling for this same resource).

## Response Schemas

### Error Envelope Schema

Applies to every `problem+json` error response referenced by FR-2 through FR-23 (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/last-admin",
  "title": "Last Administrator",
  "status": 409,
  "detail": "This is the only remaining administrator; the system cannot be left without one.",
  "instance": "/v1/admin/users/{id}/deactivate"
}
```

Error `type` slugs introduced by this story: `insufficient-permission`, `privilege-escalation`, `email-already-registered`, `cannot-target-self`, `last-admin`, `invalid-state-transition`, `not-found`. The `validation-failed`, `immutable-field`, `precondition-required`, and `already-deactivated` slugs used elsewhere in this spec's FRs are not in this list and are therefore reused from shared convention or another story rather than introduced here.

**Derived from:** source Error Envelope section.

## Enforcement Matrix

| AC | Mechanism | Marker |
|---|---|---|
| MU-AC1, 4 | Integration test suite | `[gate]` |
| MU-AC2–3 | Integration test per admin route, asserting 401 vs 403 | `[gate]` |
| MU-AC5–8 | Integration test suite | `[gate]` |
| MU-AC9–12 | Integration test suite, including ETag races | `[gate]` |
| MU-AC13 | Integration test asserting all three US-1.4 side effects plus `reason` persistence (OD-2) | `[gate]` |
| MU-AC14–17 | Integration test suite | `[gate]` |
| MU-AC16 | Concurrency test: two simultaneous deactivations of the last two admins | `[gate]` |
| MU-AC18–21 | Integration test suite with a fixed Valkey clock | `[gate]` |
| FR-17b, FR-22, FR-23 | Integration test suite (Open-Decision-derived, no source AC) | `[gate]` |

**Derived from:** source Enforcement Matrix section; OD-1/OD-2/OD-3 additions noted.

## Non-Functional Requirements

- Authorisation MUST be permission-based, never `role == "admin"`.
- List responses MUST be PII-minimised; no credential material in any payload.
- Admin endpoints carry their own rate limit (120 req/min/admin) to bound the damage from a stolen admin token.
- Every mutation is audited even when it fails authorisation — denied attempts are the interesting ones.
- Performance: MU-AC1 (filtered, paginated listing) must meet p95 ≤ 300 ms at 100k users.
- Search requires an index supporting the `q` prefix match (`pg_trgm` or a `tsvector` column) plus `(status, created_at)`.

**Derived from:** Non-Functional / Security Requirements section of the source; Data Model Notes (search-index requirement).

## Out of Scope

- Role assignment (US-3.2) — `roles` is immutable through the update endpoint (`PATCH /v1/admin/users/{id}`, per FR-11); `roles` is accepted at creation time (`POST /v1/admin/users`, per FR-5).
- Email change (US-1.3's verified flow applies to admins too).
- Bulk export of the directory — separate story, separately permissioned.
- Permanent deletion (US-1.4 DA-AC9).

**Derived from:** Out of Scope section of the source; wording clarified 2026-09-02 to name "the update endpoint" explicitly (spec-review Low finding — the original wording's referent was ambiguous against FR-5's create-time acceptance of `roles`).

## Open Questions

- Should an admin-initiated deactivation additionally require a second admin's approval for accounts holding privileged roles? (Carried over verbatim from the source's own Open Questions section, item 1: "Raised but deferred in US-1.4 Open Question 3." Deferred twice already with no story picking it up; disclosed as non-blocking per `docs/decisions/US-3.1-open-decisions.md`.)

All other Open Questions from the 2026-08-22 draft are resolved — see Open Decision Resolutions above (OD-1, OD-2, OD-3) and the precedent items resolved against the now-shipped US-1.4/US-3.2 codebase.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| MU-AC1 | "Given an authenticated admin When GET /v1/admin/users?q=smith&status=active&limit=25 is called Then respond 200 with a cursor-paginated list matching the filters And each item contains id, email, display_name, status, roles, created_at, last_login_at And no password hash, token or other credential material is present in the payload" | FR-1 |
| MU-AC2 | "Given an authenticated user whose roles do not include the users:read permission When GET /v1/admin/users is called Then respond 403 with type \".../errors/insufficient-permission\" And an auth_audit_log entry is written (event=authz_denied)" | FR-2 |
| MU-AC3 | "Given a request with no valid access token When any /v1/admin/* endpoint is called Then respond 401 and the request never reaches the admin handler" | FR-3 |
| MU-AC4 | "Given a request with limit=5000, or an unknown status value, or a malformed cursor When GET /v1/admin/users is called Then respond 422 with type \".../errors/validation-failed\" And no partial result set is returned" | FR-4 |
| MU-AC5 | "Given an authenticated admin with users:write When POST /v1/admin/users is called with {email, display_name, roles} Then respond 201 with the created resource and its ETag And users.status is \"invited\" and email_verified is false; no password is set And an invitation token (24-hour TTL) is emailed to the address And an admin_audit_log entry is written (actor=admin:{id}, event=user_created)" | FR-5 |
| MU-AC6 | "Given an account already exists with that email (case-insensitive) When POST /v1/admin/users is called Then respond 409 with type \".../errors/email-already-registered\" And no account is created and no invitation is sent" | FR-6 |
| MU-AC7 | "Given a request body containing a \"password\" field When POST /v1/admin/users is called Then respond 422 with type \".../errors/validation-failed\" Because admins must never know or choose another person's password" | FR-7 |
| MU-AC8 | "Given an admin whose own permission set does not include a permission granted by the requested role When POST /v1/admin/users is called with that role Then respond 403 with type \".../errors/privilege-escalation\" And no account is created" | FR-8 |
| MU-AC9 | "Given an authenticated admin and a current ETag for the target user When PATCH /v1/admin/users/{id} is called with If-Match and a whitelisted field Then respond 200 with the updated resource and a new ETag And one admin_audit_log row is written per changed field (old_value, new_value, actor, reason)" | FR-9 |
| MU-AC10 | "Given the record changed since the admin last read it When PATCH /v1/admin/users/{id} is called with the stale If-Match value Then respond 412 and no field is changed Given the If-Match header is absent Then respond 400 with type \".../errors/precondition-required\"" | FR-10 |
| MU-AC11 | "Given a request body containing id, created_at, email_verified, roles or an unknown field When PATCH /v1/admin/users/{id} is called Then respond 422 with type \".../errors/immutable-field\" or \".../errors/validation-failed\" And no field is changed Because role changes go through US-3.2 and email changes through the verified flow in US-1.3" | FR-11 |
| MU-AC12 | "Given a user id that does not exist When PATCH /v1/admin/users/{id} is called Then respond 404 with type \".../errors/not-found\"" | FR-12 |
| MU-AC13 | "Given an authenticated admin with users:write and an active target user When POST /v1/admin/users/{id}/deactivate is called with a required {reason} Then respond 200 And users.status becomes \"deactivated\" and deactivated_at is set And revoke_before:{target_id} is set to now, killing all access and refresh tokens And an account_lifecycle_audit_log entry is written (event=deactivated, actor=admin:{admin_id}, reason) Because these are exactly US-1.4 DA-AC1's side effects, per the DA-AC10 invariant" | FR-13 |
| MU-AC14 | "Given a target user whose status is already \"deactivated\" When POST /v1/admin/users/{id}/deactivate is called Then respond 409 with type \".../errors/already-deactivated\"" | FR-14 |
| MU-AC15 | "Given an admin whose id equals the target id When POST /v1/admin/users/{id}/deactivate is called Then respond 409 with type \".../errors/cannot-target-self\" And the self-service endpoint POST /v1/account/deactivate must be used instead" | FR-15 |
| MU-AC16 | "Given the target user is the only remaining active account holding the admin role When POST /v1/admin/users/{id}/deactivate is called Then respond 409 with type \".../errors/last-admin\" And the account remains active, so the system can never be locked out of administration" | FR-16 |
| MU-AC17 | "Given any actor When DELETE /v1/admin/users/{id} is called Then respond 405 Method Not Allowed Because erasure is handled only by the retention job in US-1.4 DA-AC9" | FR-17 |
| MU-AC18 | "Given an authenticated admin with users:write and a target user whose status is \"invited\" When POST /v1/admin/users/{id}/resend-invite is called Then respond 202 with a generic body And any previously issued, unconsumed invitation token for that account is invalidated And a fresh token with a 24-hour TTL is emailed to the address on file And an admin_audit_log entry is written (event=invitation_resent, actor=admin:{id}) Because the user id, its roles and its audit history must survive — recreating the record would not" | FR-18 |
| MU-AC19 | "Given a target user whose status is \"active\" or \"deactivated\" When POST /v1/admin/users/{id}/resend-invite is called Then respond 409 with type \".../errors/invalid-state-transition\" And no email is sent Because an active user needing access should use password reset (US-2.4), not an invitation" | FR-19 |
| MU-AC20 | "Given an invitation was resent to the same account less than 60 seconds ago When POST /v1/admin/users/{id}/resend-invite is called again Then respond 429 with a Retry-After header And the per-account limit is 5 resends per hour, mirroring US-1.2 VE-AC7" | FR-20 |
| MU-AC21 | "Given an unknown user id Then respond 404 Given an actor without users:write Then respond 403, and the denied attempt is audited" | FR-21 |

FR-17b, FR-22, and FR-23 have no source AC — all three are derived from Open Decisions (OD-3 for FR-22/FR-23; the Deactivate-slice precedent resolution for FR-17b) per this template's rule that a gap the source never specified is logged, not invented, until the user resolves it.
