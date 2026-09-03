# PR: Manage Roles (US-3.2 / spec US-3.2)

**Title:** `feat: implement US-3.2 manage roles (admin role assignment)`

## Summary

Introduces the first role/permission system in the codebase: a fixed, seeded catalogue (`customer`, `support_agent`, `admin`, `auditor` — minimal-per-persona scope mapping resolved 2026-09-01), `GET /v1/admin/roles` to read it, and `PUT /v1/admin/users/{id}/roles` to replace a target user's role set with full guard rails (unknown-role rejection, self-modification block, privilege-escalation block, last-admin protection with real transactional concurrency safety). Role changes propagate to live sessions via a new `perm_epoch` mechanism — the caller's access token goes stale (`401 token-stale`) without forcing a full re-login; `POST /v1/auth/refresh` picks up the new scopes.

This story exists because **US-2.5 (MFA/TOTP)** was blocked mid-clarification: its own privileged-role enforcement AC cited "US-3.2 MR-AC1" behavior that didn't exist in the codebase, and `docs/stories/README.md`'s own dependency notes and build order name US-3.2 as the prerequisite. Building it now unblocks US-2.5 to resume.

Linked: `docs/stories/US-3.2-manage-roles.md`, `docs/specifications/US-3.2-spec.md`, `docs/plans/US-3.2-implementation-plan.md`.

## Gate Results

- **gate-enforcer:** PASS — 7/7 pre-commit hooks, mypy strict clean (94 files), import-linter 6/6 contracts kept, 281/281 tests, 97.27% coverage (floor 85%; `roles/service.py` 99%, `roles/router.py` 100%), migration cycle proven twice.
- **implementation-verifier:** Pass (`docs/verification/US-3.2-implementation-verification.md`) — ORM containment, eager-loading, cache TTL, cross-module discipline, and contract/security items all confirmed with cited evidence; one §5 test-coverage gap found and closed same-day.
- **security-reviewer:** Pass (`docs/reviews/security/US-3.2-security-review.md`) — all AGENTS.md §7 rows Pass/N/A; 3 Low advisories, none forcing Fail.
- **reconciliation-reviewer:** Pass (`docs/reviews/reconciliation/US-3.2-reconciliation.md`) — all 7 MR-ACs fully covered and behavior-asserted; two matrix/assertion gaps found and fixed same-day; no AC-level spec drift.

## What Changed

- **New module:** `app/modules/roles/` (models, schemas, repository, service, router, dependencies, exceptions).
- **Cross-cutting:** `app/core/security.py` (JWT gains a `scopes` claim), `app/core/revocation_cache.py` (new `PermissionEpochCache`), `app/core/cache_keys.py`, `app/core/config.py` + `.env.example` (`PERM_EPOCH_TTL_SECONDS`).
- **`app/modules/users/service.py`:** the shared token-validation path gains a `perm_epoch` check (new `TokenStaleError`, 401); login and refresh now resolve and embed the caller's current scopes.
- **Migrations:** `e50fbe8161fc` (roles/permissions/role_permissions/user_roles + seed data), `d7585b660cd7` (admin_audit_log, added mid-implementation — required by MR-AC1/MR-AC6, absent from the original design since it belongs to not-yet-built US-3.1).
- **`migrations/env.py`:** one model-registration import line added (user-approved exception — identical pattern used for every prior new module).

## Real Bugs Found & Fixed During This Work

- **Concurrency race (MR-AC7):** the last-admin check had no row locking; two concurrent requests removing `admin` from different admins could both read a stale count and both succeed, leaving zero admins. Fixed with `SELECT ... FOR UPDATE`, verified deterministic across repeat runs.
- **Pre-existing flaky test** (`test_decode_access_token_tampered_signature_raises_invalid_token`, unrelated to this story) — made deterministic (was flipping a base64 tail character that sometimes falls in a non-significant padding-bit position).

## Test Plan

Traceability: `docs/tests/US-3.2-ac-test-matrix.md`. All 7 MR-ACs covered at both unit and integration level, plus:
- Full security-case matrix (no token / expired / malformed / insufficient-permission / revoked-session) on both new routes.
- Genuine `asyncio.gather` concurrency test for MR-AC7.
- Plan-review-resolved empty/duplicate-array 422s.
- OD-1's permission-catalogue completeness check (standalone CI test, not an `env.py` hook).
- Regression: full existing suite (users/account/profile) re-verified green after the `encode_access_token` signature change and the new `perm_epoch` check.

```
281 passed, 97.27% coverage (floor 85%)
```

## Config Changes

`.env.example` gained `PERM_EPOCH_TTL_SECONDS=900`, matching the new `app/core/config.py` setting — confirmed in sync.

## Commit Hygiene Note

This branch's diff also includes `docs/decisions/US-2.5-*.md` and `docs/evidence/US-2.5-*.md` — not US-3.2's own implementation, but the clarification-round artifacts that discovered and documented *why* this story was prioritized (US-2.5 blocked on it). Flagging for visibility rather than silently bundling; recommend keeping them in this PR since they're the direct causal record for the branch's existence, but split them out first if a cleaner history is preferred.

---

**This is a draft only.** Pushing the branch or opening the PR on GitHub requires an explicit instruction — nothing here has been pushed or submitted.
