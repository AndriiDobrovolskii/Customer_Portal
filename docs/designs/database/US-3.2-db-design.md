# DB Design: Manage Roles (US-3.2 / spec US-3.2)

**Source spec:** docs/specifications/US-3.2-spec.md (Data Model Notes: "roles, permissions, role_permissions, user_roles")
**Spec review:** docs/reviews/specifications/US-3.2-spec-review.md (Pass with Issues, accepted 2026-09-01)
**API design:** docs/designs/api/US-3.2-openapi.yaml

## Overview

This story introduces the first role/permission persistence in the codebase — confirmed by inspection that `app/modules/users/models.py`'s `User` model currently has no role association at all (this was the structural gap identified as US-2.5's blocking OD-1). Four new tables: `roles` and `permissions` as fixed, seeded catalogues; `role_permissions` and `user_roles` as many-to-many association tables. No existing table's columns change — `users` gains a relationship, not a column, since role membership is purely relational (matching FR-1's "full replacement" semantics, which is naturally a set-membership operation, not a scalar field).

## `roles`

Fixed, seeded catalogue (spec Background: "fixed and seeded with four roles"). Seed data (via migration `INSERT`, not application code) populates exactly `customer`, `support_agent`, `admin`, `auditor` — no create/update/delete endpoint exists in this story's scope, so this table is effectively read-only at the application layer.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid4()` | PK, matches this project's uniform UUID-PK convention (every existing table). |
| `name` | `String(32)` | No | — | Unique. One of the four catalogue values; uniqueness enforced at the DB layer, membership-in-catalogue enforced by the OD-1 CI completeness check, not a DB `CHECK` constraint (spec states no such constraint). |

**Indexes:** unique index on `name` (lookup by role name, e.g. resolving `"admin"` in the last-admin check).

## `permissions`

Fixed, seeded catalogue of the six scope strings (spec Background: `users:read`, `users:write`, `roles:write`, `audit:read`, `tickets:read`, `tickets:write`).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid4()` | PK. |
| `scope` | `String(32)` | No | — | Unique. One of the six catalogue values. |

**Indexes:** unique index on `scope`.

## `role_permissions`

Many-to-many association: which permission scopes each role grants. Modeled as an explicit association class (not a bare SQLAlchemy `secondary=` table) so the OD-1 CI completeness check and FR-6's privilege-escalation comparison can query it directly.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `role_id` | UUID | No | — | FK → `roles.id`, `ondelete="CASCADE"`. Part of composite PK. |
| `permission_id` | UUID | No | — | FK → `permissions.id`, `ondelete="CASCADE"`. Part of composite PK. |

**Primary key:** composite (`role_id`, `permission_id`) — no separate surrogate key needed; a role either grants a scope or it doesn't, no attributes on the edge itself.

**Indexes:** the composite PK covers `role_id`-first lookups (reading a role's full permission set — needed by `GET /v1/admin/roles` FR-3 and by FR-6's escalation check). No additional index needed at this table's expected size (4 roles × 6 scopes, at most 24 rows).

**Gap not decided here:** the source spec doesn't state the actual role→scope mapping (spec Open Question: "Which permission scopes does each of the four seeded roles grant?"). The seed migration's `INSERT` values for this table cannot be written until that's resolved — flagged for PLANNING, referencing `docs/decisions/US-3.2-open-decisions.md` and the spec's own Open Questions section.

## `user_roles`

Many-to-many association: which roles a user currently holds. This is the table `PUT /v1/admin/users/{id}/roles`'s full-replacement semantics (FR-1) operate on — a write deletes the user's existing rows and inserts the new set inside one transaction (also required by FR-7's atomicity guarantee for the last-admin check).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `user_id` | UUID | No | — | FK → `users.id`, `ondelete="CASCADE"`. Part of composite PK. Matches the `ondelete="CASCADE"` convention every existing FK to `users.id` in this codebase already uses (`UserSession`, `RefreshToken`, `PasswordResetToken`). |
| `role_id` | UUID | No | — | FK → `roles.id`, `ondelete="CASCADE"`. Part of composite PK. |

**Primary key:** composite (`user_id`, `role_id`) — no attributes on the edge (per-assignment metadata like "who granted this and when" is already captured by `admin_audit_log`'s FR-1-mandated entry, so is not duplicated here — avoids inventing a column the spec doesn't call for).

**Indexes:**
- The composite PK covers `user_id`-first lookups (a user's own role set — needed at login to build the JWT `scopes` claim, and for `PUT .../roles`'s response body).
- A separate index on `role_id` alone is needed for `role_id`-first lookups the composite PK's column order doesn't serve: FR-7's last-admin check ("the only active account holding the admin role" — a count query joining `user_roles` → `users` filtered by `role_id` and `users.status`) and FR-1's "old role set" read before a replacement.

## Relationships & Eager-Loading Strategy

Per `AGENTS.md` §3 ("Eager loading is mandatory" — `joinedload` for many-to-one, `selectinload` for collections):

- `User.roles` (collection, via `user_roles` → `Role`): `selectinload`. Needed wherever a user's role set is read as a whole — the login flow's JWT-claims construction (an impact on `app/modules/users/service.py`'s existing `encode_access_token` caller, flagged for `impact-analyzer`, not decided here) and `PUT .../roles`'s response body.
- `Role.permissions` (collection, via `role_permissions` → `Permission`): `selectinload`. Needed for `GET /v1/admin/roles` (FR-3) and FR-6's privilege-escalation comparison (the granting admin's own permission set vs. the requested role's).
- No many-to-one relationship in this story needs `joinedload` — every relationship introduced here is a collection.
- Default `lazy="raise_on_sql"` on every relationship per this project's data-layer convention, so an un-eager-loaded access fails loudly in tests rather than silently issuing N+1 queries or a `MissingGreenlet` in production.

## Security

No sensitive columns introduced by this story — `roles.name` and `permissions.scope` are fixed catalogue strings, not credentials or PII. `user_roles`/`role_permissions` hold only UUID foreign keys.

## Migration Note

Per `AGENTS.md` §4's migrations bullet and this project's Definition of Done: the migration itself (guards, `if_not_exists`, the seed-data `INSERT`s, `upgrade`/`downgrade`/`upgrade` proof) belongs to the implementation stage (`migration-manager`), not this design. `migrations/env.py` must not be edited (AGENTS.md §7.9, resolved as OD-1) — the permission-catalogue completeness check this story's NFR calls for is a standalone CI test, not a migration-time hook, and does not affect this table design.
