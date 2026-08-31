# PR Draft: US-004 — Deactivate Account

**Status:** Drafted content only. Pushing the branch or opening the PR requires an explicit separate instruction — this skill never runs `git push`/`gh pr create` on its own.

## Gate confirmation (all four required, all Pass)

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | Pass | Chat report, 2026-08-30 — 145/145 tests, 96.84% coverage, 6/6 import-linter contracts, migration cycle verified |
| implementation-verifier | Pass | `docs/verification/US-004-verification-report.md` |
| security-reviewer | Pass | `docs/security/US-004-security-review.md` |
| reconciliation-reviewer | Pass | `docs/reconciliation/US-004-reconciliation-report.md` |

## ⚠️ Commit hygiene flag — read before staging

`git status` shows unrelated pending changes under `.claude/skills/` (new/modified skill definitions) that predate this story's work and are not part of US-004. **Do not include `.claude/` in this PR's commit** — stage only the files listed below. Bundling them would violate `AGENTS.md` §7.8 ("no drive-by... unrelated files").

## Suggested PR title

`feat: implement US-004 deactivate account (POST /v1/account/deactivate)`

## Summary

- Implements self-service account deactivation per `docs/specifications/US-004-deactivate-account-spec.md` (spec review: Pass): `POST /v1/account/deactivate` verifies the caller's current password, atomically transitions the account to `deactivated` (guarding against a concurrent double-deactivation race), writes an `account_lifecycle_audit_log` entry, and sets a `revoke_before:{user_id}` Valkey key so every pre-existing access token is rejected on its next use.
- Introduces this project's first Valkey infrastructure: connection pool wired in `app.main`'s `lifespan`, `RevocationCache` gateway (`app/core/revocation_cache.py`) as a shared, fail-closed token-denylist primitive per `AGENTS.md` §3 — approved dependency addition `redis>=5.0` (user sign-off recorded in `docs/plans/US-004-implementation-plan.md`).
- Extends `UserService.get_authenticated_user` (the shared auth dependency every route depends on) to reject any token issued before the account's `revoke_before` timestamp, failing closed on a cache-read error.
- New module `app/modules/account/` (models, schemas, repository, service, router, dependencies, exceptions), plus `app/modules/users/models.py`'s new `deactivated_at` column and `UserStatus.ACTIVE`/`DEACTIVATED` enum members.
- FR-4–FR-10 (login/refresh/reactivation/purge-job/admin-deactivation behavior) are explicitly **not** implemented here — they're owned by US-005/US-006/US-007/US-011 and a future cron story; see `docs/designs/api/US-004-api-design.md`'s FR-ownership table.

**Linked docs:** spec `docs/specifications/US-004-deactivate-account-spec.md` · plan `docs/plans/US-004-implementation-plan.md` · task breakdown `docs/plans/US-004-task-breakdown.md`.

## Test plan

- **Unit** (`tests/unit/modules/account/test_account_service.py`, 3 tests): correct-password success (asserts status/timestamp update, cache write with TTL, audit log entry), wrong-password 401, already-deactivated 409.
- **Unit** (`tests/unit/modules/users/test_users_service.py`, +4 tests): `get_authenticated_user`'s new `revoke_before` branch — token before/after the revocation timestamp, absent timestamp, and a simulated cache-read error (fail-closed proof).
- **Integration** (`tests/integration/modules/account/test_account_router.py`, 9 tests): full HTTP round trip for 200/401/409, a genuine concurrent-request race (`asyncio.gather`, real independent connections) proving exactly one of two simultaneous requests succeeds, reuse-of-pre-deactivation-token → 401, and all four `AGENTS.md` §5 security cases (no token / expired / malformed / revoked session) for the new route.
- **Result:** 145/145 tests pass, 96.84% coverage (85% required), confirmed across 3 consecutive full-suite runs. Migration `upgrade → downgrade → upgrade` proven via the test suite's session-scoped testcontainer fixture, no errors.
- Full traceability: `docs/tests/US-004-traceability-matrix.md` (AC → test function, reconciled against actual shipped test names).

## Risk / rollback

- Per `docs/plans/US-004-implementation-plan.md`'s Risks section: the `users/service.py` change touches the shared auth dependency every existing authenticated route depends on (`profile`) — mitigated by an explicit test proving an active user's token is unaffected (`revoke_before` absent).
- Migration is purely additive (`ADD COLUMN ... NULL`, `CREATE TABLE`) — no backfill, no `CONCURRENTLY` hazard, clean `downgrade()`.
- Rollback: `alembic downgrade -1` reverses the schema change; reverting the code commit removes the endpoint and the auth-dependency check (the Valkey infra and `redis` dependency can stay — inert until a future story reads `revoke_before` again).

## `.env.example` alignment

Confirmed — `VALKEY_URL=redis://localhost:6379/0` added alongside `app/core/config.py`'s new `valkey_url` setting.

## Files to stage (excludes `.claude/` and this repo's gitignored pipeline-artifact directories)

**Correction:** the first draft of this list wrongly included `docs/plans/`, `docs/impact-analysis/`, `docs/designs/`, `docs/verification/`, `docs/security/`, `docs/reconciliation/`, `docs/reviews/plans/`, `docs/tests/`, `docs/catalog/`, `docs/pr/` — every one of those directories carries its own `.gitignore` (`*` / `!.gitignore`), a deliberate repo convention keeping pipeline working-docs out of history (confirmed via `git check-ignore -v`; contrast `docs/specifications/` and `docs/reviews/specifications/`, which *are* tracked and already committed, unchanged by this story). Corrected list below.

```
.env.example
app/api/v1/router.py
app/core/cache_keys.py                          (new)
app/core/config.py
app/core/revocation_cache.py                    (new)
app/db/dependencies.py
app/main.py
app/modules/account/                            (new)
app/modules/users/dependencies.py
app/modules/users/models.py
app/modules/users/schemas.py
app/modules/users/service.py
migrations/versions/7e371ad49a0a_add_account_deactivation.py   (new)
pyproject.toml
uv.lock
tests/conftest.py
tests/integration/modules/account/              (new)
tests/unit/modules/account/                     (new)
tests/unit/modules/users/test_users_service.py
docs/workflow/active-story.yaml
docs/workflow/workflow-state.yaml
docs/workflow/history.jsonl
.secrets.baseline
```

---

**This is drafted content only.** Nothing has been staged, committed, or pushed. Say the word if you'd like it staged/committed (excluding `.claude/`, per the flag above) or the PR opened via `gh pr create`.
