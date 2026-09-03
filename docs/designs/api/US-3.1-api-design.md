# API Design: Manage Users (US-3.1 / spec US-3.1)

**Source spec:** docs/specifications/US-3.1-spec.md (revised 2026-09-02)
**Spec review:** docs/reviews/specifications/US-3.1-spec-review.md (Pass with Issues, accepted 2026-09-02)
**OpenAPI fragment:** docs/designs/api/US-3.1-openapi.yaml

## Endpoints

### `GET /v1/admin/users`

Cursor-paginated, filtered directory search (FR-1). Requires `users:read`. Query params per the source story's API Contract table: `q`, `status`, `role`, `cursor`, `limit`. `422` on `limit=5000`, an unknown `status`, or a malformed `cursor` (FR-4) — no partial result set.

### `GET /v1/admin/users/{id}`

Single-resource fetch (FR-22/FR-23, Open Decision OD-3 — no source AC). Same item shape as one list entry, plus an `ETag`. Requires `users:read`; `404` on an unknown id, mirroring FR-12's Update behavior.

### `POST /v1/admin/users`

Invitation-only creation (FR-5). Requires `users:write`. `409 email-already-registered` on a duplicate (FR-6, BR-001's atomic data-layer enforcement). `422 validation-failed` on a `password` field or any field outside the schema (FR-7) — the request schema simply never declares a `password` property, so `additionalProperties: false` does this without a dedicated check. `403 privilege-escalation` when the requested `roles` grant a permission the caller doesn't hold (FR-8), reusing US-3.2's `RoleService` privilege-check mechanism.

### `PATCH /v1/admin/users/{id}`

Correct whitelisted fields (FR-9). Requires `users:write` and `If-Match`. `400 precondition-required` when `If-Match` is absent, `412` when it's stale (FR-10) — both slug and mechanism reused verbatim from `app/modules/profile/exceptions.py`. `422 immutable-field` when the body contains `id`/`created_at`/`email_verified`/`roles` (checked against the raw body before schema validation, mirroring `app/modules/profile/service.py`'s `_IMMUTABLE_FIELD_NAMES` pattern), `422 validation-failed` for `email` or any other undeclared field (FR-11). `404` on an unknown id (FR-12). On success, one `admin_audit_log` row is written per changed field, using the `field`/`old_value`/`new_value`/`reason` columns OD-1 added to that table.

### `POST /v1/admin/users/{id}/deactivate`

Admin-initiated deactivation (FR-13). Requires `users:write` and a mandatory `{reason}`. Applies DA-AC1's side effects (`status`, `deactivated_at`, `revoke_before`) plus writes `reason` into the nullable column OD-2 added to `account_lifecycle_audit_log`. `409` covers three distinct causes with distinct `type` slugs: already-deactivated (FR-14), self-targeting (FR-15), and last-admin (FR-16, reusing US-3.2's `RoleService.count_active_admins_excluding`). `404` on an unknown id (FR-17b — no source AC, resolved by precedent with FR-12/FR-21 during SPECIFICATION).

### `DELETE /v1/admin/users/{id}`

`405` for any authenticated caller, `401` for an unauthenticated one (FR-17). **Resolved tension (2026-09-02):** MU-AC17's "any actor" and MU-AC3's blanket "no valid access token → 401 on any `/v1/admin/*` endpoint" both apply to this route, and read together as: authentication still gates the route (401 without a token), but once authenticated, every caller gets 405 regardless of role or permission scope — "any actor" describes the *lack of a permission check*, not an exemption from authentication. No request/response body beyond the status.

### `POST /v1/admin/users/{id}/resend-invite`

Reissue an invitation (FR-18). Requires `users:write` and target status `invited`. `409 invalid-state-transition` for `active`/`deactivated` targets (FR-19). `429` with `Retry-After` on the 60-second cooldown or 5/hour cap (FR-20), reusing `app/modules/email_verification/exceptions.py`'s `TooManyAttemptsError` mechanism. `404`/`403` mirror FR-2/FR-12 (FR-21).

## Cross-Cutting Patterns Reused, Not Invented

- `401` on every endpoint and `403 insufficient-permission` for a missing scope are the same pattern every other admin-gated endpoint in this project uses (established by this story's own MU-AC2/MU-AC3, and the shared auth middleware NFR-004 describes).
- The `ETag`/`If-Match` mechanics reuse `app/core/etag.py`'s `compute_profile_etag` (a strong ETag over a defined field set) and `app/modules/profile/service.py`'s `If-Match`-absent/stale handling (`PreconditionRequiredError`/`PreconditionFailedError`, 400/412) verbatim — this project's only existing ETag precedent, previously unavailable to US-3.2 (see that story's own Open Question 7, now resolved: `GET /v1/admin/users/{id}` from this story is exactly the endpoint a caller uses to obtain a target user's first ETag, for both this story's own `PATCH` and US-3.2's `PUT .../roles`).
- `UpdateUserRequest`'s editable field set (`display_name`, `locale`, `timezone`, `avatar_url`) is reused verbatim from US-1.3's `ProfileUpdate` schema, minus `email`/`current_password` — same underlying `User` model columns, same "whitelisted field" concept the story names but never enumerates itself.
- The immutable-vs-validation-failed split on `PATCH` (FR-11) reuses `app/modules/profile/service.py`'s exact two-step check: raw-body-keys-against-a-known-immutable-set first (→ `immutable-field`), then Pydantic `model_validate` on the remainder (→ `validation-failed`).
- The `429`/`Retry-After` mechanism on `resend-invite` (FR-20) reuses `app/modules/email_verification/exceptions.py`'s `TooManyAttemptsError` pattern (a `ProblemError` subclass that sets `self.headers = {"Retry-After": ...}` dynamically).
- `422 validation-failed`'s body shape (`errors: [{field, message, code}]`) reuses `app/core/exceptions.py`'s existing `FieldError` dataclass, already used by every other module in this codebase — not a new shape.

## Open Questions Not Resolved by the Spec (deferred to PLANNING, not decided here)

Per the OpenAPI Designer skill's own rule — "If the OpenAPI design needs a constraint the spec never stated, that's a spec gap — log it rather than deciding it here" — the following are this contract's own choices, not stated by the story or spec, and should be confirmed (or overridden) at PLANNING:

1. **List response envelope field names.** `UserListResponse`'s `items`/`next_cursor` naming is this contract's own choice — the story says only "cursor-paginated list," not an envelope shape.
2. **Cursor encoding.** Opaque string assumed; the actual encoding (offset-based, keyset-based on `created_at`/`id`, etc.) is an implementation decision for `data-layer-builder`, not fixed here.
3. **`q`'s matched field(s).** The story's example (`q=smith`) implies at least `display_name` and/or `email`; neither the story nor the spec states which columns `q` searches or whether it's prefix-only vs. substring — the spec's Data Model Notes only says the search needs an index (`pg_trgm` or `tsvector`), not which columns it covers.
4. **`limit`'s valid range/default.** Only the rejected value (`5000`) is stated (FR-4); this contract's own choice of `maximum: 100` is not derived from the story.
5. **412's error `type` slug name.** The story's Error Envelope slug list names `precondition-required` (400) but not a distinct slug for 412; this contract reuses `precondition-failed` from `app/modules/profile/exceptions.py`'s existing precedent rather than inventing a new one, but the story itself never names it.
6. **429's error `type` slug name.** Same situation as above — not in the story's introduced-slugs list; this contract reuses `too-many-requests`, following the existing `email_verification` module's convention as the closest live example (that module's own error type naming, not literally copied since it predates this story's slug-naming discipline).
7. **`ResendInviteResponse`'s exact shape.** The story says only "a generic body" (MU-AC18) — this contract defines an empty object; a future story could add fields without breaking this contract's `202` response, but nothing here should be read as excluding that.
8. **Immutable-field check does not cover `email`.** MU-AC11's immutable list is `id`, `created_at`, `email_verified`, `roles` — it does not name `email`, even though the spec's Out of Scope section excludes email changes from this endpoint. This contract treats a submitted `email` as `validation-failed` (undeclared field), not `immutable-field`, since the story's own MU-AC11 list doesn't include it — flagged here in case `story-spec-writer`/the user intended `email` to share the `immutable-field` treatment instead.
9. ~~**`PATCH`'s request body has no `reason` field.**~~ **Resolved by `planner` 2026-09-02** (`US-3.1-implementation-plan.md` Architectural Change #4): `UpdateUserRequest` now requires `reason`, mirroring `deactivate`'s explicit `{reason}`.
