# API Design: US-2.6 Active Session Management

**Contract:** `US-010-openapi.yaml`
**Spec:** `docs/specifications/US-010-active-session-management-spec.md` (Pass with Issues, resolved 2026-09-02 — `docs/reviews/specifications/US-010-spec-review.md`)

## Endpoints in this story's contract

| Method | Path | Auth | Success | Failure |
|---|---|---|---|---|
| GET | `/v1/auth/sessions` | Bearer, standard | `200`, one entry per live family (FR-1) | `401` unauthenticated (FR-5) |
| DELETE | `/v1/auth/sessions/{family_id}` | Bearer, standard | `204` — revoked or already idempotent (FR-2, FR-4) | `401` unauthenticated; `404` not-owned/unknown (FR-3); `409` own current session (FR-6) |

- **Route path matches the deployed prefix, not the story's literal path**, per US-2.2/US-2.3's own precedent: the actual mounted path is `/api/v1/auth/sessions` (`app/api/v1/router.py` mounts `users_router` under `/api/v1`) — this contract documents `/v1/auth/...` per the spec's own path convention, same disclosed divergence as every prior story in this epic.
- **Both endpoints require standard Bearer auth** — no per-route auth exception exists here (unlike `/logout`'s revoked-jti leniency, US-2.2). A caller whose access token itself fails to authenticate gets `401` on both routes; nothing here weakens or special-cases the shared `get_current_user` dependency.
- **The "current session" mechanism is a service-layer read, not a request parameter.** Per the spec-review resolution, the router reads the optional `refresh_token` cookie (same cookie `/v1/auth/refresh` and `/v1/auth/logout` already read via FastAPI's `Cookie()`), passes it into the service alongside the bearer-authenticated user, and the service hashes it to find a matching live `RefreshToken.family_id`. This cannot be expressed as an OpenAPI request schema field — it's an implicit input via cookie, documented in each response's description rather than as a formal parameter, mirroring how `/logout`'s conditional `Set-Cookie` behavior was handled in US-006's contract.
- **`GET`'s `is_current` flag and `DELETE`'s `409` share one mechanism.** If the `refresh_token` cookie is absent, expired, or matches no live family, `GET` returns every entry with `is_current: false` and `DELETE` never returns `409` for that request — both endpoints degrade to "no current family is known" rather than erroring, so a caller who authenticates via bearer token alone (no cookie, e.g. a non-browser API client) still gets a complete, valid response.
- **`404` covers three distinct causes with one response shape** (a different user's family, an already-known-but-malformed `family_id`, and a `family_id` that never existed) — deliberately, per FR-3's anti-enumeration rationale carried over unchanged from US-2.2/US-2.3's established pattern in this codebase.
- **One new error slug**: `.../errors/current-session` (`409`, FR-6). This is not in the source story's own Error Envelope section (which names only `not-found`) — a disclosed scope addition from the spec's OD-1 resolution, flagged by the spec review and accepted by the user. `not-found` (`404`) and the shared `unauthenticated` (`401`) slug are both reused as-is from the existing project-wide envelopes.
- **No response body on `204`.** Neither `FR-2` nor `FR-4` describes a body for the successful/idempotent `DELETE` — matches the `204`-no-body pattern already established by `/logout`.
- **`session_evicted` (FR-7) never appears in this contract.** Cap eviction is triggered entirely by the *login* flow (US-2.1's endpoint), not by any endpoint this story adds — it's a service-layer side effect of `POST /v1/auth/login`/refresh's existing family-creation path, out of this story's own API surface. `implementation-planner`/`service-and-router-builder` should treat FR-7 as a change to `UserService`'s login path, not a new route.

## Validation Rules Carried Over

- `family_id` path parameter: UUID format (matches `RefreshToken.family_id`'s type). No spec-stated length/pattern constraint beyond "is a valid identifier" — a syntactically invalid value (fails UUID parsing) folds into the same `404` as an unknown-but-well-formed one, per the spec's resolved malformed-`family_id` precedent (no `400` path exists for this).
- No request body on either endpoint — nothing to validate at the schema level.

## Open Questions (not resolved by the spec — logged per openapi-designer's escape hatch)

None. The spec-review's two Medium findings (current-session identification, concurrent cap-eviction race) were both resolved by the user before this design was drafted and are reflected above and in the contract's response descriptions.

## Existing implementation this contract supersedes

No `GET /v1/auth/sessions` or `DELETE /v1/auth/sessions/{family_id}` route exists yet anywhere in `app/modules/users/router.py` — both are new. The underlying data (`RefreshToken.family_id`/`ip`/`user_agent`/`last_used_at`/`revoked_at`) and the revocation write path (US-2.2's logout mechanism) already exist and are reused, not reimplemented.

## Out of scope (per spec)

Logout of the current session and logout-everywhere (US-2.2, unchanged); admin-facing visibility into another user's sessions (not currently required; would need its own permission and audit story) — unchanged from `docs/specifications/US-010-active-session-management-spec.md#out-of-scope`.
