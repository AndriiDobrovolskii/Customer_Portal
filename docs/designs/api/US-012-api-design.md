# API Design: Manage Roles (US-3.2 / spec US-012)

**Source spec:** docs/specifications/US-012-manage-roles-spec.md
**Spec review:** docs/reviews/specifications/US-012-spec-review.md (Pass with Issues, accepted 2026-09-01)
**OpenAPI fragment:** docs/designs/api/US-012-openapi.yaml

## Endpoints

### `GET /v1/admin/roles`

Reads the fixed, seeded catalogue and the permission scopes each role grants (FR-3). Requires `users:read` per the source story's API Contract table. No request body, no path/query parameters. Returns `200` with `{"roles": [{"name", "permissions": [...]}]}`.

### `PUT /v1/admin/users/{id}/roles`

Full replacement of a target user's role set (FR-1). Requires `roles:write`. Requires `If-Match` with the target's current ETag. Body: `{"roles": [str]}`. On success, `perm_epoch:{target_id}` is set to now (FR-1), an `admin_audit_log` entry is written, and the response carries a new `ETag` reflecting the updated role set.

Three negative paths share `403` but are distinct `type` slugs: missing `roles:write` entirely (cross-cutting `insufficient-permission`), self-targeting (`cannot-target-self`, FR-5), and privilege escalation (`privilege-escalation`, FR-6, additionally audited with `severity=high`). `409 last-admin` blocks removing the sole remaining admin (FR-7), enforced in one transaction. `422 validation-failed` rejects any role name outside the catalogue (FR-4), with the entire request refused — no partial application.

## Cross-Cutting Patterns Reused, Not Invented

- `401` on both endpoints and `403 insufficient-permission` for a missing scope are the same pattern every other admin-gated endpoint in this project uses (established by US-3.1's MU-AC2/MU-AC3, and the shared auth middleware NFR-004 describes) — included here for contract completeness, not because this story's own ACs restate them.
- The `ETag`/`If-Match` mechanics mirror `app/core/etag.py`'s existing `compute_profile_etag` pattern (a strong ETag over the resource's current field values) and `app/modules/profile/router.py`'s `If-Match` header handling — the implementation stage should follow that precedent rather than inventing a new ETag scheme.

## Open Questions Not Resolved by the Spec (deferred to PLANNING, not decided here)

Per the OpenAPI Designer skill's own rule — "If the OpenAPI design needs a constraint the spec never stated, that's a spec gap — log it rather than deciding it here" — the following are carried forward from `US-012-spec-review.md` rather than answered in this contract:

1. **Missing/stale `If-Match`.** The contract marks `If-Match` `required: true` (per the story's API Contract table), but neither the story nor the spec states the response when it's absent or doesn't match — no `400`/`412` response is defined here pending that decision.
2. **Non-existent target user (`{id}` unknown).** No `404` response is defined; all of FR-1, FR-4–FR-7 implicitly assume the target exists.
3. **Empty `roles` array on `PUT`.** The request schema allows an empty array structurally; whether it's a valid "revoke everything" request or should be rejected is unresolved.
4. **Duplicate role names in the request array.** Not addressed by the request schema constraints (no `uniqueItems`) pending a decision on reject/dedupe/accept.
5. **Check-precedence order** when multiple negative conditions apply to one request (e.g., self-target with an unknown role name) — the contract lists all four negative-path responses but does not encode which one FastAPI/service logic should surface first.
6. **Role-to-scope mapping** for the four seeded roles (needed for `GET /v1/admin/roles`'s actual seed data and for the privilege-escalation check in FR-6) is not stated by the source story.
7. **Initial ETag acquisition.** `PUT .../roles` requires a current `If-Match` value, but this story defines no `GET /v1/admin/users/{id}` (that belongs to US-3.1, not yet built). How a caller obtains the very first ETag for a target user is a cross-story sequencing question for PLANNING, not something this contract can resolve alone.
8. **Admin-bootstrap dependency.** Per the spec's OD-2 resolution, the break-glass command is assumed to exist before this endpoint is reachable at all — not part of this contract, but a deployment precondition.
