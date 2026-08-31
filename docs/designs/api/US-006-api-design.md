# API Design: US-2.2 Logout

**Contract:** `US-006-openapi.yaml`
**Spec:** `docs/specifications/US-006-logout-spec.md` (Pass with Issues, accepted 2026-08-31 — `docs/reviews/specifications/US-006-spec-review.md`)

## Endpoints in this story's contract

| Method | Path | Auth | Success | Failure |
|---|---|---|---|---|
| POST | `/v1/auth/logout` | Bearer, with a logout-only leniency for an already-revoked jti (resolved OD-2) | `204`, clears the refresh cookie if one was present (FR-1, FR-4) | `401` unauthenticated — only for a token that fails to authenticate at all, not one that's merely revoked (FR-3) |
| POST | `/v1/auth/logout-all` | Bearer, standard (no leniency) | `204` (FR-2) | `401` unauthenticated, standard rejection including an already-revoked jti (FR-5) |

- **Route path matches the deployed prefix, not the story's literal path:** per US-005's own precedent, the actual mounted path is `/api/v1/auth/logout` (`app/api/v1/router.py` mounts `users_router` under `/api/v1`) — this contract documents `/v1/auth/...` per the spec's own path convention, same divergence already disclosed and accepted for login.
- **`/v1/auth/logout`'s idempotency carve-out (resolved OD-2) is a per-route auth exception, not a schema concern.** FR-4/FR-5 require this endpoint — and only this endpoint — to still authenticate a caller whose `user_sessions.revoked_at` is already set. The existing shared dependency (`app/modules/users/dependencies.py::get_current_user` → `UserService.get_authenticated_user`) rejects any revoked jti unconditionally today; it's shared by every authenticated route including `/logout-all`. This contract cannot express "except on this one route" as an OpenAPI construct — flagged as an Open Question below for `planner`/`service-and-router-builder` to resolve at the dependency-injection level, not decided here.
- **No response body on `204`.** Neither success response returns JSON — `LO-AC1`/`LO-AC2`/`LO-AC4` all specify `204` with no body content, distinguishing this from every prior story's `200`-with-body pattern.
- **`Set-Cookie` on `/logout` is conditional, not a schema field.** It's present only when a refresh cookie was sent on the request (resolved OD-6) — there's no request-body field to gate this on, so the condition is stated in the response description rather than as a schema constraint.
- **Lookup-miss behavior (spec-review finding, resolved 2026-08-31) does not change the contract's response shape.** A refresh cookie whose value matches no `refresh_tokens` row still produces the identical `204` + conditional cookie-clear as the matched case — this is a service-layer branch, invisible at the contract level by design (anti-enumeration intent).
- **No new error `type` slugs.** Both `401` responses reuse the project's existing `UnauthenticatedError`/`unauthenticated` type slug (`app/modules/users/exceptions.py`) — per the spec's own NFR, this story introduces none.

## Open Questions (not resolved by the spec — logged per openapi-designer's escape hatch)

1. **How does `/v1/auth/logout`'s revoked-jti leniency (OD-2) get implemented without weakening every other route?** The shared `get_current_user` dependency currently returns `None` (→ `401`) for any revoked jti, and every authenticated route in the project depends on that same function. Implementing OD-2 requires either (a) a second, logout-specific dependency/service method (e.g. `get_authenticated_user(token, allow_revoked=True)`) used only by `POST /v1/auth/logout`'s router function, or (b) some other mechanism that keeps `/logout-all` and every other route on the strict path. Recommend (a) — an explicit opt-in parameter is harder to accidentally reuse than a separate near-duplicate function — but this is a `planner`/`service-and-router-builder` decision, not decided here.
2. **Does `/v1/auth/logout`'s leniency also need to distinguish "jti unknown entirely" (never issued, or a session row that's expired and been pruned) from "jti revoked"?** FR-4's leniency is specifically for *revoked* sessions; a jti that never existed at all should presumably still `401` like today. The spec's OD-2 resolution doesn't explicitly address this distinction (it discusses "already revoked," not "never existed") — recommend treating "no matching session row" as a standard `401` (unchanged from today), and only a `revoked_at IS NOT NULL` match gets the `204` leniency, but flagging for confirmation since it's not explicitly stated.

## Existing implementation this contract supersedes

No `POST /v1/auth/logout` or `/v1/auth/logout-all` route exists yet anywhere in `app/modules/users/router.py` — this is new, not an extension of a minimal existing endpoint (unlike login/US-2.1, which extended a pre-existing minimal handler).

## Out of scope (per spec)

Per-device session listing and selective revocation (US-2.6), account deactivation's own revocation trigger (US-1.4), CSRF protection (resolved OD-4 — no CSRF mechanism exists anywhere in the codebase; tracked as a separate follow-up), refresh-token single-use consumption/rotation (`consumed_at`, remains US-2.3's responsibility) — unchanged from `docs/specifications/US-006-logout-spec.md#out-of-scope`.
