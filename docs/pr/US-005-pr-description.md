# PR Draft: US-2.1 — Login

**Status:** Drafted content only. Pushing the branch or opening the PR requires an explicit separate instruction — this skill never runs `git push`/`gh pr create` on its own.

## Gate confirmation (all four required, all Pass)

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | Pass | Chat report, 2026-08-31 — 7/7 pre-commit hooks green, mypy strict clean (81 files), lint-imports clean (6/6), 167/167 tests, 97.16% coverage, migration cycle proven |
| implementation-verifier | Pass | `docs/verification/US-005-verification-report.md` |
| security-reviewer | Pass | `docs/security/US-005-security-review.md` |
| reconciliation-reviewer | Pass | `docs/reconciliation/US-005-reconciliation-report.md` (found + fixed one gap same-day: a missing test surfaced a real `verify_password_dummy()` logic bug, harmless in production since its return value was never used, now fixed) |

## ⚠️ Commit hygiene flags — read before staging

1. **`.gitignore` fix, deliberately included in this PR (user-approved 2026-08-31).** Eleven directories (`docs/{catalog,designs/api,designs/database,impact-analysis,plans,pr,reconciliation,reviews/plans,security,tests,verification}`) each carried a `*`/`!.gitignore` rule written when the directory was still empty — silently excluding every pipeline doc from git ever since, including all of US-004's own plan/design/verification/security/reconciliation docs (confirmed still untracked on disk today). A prior session's `US-004-pr-description.md` draft speculated this was "a deliberate repo convention" — re-investigated this session and concluded that reading doesn't hold up (the comment literally says "currently empty," and the whole point of this pipeline is a durable audit trail). User explicitly chose to fix it and include this story's own docs; US-004's equivalent docs are deliberately left untracked for now as a possible separate follow-up commit, not silently bundled here.
2. **Everything staged below is this story's own scope** — no unrelated files, no drive-by refactors (`AGENTS.md` §7.8). `pyproject.toml`/`uv.lock` are unchanged (no new dependency was needed — `secrets`/`hashlib` are stdlib).

## Suggested PR title

`feat: implement US-2.1 login (POST /v1/auth/login)`

## Summary

- Implements `POST /v1/auth/login` per `docs/specifications/US-005-login-spec.md` (spec review: Pass with Issues, accepted): credential verification, anti-enumeration timing parity via a dummy Argon2id path, brute-force throttling (10/account, 20/IP per 15 min, independent per-account reset), account-state gating, request validation, and audit logging — extending the pre-existing minimal endpoint (VE-AC5/VE-AC6 only) rather than replacing it.
- **Resolved OD-10 (found via `advisor()` review, not in the original spec text):** deactivated-account login within its 30-day grace period now reactivates the account instead of blocking it (DA-AC8), via a new cross-module `AccountService.reactivate_account()` call from `users/service.py` — the behavior US-004's own design doc had explicitly deferred to this story but the original spec never carried.
- **Resolved OD-9:** introduces a minimal `refresh_tokens` table (`token_hash`, `family_id`, `user_id`, `issued_at`, `expires_at`) for FR-1's "sets a refresh token" cookie — the source story never modeled this table, but US-2.3's own Out of Scope section assigns "initial token issuance" here.
- New `app/modules/users/cache.py` (`LoginThrottleCache`) — the module's first Valkey surface, atomic `INCR`+`EXPIRE` pipeline per write.
- `InvalidCredentialsError` reclassified from a bare `DomainError` to a `ProblemError` (proper `401 invalid-credentials` problem+json body); new `AccountDeactivatedError` (403), `TooManyAttemptsError` (429, `Retry-After` header).
- Reworked `app/main.py`'s `request_validation_error_handler` to render RFC 7807 `problem+json` (`type=".../errors/validation-failed"`, `errors: [{field, code, message}]`) instead of its previous plain-JSON shape — a pre-existing gap this story's own FR-6 needed fixed.
- **Found and fixed, user-approved:** `migrations/env.py` never imported `app.modules.account.models`, so `account_lifecycle_audit_log` was invisible to autogenerate and got proposed for deletion by this story's own migration — fixed with a one-line import (mirrors the three existing module imports already there).

**Linked docs:** spec `docs/specifications/US-005-login-spec.md` · open decisions `docs/decisions/US-2.1-open-decisions.md` (10 resolved) · plan `docs/plans/US-005-implementation-plan.md` · task breakdown `docs/plans/US-005-task-breakdown.md`.

## Test plan

- **Unit** (`tests/unit/modules/users/test_users_service.py`, 39 tests total, ~19 login-specific): every `authenticate_user` branch — success, wrong password, unknown email (dummy-verify called), unverified, deactivated past/within grace (reactivation), ordering guarantee, account/IP throttling, counter-reset asymmetry.
- **Unit** (`tests/unit/modules/account/test_account_service.py`, 6 tests, 3 new): `reactivate_account`'s within-grace/past-grace/already-active branches.
- **Unit** (`tests/unit/core/test_security.py`, 11 tests, 4 new): dummy-verification produces a real Argon2id hash and is reused across calls (not a flaky timing threshold, per `AGENTS.md` §5's determinism rule); refresh-token generation produces distinct random raw/hash pairs.
- **Integration** (`tests/integration/modules/users/test_users_router.py`, 25 tests, 12 new/changed): full HTTP round trip for every AC — 200 with cookie attributes/persisted state, 401 (wrong password and unknown email, asserted byte-identical), 403 (unverified, deactivated-past-grace), 200-with-reactivation (persisted `users.status`/`account_lifecycle_audit_log`), 429 with real persisted Valkey throttle state, 422 (missing/unknown/empty password) with no throttle-counter increment.
- **Result:** 167/167 tests pass, 97.16% coverage (85% required). Migration `upgrade → downgrade → upgrade` proven against a standalone Postgres container, plus a follow-up autogenerate run confirming the `env.py` fix eliminated the spurious `account_lifecycle_audit_log` drop for good.
- Full traceability: `docs/tests/US-005-traceability-matrix.md` (AC → test function, reconciled against actual shipped test names — one gap found and fixed in-session, see reconciliation report).

## Risk / rollback

- Per `docs/plans/US-005-implementation-plan.md`'s Risks section: reactivation's atomic conditional update (`AccountRepository.reactivate_if_within_grace`) mirrors the existing `deactivate_if_not_already` pattern, so a concurrent duplicate call can't double-reactivate. Throttle-counter increments use a Valkey pipeline (`INCR`+`EXPIRE` together), not a read-then-write pair, so a concurrent failed login can't under-count.
- `InvalidCredentialsError`'s response-shape change (bare JSON → `problem+json`) is the one behavior change to already-shipped code — no external consumer exists yet, so this is not considered a breaking-contract risk.
- Migration is additive only (`CREATE TABLE` × 2, `ADD COLUMN ... NULL`) plus the `env.py` import fix — no backfill, no destructive change, clean `downgrade()`.
- Rollback: `alembic downgrade -1` reverses the schema change; reverting the code commit removes the endpoint's new behavior. The `env.py` import fix should be kept even on rollback — it fixes a real bug unrelated to this story's own revert.

## `.env.example` alignment

Confirmed — `LOGIN_FAILURE_THRESHOLD_ACCOUNT`, `LOGIN_FAILURE_THRESHOLD_IP`, `LOGIN_THROTTLE_WINDOW_SECONDS`, `REFRESH_TOKEN_TTL_SECONDS` all added, matching `app/core/config.py`'s four new `Settings` fields exactly.

## Files to stage

```
.env.example
.secrets.baseline
app/core/cache_keys.py
app/core/config.py
app/core/security.py
app/main.py
app/modules/account/repository.py
app/modules/account/service.py
app/modules/users/cache.py                              (new)
app/modules/users/dependencies.py
app/modules/users/exceptions.py
app/modules/users/models.py
app/modules/users/repository.py
app/modules/users/router.py
app/modules/users/schemas.py
app/modules/users/service.py
migrations/env.py
migrations/versions/1cdc08e88be9_add_login_audit_and_refresh_tokens.py   (new)
tests/integration/modules/users/test_users_router.py
tests/unit/core/test_security.py
tests/unit/modules/account/test_account_service.py
tests/unit/modules/users/test_users_service.py
docs/catalog/.gitignore                                  (fixed)
docs/catalog/US-2.1-pipeline-status.md                    (new)
docs/decisions/US-2.1-open-decisions.md                   (new)
docs/designs/api/.gitignore                               (fixed)
docs/designs/api/US-005-api-design.md                     (new)
docs/designs/api/US-005-openapi.yaml                      (new)
docs/designs/database/.gitignore                          (fixed)
docs/designs/database/US-005-db-design.md                 (new)
docs/designs/database/US-005-entity-model.md               (new)
docs/impact-analysis/.gitignore                           (fixed)
docs/impact-analysis/US-005-impact-analysis.md             (new)
docs/plans/.gitignore                                     (fixed)
docs/plans/US-005-implementation-plan.md                   (new)
docs/plans/US-005-task-breakdown.md                        (new)
docs/pr/.gitignore                                        (fixed)
docs/reconciliation/.gitignore                            (fixed)
docs/reconciliation/US-005-reconciliation-report.md        (new)
docs/reviews/plans/.gitignore                             (fixed)
docs/reviews/plans/US-005-plan-review.md                   (new)
docs/reviews/specifications/US-005-spec-review.md
docs/security/.gitignore                                  (fixed)
docs/security/US-005-security-review.md                    (new)
docs/specifications/US-005-login-spec.md
docs/tests/.gitignore                                     (fixed)
docs/tests/US-005-traceability-matrix.md                   (new)
docs/verification/.gitignore                              (fixed)
docs/verification/US-005-verification-report.md            (new)
docs/workflow/active-story.yaml
docs/workflow/history.jsonl
docs/workflow/workflow-state.yaml
```

**Deliberately excluded:** `docs/catalog/US-004-pipeline-status.md`, `docs/designs/api/US-004-*`, `docs/designs/database/US-004-*`, `docs/impact-analysis/US-004-*`, `docs/plans/US-004-*`, `docs/pr/US-004-pr-description.md`, `docs/reconciliation/US-004-*`, `docs/reviews/plans/US-004-*`, `docs/security/US-004-*`, `docs/tests/US-004-*`, `docs/verification/US-004-*` — all still-untracked from before this session, out of scope for this story's PR (see hygiene flag #1 above).

---

**This is drafted content only.** Nothing has been staged as a commit, committed, or pushed (the files above are staged in the working tree via `git add` from this session, but no commit exists yet). Say the word if you'd like it committed and/or the PR opened via `gh pr create`.
