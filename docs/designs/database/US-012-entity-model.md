# Entity Model: Manage Roles (US-3.2 / spec US-012)

## Entities

### `Role` (`roles`)

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK |
| `name` | `Mapped[str]` → `String(32)` | No | — | `unique=True` |

### `Permission` (`permissions`)

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK |
| `scope` | `Mapped[str]` → `String(32)` | No | — | `unique=True` |

### `RolePermission` (`role_permissions`)

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `role_id` | `Mapped[uuid.UUID]` | No | — | PK (composite), FK → `roles.id`, `ondelete="CASCADE"` |
| `permission_id` | `Mapped[uuid.UUID]` | No | — | PK (composite), FK → `permissions.id`, `ondelete="CASCADE"` |

### `UserRole` (`user_roles`)

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `user_id` | `Mapped[uuid.UUID]` | No | — | PK (composite), FK → `users.id`, `ondelete="CASCADE"`, index |
| `role_id` | `Mapped[uuid.UUID]` | No | — | PK (composite), FK → `roles.id`, `ondelete="CASCADE"`, index |

## Relationships

```
User (1) ──< UserRole >── (1) Role (1) ──< RolePermission >── (1) Permission
```

| Owning side | Relationship | Cardinality | Loading strategy | Used by |
|---|---|---|---|---|
| `User` | `roles` (via `UserRole`) | one-to-many (association) | `selectinload` | JWT `scopes`-claim construction at login (impact on existing login flow, flagged for `impact-analyzer`); `PUT .../roles` response body (FR-1) |
| `Role` | `permissions` (via `RolePermission`) | one-to-many (association) | `selectinload` | `GET /v1/admin/roles` (FR-3); privilege-escalation check (FR-6) |

Both are collection relationships resolved through an explicit association entity (`UserRole`, `RolePermission`) rather than a bare SQLAlchemy `secondary=` table, so each association can be queried and audited directly (e.g. the OD-1 CI completeness check enumerating `role_permissions` rows against the `permissions` catalogue).

`lazy="raise_on_sql"` is the default on every relationship above, per this project's data-layer convention — an un-eager-loaded access must fail loudly rather than issue a surprise query.

## Indexes Summary

| Table | Index | Purpose |
|---|---|---|
| `roles` | unique on `name` | Resolve `"admin"`/etc. by name (last-admin check, seed lookups) |
| `permissions` | unique on `scope` | Resolve a scope string by value |
| `role_permissions` | composite PK (`role_id`, `permission_id`) | Role→permissions lookup (FR-3, FR-6); no separate index needed at catalogue scale |
| `user_roles` | composite PK (`user_id`, `role_id`) | User→roles lookup (JWT claims, FR-1 response) |
| `user_roles` | secondary index on `role_id` | Role→users lookup (FR-7 last-admin count, FR-1 old-role-set read) |

## Traceability

| Entity/Relationship | Functional Requirement(s) |
|---|---|
| `Role`, `Permission` | FR-3 (catalogue read), Background (fixed/seeded catalogue) |
| `RolePermission` | FR-3, FR-6 (privilege-escalation comparison) |
| `UserRole` | FR-1 (replace role set), FR-2 (perm_epoch propagation depends on knowing the affected user), FR-7 (last-admin count) |
| `User.roles` relationship | FR-1, and the cross-cutting JWT `scopes` claim every FR in this spec depends on being readable |

## Known Gaps (not decided at this stage)

- Role→permission seed mapping is undecided (spec Open Question) — `role_permissions` seed `INSERT` values cannot be written until resolved.
- Whether an empty `user_roles` set for a user (all roles revoked) is valid is unresolved (spec-review Missing Edge Case) — affects nothing in this entity model itself (an empty set is representable — zero rows), but affects the service-layer validation PLANNING must define.
