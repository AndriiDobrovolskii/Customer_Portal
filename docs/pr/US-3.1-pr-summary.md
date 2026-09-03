# PR: Implement US-3.1 — Manage Users

**Branch:** `feat/us-3.1-manage-users` → `main`
**Story:** `docs/stories/US-3.1-manage-users.md` · **Spec:** `docs/specifications/US-3.1-spec.md`

## Title

```
feat: implement US-3.1 admin user management
```

## Summary

Adds the admin user-management surface: searching/paging the directory, provisioning a colleague by email invitation, correcting whitelisted profile fields, admin-initiated deactivation with immediate session revocation, and reissuing an expired invitation.

- **New module, `app/modules/admin_users/` (7 endpoints):** `GET`/`POST /v1/admin/users`, `GET`/`PATCH`/`POST .../deactivate`/`DELETE` (405-only) on `/v1/admin/users/{id}`, `POST .../resend-invite`. Not an extension of `app/modules/users/` — mirrors the existing `profile`/`roles` precedent of a separate module owning its own repository against the shared `User` table.
- **New `invitation_tokens` table**, matching the existing `email_verification_tokens`/`password_reset_tokens` shape exactly.
- **Two existing audit tables extended with nullable columns**, closing schema gaps a pre-existing 2026-08-22 draft spec had assumed away before US-1.4/US-3.2 actually shipped: `admin_audit_log` (+`field`/`old_value`/`new_value`/`reason`) and `account_lifecycle_audit_log` (+`reason`).
- **ETag/`If-Match` concurrency control reuses this project's only existing precedent** (`app/core/etag.py`, `app/modules/profile`'s immutable-field-before-Pydantic-validation pattern) rather than inventing a second scheme.
- **First use of `pg_trgm`** in this codebase, for the directory's free-text search — deliberately its own migration (not bundled with the rest of the schema change), per this project's established `CREATE INDEX CONCURRENTLY` precedent.
- **A genuine concurrency bug in already-shipped US-3.2 code was found and fixed by this story's own tests:** the shared last-admin check locked only `user_roles` rows, giving no protection against a concurrent `users.status` update — two simultaneous deactivations of the last two admins could both succeed. Now locks both tables (`app/modules/roles/repository.py`); benefits US-3.2's existing `replace_user_roles` caller too, still green.

## Test Plan

Full pipeline: CLARIFICATION → SPECIFICATION → SPEC_REVIEW → DESIGN → PLANNING → TESTS → IMPLEMENTATION → VERIFICATION → SECURITY_REVIEW → RECONCILIATION, all gates Pass.

- [x] **gate-enforcer:** PASS — 7/7 pre-commit hooks (ruff lint+format, mypy strict on 113 files, import-linter 6/6 contracts, unit tests, no-mock-in-integration-tests, detect-secrets), 509/509 tests passing (281 unit + 228 integration), 96.64% coverage (floor 85%; `admin_users/service.py` 96%, `admin_users/router.py` 100%). Two migrations (`a5edc35c8e96`, `1b2b1d52dd71`) each proven `upgrade → downgrade → upgrade` against real Postgres.
- [x] **implementation-verifier:** Pass (`docs/verification/US-3.1-implementation-verification.md`) — ORM containment, cache-TTL, cross-module (service→service) discipline, `response_model`/`extra="forbid"`/`.env.example`/no-sensitive-`*Read`-field all confirmed. 1 real gap found+fixed same-day: 5 of 7 protected routes only had a `missing_token` security case at the integration level, not the full `AGENTS.md` §5 five-case set — 24 tests added.
- [x] **security-reviewer:** Pass (`docs/reviews/security/US-3.1-security-review.md`) — all 6 `AGENTS.md` §7 rows Pass (3 N/A: this story has no password/credential handling at all — creation is invitation-only and structurally cannot accept a `password` field). 2 Low advisory findings noted, neither forcing a Fail.
- [x] **reconciliation-reviewer:** Pass (`docs/reviews/reconciliation/US-3.1-reconciliation.md`) — all 21 source ACs plus FR-17b/FR-22/FR-23 (no-AC) have full, verified test coverage. Initial pass was Fail: MU-AC9 and MU-AC18 both explicitly name `actor` as a required audit-row field, and neither test asserted it (the field was written correctly, just never proven) — fixed same-day with 4 assertions across 4 existing tests. 29 other matrix-vs-shipped test-name mismatches individually verified as harmless pre-implementation-to-shipped renames, not gaps. No spec drift found.
- [x] `docs/tests/US-3.1-ac-test-matrix.md` — full AC → test mapping, unit vs. integration split (superseded in detail by the reconciliation report's verified name mapping).

## Risk / Rollback Notes

- **Migration split for the same reason US-2.6's was:** `a5edc35c8e96` (ordinary transactional DDL — new table, 5 nullable columns, one composite index) is separate from `1b2b1d52dd71` (`CREATE EXTENSION pg_trgm` + two `CREATE INDEX CONCURRENTLY` builds, `autocommit_block()`), since `users` is written on every login/registration/profile-update — a plain `CREATE INDEX` would have locked it. No data loss on rollback (`downgrade()` real and proven for both).
- **`pg_trgm` extension creation** may require elevated database privileges on some managed PostgreSQL providers — this codebase's first use of the extension, flagged in `docs/plans/US-3.1-implementation-plan.md`'s Risks as worth confirming works in the actual deploy target.
- **Cross-cutting fix to already-shipped US-3.2 code:** `roles/repository.py`'s `count_active_admins_excluding` now locks `User` rows in addition to `UserRole` rows (`with_for_update(of=[UserRole, User])`). Purely additive locking — more conservative, never less correct — and the existing `replace_user_roles` concurrency test (`test_replace_user_roles_concurrent_last_admin_removal_only_one_succeeds`) still passes.
- **2 new settings**, both with safe defaults: `INVITATION_TOKEN_TTL_HOURS` (24), `INVITATION_RESEND_HOURLY_LIMIT` (5) — no environment fails to start without an override.
- **`EmailSender` protocol gained `send_invitation_email`**, a required addition to the shared `app/core/email.py` Protocol — 3 existing test fakes (`email_verification`, `profile`, `users` unit tests) updated to implement it; no behavior change to any existing email path.
- The last-admin concurrency fix is proven under genuine concurrent load: `test_concurrent_deactivate_last_two_admins_exactly_one_succeeds` runs two real simultaneous deactivations via `real_client`/`asyncio.gather` and asserts exactly one `200`/one `409`, never both.

## Config

`.env.example` updated with both new settings: `INVITATION_TOKEN_TTL_HOURS`, `INVITATION_RESEND_HOURLY_LIMIT` — confirmed matching `app/core/config.py` 1:1.

## Commit Hygiene

Confirmed via `git status`/`git log origin/main..HEAD`: 5 commits, every changed/new file traces to this story's scope — the new `admin_users` module, cross-cutting changes to `roles`/`account`/`users`/`app/core/email.py`/`app/core/config.py`/`app/api/v1/router.py`, 2 new migrations, `migrations/env.py`'s one-line model-registration import (protected file, explicit user sign-off obtained before it was added), tests, `.env.example`/`.secrets.baseline`, and this story's own `docs/` artifacts. No unrelated file and no drive-by refactor outside this scope.

---

**This is drafted content only.** Pushing the branch and opening the PR (`git push` / `gh pr create`) require an explicit, separate instruction.
