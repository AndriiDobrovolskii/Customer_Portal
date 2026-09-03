# PR: Implement US-2.6 — Active Session Management

**Branch:** `feat/us-2.6-active-sessions` → `main`
**Story:** `docs/stories/US-2.6-active-sessions.md` · **Spec:** `docs/specifications/US-2.6-spec.md`

## Title

```
feat: implement US-2.6 active session management
```

## Summary

Adds self-service session management: listing every live login session (refresh-token family) with privacy-safe metadata (approximate location, device/browser label, last-used time, current-device flag), and revoking any one of them individually — reusing US-2.2's existing revocation mechanism, not a new one.

- **2 new endpoints:** `GET /v1/auth/sessions` (list), `DELETE /v1/auth/sessions/{family_id}` (revoke one).
- **A "session" is a derived view, not a new table:** every column this story reads (`family_id`, `ip`, `user_agent`, `last_used_at`, `revoked_at`) already existed from US-2.1/US-2.2/US-2.3 — the only schema change is one composite index and one audit-log column.
- **Current-session identification via cookie, not JWT:** both routes read the optional `refresh_token` cookie (the same one `/auth/refresh`/`/auth/logout` already read), hash it, and match it to a live token — no new JWT claim.
- **Live-session cap (20 families/user) with row-locked eviction:** the login path now evicts the oldest family when a login would exceed the cap, under a `SELECT...FOR UPDATE` scoped to the acting user only — proven safe under real concurrent logins, not just assumed.
- **2 new dependencies:** `user-agents` (device/browser label parsing) and `geoip2` (MaxMind GeoLite2-City reader) — the `.mmdb` database itself is fetched at build/deploy time, not committed to this repo.
- Revoking the caller's own current session is rejected (`409`) rather than silently performed — logout already owns that.

## Test Plan

Full pipeline: CLARIFICATION → SPECIFICATION → SPEC_REVIEW → DESIGN → PLANNING → TESTS → IMPLEMENTATION → VERIFICATION → SECURITY_REVIEW → RECONCILIATION, all gates Pass.

- [x] **gate-enforcer:** PASS — 7/7 pre-commit hooks (ruff lint+format, mypy strict, import-linter 6/6 contracts, unit tests, no-mock-in-integration-tests, detect-secrets), `mypy app tests` clean (101 files), 409/409 tests passing (243 unit + 166 integration), 97.42% coverage (floor 85%; `service.py` 97%, `router.py`/`geoip.py`/`device.py` 100%). Two migrations (`5dccea7a3749`, `db8cbd5e3697`) each proven `upgrade → downgrade → downgrade → upgrade → upgrade` against real Postgres.
- [x] **implementation-verifier:** Pass (`docs/verification/US-2.6-implementation-verification.md`) — ORM containment, eager-loading N/A (no new relationship), cache-TTL N/A (no `cache.py` change), cross-module discipline, `response_model`/`.env.example`/no-sensitive-field all confirmed. No gaps found.
- [x] **security-reviewer:** Pass (`docs/reviews/security/US-2.6-security-review.md`) — all 6 `AGENTS.md` §7 rows Pass (3 N/A: this story adds no credential handling or inbound schema). 2 Low advisory findings noted (regex-based UA parsing on stored attacker-controlled input; the new `geoip_database_path` setting shares the existing `breached_password_list_path` trust model), neither forcing a Fail.
- [x] **reconciliation-reviewer:** Pass (`docs/reviews/reconciliation/US-2.6-reconciliation.md`) — all 5 source ACs (SM-AC1–SM-AC5) plus FR-6/FR-7 (no-AC, Open-Decision-derived) have full, verified test coverage at the status/body/persisted-state level. No spec drift found.
- [x] `docs/tests/US-2.6-ac-test-matrix.md` — full AC → test mapping, unit vs. integration split.

## Risk / Rollback Notes

- **Additive-and-index-only migration, split for the write-heavy table hazard:** `5dccea7a3749` adds one nullable `auth_audit_log.target_family` column (guarded `add_column`/`drop_column`); `db8cbd5e3697` adds the `refresh_tokens` composite index via `CREATE INDEX CONCURRENTLY` in its own migration (`autocommit_block()`), since `refresh_tokens` is written on every login/refresh — a plain `CREATE INDEX` would have locked that table. No data loss on rollback (`downgrade()` is real and proven for both).
- **2 new pyproject.toml dependencies** (`user-agents`, `geoip2`) — explicitly approved by the user, distinct from the Open Decisions that approved the mechanism, not the package names.
- **New required deploy-time step, not a code dependency:** the GeoLite2-City `.mmdb` file must be fetched via a license key at build/deploy time (`app/core/geoip.py` degrades to omitting location when the file is absent — confirmed by `test_geoip_lookup_missing_database_file_returns_none`, so its absence in any environment, including this one, never breaks the app).
- **New settings**: `MAX_LIVE_SESSIONS_PER_USER` (default 20), `GEOIP_DATABASE_PATH` — both have safe defaults, no environment fails to start without an override.
- The row-locked cap-eviction path (flagged in `docs/plans/US-2.6-implementation-plan.md`'s Risks as the concurrency-sensitive line) is proven under genuine concurrent load: `test_concurrent_logins_at_cap_boundary_never_exceed_cap` runs two real simultaneous logins via `real_client`/`asyncio.gather` and asserts the final live-family count never exceeds the cap.

## Config

`.env.example` updated with both new settings this story introduces: `MAX_LIVE_SESSIONS_PER_USER`, `GEOIP_DATABASE_PATH` — confirmed matching `app/core/config.py` 1:1.

## Commit Hygiene

Confirmed via `git status`: every changed/new file traces to this story's scope — the `users` module (schemas/models/repository/router/service/exceptions), 2 new `app/core/` primitives (`geoip.py`, `device.py`), `app/core/config.py`, 2 new migrations, tests, `pyproject.toml`/`.env.example`/`.secrets.baseline` for the 2 approved dependencies, and this story's own `docs/` artifacts. No unrelated file and no drive-by refactor outside this scope.

---

**This is drafted content only.** Pushing the branch and opening the PR (`git push` / `gh pr create`) require an explicit, separate instruction.
