# PR Draft: US-2.4 — Password Reset

**Status:** Drafted content only. Pushing the branch or opening the PR requires an explicit separate instruction — this skill never runs `git push`/`gh pr create` on its own.

## Gate confirmation (all four required, all Pass)

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | Pass | Chat report, 2026-09-01 — 7/7 pre-commit hooks green, mypy strict clean (82 files), import-linter clean, 244/244 tests, 97.12% coverage (85% floor; `service.py` 98%, `router.py` 100%), migration cycle proven |
| implementation-verifier | Pass | `docs/verification/US-008-verification-report.md` — no ORM leak, eager-loading N/A (no relationships touched), every rate-limit cache write TTL'd, no new cross-module coupling, §5's four-security-case table N/A (both endpoints intentionally unauthenticated) |
| security-reviewer | Pass | `docs/security/US-008-security-review.md` — all 6 §7 rows Pass, including a reasoned-through analysis of PR-AC4's spec-required `token-expired`/`token-invalid` split (precedented by `email_verification`, doesn't leak account existence); 3 Low advisories, all disclosed/pre-existing/already-accepted |
| reconciliation-reviewer | Pass | `docs/reconciliation/US-008-reconciliation-report.md` — found + fixed two matrix-accuracy gaps same-day: 5 test functions renamed during T6 for line-length, 1 test (unverified-account eligibility) missing its row; 1 Low Spec Drift finding disclosed (unverified-account exclusion, no external contract change) |

## Commit hygiene — no flags

Every new `docs/*` file for this story shows as untracked (`??`) in `git status`, not silently excluded by a stale `.gitignore` (that class of bug was fixed by US-2.2's own PR). No unrelated files, no drive-by refactors (`AGENTS.md` §7.8). `.env.example` and `app/core/config.py` both gained the same 5 new settings — confirmed aligned.

## Suggested PR title

`feat: implement US-2.4 password reset (POST /v1/auth/password-reset/*)`

## Summary

- Implements `POST /v1/auth/password-reset/request` and `POST /v1/auth/password-reset/confirm` per `docs/specifications/US-008-password-reset-spec.md` (spec review: Pass with Issues, accepted; all findings resolved) and `docs/stories/US-2.4-password-reset.md` (PR-AC1–PR-AC6): single-use, 30-minute reset tokens with anti-enumeration on the request endpoint, atomic Postgres check-and-consume on confirm, three-limit request throttling, a local breached-password check, and full session/refresh-family revocation plus a security notification on a successful reset.
- **Resolved OD-1–OD-3** (`docs/decisions/US-2.4-open-decisions.md`, found via `us-clarifier` reading the now-shipped US-2.1/US-2.2/US-2.3 codebase): breached-password check is a local static list/bloom filter, never a live third-party call (this codebase's first and only fully self-contained check of its kind); the three request-throttle limits are checked in cooldown → per-account/hour → per-IP/hour order; the request endpoint writes an `auth_audit_log` entry on every attempt, including unknown/deactivated accounts.
- **Two of the pre-existing spec's own open questions resolved by direct precedent, not invention**: PR-AC4's expired/consumed/unknown token-state mapping (`email_verification`'s identical split), and no dedicated email-format validation on the request endpoint (`LoginRequest.email`'s existing precedent).
- **Spec-review-accepted atomic consumption**: `UPDATE password_reset_tokens SET consumed_at = now() WHERE token_hash = :hash AND consumed_at IS NULL RETURNING *` (`repository.py::consume_password_reset_token`), the same pattern as US-2.3's refresh-token consumption — proven under genuine concurrent load, not simulated (`test_password_reset_confirm_concurrent_same_token_exactly_one_succeeds`, `asyncio.gather` against real Postgres).
- **Rate-limit keying deliberately deviates from `LoginThrottleCache`'s precedent**: the account-scoped cooldown/hourly counters are keyed by a SHA-256 hash of the normalized email, not `user_id` — necessary because anti-enumeration requires the same throttling to apply to an email with no account at all.
- **Found and fixed, unanticipated by the plan:** `UserRepository.update_password_hash` didn't exist — no prior write path actually covered replacing an existing user's password hash (registration inserts a new row, login never writes it). A schema-level `min_length=12` on `new_password` was also found to short-circuit before the service's unified `PasswordPolicyError` could run, producing the wrong error envelope for the too-short case — removed per `AGENTS.md` §4.4.5's joint-validation rule. The `confirm` route also returned a literal JSON `null` body at `200` instead of the story's stated empty body — fixed by returning `Response(status_code=200)` explicitly.
- **Found and fixed, unanticipated by the plan:** `EmailSender`'s two new methods broke `RecordingEmailSender` fakes in `email_verification`'s and `profile`'s own unit test suites — same class of ripple US-2.3 hit for the identical reason (shared `app/core/` infrastructure). Both fakes updated.
- **Surfaced but not fixed (out of this story's scope):** US-2.3's own RT-AC6 concurrency integration test passes vacuously — its final assertion queries via a fresh `engine.connect()` that can never see this test infrastructure's uncommitted savepoint-nested writes, so an empty query result silently satisfies a for-loop with zero iterations. Flagged for a possible follow-up (`AGENTS.md` §7.8 — no drive-by fix here); this story's own equivalent assertion was written against `db_session` instead, which does see the writes.

**Linked docs:** spec `docs/specifications/US-008-password-reset-spec.md` · open decisions `docs/decisions/US-2.4-open-decisions.md` (3 resolved) · plan `docs/plans/US-008-implementation-plan.md` · task breakdown `docs/plans/US-008-task-breakdown.md`.

## Test plan

- **Unit** (`tests/unit/modules/users/test_users_service.py`, 20 new tests): every branch of `request_password_reset()`/`confirm_password_reset()` — token issuance + prior-token invalidation + audit entry, anti-enumeration for unknown/deactivated/unverified accounts (each still writing the audit entry), all three throttle limits plus the resolved check-order precedence, password replacement + revocation + notification + audit on success, all three token-state rejections (unknown/consumed/expired), all three policy rejections (short/breached/reused) each proving the token survives, and the atomic-consume race.
- **Integration** (`tests/integration/modules/users/test_users_router.py`, 10 new tests): full HTTP round trip against real Postgres + Valkey — `202` + generic body + persisted token + audit row, byte-identical body for a known vs. unknown email, `200` + persisted Argon2id hash change, real session/refresh-cookie revocation proven via protected-route probes (not just a cache-call assertion), all three `400`/`422` rejection paths with real DB rows, a real retry-after-rejection success, `429` with `Retry-After`, and a genuine concurrent `confirm` race via `asyncio.gather`/`real_client` proving the atomic consume for real.
- **Result:** 244/244 tests pass (214 + 30 new), 97.12% coverage (85% required; `service.py` 98%, `router.py` 100%). Migration `upgrade → downgrade → upgrade` proven against a standalone Postgres container; resulting schema independently confirmed via `\d password_reset_tokens`.
- Full traceability: `docs/tests/US-008-traceability-matrix.md` (6/6 AC → test mapping, reconciled against actual shipped test names — 2 accuracy gaps found and fixed during reconciliation).

## Risk / rollback

- Per `docs/plans/US-008-implementation-plan.md`'s Risks section: the anti-enumeration timing discipline (unknown/deactivated/unverified paths must cost comparably to the real path) is this story's subtlest risk — mitigated by keeping the code-path shape identical (lookup → rate-limit check → early-return) rather than branching structurally.
- FR-2/atomicity depends entirely on the single `UPDATE ... WHERE consumed_at IS NULL RETURNING` statement — no other code path reads then separately writes `consumed_at`.
- Migration is additive only (one wholly new table, no `ALTER` on any existing table) — no backfill, no destructive change, clean `downgrade()`.
- Rollback: `alembic downgrade -1` reverses the schema change; reverting the code commit removes both endpoints' behavior. `UserRepository.update_password_hash` and the two `RecordingEmailSender` fake updates are safe to keep even on a rollback of this story's endpoints — neither changes behavior outside what this story itself needs.

## `.env.example` alignment

Confirmed — 5 new settings introduced by this story (`PASSWORD_RESET_TOKEN_TTL_MINUTES`, `PASSWORD_RESET_COOLDOWN_SECONDS`, `PASSWORD_RESET_ACCOUNT_HOURLY_LIMIT`, `PASSWORD_RESET_IP_HOURLY_LIMIT`, `BREACHED_PASSWORD_LIST_PATH`) all appear in both `app/core/config.py` and `.env.example` (the latter was found missing them during gate-enforcer's own §6.7 spot-check and fixed same-day).

## Files to stage

```
.env.example
.secrets.baseline
app/core/breached_passwords.py                                    (new)
app/core/data/common_passwords.txt                                (new)
app/core/cache_keys.py
app/core/config.py
app/core/email.py
app/modules/users/cache.py
app/modules/users/dependencies.py
app/modules/users/exceptions.py
app/modules/users/models.py
app/modules/users/repository.py
app/modules/users/router.py
app/modules/users/schemas.py
app/modules/users/service.py
migrations/versions/9a4776e19934_add_password_reset_tokens.py     (new)
tests/integration/modules/users/test_users_router.py
tests/unit/modules/email_verification/test_email_verification_service.py
tests/unit/modules/profile/test_profile_service.py
tests/unit/modules/users/test_users_service.py
docs/catalog/US-2.4-pipeline-status.md                             (new)
docs/decisions/US-2.4-open-decisions.md                            (new)
docs/designs/api/US-008-api-design.md                              (new)
docs/designs/api/US-008-openapi.yaml                               (new)
docs/designs/database/US-008-db-design.md                          (new)
docs/designs/database/US-008-entity-model.md                       (new)
docs/evidence/US-2.4-clarification-report.md                       (new)
docs/impact-analysis/US-008-impact-analysis.md                     (new)
docs/plans/US-008-implementation-plan.md                           (new)
docs/plans/US-008-task-breakdown.md                                (new)
docs/reconciliation/US-008-reconciliation-report.md                (new)
docs/reviews/plans/US-008-plan-review.md                           (new)
docs/reviews/specifications/US-008-spec-review.md
docs/security/US-008-security-review.md                            (new)
docs/specifications/US-008-password-reset-spec.md
docs/tests/US-008-traceability-matrix.md                           (new)
docs/verification/US-008-verification-report.md                    (new)
docs/workflow/active-story.yaml
docs/workflow/history.jsonl
docs/workflow/workflow-state.yaml
```

**Note:** `docs/workflow/*` also carries this session's US-2.3 tracking-file reconciliation (those files were stale from a prior session — backfilled before this story began, per `workflow-state.yaml`'s own note) — not scope creep from this story, but bundled in the same three files since they're append-only/single-current-state trackers.

---

**This is drafted content only.** Nothing has been staged as a commit, committed, or pushed. Say the word if you'd like it staged, committed, and/or the PR opened via `gh pr create`.
