# Impact Analysis: Multi-Factor Authentication / TOTP (US-2.5 / spec US-2.5)

**Spec:** docs/specifications/US-2.5-spec.md
**API design:** docs/designs/api/US-2.5-openapi.yaml, US-2.5-api-design.md
**DB design:** docs/designs/database/US-2.5-db-design.md, US-2.5-entity-model.md

## 1. Affected Files, by Layer

This story extends the existing `app/modules/users/` module — every prior auth story (login US-2.1, logout US-2.2, refresh US-2.3, password reset US-2.4) lives there, not in a separate module, and MFA is the same "auth" domain. No new module is created (unlike US-3.2's `roles`, which was a genuinely separate admin-facing domain).

### Modified — `app/modules/users/`

| File | Reason |
|---|---|
| `models.py` | Add 4 columns to `User` (`mfa_enabled`, `mfa_secret_encrypted`, `mfa_activated_at`, `mfa_reenrollment_required`) and a new `MfaRecoveryCode` model, per `docs/designs/database/US-2.5-entity-model.md`. |
| `schemas.py` | New: `MfaEnrollRequest/Response`, `MfaActivateRequest/Response`, `MfaVerifyRequest`, `MfaDisableRequest`, `MfaRequiredResponse` (the `mfa_required`/`mfa_token` challenge shape, FR-3). Modified: `LoginResponse` and `RefreshResponse` (confirmed at lines 38-46) gain an optional grace-period-deadline field (OD-4) — additive, not breaking. |
| `repository.py` | New `MfaRecoveryCode` CRUD (create-10-at-once, list unconsumed for a user, mark one consumed, hard-delete-all-for-user per FR-8), plus `User` field-update methods for the 4 new columns (enroll/activate/disable/set-reenrollment-flag). |
| `cache.py` | New gateway class(es) for: the MFA verify brute-force counter (FR-5/OD-10 — same shape as the existing `LoginThrottleCache` at lines 15-70), and the replay-protection key `mfa_used_step:{user_id}:{step}` (FR-4). If the `mfa_token` itself is Valkey-backed (see §2), its store/consume/lookup also lives here. |
| `service.py` | New methods: `enroll_mfa`, `activate_mfa`, `verify_mfa` (TOTP + recovery-code paths), `disable_mfa`. Modified: the existing login flow (`authenticate_user`, confirmed calling `encode_access_token` at line 476/478) must branch on `mfa_enabled` (FR-3) and, independently, on the enrolment-scoping condition (FR-6) — this is the highest-blast-radius change in this story, since it touches the login path every user goes through. The existing refresh flow (confirmed calling `encode_access_token` again at line 724/726) must re-evaluate the same enrolment-scoping condition per the spec-review resolution. |
| `exceptions.py` | New: `MfaInvalidCodeError` (401, FR-4), `MfaRequiredForRoleError` (409, FR-6), and an error for an invalid/expired `mfa_token` presented to `/verify` (folds into the same `MfaInvalidCodeError` per the OpenAPI design, or a separate class — left to `planner`). |
| `router.py` | 4 new routes: `POST /v1/auth/mfa/enroll`, `POST /v1/auth/mfa/activate`, `POST /v1/auth/mfa/verify`, `DELETE /v1/auth/mfa`, per `US-2.5-openapi.yaml`. |
| `dependencies.py` | New dependency for the `mfaTokenAuth` security scheme (FR-3/FR-4/FR-5/FR-7) — distinct from the existing bearer-access-token dependency, since an `mfa_token` must not be accepted where a normal access token is expected or vice versa. |

### Modified — cross-cutting (`app.core`)

| File | Reason |
|---|---|
| `app/core/security.py` | `AccessTokenClaims` (currently `user_id`, `jti`, `exp`, `scopes` — confirmed lines 93-98) needs a new field marking a token as enrolment-scoped (FR-6/FR-7); `encode_access_token()`/`decode_access_token()` signatures change again (the second time this story sequence has touched this function, after US-3.2's own `scopes` addition). Every access-token-minting call site (login, refresh) is affected. |
| New crypto utility (new file, e.g. `app/core/crypto.py`, or added to `security.py`) | AES-GCM encrypt/decrypt for the TOTP secret at rest (OD-2) — no existing utility in `app.core` does symmetric encryption today (confirmed: `security.py` only hashes/signs, never encrypts-for-later-decryption). |
| `app/core/config.py` | New settings: an AES-GCM key (OD-2, dev-only KMS stand-in), the `mfa_token` TTL (5 min, FR-3), the verify-lockout threshold (5, FR-5 — may already generalize from `login_failure_threshold_account`'s existing pattern), the 14-day grace-period length (FR-6). Exact names/defaults left to `planner`. |
| `app/core/cache_keys.py` | New key functions (mirroring the existing `revoke_before_key`/`perm_epoch_key`/`login_fail_*` pattern, lines 4-33): `mfa_used_step_key(user_id, step)`, an `mfa_token` key if it's Valkey-backed (see §2), and a verify-attempt-counter key. |
| `.env.example` | Must be updated to match every new setting, per `AGENTS.md` §4. |

### Modified — `app/modules/roles/` (already-merged US-3.2 code)

| File | Reason |
|---|---|
| `models.py` | `UserRole` gains `granted_at` (spec-review resolution) — a change to an already-shipped, already-merged table/model, not new code from this story's own design. |
| `repository.py` | `replace_for_user` (confirmed at line 38 of `service.py`'s Protocol, implemented in `repository.py`) must set `granted_at=now()` explicitly on every inserted row, rather than relying solely on the column's `server_default`, so FR-6's grace-period clock reflects the actual grant moment for new writes, not just backfilled history. |
| `service.py` | New method `get_role_names_for_user(user_id) -> list[str]` — a thin wrapper around the already-existing `UserRoleRepositoryProtocol.list_role_names_for_user` (confirmed at line 32, already called internally by `resolve_scopes_for_user` at line 87) — FR-6 needs role *names*, not the flattened *scopes* `resolve_scopes_for_user` returns, and nothing currently exposes that distinction publicly. |

## 2. Cross-Module Ripple

- **`users.service` → `roles.service`, new call: `get_role_names_for_user`.** Called from the login and refresh flows (FR-6) to check for `admin`/`auditor`/`support_agent` membership. This is the same direction (`users` → `roles`) US-3.2 already established for `resolve_scopes_for_user` — not a new architectural direction, but a new method on that existing dependency.
- **`users.service` reading `user_roles.granted_at` indirectly, via `roles.service`.** FR-6's grace-period clock needs the grant timestamp; whether `get_role_names_for_user` also returns `granted_at` (requiring a richer return type than `list[str]`) or a second `roles.service` method is needed is **not decided here** — flagged for `planner`.
- **No new dependency the other direction** — `roles` still never calls into `users`.
- **`app/api/v1/router.py`** — likely no change, since the 4 new routes attach to the already-registered `users.router` under the existing `/v1/auth` prefix (confirmed pattern from US-2.1/US-2.3/US-2.4, all added to the same router without a new `include_router` call). Confirm at PLANNING, not assumed here.

### Open architectural tension (not decided here, per this skill's scope — flagged for `planner`)

- **How the "enrolment-scoped token" restriction is actually enforced.** Two candidate shapes exist and the spec/API design don't pick one: (a) a claim on the normal JWT access token (e.g. `mfa_enrollment_required: bool`) checked by a new shared dependency that 403s any route except the two enrolment endpoints — mirrors how `perm_epoch`/`revoke_before` are already checked in shared middleware; or (b) a structurally different, narrower token type for this state. Whichever is chosen, it is the second time this story sequence adds a new cross-cutting check to the shared authenticated-request path (after US-3.2's `perm_epoch` check) — comparable blast radius.
- **Whether `mfa_token` (FR-3) is a signed JWT (a third token type alongside access/refresh) or an opaque Valkey-backed random token** (matching this project's existing `PasswordResetToken`/email-verification-token pattern: random value, only a hash persisted, natural single-use via delete-on-consume). The spec states its properties (single-use, 5-minute TTL, scoped to verification only) but not its mechanism — the Valkey-backed approach has closer precedent in this codebase; the JWT approach reuses existing `security.py` signing infrastructure. Left to `planner`.

## 3. Migration/Schema Impact

**Yes, a migration is required.**

- `users`: 4 new columns (`mfa_enabled` `NOT NULL DEFAULT false`, `mfa_secret_encrypted` nullable, `mfa_activated_at` nullable, `mfa_reenrollment_required` `NOT NULL DEFAULT false`). All additive with safe defaults — no existing `INSERT` into `users` breaks, since every new column either allows `NULL` or has a server default.
- `mfa_recovery_codes`: new table, no impact on any existing query.
- `user_roles`: 1 new column (`granted_at`, `NOT NULL DEFAULT now()`). Additive with a server default, so existing rows backfill automatically and no existing `INSERT` into `user_roles` breaks structurally — but `roles/repository.py`'s `replace_for_user` `INSERT` should be updated to set it explicitly (see §1) rather than silently relying on the default, or FR-6's clock will read "when the migration ran" for every pre-existing grant instead of "unset/irrelevant," which is a data-quality nuance for `planner` to weigh, not a hard blocker.

No column changes type or nullability on any existing table; no existing repository query breaks structurally.

## 4. Test-Surface Impact

### New test files
- A dedicated unit test file for the new crypto utility (e.g. `tests/unit/core/test_crypto.py`) if `app/core/crypto.py` is created as a separate module (see §1) — round-trip encrypt/decrypt, and a wrong-key/tampered-ciphertext failure case.
- Likely a new `tests/unit/modules/users/test_mfa_service.py` and/or `tests/integration/modules/users/test_mfa_router.py` given the volume of new behavior (enroll/activate/verify/disable, two enrolment-scoped-token triggers) — or extension of the existing `test_users_service.py`/`test_users_router.py` files. Exact split is an `implementation-planner` task-breakdown decision, not decided here.

### Existing test files that must change
- `tests/unit/core/test_security.py` — `AccessTokenClaims`/`encode_access_token`/`decode_access_token` signature changes again (already touched once by US-3.2 for `scopes`).
- `tests/unit/modules/users/test_users_service.py` — login and refresh flow tests need new branches (MFA challenge, enrolment-scoping check) added alongside every existing test that calls `authenticate_user`/`rotate_refresh_token`.
- `tests/integration/modules/users/test_users_router.py` — login/refresh integration tests may need new assertions wherever they decode/inspect token claims or response bodies.
- `tests/unit/modules/roles/test_roles_service.py` — new `get_role_names_for_user` method needs unit coverage; `replace_user_roles`'s existing tests may need a `granted_at` assertion added.
- `tests/integration/modules/roles/test_roles_router.py` — only if `granted_at` becomes visible in any roles-module response body (not currently planned); otherwise unaffected.
- `tests/conftest.py` — likely needs a fixture/fake extension for seeding a test user's MFA state (enrolled/pending/disabled) and role-grant timestamp, similar to how existing fixtures seed other per-user state.
