# PR: Implement US-2.5 — Multi-Factor Authentication (TOTP)

**Branch:** `feat/us-2.5-mfa-totp` → `main`
**Story:** `docs/stories/US-2.5-mfa-totp.md` · **Spec:** `docs/specifications/US-009-mfa-totp-spec.md`

## Title

```
feat: implement US-2.5 multi-factor authentication (TOTP)
```

## Summary

Adds RFC 6238 TOTP-based multi-factor authentication: secret enrolment and activation with recovery-code issuance, a login-time MFA challenge with brute-force lockout and replay protection, mandatory enforcement for privileged roles (`admin`/`auditor`/`support_agent`) with a 14-day rollout grace period, and recovery-code login when an authenticator device is lost.

- **4 new endpoints:** `POST /v1/auth/mfa/enroll`, `POST /v1/auth/mfa/activate`, `POST /v1/auth/mfa/verify`, `DELETE /v1/auth/mfa`.
- **2 extended endpoints:** `POST /v1/auth/login` (returns an MFA challenge instead of tokens when `mfa_enabled=true`) and `POST /v1/auth/refresh` (re-evaluates enrolment scoping on every rotation).
- **Enrolment-scoped-token mechanism:** a new `mfa_enrollment_required` JWT claim, default-deny enforced centrally in `UserService.get_authenticated_user`, with two independent triggers — a privileged-role grant while `mfa_enabled=false` (14-day grace period, timed from a new `user_roles.granted_at` column), and recovery-code consumption (immediate, no grace period).
- **New dependency:** `cryptography` (AES-GCM envelope encryption for the TOTP secret at rest — a local symmetric key from settings, explicitly documented as a dev-only stand-in for a real KMS-managed key in production).
- Recovery codes are Argon2id-hashed, single-use, and count toward the same verification-lockout counter as a wrong TOTP guess.

This story required merging its blocking dependency (US-3.2, Manage Roles — PR #9) first, since FR-6's privileged-role enforcement is built on that story's role/scope system.

## Test Plan

Full pipeline: CLARIFICATION → SPECIFICATION → SPEC_REVIEW → DESIGN → PLANNING → TESTS → IMPLEMENTATION → VERIFICATION → SECURITY_REVIEW → RECONCILIATION, all gates Pass.

- [x] **gate-enforcer:** PASS — 7/7 pre-commit hooks (ruff lint+format, mypy strict, import-linter 6/6 contracts, unit tests, no-mock-in-integration-tests, detect-secrets), `mypy app tests` clean, 367/367 tests passing (214 unit + 153 integration), 97.35% coverage (floor 85%; `service.py` 97%, `router.py` 100%). Migration `cef55228a927` upgrade→downgrade→upgrade proven against real Postgres.
- [x] **implementation-verifier:** Pass (`docs/verification/US-009-verification-report.md`) — ORM containment, eager-loading N/A, every cache write TTL'd, service→service cross-module discipline, `response_model`/`extra="forbid"`/privilege-field exclusion all confirmed. One gap found+fixed same-day: 13 missing `AGENTS.md` §5 security-case tests across `enroll`/`activate`/`disable`/`verify`, all added.
- [x] **security-reviewer:** Pass (`docs/security/US-009-security-review.md`) — all 6 `AGENTS.md` §7 non-negotiable rules checked with cited evidence. Rule 2 (no reversible encryption for credentials) required explicit reasoning: the TOTP secret's AES-GCM envelope encryption is correct, not a violation, since a TOTP secret must be recomputed-from to verify a code (no one-way hash is possible), unlike recovery codes (Argon2id-hashed, compare-only). One real defect found+fixed same-day: `disable_mfa`'s sequential password-then-code check let a stolen bearer session distinguish which factor was wrong via the response body — fixed to evaluate both factors unconditionally, one exception type on either failure.
- [x] **reconciliation-reviewer:** Pass (`docs/reconciliation/US-009-reconciliation-report.md`) — all 7 source ACs (MF-AC1–MF-AC7) plus FR-8 (the no-AC disable-success path) have full, verified test coverage. 7 gaps found (test functions named in the pre-implementation traceability matrix that didn't exist under any name) and closed same-day with 6 new tests, none requiring a code change: `granted_at`'s write path now proven against a real database (it's FR-6's sole grace-period-clock data source), the enrolment-scoped-token allow-list boundary proven in both directions (`enroll` accepts, `disable` rejects), OD-10's shared lockout counter proven for a recovery-code guess, the both-triggers-true precedence proven, and replay protection proven against real Valkey rather than only a fake. No AC-level spec drift found.
- [x] `docs/tests/US-009-traceability-matrix.md` — full AC → test mapping, unit vs. integration split, updated 2026-09-02 with a reconciliation note after the gap-closure pass.

## Risk / Rollback Notes

- **Additive migration only** (`cef55228a927`): 4 new nullable-safe `users` columns, a new `mfa_recovery_codes` table, and one new `user_roles.granted_at` column (backfilled to `now()` for existing rows, `server_default=func.now()` going forward) — no destructive change, no data loss on rollback (`downgrade()` is real and proven).
- **New pyproject.toml dependency** (`cryptography>=42.0`) — required for AES-GCM; no existing dependency provided this.
- **New required setting**: `MFA_SECRET_ENCRYPTION_KEY` must be set in every environment before this deploys (documented in `.env.example`); missing it fails fast at settings load, not silently.
- The enrolment-scoped-token default-deny check in `get_authenticated_user` is the single highest-risk line in this story (per `docs/plans/US-009-implementation-plan.md`'s Risks section) — it is dedicated-tested in both directions (rejects on other routes, accepts on the two enrolment routes) plus 2 full end-to-end flow tests, one per trigger.

## Config

`.env.example` updated with all 4 new settings this story introduces: `MFA_SECRET_ENCRYPTION_KEY`, `MFA_TOKEN_TTL_SECONDS`, `MFA_VERIFY_LOCKOUT_THRESHOLD`, `MFA_GRACE_PERIOD_DAYS` — confirmed matching `app/core/config.py` 1:1.

## Commit Hygiene

Confirmed via `git status`: every changed/new file traces to this story's scope — the `users` module (schemas/models/repository/cache/service/router/dependencies/exceptions), the `roles` module's `granted_at` addition (this story's own dependency, not a US-3.2 change), `app/core/{crypto (new),security,config,email,cache_keys}.py`, the one new migration, tests, and this story's own `docs/` artifacts. No unrelated file and no drive-by refactor outside this scope.

---

**This is drafted content only.** Pushing the branch and opening the PR (`git push` / `gh pr create`) require an explicit, separate instruction.
