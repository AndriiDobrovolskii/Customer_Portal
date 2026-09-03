# API Design: US-2.3 Refresh Token

**Contract:** `US-2.3-openapi.yaml`
**Spec:** `docs/specifications/US-2.3-spec.md` (Pass with Issues, accepted 2026-09-01 — `docs/reviews/specifications/US-2.3-spec-review.md`, all 3 same-day findings resolved)

## Endpoints in this story's contract

| Method | Path | Auth | Success | Failure |
|---|---|---|---|---|
| POST | `/v1/auth/refresh` | Refresh cookie only (no Bearer token) | `200` + `{access_token, expires_in}` + rotated refresh cookie (FR-1) | `401 token-invalid` (FR-2/FR-3/FR-4/FR-6, indistinguishable), `429 too-many-attempts` (FR-2's rate limit, resolved OD-1) |

- **Route path matches the deployed prefix, not the story's literal path:** per US-2.1/US-2.2's own precedent, the actual mounted path is `/api/v1/auth/refresh` (`app/api/v1/router.py` mounts `users_router` under `/api/v1`) — this contract documents `/v1/auth/...` per the spec's own path convention, same disclosed divergence as login and logout.
- **Single `401` type covers four FRs, deliberately.** FR-3's "indistinguishable" requirement (resolved OD-3: status+body only) means the contract cannot and should not expose four separate response schemas for FR-2/FR-3/FR-4/FR-6 — they all render as one `RefreshTokenInvalidProblem`. FR-2's side effects (family revocation, `severity=high` audit entry, security email) are real but invisible at the contract level, same pattern as US-2.2's lookup-miss branch being invisible in its own contract.
- **`429` is a new response shape for this endpoint, but not a new type slug.** Reuses `too-many-attempts` from login (US-2.1/US-2.1) rather than inventing a fresh one — consistent with the spec's own "no new error type slugs" statement, since the spec's claim was scoped to the `401` family and this is a distinct status the spec's Open Decision Resolutions section (OD-1) separately authorizes.
- **Response body has no `token_type` field**, unlike login's `LoginResponse`. The source story's own API Contract table states the success body as exactly `{"access_token": str, "expires_in": 900}` — this is a real, stated divergence from login's response shape, not an oversight in this design.
- **No request body.** The refresh token travels as a cookie, not a JSON payload — consistent with the spec's Out of Scope exclusion of the `X-Client-Type: mobile` body-delivery variant (resolved OD-2).
- **Auth scheme is a new `apiKey`-in-cookie security scheme (`refreshCookieAuth`), not `bearerAuth`.** Every other authenticated endpoint in this project's contracts so far (`logout`, `logout-all`) uses `bearerAuth` (the access token); this is the first endpoint whose sole credential is the refresh cookie itself, so reusing `bearerAuth` would misstate what's actually checked.

## Check order surfaced in the contract

The spec's five-step check order (resolved OD-5, plus the rate-limit position resolved in the 2026-09-01 spec-review addendum) is reflected directly in the `200`/`401`/`429` response descriptions rather than as separate schemas, since only the outcome (which status, which body) is contract-visible:

1. Rate limit (`family_id`-keyed, resolved OD-1) → `429`.
2. Token exists and not expired (also covers the FR-5 absolute cap, same `expires_at` mechanism) → else `401` (FR-3).
3. Token already consumed (reuse) → `401` (FR-2), with invisible side effects.
4. Account eligibility (deactivated / `revoke_before`) → else `401` (FR-6).
5. Idle timeout (`last_used_at`) → else `401` (FR-4).
6. Atomic consume-and-rotate (FR-7) → `200`.

## Open Questions (not resolved by the spec — logged per openapi-designer's escape hatch)

1. **Does the rotated refresh cookie carry the same `HttpOnly`/`Secure`/`SameSite=Strict` attributes login's cookie does?** FR-1 says the endpoint "issues a new refresh token and sets it as the cookie (rotation)," describing the *value* rotating, not independently restating the cookie's attributes. This design assumes continuity with the existing cookie mechanism (same attributes as US-2.1/US-2.1's `LoginResponse` cookie) rather than treating the omission as license to choose differently, but the spec itself never states this — flagged for `db-designer`/`planner` to confirm rather than silently assumed as settled.
2. **Is a `Retry-After` value computable without a `family_id`-keyed TTL store already existing?** OD-1's resolution reuses the `TooManyAttemptsError` *pattern*, but that pattern currently keys by IP/account (`LoginThrottleCacheProtocol`); a `family_id`-keyed equivalent cache/counter doesn't exist yet. Not a contract-level gap (the response shape is settled), but flagged for `db-designer`'s Valkey design to size correctly.

## Existing implementation this contract supersedes

No `POST /v1/auth/refresh` route exists yet anywhere in `app/modules/users/router.py` — this is new. Supporting pieces already exist from US-2.1 (issuance: `generate_refresh_token`, `create_refresh_token`, `family_id`) and US-2.2 (`revoked_at`, `get_refresh_token_by_hash`, `revoke_refresh_token_family`); this story adds the rotation/consumption/reuse-detection behavior itself.

## Out of scope (per spec)

Initial token issuance (US-2.1), session listing (US-2.6), `X-Client-Type: mobile` body-delivery (resolved OD-2), linking `user_sessions` to `refresh_tokens.family_id` for reuse-detection to also kill a live access token (resolved OD-6) — unchanged from `docs/specifications/US-2.3-spec.md#out-of-scope`.
