# Spec Review: Manage Roles

**Original Story:** docs/backlog/US-3.2-manage-roles.md
**Spec Reviewed:** docs/specifications/US-012-manage-roles-spec.md
**Story ID:** US-012 (spec's own Story ID field; the backlog story itself is filed as US-3.2)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All seven Acceptance Criteria in US-3.2 (MR-AC1–MR-AC7) are fully and accurately covered by FR-1–FR-7 in the spec, with no contradictions and no scope creep — the FRs are faithful prose renderings of the Gherkin ACs, and the Background/Non-Functional/Out of Scope sections track the source's Assumptions table, Data Model Notes, and Out of Scope section closely. The spec's own Open Questions section is thorough, correctly surfacing real gaps in the source (role-to-scope mapping, audit logging on three of the four negative paths, ETag-mismatch behavior, check-precedence ordering, duplicate role handling) rather than silently inventing answers. The issues found here are narrower: FR-3 does not reproduce the concrete JSON response shape the source's API Contract table defines for `GET /v1/admin/roles`, and two operationally plausible boundary conditions implied by the source's own scope (a non-existent target user, and a `PUT` with an empty `roles` array) are addressed by neither the story nor the spec.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| MR-AC1 | "Given an authenticated admin with roles:write and a current ETag for the target user When PUT /v1/admin/users/{id}/roles is called with If-Match and {\"roles\": [\"support_agent\"]} Then respond 200 with the resulting role set And the operation is a full replacement, so it is idempotent on repeat And perm_epoch:{target_id} is set to now in Valkey And an admin_audit_log entry is written with the old and new role sets and the actor" | Covered | FR-1 | Matches verbatim in substance. |
| MR-AC2 | "Given a target user with a live session whose access token was issued before the role change When that user calls any authenticated endpoint Then respond 401 with type \".../errors/token-stale\" And when the client then calls POST /v1/auth/refresh, a new access token is issued carrying the updated scopes Because perm_epoch invalidates access tokens only, leaving the refresh family intact" | Covered | FR-2 | Matches verbatim in substance. |
| MR-AC3 | "Given an authenticated admin When GET /v1/admin/roles is called Then respond 200 with each role and the permission scopes it grants" | Covered | FR-3 | Substance matches; FR-3 additionally requires the `users:read` scope, correctly cited as drawn from the source's API Contract table rather than the AC's own Gherkin text. Response JSON shape not reproduced — see Ambiguities. |
| MR-AC4 | "Given a request containing a role name that is not in the catalogue When PUT /v1/admin/users/{id}/roles is called Then respond 422 with type \".../errors/validation-failed\" And the entire request is rejected — no role in the list is applied" | Covered | FR-4 | Matches verbatim in substance. |
| MR-AC5 | "Given an admin whose id equals the target id When PUT /v1/admin/users/{id}/roles is called Then respond 403 with type \".../errors/cannot-target-self\" Because an admin must not be able to grant themselves permissions unilaterally" | Covered | FR-5 | Matches verbatim in substance. |
| MR-AC6 | "Given an admin attempting to grant a role containing a permission they do not themselves hold When PUT /v1/admin/users/{id}/roles is called Then respond 403 with type \".../errors/privilege-escalation\" And an admin_audit_log entry is written (event=authz_denied, severity=high)" | Covered | FR-6 | Matches verbatim in substance. |
| MR-AC7 | "Given the target is the only active account holding the admin role When PUT /v1/admin/users/{id}/roles is called with a set that excludes admin Then respond 409 with type \".../errors/last-admin\" And the check and the update run in one transaction, so two concurrent requests cannot together remove both remaining admins" | Covered | FR-7 | Matches verbatim in substance. |

## Ambiguities & Non-Verifiable Statements

- **[Medium] Concrete response JSON shape not reproduced for the role catalogue** — Spec says (FR-3): "the system responds `200` with each role and the permission scopes it grants." The source's API Contract table states the exact success shape: `` 200 `{"roles": [{"name", "permissions": [...]}]}` `` (US-3.2-manage-roles.md, line 34). The spec does not carry this field-level shape into FR-3 or any dedicated schema section. A developer or QA engineer could not write an exact response-schema/contract test directly against the spec text as written — they would need to cross-reference the original story's API Contract table for the concrete field names and nesting.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Medium] Non-existent target user** — Neither the story nor the spec state what `PUT /v1/admin/users/{id}/roles` (or, by extension, any of the checks in MR-AC1/MR-AC4–MR-AC7 / FR-1, FR-4–FR-7) returns when `{id}` does not correspond to an existing user. All seven ACs and FRs implicitly assume the target exists. Does the source's scope reasonably imply a 404 case here, and if so what error `type` should it use?
- **[Low] Empty `roles` array on PUT** — The source's Assumptions table states assignment semantics as "`PUT` replaces the full set... removals are explicit rather than implied" (US-3.2-manage-roles.md, Decision #2), and MR-AC1/FR-1 describe the operation as "a full replacement." Neither the story nor the spec (FR-1) state whether `{"roles": []}` is a valid request that leaves a user with zero roles, or whether it is rejected. If accepted, how would it interact with MR-AC7's last-admin check when the target is not currently an admin?

## Verdict Rationale

Pass with Issues: all seven ACs are fully covered with no contradictions and no unsupported scope additions, so this does not rise to Fail. The Ambiguity and Missing Edge Case findings above — an unreproduced response schema and two unaddressed boundary conditions (non-existent target, empty role set) — are worth resolving before implementation begins but do not block it outright, especially since the spec's own Open Questions section already transparently surfaces several other real gaps in the source rather than silently papering over them.
