# API Design: View Audit Information (US-3.3 / spec US-3.3)

**Source spec:** docs/specifications/US-3.3-spec.md
**Spec review:** docs/reviews/specifications/US-3.3-spec-review.md (Pass with Issues, third run, 2026-09-02)
**OpenAPI fragment:** docs/designs/api/US-3.3-openapi.yaml

## Endpoints

### `GET /v1/admin/audit-logs`

Filtered, cursor-paginated, newest-first query (FR-1). Requires `audit:read`. Query params: `actor_id`, `event`, `target_id` (all optional filters), `from`/`to` (bound the window to 90 days, FR-5), `cursor`/`limit` (keyset pagination; `limit` capped at 100, invalid `cursor` rejected — both per the `app/modules/admin_users::list_users` precedent, spec's OD-5). Two side effects on success, not part of the response shape: a self-audit entry (FR-2, `event=audit_log_viewed`) recording the actor and exact filter parameters, and — on a `403` — a denial entry (FR-3).

### `PATCH` / `PUT` / `DELETE /v1/admin/audit-logs`

Always `405 Method Not Allowed`, for every actor including an administrator (FR-4). No request body is read. Unlike `FR-3`'s `insufficient-permission` or `FR-5`'s `range-too-wide`, the source story's amended AU-AC4 states no `problem+json` `type` slug for this response — this contract uses FastAPI's default `405` (empty body beyond the standard `Allow` header) rather than inventing one.

## Cross-Cutting Patterns Reused, Not Invented

- `401`/`403 insufficient-permission` follow the same established pattern as every other admin-gated endpoint in this project (US-3.1 MU-AC2/MU-AC3 precedent).
- `limit`/`cursor` bounds and their `422 validation-failed` shape reuse the shipped `admin_users` list endpoint's mechanics verbatim (spec's OD-5) rather than inventing new pagination semantics.
- The list response envelope (`{"items": [...], "next_cursor": str | null}`) mirrors `admin_users`'s `UserListResponse` shape.

## Per-Entry Path Not Modeled

AU-AC4's "or any entry" implies `PATCH`/`PUT`/`DELETE /v1/admin/audit-logs/{id}` should also `405`. No `GET /v1/admin/audit-logs/{id}` (single-entry read) exists anywhere in the story or spec, so no route pattern for `{id}` is registered at all — Starlette/FastAPI returns `404` for any method on a genuinely unregistered path, not `405`. Satisfying AU-AC4's "or any entry" literally would require either registering a `{id}` path (with no defined `GET` behavior to anchor it) or an application-wide catch-all handler. Not decided here — flagged for PLANNING, since it's a routing-architecture choice, not an API-contract-shape one.

## Open Questions Not Resolved by the Spec (deferred to PLANNING, not decided here)

Carried forward from `US-3.3-spec-review.md` rather than answered in this contract:

1. **Historical-row field availability (FR-1).** `actor_role`/`outcome`/`category` aren't stored on any of the four existing per-domain tables today; whether the view synthesizes them for pre-migration rows or the field-list guarantee only holds going forward is unresolved. `AuditLogEntry` in the OpenAPI schema declares all of them `required` per the AC's literal text — this contract does not weaken that, but implementation may not be able to honor it for old rows without a decision here.
2. **Write target for the self-audit/denial entries (FR-2/FR-3).** Whether `audit_log` is itself a writable central table or a read-only view over the four existing per-domain tables is unresolved (OD-1 settled the name, not the shape) — this determines which table `event=audit_log_viewed`/denial rows actually land in. Not an API-contract question, but this endpoint's own side effects depend on it.
3. **Single missing `from`/`to` bound.** FR-5 only specifies behavior for both-omitted or over-90-days; a single missing bound (reject/default/open-ended) is unstated. The OpenAPI contract marks both params optional and independent, consistent with the AC's literal silence on this case.
4. **`limit`'s default value.** The story's AC shows `limit=50` as an example, not a stated default. This contract's schema declares `default: 50` as the closest-available reading, but the source never actually commits to that number as the default when `limit` is omitted entirely.
5. **"Fields marked sensitive" enumeration (FR-6).** Beyond the four named exclusions, the complete redaction list is undefined — not an API-shape question, but relevant to what `AuditLogEntry.event`/other free-text-adjacent fields may ever contain.
