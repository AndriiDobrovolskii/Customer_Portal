# API Design: Password Reset (US-2.4 / spec US-2.4)

**OpenAPI fragment:** `docs/designs/api/US-2.4-openapi.yaml`
**Spec:** `docs/specifications/US-2.4-spec.md`
**Spec review:** `docs/reviews/specifications/US-2.4-spec-review.md` (Pass with Issues, accepted 2026-09-01)
**Written:** 2026-09-01

## Endpoints

### `POST /v1/auth/password-reset/request`

Unauthenticated. Always responds `202` with an identical generic body (FR-1/FR-3, NFR-002 anti-enumeration) — the only observable variance permitted is the `429` throttling response, which is checked before the account lookup ever distinguishes existence, so it can't itself leak account existence either (a nonexistent account is throttled on the same per-IP counter as a real one).

Three request-throttling limits apply, checked in this order (resolved OD-2): 60 s per-account cooldown → 5/account/hour → 10/IP/hour. `TooManyAttemptsProblem` reuses the `too-many-attempts` slug already established by login (US-2.1) and refresh (US-2.3) rather than introducing a new one.

On a real, eligible account, this endpoint: generates a 32-byte `secrets.token_urlsafe(32)` token (SHA-256 hash persisted), invalidates any prior unconsumed token for the account, sends the reset email with the token in the URL fragment, and writes `auth_audit_log(event=password_reset_requested)` (resolved OD-3). On an unknown or deactivated account: no token, no email — but the audit entry is still written, since that write is server-side only and doesn't affect the response, preserving anti-enumeration.

### `POST /v1/auth/password-reset/confirm`

Unauthenticated — the token itself is the credential (source story's API Contract: "Auth: None (token is the credential)"). Token consumption is atomic (`UPDATE...WHERE consumed_at IS NULL RETURNING`), resolving the spec-review's Missing Edge Cases finding (accepted 2026-09-01): two concurrent `confirm` calls against the same token can never both succeed, mirroring US-2.3's `consume_refresh_token` pattern (RT-AC6).

Three failure paths, all `problem+json`:
- `400 token-invalid` — unknown hash or already-consumed (including the losing side of the atomic race).
- `400 token-expired` — token's `expires_at` has passed.
- `422 password-policy` — new password too short, breached (checked against a local static list/bloom filter, resolved OD-1 — no live network call), or equal to the current password. Token is NOT consumed on this path.

On success: password hash replaced (Argon2id), `revoke_before:{user_id}` set to now (reusing the existing revocation mechanism — already documented in `docs/product/business-glossary.md`'s **Revocation** entry as one of this story's own triggers), notification email sent, `auth_audit_log(event=password_reset_completed)` written.

## Cross-Cutting

- **NFR-001 (secret handling):** the raw token travels only in the URL fragment (never a query string) and the request body — never logged.
- **NFR-002 (anti-enumeration):** covered above; response timing must also be comparable between the real-account and unknown/deactivated-account paths (spec NFR), which PLANNING/IMPLEMENTATION must account for (e.g. still performing an email-lookup-equivalent cost on the unknown path), same discipline as login's `verify_password_dummy()`.
- **NFR-003 (rate limiting):** three-limit structure above.
- **NFR-005 (DB-enforced invariants):** atomic token consumption, same class of guarantee as `US-1.1`'s email uniqueness and `US-2.3`'s refresh-token consumption.
- **NFR-011 (performance):** the spec's own NFR states the request endpoint returns within 300 ms regardless of SMTP latency (email dispatch must not block the response).

## Open Questions (deferred to PLANNING)

- **OQ-1:** Storage form and size of the local breached-password list/bloom filter (OD-1) — a bundled flat list checked via a hash set, or an actual bloom filter structure — is an implementation sizing decision for `db-designer`/`data-layer-builder`, not decided here. Either satisfies this design's contract (the check is a service-layer concern, invisible to the API shape).
- **OQ-2:** Valkey key structure for the three-limit throttle (OD-2) — one combined cache gateway with three counters per account/IP, or three independent keys — needs `db-designer`/`implementation-planner` sizing, following the `RefreshRateLimitCache` precedent (US-2.3) of one dedicated gateway class per rate-limited route.
