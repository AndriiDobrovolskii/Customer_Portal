# API Design: US-2.1 Login

**Contract:** `US-2.1-openapi.yaml`
**Spec:** `docs/specifications/US-2.1-spec.md` (Pass with Issues, accepted 2026-08-31 — `docs/reviews/specifications/US-2.1-spec-review.md`)

## Endpoint in this story's contract

Only `POST /v1/auth/login` (FR-1–FR-6) belongs to US-2.1's own contract:

| Method | Path | Auth | Success | Failure |
|---|---|---|---|---|
| POST | `/v1/auth/login` | None (public) | `200` + `{access_token, token_type, expires_in}` + `Set-Cookie: refresh_token` | `401` invalid-credentials (FR-2, FR-3), `403` email-not-verified / account-deactivated (FR-4), `422` validation-failed (FR-6), `429` too-many-attempts (FR-5) |

- **Anti-enumeration (FR-2/FR-3):** the `401` response for wrong password and unknown email is one schema, `InvalidCredentialsProblem` — deliberately not two, so nothing in the contract itself could tempt an implementer into a distinguishing field. NFR-002 governs.
- **Two `403` problem types, one status code (FR-4):** `oneOf` in the `403` response schema, not a shared body — `email-not-verified`'s type slug is owned by US-1.2 (VE-AC5) and `account-deactivated`'s by US-1.4 (DA-AC6); this story reuses both, introduces neither. Credential verification always precedes this check (spec FR-4), so the ordering guarantee is a service-layer invariant, not something the contract alone can enforce — flagged for `planner`/`service-and-router-builder`.
- **Reactivation branch (resolved OD-10, added 2026-08-31):** a deactivated account within its 30-day grace period does **not** hit the `403` response at all — it reactivates and returns the same `200 LoginResponse` as FR-1's ordinary success path. No new response schema is needed; the `403 AccountDeactivatedProblem` response now applies only to the past-grace-period case. This is a contract-shape clarification, not a new endpoint or schema.
- **Token signing (resolved OD-1):** `LoginResponse.access_token` is described as HS256-signed via the project's existing shared secret, not RS256/JWKS — this closes the gap the spec's Assumption Resolutions section flagged, expressed as an explicit contract-level note so `schema-builder` doesn't need to cross-reference the decision log.
- **Empty-string password (resolved OD-8):** expressed directly as `minLength: 1` on `LoginRequest.password`, so Pydantic's own validation produces the `422` — no service-layer branch needed for this case.
- **Retry-After (FR-5):** modeled as a response header on `429`, seconds until the *triggering* counter's window clears (account or IP, whichever caused the throttle) — the spec doesn't state which counter's remaining TTL should be reported when both are near their limits simultaneously; see Open Questions below.
- **No `security:` requirement:** this is the one auth endpoint that is deliberately unauthenticated (`security: []`), consistent with every other login/registration-adjacent endpoint in this project.

## Requirements described by the spec but not new to this contract

FR-1's account-state checks depend on `users.status`/`users.email_verified` already existing (US-1.1–US-1.4, shipped) — this story reads them, doesn't define them. `db-designer` only needs to add the new `auth_audit_log` table; no changes to `users` are required.

## Existing implementation this contract supersedes

`app/modules/users/router.py`/`service.py:authenticate_user` already implements a *minimal* `POST /v1/auth/login` (commit `90a612b`, scoped to VE-AC5/VE-AC6 only). Flagged here so `planner`/`service-and-router-builder` extend it rather than rediscover the gap during IMPLEMENTATION:

- Current `LoginResponse` has only `access_token`/`token_type` (`token_type: str = "bearer"`, lowercase) — this contract requires `token_type: "Bearer"` (capital B, per the spec's Success Response Schema) and adds `expires_in`.
- Current `InvalidCredentialsError` (`app/modules/users/exceptions.py`) is a bare `DomainError`, not a `ProblemError` with `type_slug`/`status` set — it isn't yet wired to render the `401 invalid-credentials` problem+json body this contract requires.
- Current `authenticate_user` raises immediately when `user is None` (no dummy-hash verification) — FR-3's comparable-timing requirement is unimplemented.
- Current `authenticate_user` checks only `email_verified`, never `UserStatus.DEACTIVATED` (`users.deactivated_at`/`status` both already exist on the model, per US-1.4) — FR-4's deactivated branch is unimplemented.
- No brute-force throttling, no `auth_audit_log` writes, no refresh-token cookie, no `users.last_login_at` update exist yet anywhere in the login path.
- The revocation substrate question US-1.4's own API design flagged as an open architectural question ("Valkey `revoke_before` vs. Postgres `user_sessions.revoked_at`") is **resolved** as of the merged US-1.4 implementation: `app.core.revocation_cache.RevocationCache` + `revoke_before:{user_id}` in Valkey, fail-closed. Login does not need to re-litigate this — it only needs to gate on `users.status`/`email_verified`, the same way the existing minimal endpoint already does for `email_verified`.

## Open Questions (not resolved by the spec — logged per openapi-designer's escape hatch)

1. **Retry-After value when both the account and IP counters are near their limits.** FR-5 doesn't state which counter's remaining-TTL should populate `Retry-After` when a request is throttled by both simultaneously (e.g. account counter has 3s left, IP counter has 200s left). Recommend the longer of the two remaining TTLs (the caller genuinely cannot succeed until both clear), but this is a `planner`/implementation decision, not decided here.
2. **`auth_audit_log`'s `actor_id` type for the unknown-email case (FR-3).** The spec states `actor_id` is null/absent when no account matched. `db-designer` needs to confirm the column is nullable (it will be, given FR-3), noted here so it isn't missed.

## Out of scope (per spec)

Refresh/rotation mechanics (US-2.3), session termination (US-2.2), MFA challenge branch (US-2.5), registration/email verification (US-1.1, US-1.2), RS256/JWKS signing (resolved OD-1), mobile JSON-body refresh transport (resolved OD-2) — unchanged from `docs/specifications/US-2.1-spec.md#out-of-scope`.
