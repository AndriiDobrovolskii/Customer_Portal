# Implementation Plan: US-2.1 Login

**Spec:** `docs/specifications/US-2.1-spec.md` (Pass with Issues, accepted 2026-08-31)
**API:** `docs/designs/api/US-2.1-openapi.yaml`, `US-2.1-api-design.md`
**DB:** `docs/designs/database/US-2.1-db-design.md`, `US-2.1-entity-model.md` (amended 2026-08-31 with `refresh_tokens`, resolved OD-9)
**Impact analysis:** `docs/impact-analysis/US-2.1-impact-analysis.md`

## Goal

Extend the existing minimal `POST /v1/auth/login` (`app/modules/users/`, VE-AC5/VE-AC6 only) into the full US-2.1 endpoint: anti-enumeration timing (FR-3), account-state gating including deactivation (FR-4), brute-force throttling (FR-5), request validation (FR-6), `auth_audit_log` writes (FR-1–FR-4), `users.last_login_at` (FR-1), and initial refresh-token issuance (FR-1, resolved OD-9).

## Amendments (2026-08-31, post-plan-review — found via `advisor()` consultation before IMPLEMENTATION started)

Three findings surfaced after this plan was first reviewed (`docs/reviews/plans/US-2.1-plan-review.md`), all folded in below rather than tracked separately:

1. **OD-10 (user-resolved): FR-4 gained a reactivation branch.** Deactivated + within 30-day grace period + correct credentials now reactivates the account (cross-module call into `account`) instead of always returning `403`. See `docs/decisions/US-2.1-open-decisions.md` OD-10.
2. **Bug found, no user decision needed:** the deactivation gate must test `user.status == UserStatus.DEACTIVATED.value`, never `status != UserStatus.ACTIVE` — nothing in the codebase ever sets `status` to `"active"` (confirmed via repo-wide grep), so the latter would 403 every real user.
3. **Bug found, no user decision needed:** `app/main.py`'s `request_validation_error_handler` renders plain JSON, not the RFC 7807 `problem+json` shape FR-6 requires. Needs rework so `LoginRequest` validation failures (including OD-8's empty-password case) render `type=".../errors/validation-failed"` with an `errors` array, consistent with `problem_error_handler`'s existing `{field, code, message}` shape (the OpenAPI fragment's `{field, message}` is corrected to match — `code` was already part of every other error response's shape and there's no reason FR-6 should be the one exception).

## Architectural Changes

- **`InvalidCredentialsError` becomes a `ProblemError` subclass** (`type_slug="invalid-credentials"`, `status=401`), replacing its current bare-`DomainError` status and the bespoke handler in `app/main.py` that renders a non-problem+json body. This is a breaking response-shape change for the *existing* minimal endpoint's error responses — acceptable since nothing outside this codebase consumes it yet, but noted because it's the one change here that alters already-shipped behavior rather than adding to it.
- **Two new `ProblemError` subclasses**: `AccountDeactivatedError` (403, FR-4) and `TooManyAttemptsError` (429, FR-5, with a `Retry-After` header via `__init__`, mirroring `UnauthenticatedError`'s existing pattern).
- **New per-module `cache.py`** (`app/modules/users/cache.py`) for the two Valkey throttle counters — the first Valkey surface owned by `users` itself (today it only *consumes* `app.core.revocation_cache.RevocationCache`, injected from core).
- **New `RefreshToken` model + `refresh_tokens` table** (resolved OD-9) — `users` module's first table beyond `User`/`UserSession`. `token_hash`/`family_id` generation lives in `app/core/security.py` alongside the existing token/password helpers, mirroring how `encode_access_token`/`verify_password` already live there rather than in the service.
- **Dummy-hash verification path** for FR-3 — a new `app/core/security.py` helper verifies the supplied password against a fixed, pre-computed Argon2id hash when no account matches, so the cost is comparable to a real verification without a real user record involved.
- **Ordering rework in `authenticate_user`**: credential check (real or dummy) → account-existence branch → throttle check/increment → state-gate check (deactivated-past-grace, then unverified) → **reactivation branch** (deactivated-within-grace, calls `AccountService.reactivate_account`) → success path. The existing method's structure (email lookup → password check → verified check → issue token) is insufficient — FR-4 requires deactivation gating (and now, per resolved OD-10, conditional reactivation) in the same "credential check always precedes state check" position `email_verified` already occupies, the deactivation check must test `status == DEACTIVATED` (never `!= ACTIVE`, per Amendment #2 above), and FR-5's throttle check must run for every credential-verification outcome, not just failures.

## Files To Create

| File | Reason |
|---|---|
| `app/modules/users/cache.py` | Throttle-counter gateway (FR-5): increment/read/reset `login_fail:account:{user_id}`, `login_fail:ip:{ip}`. |
| `tests/unit/modules/users/test_users_cache.py` | New file needs its own unit tests (AGENTS.md §5: "a new `app/modules/x/service.py` requires `tests/unit/modules/x/test_x_service.py`" — same rule applies to a new `cache.py`). |
| `migrations/versions/<rev>_add_login_audit_and_refresh_tokens.py` | New Alembic revision for `users.last_login_at`, `auth_audit_log`, `refresh_tokens` — generated via `migration-manager`, not hand-written here. |

## Files To Modify

Per `docs/impact-analysis/US-2.1-impact-analysis.md`'s survey (not re-derived here):

| File | Change |
|---|---|
| `app/modules/users/models.py` | Add `User.last_login_at`; add `AuthAuditLog`; add `RefreshToken`. |
| `app/modules/users/schemas.py` | `LoginRequest.password` gets `min_length=1` (OD-8); `LoginResponse` gets `token_type: Literal["Bearer"]` (was `str = "bearer"`) and `expires_in: int`. |
| `app/modules/users/repository.py` | New methods: update `users.last_login_at`; insert `AuthAuditLog`; insert `RefreshToken`. |
| `app/modules/users/service.py` | `authenticate_user` reworked per Architectural Changes above. |
| `app/modules/users/exceptions.py` | `InvalidCredentialsError` → `ProblemError`; add `AccountDeactivatedError`, `TooManyAttemptsError`. |
| `app/modules/users/router.py` | `login` handler gains `get_request_id` (existing `app.core.dependencies` helper, reused as-is), a new client-IP dependency, `User-Agent` header read, and `Set-Cookie` response construction. |
| `app/modules/users/dependencies.py` | `get_user_service` injects the new `cache.py` gateway, a new `get_client_ip` dependency, and (resolved OD-10) an `AccountService`-typed collaborator for reactivation — the same cross-module DI pattern `profile/dependencies.py` already uses to inject `UserService` into `ProfileService` for `revoke_other_sessions`. |
| `app/core/security.py` | Add dummy-verification helper; add refresh-token raw-value + `token_hash` generation (SHA-256, matching `US-2.3` Assumption #5's token design). |
| `app/core/config.py` | New settings: `login_failure_threshold_account` (10), `login_failure_threshold_ip` (20), `login_throttle_window_seconds` (900), `refresh_token_ttl_seconds` (recommend 30 days = `2_592_000`, matching US-2.3's absolute-cap figure — flagged in `US-2.1-db-design.md` as this story's own choice to make, not fixed by any spec). |
| `app/core/cache_keys.py` | Add `login_fail_account_key(user_id)`, `login_fail_ip_key(ip)`. |
| `app/main.py` | Remove the bespoke `invalid_credentials_error_handler` (now redundant/shadowing once `InvalidCredentialsError` is a `ProblemError`). Rework `request_validation_error_handler` to render `problem+json` (`type=".../errors/validation-failed"`, `errors: [{field, code, message}]`) instead of its current plain-JSON shape (amendment #3). |
| `app/modules/account/service.py` | New `reactivate_account(user_id)` method (resolved OD-10). |
| `app/modules/account/repository.py` | New atomic "reactivate if within grace period" method, mirroring `deactivate_if_not_already` (resolved OD-10). |
| `.env.example` | Add the four new settings above, matching existing `KEY=value` style. |
| `tests/unit/modules/users/test_users_service.py` | Extend for every new `authenticate_user` branch. |
| `tests/integration/modules/users/test_users_router.py` | Extend for LI-AC1–LI-AC6 (response shape, cookie, headers, problem+json bodies, status codes). |

## Protected files — flagged per AGENTS.md §7.9, none touched

`pyproject.toml`, `migrations/env.py`, `.pre-commit-config.yaml` are not modified by this plan. No new third-party dependency is needed — `secrets`/`hashlib` (stdlib) cover raw-token generation and hashing; the throttle counters use the Valkey client already a project dependency.

## Risks

- **Reactivation atomicity (resolved OD-10).** Two concurrent login requests for the same deactivated-but-within-grace account must not both reactivate and both proceed as if they won a race that only one should. Mitigate: `AccountRepository`'s new reactivation method uses the same atomic-conditional-update pattern as the existing `deactivate_if_not_already` (`UPDATE ... WHERE status='deactivated' AND deactivated_at > now() - interval '30 days' RETURNING ...`) — the second concurrent caller sees `status` already `'active'`, the `WHERE` matches zero rows, and it falls through to the ordinary already-active success path instead of erroring (unlike deactivation's `409`, there's no failure mode here — a login that finds an already-reactivated account should just log in normally).
- **Reactivation must not become an enumeration or downgrade oracle.** The reactivation branch only ever fires after credential verification succeeds (same "credential check precedes state check" ordering as the rest of FR-4), so it doesn't create a new anti-enumeration gap. It does change what `200` "means" (either an ordinary login, or a login-that-reactivated) — the spec doesn't require the response to distinguish these two cases to the caller, so `LoginResponse` doesn't gain a new field for it; distinguishing them is left to the `auth_audit_log`/`account_lifecycle_audit_log` trail for staff, not the API response.

- **Ordering regression risk (FR-4's "credential check always precedes state check").** The existing code already gets this right for `email_verified`; extending it to `deactivated` in the wrong position would silently violate the anti-enumeration guarantee the spec review specifically checked. Mitigate: a single ordered sequence of guard clauses, not two independent `if` blocks that could be reordered by a future edit; a dedicated integration test asserting the ordering (deactivated + wrong password → generic 401, never account-deactivated).
- **Throttle check placement relative to credential verification.** FR-5 must count every attempt (per LI-AC5's "10 failed login attempts"), but the *check* (is this account/IP already over the limit?) should happen before paying the Argon2id cost — otherwise a throttled attacker still forces full hashing cost per request, weakening the point of throttling. Recommend: check-before-verify, increment-after-a-failed-verify. This ordering isn't stated by any FR explicitly — flagging as an implementation-time judgment call, not a spec gap serious enough to send back to `story-spec-writer`.
- **Migration risk: `refresh_tokens.user_id` FK with `ondelete="CASCADE"` is new to this table set.** Low risk in isolation (standard pattern, already used by `EmailVerificationToken`/`EmailChangeToken`), but this is an additive-only migration (`CREATE TABLE`, two new nullable-safe columns) — no data backfill, no `ALTER` on an existing populated column, so the `AGENTS.md` §4 "expand→migrate→contract" concern doesn't apply here.
- **`InvalidCredentialsError`'s handler removal is the one behavior-changing edit to already-shipped code.** Any existing test asserting the old `{"detail": ...}` shape (rather than the RFC 7807 shape) will need updating, not just extending — flagged so `test-writer`/`gate-enforcer` don't treat a red test here as a regression to investigate rather than an expected, intentional shape change.
- **Throttle-counter increment concurrency (plan-review finding, resolved).** Two concurrent failed-login requests for the same account must not under-count. Mitigate: the `cache.py` gateway increments via Valkey's atomic `INCR` (with `expire`/`ex` for the TTL), never a read-then-write pair — the same class of hazard `US-2.3`'s RT-AC6 calls "the requirement, not an implementation detail" for refresh-token rotation. `INCR` alone is sufficient here since, unlike RT-AC6's check-and-consume, nothing about this counter needs a conditional (compare-and-swap); it only needs to not lose updates.
- **Dummy-hash verification cost drift.** If the fixed dummy hash's Argon2id parameters (`time_cost`/`memory_cost`/`parallelism`) ever diverge from the live `settings.argon2_*` values used for real verification, FR-3's "comparable timing" guarantee silently degrades. Mitigate: derive the dummy hash from `get_settings()` at call time (or regenerate it whenever settings change), not a hardcoded string computed once at old parameter values.

## Validation Strategy

- `pre-commit run --all-files` — Ruff format/lint, mypy strict on `app tests`, secret scan, no-mock-in-integration grep — must be green before this plan is considered implemented (`gate-enforcer`'s job, not this plan's).
- `lint-imports` — the new `cache.py` must declare itself as a `cache.py`-layer file (Valkey client type + stdlib only, no service/router/sqlalchemy imports) or the `exhaustive=true` contract fails the build.
- Migration cycle: `alembic upgrade head` → `downgrade` → `upgrade` proven clean (`migration-manager`'s job), plus the generated file actually read for anything the Rewriter can't reach (none expected here — this is a pure additive migration, but the read-before-trust rule applies regardless).
- `.env.example` updated with the four new settings (AGENTS.md §6.7).

## Testing Strategy

Per `AGENTS.md` §5's unit/integration split:

- **Unit** (`tests/unit/modules/users/test_users_service.py`, hand-written fakes for `UserRepositoryProtocol`/the new cache gateway/`RevocationCacheReaderProtocol` — never `MagicMock`): every `authenticate_user` branch — success (FR-1), wrong password (FR-2), unknown email with dummy-verification called (FR-3), unverified (FR-4a), deactivated-past-grace (FR-4b), deactivated-within-grace reactivation (resolved OD-10 — asserts `AccountService.reactivate_account` called via a hand-written fake, and that the normal success path follows), ordering (deactivated-past-grace + wrong password → still generic 401), throttled account (FR-5a), throttled IP (FR-5b), successful login resets account counter but not IP counter (resolved OD-5).
- **Unit** (`tests/unit/modules/users/test_users_cache.py`, new): increment/read/reset behavior of the throttle-counter gateway, TTL set on every write (AGENTS.md §3 "every cache write sets a TTL").
- **Integration** (`tests/integration/modules/users/test_users_router.py`, real Postgres + Valkey, `AsyncClient`/`ASGITransport`, no mocking): full request/response cycle for LI-AC1–LI-AC6 — status code, body shape, `Set-Cookie` presence/attributes (FR-1), `Retry-After` header (FR-5), persisted state (`users.last_login_at` updated, `auth_audit_log` row written with correct `event`/`reason`, `refresh_tokens` row written). Empty-string password (OD-8) asserted as `422` with the RFC 7807 shape (amendment #3), not `401` and not the old plain-JSON shape. Reactivation (resolved OD-10) asserted end-to-end against real Postgres: `users.status`/`deactivated_at` actually flip, `account_lifecycle_audit_log` gets a real `reactivated` row, a session is actually issued.
- **New unit tests** (`tests/unit/modules/account/test_account_service.py`, extended): `reactivate_account`'s own branches — within grace, past grace, already active (idempotent no-op) — mirroring the existing `test_account_service.py` structure for `deactivate_account`.
- Coverage floor 85% overall, 90%+ for `service.py`/`router.py` per AGENTS.md §5 — the reworked `authenticate_user` is the module's largest branch count, so the unit-test list above is written to hit every branch, not just the happy path.
