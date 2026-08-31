# API Design: US-004 Deactivate Account

**Contract:** `US-004-openapi.yaml`
**Spec:** `docs/specifications/US-004-deactivate-account-spec.md` (Pass, `docs/reviews/specifications/US-004-spec-review.md`)

## Endpoint in this story's contract

Only `POST /v1/account/deactivate` (FR-1, FR-2, FR-3) belongs to US-004's own contract:

| Method | Path | Auth | Success | Failure |
|---|---|---|---|---|
| POST | `/v1/account/deactivate` | Bearer (self) | `200` + `{status, deactivated_at}` | `401` invalid-credentials (bad `current_password`, FR-2), `409` already-deactivated (FR-3) |

- **Auth-before-state-check ordering:** password verification happens before the status check, mirroring the existing anti-enumeration pattern in `app/modules/users/service.py:authenticate_user` (verify password before checking `email_verified`). Applied here so a caller who doesn't know the password can't learn "this account is already deactivated" — not explicitly required by FR-1–FR-3, but consistent with the anti-enumeration principle FR-6/FR-7 state elsewhere in the same spec.
- **Idempotency:** deliberately *not* idempotent — a second call from a client that doesn't know it already succeeded gets `409`, per FR-3. This matches the spec's explicit choice (contrast with logout, which US-006 states is idempotent).
- **Concurrency (Clarification #2):** the 200/409 split for two simultaneous requests is a data-layer conditional-update guarantee (`UPDATE ... WHERE status = 'active'`), not something the contract can express — flagged for `db-designer` and the service layer.
- **Response body:** `200` returns the two fields whose new values are directly relevant to a client that just changed the account's own state — no email/name payload duplicating `/v1/profile`.

## Requirements described by the spec but NOT in this story's contract

FR-4 through FR-10 describe behavior that lives in other endpoints or jobs. Recorded here as cross-story invariants this story's implementation must not break, but the routes themselves are out of this contract:

| FR | Behavior | Owning story |
|---|---|---|
| FR-4 | Pre-existing access token rejected after deactivation (`revoke_before` vs. token `iat`) | Shared auth-check path — no single owning story yet; see Open Question 1 below |
| FR-5 | Refresh token rejected after deactivation | US-007 Refresh Token |
| FR-6 | Deactivated account gets `403 account-deactivated` on login with correct credentials | US-005 Login |
| FR-7 | Deactivated account gets generic `401` on login with wrong credentials (no status leak) | US-005 Login |
| FR-8 | Reactivation on login within 30-day grace period | US-005 Login (extension) |
| FR-9 | Scheduled permanent deletion after grace period | New cron story (none exists yet — pattern precedent: `purge_unverified_accounts`, commit `ed6e2a9`) |
| FR-10 | Admin-initiated deactivation applies the identical revocation invariant | US-011 Manage Users (`US-3.1.4 deactivate`, already scoped in `US-011-manage-users-spec.md`) |

US-004 is responsible for the write side of the invariant (setting `revoke_before`/equivalent and the audit row) — every FR-4–FR-8 consumer must read the same signal US-004 writes, but building those consumers is not this story's job.

## Open Questions (not resolved by the spec — logged per openapi-designer's escape hatch)

1. **Revocation substrate mismatch.** The spec (FR-1, FR-4) and `docs/product/business-glossary.md` ("Revocation (`revoke_before`)") both specify a per-user Valkey timestamp key `revoke_before:{user_id}` checked on every authenticated request, consistent with `AGENTS.md`'s architecture (Valkey as the token-denylist substrate, fails closed). The **current** login/session implementation (`app/modules/users/service.py`, `app/modules/users/models.py:UserSession`) instead uses a Postgres `user_sessions` table with per-row `revoked_at`, set via `revoke_sessions_except`, and has no Valkey involvement in the auth path at all. `POST /v1/account/deactivate` cannot correctly set "the" revocation signal until it's decided which of these is authoritative — this affects `db-designer` (does US-004 need a new Valkey write, or a `user_sessions` bulk-revoke query, or both during a transition?) and `data-layer-builder`'s `cache.py`. **Not resolved here** — this is a `planner`-level architectural decision per the spec-review/openapi-designer escape hatch ("if the design needs a constraint the spec never stated, log it, don't decide it"), and it has stakes beyond US-004 since US-005/006/007 will hit the same question. Recommend flagging explicitly at the PLANNING stage.
2. **`users.status` enum extension.** `app/modules/users/schemas.py:UserStatus` currently has `PENDING_VERIFICATION`/(others per US-001–003); confirm `"deactivated"` is added there rather than introduced as a separate ad hoc string, for db-designer.

## Out of scope (per spec)

Full admin deactivation contract, final anonymization mechanics for FR-9, data export before deactivation — unchanged from `docs/specifications/US-004-deactivate-account-spec.md#out-of-scope`.
