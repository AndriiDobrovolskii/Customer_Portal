# Implementation Plan: Multi-Factor Authentication / TOTP (US-2.5 / spec US-009)

**Spec:** docs/specifications/US-009-mfa-totp-spec.md
**API design:** docs/designs/api/US-009-openapi.yaml, US-009-api-design.md
**DB design:** docs/designs/database/US-009-db-design.md, US-009-entity-model.md
**Impact analysis:** docs/impact-analysis/US-009-impact-analysis.md (including its two open architectural tensions, resolved below)

## Goal

Add TOTP-based MFA to the existing `users` module: enrolment/activation with recovery codes, a login-time challenge and its verification (with skew tolerance, replay protection, and brute-force lockout), mandatory enforcement for privileged roles via a shared enrolment-scoped-token mechanism with a 14-day grace period, and a second independent trigger for that same mechanism on recovery-code use.

## Architectural Changes

1. **Extends `app/modules/users/`, no new module** — consistent with every prior auth story (login, logout, refresh, password reset) living there.

2. **Enrolment-scoped-token enforcement resolves the impact-analysis tension as: a JWT claim, default-deny.** `AccessTokenClaims`/`encode_access_token()`/`decode_access_token()` gain `mfa_enrollment_required: bool = False`. The **existing** `UserService.get_authenticated_user()` (the single choke point every route already goes through via `CurrentUserDep`) rejects a `mfa_enrollment_required=True` token with a new `403 mfa-enrollment-required` for every caller by default — mirroring exactly how `get_current_user_allow_revoked` (US-2.2) is a narrow, separate opt-in dependency rather than a default-behavior change. A new `get_current_user_allow_enrollment_scoped` dependency (and `CurrentUserAllowEnrollmentScopedDep` type alias, same file, same pattern as the `_allow_revoked` pair) is used **only** by `POST /v1/auth/mfa/enroll` and `POST /v1/auth/mfa/activate`. **This means no other module or route changes** — the default dependency handles the restriction centrally, so `roles`, `profile`, `account`, etc. are untouched. This resolves impact-analysis's "second cross-cutting check, comparable blast radius to `perm_epoch`" concern down to a single-file, single-choke-point change.

3. **`mfa_token` (FR-3) resolves as Valkey-backed, opaque, not a third JWT type.** Generated via `secrets.token_urlsafe(32)` (matching `generate_refresh_token()`'s existing pattern), only its SHA-256 hash is used as the Valkey key (reusing `hash_refresh_token`-style hashing — a sibling function, not the same one, since the domain differs), value is the `user_id`, TTL 5 minutes (FR-3). Consumption is atomic single-use via Valkey `GETDEL` (available on this project's Redis-compatible Valkey client) — no separate "mark consumed" step, no race window. The failed-attempt counter (FR-5) is a sibling key, `mfa_verify_attempts:{token_hash}`, incremented on each wrong code; hitting 5 deletes the `mfa_token` key too (both FR-4/FR-5 outcomes converge on "the token is now gone"). Chosen over a JWT because this project's only other short-lived, single-use, security-critical tokens (`PasswordResetToken`, `RefreshToken` rotation) already use a hash-plus-store pattern, and Valkey's `GETDEL` gives single-use atomicity a JWT can't (a JWT is valid until its own `exp`, with no way to invalidate mid-flight except another denylist).

4. **New crypto utility, `app/core/crypto.py`.** AES-GCM encrypt/decrypt for the TOTP secret (OD-2) — a new file rather than adding to `security.py`, since `security.py` today only hashes/signs (one-way or verifiable, never reversible), and encryption-for-later-decryption is a distinct concern worth its own module boundary. Key sourced from a new `SecretStr` setting, matching the `jwt_secret_key` precedent (dev-only default, override in prod).

5. **`roles` module gains one new read method returning grant timestamps, not just names.** `UserRoleRepositoryProtocol` gains `list_role_grants_for_user(user_id) -> list[tuple[str, datetime]]` (role name + `granted_at` pairs) — a superset of the existing `list_role_names_for_user`, added as a new method rather than changing that one's return type (which `resolve_scopes_for_user` already depends on and doesn't need timestamps for). `RoleService` gains `get_role_grants_for_user(user_id) -> list[RoleGrant]` (`RoleGrant` a small `NamedTuple(name: str, granted_at: datetime)`), the public method `users.service` calls for FR-6's role-and-grace-period check. `replace_for_user`'s `INSERT` is updated to set `granted_at=func.now()` explicitly on every written row (not relying solely on the column default), so a role replacement always reflects "granted now," including a role that was already held and is being re-granted in the same call.

6. **Login and refresh both re-run the same enrolment-scoping decision.** A new private helper on `UserService`, `_resolve_enrollment_scoping(user)`, called from both `authenticate_user` (login) and `rotate_refresh_token` (refresh) before calling `encode_access_token`, returns whether the issued token should be `mfa_enrollment_required=True` and (for login's response body only) the grace-period deadline field, if any. Centralizing this in one helper avoids the two call sites drifting out of sync — a real risk `impact-analyzer` didn't call out explicitly but is implied by "refresh re-evaluates the same condition."

## Plan-Review Resolutions (2026-09-01)

- **`app/api/v1/router.py` — confirmed no change needed.** The 4 new MFA routes attach to the already-registered `users.router` (the same aggregation every prior auth story used); no new `include_router` call is required.
- **Concurrency shape of the two new single-use Valkey primitives — confirmed benign.** `mfa_token` consumption via `GETDEL` is atomic: two simultaneous `/verify` calls with the same `mfa_token` result in exactly one caller getting the `user_id` back and the other getting `nil` (treated as an invalid/already-used token, `mfa-invalid-code`) — the correct single-use outcome, not a race to guard against further. The failed-attempt counter's 5th-failure deletion of the `mfa_token` key races only against a concurrent *correct* code on the same token, which is an inherently ambiguous client-side scenario (retrying while a prior attempt is in flight) — either outcome (the correct attempt lands first and succeeds, or the deletion lands first and the correct attempt now sees an invalid token) is acceptable, since the client caused the ambiguity by parallelizing calls with the same single-use token.

## Files To Create

| File | Purpose |
|---|---|
| `app/core/crypto.py` | `encrypt_mfa_secret(plaintext: bytes) -> bytes` / `decrypt_mfa_secret(ciphertext: bytes) -> bytes`, AES-GCM, key from settings (OD-2). |
| `tests/unit/core/test_crypto.py` | Round-trip encrypt/decrypt; wrong-key and tampered-ciphertext failure cases. |
| `migrations/versions/<rev>_add_mfa_columns_and_recovery_codes.py` | 4 new `users` columns, new `mfa_recovery_codes` table, `user_roles.granted_at` column — per `US-009-entity-model.md`. |
| `tests/unit/modules/users/test_mfa_service.py` | Unit tests for `enroll_mfa`/`activate_mfa`/`verify_mfa`/`disable_mfa`, hand-written fakes, no `MagicMock`. |
| `tests/integration/modules/users/test_mfa_router.py` | Integration tests against real PostgreSQL + Valkey for all 4 new endpoints. |

## Files To Modify

| File | Change |
|---|---|
| `app/core/security.py` | `AccessTokenClaims` gains `mfa_enrollment_required: bool`; `encode_access_token()`/`decode_access_token()` updated. New `generate_mfa_token()`/`hash_mfa_token()` pair, mirroring `generate_refresh_token()`/`hash_refresh_token()`. |
| `app/core/cache_keys.py` | `mfa_token_key(token_hash)`, `mfa_verify_attempts_key(token_hash)`, `mfa_used_step_key(user_id, step)`. |
| `app/core/config.py` | New settings: `mfa_secret_encryption_key: SecretStr`, `mfa_token_ttl_seconds` (300), `mfa_verify_lockout_threshold` (5), `mfa_grace_period_days` (14). |
| `.env.example` | Add the 4 new settings. |
| `app/modules/users/models.py` | 4 new `User` columns; new `MfaRecoveryCode` model. |
| `app/modules/users/schemas.py` | `MfaEnrollRequest/Response`, `MfaActivateRequest/Response`, `MfaVerifyRequest`, `MfaDisableRequest`, `MfaRequiredResponse`; `LoginResponse`/`RefreshResponse` gain an optional grace-period-deadline field. |
| `app/modules/users/repository.py` | `MfaRecoveryCode` CRUD (create-10, list-unconsumed-for-user, mark-consumed, delete-all-for-user); `User` field updates for the 4 new columns. |
| `app/modules/users/cache.py` | New `MfaTokenCache` (issue/consume via `GETDEL`, attempt-counter increment/invalidate) and `MfaReplayCache` (`mfa_used_step` set-if-not-exists with TTL). |
| `app/modules/users/service.py` | New: `enroll_mfa`, `activate_mfa`, `verify_mfa`, `disable_mfa`, `_resolve_enrollment_scoping`. Modified: `authenticate_user` (MFA challenge branch, FR-3; enrolment-scoping via the new helper); `rotate_refresh_token` (re-run the same helper); `get_authenticated_user` (reject `mfa_enrollment_required` tokens by default, per Architectural Change #2). |
| `app/modules/users/exceptions.py` | `MfaInvalidCodeError` (401), `MfaRequiredForRoleError` (409), `MfaEnrollmentRequiredError` (403, the new default-deny case). |
| `app/modules/users/router.py` | 4 new routes; `enroll`/`activate` use the new `CurrentUserAllowEnrollmentScopedDep`, everything else unchanged. |
| `app/modules/users/dependencies.py` | New `get_current_user_allow_enrollment_scoped` / `CurrentUserAllowEnrollmentScopedDep`, mirroring the existing `_allow_revoked` pair exactly. |
| `app/modules/roles/models.py` | `UserRole` gains `granted_at`. |
| `app/modules/roles/repository.py` | New `list_role_grants_for_user`; `replace_for_user` sets `granted_at=func.now()` explicitly on insert. |
| `app/modules/roles/service.py` | New `get_role_grants_for_user` (+ `RoleGrant` NamedTuple). |
| `tests/unit/core/test_security.py` | Cover the new claim and the `mfa_token` helpers. |
| `tests/unit/modules/users/test_users_service.py` | New branches on `authenticate_user`/`rotate_refresh_token`/`get_authenticated_user` for enrolment-scoping and the MFA challenge. |
| `tests/integration/modules/users/test_users_router.py` | Login/refresh integration coverage for the new response fields and enrolment-scoped-token behavior. |
| `tests/unit/modules/roles/test_roles_service.py` | Cover `get_role_grants_for_user`; extend `replace_user_roles` tests for the explicit `granted_at` write. |
| `tests/conftest.py` | Fixture/fake extensions: a test user's MFA state (never-enrolled/PENDING/ACTIVE/disabled), a role grant's `granted_at`. |

No file under `AGENTS.md` §7.9 protection (`migrations/env.py`, `pyproject.toml` contracts, `.pre-commit-config.yaml`) is touched by this plan.

## Risks

- **`encode_access_token()`/`decode_access_token()` signature change, again.** The second time this function has changed in this story sequence (after US-3.2's `scopes` addition). Same mitigation as before: every call site (login, refresh) updates in the same task; a missed one is a hard build-time failure, not a silent bug.
- **The default-deny enrolment-scoping check (`get_authenticated_user`) is now the single highest-leverage line in the codebase for an authorization bug** — a bug here either locks out every user (over-broad denial) or silently lets a should-be-scoped token reach every endpoint (under-enforcement, a real security regression). Needs the most thorough test coverage of anything in this story, both directions.
- **`mfa_reenrollment_required` and the role-grant grace-period check both feed the same enrolment-scoping decision** — `_resolve_enrollment_scoping` must OR the two conditions correctly and never let one silently mask the other (e.g. a user who is both past their grace period AND has `mfa_reenrollment_required=true` is still just "scoped," not double-scoped or under-scoped).
- **Argon2id one-of-N recovery-code verification (FR-7) is O(remaining codes) per attempt** — at most 10 Argon2id verifications per call, each independently costed like a password check; acceptable at this scale but worth noting against the spec's ≤50ms p95 NFR (which is stated for *TOTP* verification specifically — recovery-code verification is a different, slower path the NFR doesn't explicitly cover; flagged, not a contradiction).
- **Migration: `user_roles.granted_at NOT NULL DEFAULT now()`** touches an already-merged, already-in-production-shape table. Must be proven via the standard `upgrade → downgrade → upgrade` cycle before this story's migration is trusted, same as any other change to that table would require.
- **Open spec-review-carried gaps not resolved by this plan** (see `US-009-api-design.md` Open Questions): activate's error-shape distinction (wrong code vs. no pending enrolment), whether `DELETE /v1/auth/mfa` accepts a recovery code, and disable's check-precedence order (401 vs 409 first). `implementation-planner`/`plan-reviewer` should decide whether these need resolving before coding starts.

## Validation Strategy

- `pre-commit run --all-files` green (7/7 hooks), mypy strict clean on every new/changed file, `lint-imports` clean.
- Migration: `upgrade → downgrade → upgrade` proven via a real PostgreSQL instance, including the `user_roles.granted_at` backfill behavior on pre-existing rows.
- Coverage floor 85% overall, 90%+ on `users/service.py` and `users/router.py` (already the incumbent floor for this module), per `AGENTS.md` §6/NFR-009.
- A dedicated test asserting `get_authenticated_user` rejects an `mfa_enrollment_required` token against every route *except* the two enrollment endpoints, and accepts it on those two — this is the single most important test in the story, per the Risks section above.

## Testing Strategy

- **Unit (hand-written fakes, no `MagicMock`):** `enroll_mfa` (fresh-secret-on-re-enroll, OD-11), `activate_mfa` (recovery-code issuance, exit-condition clearing), `verify_mfa` (TOTP success/failure/replay/skew, recovery-code success/consumption, shared lockout counter), `disable_mfa` (privileged-block vs. non-privileged success path with full purge), `_resolve_enrollment_scoping` (both triggers, grace-period boundary, OR-combination). `app/core/crypto.py` round-trip and failure cases.
- **Integration (real PostgreSQL + Valkey, no `unittest.mock`):** all 7 MF-ACs end-to-end through the router, per the spec's Enforcement Matrix `[gate]` markers; the enrolment-scoped-token flow end-to-end (privileged grant → scoped login → blocked non-enrollment call → activate → `token-stale` → refresh → normal token); the recovery-code trigger's equivalent flow; FR-5's brute-force lockout with a fixed Valkey counter; FR-4's skew/replay with a fixed TOTP clock.
- **Regression:** full existing suite green, particularly `users` and `roles` module tests touched by the `encode_access_token()` signature change and the new default-deny check in `get_authenticated_user`.
