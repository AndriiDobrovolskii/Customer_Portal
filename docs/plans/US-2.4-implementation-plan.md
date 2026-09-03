# Implementation Plan: Password Reset (US-2.4 / spec US-2.4)

**Spec:** `docs/specifications/US-2.4-spec.md`
**Impact analysis:** `docs/impact-analysis/US-2.4-impact-analysis.md`
**Written:** 2026-09-01

## Goal

Add `POST /v1/auth/password-reset/request` and `POST /v1/auth/password-reset/confirm` to the existing `users` module, per FR-1–FR-6, with no new module and no cross-module coupling beyond what already exists.

## Architectural Changes

1. **New table `password_reset_tokens`** — per `db-design.md`, column-for-column identical to `EmailVerificationToken` plus atomic-consume semantics.

2. **Rate limiting is Valkey-backed for all three limits, keyed to work even for an unknown email (resolves DESIGN's OQ-2).** `email_verification`'s own resend cooldown is Postgres-based (`latest.issued_at` on an existing token row), but that precedent doesn't transfer here: FR-3's anti-enumeration requires the *same* throttling to apply to an unknown/deactivated-account request, which creates no `password_reset_tokens` row to count. A Postgres-row-count approach would silently exempt unknown-email requests from every limit, defeating the point. Decision: a new `PasswordResetRateLimitCache` (mirrors `LoginThrottleCache`/`RefreshRateLimitCache`), with the per-account cooldown/hourly counters keyed by a SHA-256 hash of the normalized (lowercased, trimmed) email — not `user_id`, since an unknown email has none — and the per-IP counter keyed by IP, same as `LoginThrottleCache`. New `cache_keys.py` helpers: `password_reset_cooldown_key(email_hash)`, `password_reset_account_hourly_key(email_hash)`, `password_reset_ip_hourly_key(ip)`.

3. **Breached-password check is a new, self-contained local module (resolves DESIGN's OQ-1).** A bundled flat wordlist (`app/core/data/common_passwords.txt` or similar), loaded once into a module-level `frozenset[str]` and exposed as `is_breached_password(password: str) -> bool` in a new `app/core/breached_passwords.py` (sits beside `security.py` as a password-handling concern, not users-module-specific — mirrors how `hash_password`/`verify_password` live in `core` despite being called only from `users`). A plain set lookup is O(1) and needs no bloom-filter complexity at this list's expected scale (tens of thousands of entries); OD-1 sanctioned either form and the user's approved option was framed as "list/bloom filter" — a set is the simplest thing satisfying "local, no network call."

4. **Two new `ProblemError` subclasses resolve the status conflict impact-analyzer flagged** — `TokenInvalidError` (401) already exists in `users/exceptions.py` for refresh-token reuse (US-2.3) and cannot be reused for this story's `400` responses. New `PasswordResetTokenInvalidError` (400, `token-invalid`) and `PasswordResetTokenExpiredError` (400, `token-expired`) are added instead, reusing the same *slugs* under new *classes* — this project already has this exact pattern (`email_verification` and `profile` modules each carry their own `TokenExpiredError`/`TokenInvalidError` classes sharing the same slugs), so this is applying an established convention, not inventing a new one.

5. **`PasswordPolicyError` (422) uses `ProblemError`'s existing `errors: list[FieldError] | None` field** — already present on the base class (used by `RegistrationValidationError`'s pattern), so no new response-shape mechanism is needed; the service populates `errors` with one `FieldError(field="new_password", message=..., code=...)` per failed rule.

6. **No cross-module calls.** Confirmed by impact-analyzer: unlike login's reactivation path, a deactivated account is simply treated identically to an unknown one here — no `AccountService` call.

## Files To Create

- None at the module-directory level — all files below already exist and are extended, except:
- `app/core/breached_passwords.py` (new file, per Architectural Change #3)
- `app/core/data/common_passwords.txt` (new bundled data asset)

## Files To Modify

Per `impact-analysis.md`'s survey — reason given only where it adds detail beyond that survey:

- `app/modules/users/models.py` — add `PasswordResetToken`.
- `app/modules/users/schemas.py` — add the three request/response schemas.
- `app/modules/users/repository.py` — add `create_password_reset_token`, `get_password_reset_token_by_hash`, `invalidate_password_reset_tokens_for_user`, `consume_password_reset_token` (atomic).
- `app/modules/users/cache.py` — add `PasswordResetRateLimitCache` (Architectural Change #2).
- `app/core/cache_keys.py` — add the three new key helpers.
- `app/modules/users/service.py` — add `request_password_reset()`, `confirm_password_reset()`.
- `app/modules/users/exceptions.py` — add `PasswordResetTokenInvalidError`, `PasswordResetTokenExpiredError`, `PasswordPolicyError`.
- `app/modules/users/router.py` — add the two routes.
- `app/modules/users/dependencies.py` — wire `PasswordResetRateLimitCache` into `get_user_service`; `UserService.__init__` gains one parameter.
- `app/core/email.py` — `EmailSender` Protocol + `LoggingEmailSender` gain `send_password_reset_email` and `send_password_reset_notice`.
- `app/core/config.py` — new settings (token TTL, three rate-limit thresholds/windows, breach-list path).
- `tests/unit/modules/users/test_users_service.py`, `tests/integration/modules/users/test_users_router.py` — extended (see Testing Strategy).
- Wherever `RecordingEmailSender`-style fakes live in `email_verification`/`profile` tests — extended with the two new Protocol methods (same ripple US-2.3 already hit).
- New migration under `migrations/versions/` (additive only — see Risks).

**No `AGENTS.md` §7.9-protected file needs a change** (no touch to `pyproject.toml` contracts, `migrations/env.py`, or `.pre-commit-config.yaml`).

## Risks

- **Migration risk: low.** Purely additive new table, no `ALTER` on existing tables — same shape as US-2.2's `9f9d9263bdfc` and US-2.3's `c8eeaa6b5ff6`. Must still be proven `upgrade → downgrade → upgrade` per `AGENTS.md` §4.
- **Concurrency risk: addressed by design.** `consume_password_reset_token`'s atomic `UPDATE...WHERE consumed_at IS NULL RETURNING` is the load-bearing guard for the spec-review-accepted concurrent-confirm race; a plain read-then-update here would reopen exactly the gap the spec review flagged.
- **Anti-enumeration timing risk (NFR-002).** The unknown/deactivated-account path in `request_password_reset()` must pay comparable cost to the real-account path (DB lookup + rate-limit check, but no token creation/email dispatch) — same discipline as `verify_password_dummy()` in login. Not itself a password-hash operation here, so no dummy-hash-cost call is needed, but the code path shape (lookup → rate-limit check → early-return-with-202) must not diverge in a way that's independently timeable from the full path.
- **Rate-limit keying risk.** Keying the per-account limiter by an email hash (Architectural Change #2) rather than `user_id` is a deliberate deviation from `LoginThrottleCache`'s `user_id`-based keying, made necessary by anti-enumeration; if a future reviewer assumes email-hash and `user_id` keying are interchangeable across this codebase's rate limiters, that assumption is wrong for this one specifically — worth a code comment at the point of use (implementation-time note, not a plan action item).
- **`EmailSender` Protocol ripple.** Adding two methods breaks any other module's `RecordingEmailSender`-style fake until updated — already anticipated in Files To Modify, flagged here because US-2.3's gate-enforcer caught this exact class of gap only at the very end of its own implementation.
- **New data-asset class of risk (plan-review finding, fixed same-day).** `app/core/data/common_passwords.txt` is the first bundled non-code data file this application ships. Source: a well-known public common/breached-password list (e.g. the top-N subset of the "10 Million Password List" / RockYou-derived lists already widely used for exactly this purpose), truncated to on the order of 10,000–100,000 entries — large enough to catch the common case, small enough that loading it into a `frozenset[str]` once at first use costs low-single-digit milliseconds and a few MB of resident memory, negligible against the endpoint's 300 ms budget (NFR).

## Validation Strategy

- `pre-commit run --all-files` clean (7/7 hooks), matching every prior Epic 2 story.
- `mypy --strict` clean across all modified/new files.
- `lint-imports` clean — the layering additions here (repository/cache/service/router/dependencies) all follow the existing US-2.1–2.3 import shape; no new cross-layer import is introduced.
- Migration cycle (`upgrade → downgrade → upgrade`) proven against a real Postgres instance before IMPLEMENTATION's gate, per `AGENTS.md` §4.

## Testing Strategy

- **Unit (`tests/unit/modules/users/test_users_service.py`):** hand-written fakes, no `MagicMock`, per `AGENTS.md` §5 — extend `FakeUserRepository` with password-reset-token seeding/consumption methods (including a `simulate_race_on_consume`-style flag mirroring US-2.3's RT-AC6 fake, for the atomic-consume race) and a `FakePasswordResetRateLimitCache`; add a fake/stub for the new breach-check collaborator so tests don't depend on the real bundled wordlist. Cover FR-1 through FR-6 plus the token-state-mapping precedent (FR-4) and the check-order precedence (FR-6/OD-2).
- **Integration (`tests/integration/modules/users/test_users_router.py`):** real Postgres + Valkey via testcontainers, no `unittest.mock`, per `AGENTS.md` §5 — both endpoints' full request/response cycle, the anti-enumeration timing-comparable path (PR-AC3), and a genuine concurrent-`confirm` test via `asyncio.gather` proving exactly one success (mirroring US-2.3's own RT-AC6 integration proof).
- Coverage floor 85% overall, 90%+ for `service.py`/`router.py`, per `AGENTS.md` §6/§7.7 — not a target, a floor.
