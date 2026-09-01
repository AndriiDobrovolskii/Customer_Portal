# PR Draft: US-2.3 — Refresh Token

**Status:** Drafted content only. Pushing the branch or opening the PR requires an explicit separate instruction — this skill never runs `git push`/`gh pr create` on its own.

## Gate confirmation (all four required, all Pass)

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | Pass | Chat report, 2026-09-01 — 7/7 pre-commit hooks green, mypy strict clean (81 files), import-linter clean, 213/213 tests, 97.24% coverage (85% floor; `service.py` 99%, `router.py` 100%), migration cycle proven |
| implementation-verifier | Pass | `docs/verification/US-007-verification-report.md` (found + fixed one gap same-day: missing dedicated "no cookie" security-case test, this project's own per-route pattern) |
| security-reviewer | Pass | `docs/security/US-007-security-review.md` (all 6 §7 rows Pass/N/A; dedicated IDOR-analog analysis prompted by US-2.2's own post-Pass finding found no equivalent gap — refresh has a single credential, no second identity to reconcile against; 3 [Low] advisories, all disclosed/already-accepted tradeoffs) |
| reconciliation-reviewer | Pass | `docs/reconciliation/US-007-reconciliation-report.md` (found + fixed two matrix-accuracy gaps same-day: RT-AC6's row pointed at a never-written repository-test file; two function names were stale after a line-length-driven rename) |

## Commit hygiene — no flags this time

Every new `docs/*` file for this story shows as untracked (`??`) in `git status`, not silently excluded — unlike US-2.1/US-2.2, this story hit no stale-`.gitignore` bug (those were already fixed by US-2.2's own PR). No unrelated files, no drive-by refactors (`AGENTS.md` §7.8). `.env.example`/`app/core/config.py` are unchanged — the rate limit (60/family/hour), grace window (10s), and idle timeout (14 days) are module-level constants in `service.py`, not settings, per the plan's stated Validation Strategy.

## Suggested PR title

`feat: implement US-2.3 refresh token (POST /v1/auth/refresh)`

## Summary

- Implements `POST /v1/auth/refresh` per `docs/specifications/US-007-refresh-token-spec.md` (spec review: Pass with Issues, accepted; all findings resolved) and `docs/stories/US-2.3-refresh-token.md` (RT-AC1–RT-AC6): single-use rotation with an atomic Postgres check-and-consume, reuse detection with family-wide revocation + `severity=high` audit entry + security email, idle (14-day) and absolute (30-day) lifetime enforcement, denial for deactivated/revoked accounts, atomic handling of concurrent same-token requests, and a per-family rate limit (60/hour).
- **Resolved OD-1–OD-6** (`docs/decisions/US-2.3-open-decisions.md`, found via `us-clarifier` reading the now-shipped US-2.1/US-2.2 codebase): rate-limit response is `429`+`Retry-After` reusing the existing throttle pattern; mobile (`X-Client-Type`) body-delivery descoped as a follow-up; RT-AC3's "indistinguishable" scoped to status/body only (no timing-safe dummy needed, unlike login); dedicated `auth_audit_log.severity` column added; reuse detection checked before account-eligibility (always alerts, even against a deactivated account); accepted a ≤15-minute residual access-token window on reuse rather than linking `user_sessions` to `refresh_tokens.family_id`.
- **Five-step check order** (resolved OD-5, refined by a same-day spec-review addendum for the rate-limit's position and the expired-vs-reused precedence): unknown → rate limit → expired/absolute-cap → revoked-by-logout → reuse → account eligibility → idle timeout → atomic consume-and-rotate. Implemented as one linear sequence in `rotate_refresh_token()` (`app/modules/users/service.py`) rather than independently-callable checks, specifically to prevent future reordering from silently reopening the resolved-OD-5 ambiguity.
- **Atomic consume via Postgres, not Valkey**: `UPDATE refresh_tokens SET consumed_at = now() WHERE token_hash = :hash AND consumed_at IS NULL RETURNING *` (`repository.py::consume_refresh_token`) — the row is already the state's source of truth, so no second system was introduced for the same fact. Proven under genuine concurrent load, not simulated (`test_refresh_concurrent_requests_exactly_one_succeeds`, `asyncio.gather` against real Postgres).
- **Found and fixed, unanticipated by the plan:** `UserRepository.get_by_id` didn't exist — needed for the account-eligibility check and the reuse-alert email's recipient lookup — added directly (same "unowned/missing infra" pattern as prior stories' T0-style additions). Rotation also needed a new `user_sessions` row for each newly-issued access token (otherwise it could never authenticate); reused the existing `create_session` method, no new repository method required.
- **Found and fixed, unanticipated by the plan:** `EmailSender`'s new `send_refresh_reuse_alert` method broke `RecordingEmailSender` fakes in `email_verification`'s and `profile`'s own unit test suites — the protocol is shared `app/core/` infrastructure, not users-only. Both fakes updated.

**Linked docs:** spec `docs/specifications/US-007-refresh-token-spec.md` · open decisions `docs/decisions/US-2.3-open-decisions.md` (6 resolved) · plan `docs/plans/US-007-implementation-plan.md` · task breakdown `docs/plans/US-007-task-breakdown.md`.

## Test plan

- **Unit** (`tests/unit/modules/users/test_users_service.py`, 17 new tests): every branch of `rotate_refresh_token()` — successful rotation preserving `family_id`/`expires_at`, a new `user_sessions` row for the new access token, reuse detection (including against a deactivated account and an email-send failure that doesn't block the response), unknown/no-cookie/revoked-by-logout/expired-and-reused precedence, idle timeout (with and without the `last_used_at` fallback to `issued_at`), absolute cap regardless of recent use, account ineligibility (deactivated + `revoke_before`), the concurrent-race grace window, and the rate limit.
- **Integration** (`tests/integration/modules/users/test_users_router.py`, 10 new tests): full HTTP round trip for RT-AC1–RT-AC6 against real Postgres + Valkey — `200` + rotated cookie + persisted state (RT-AC1), `401` + persisted family-wide revocation + `severity=high` audit row (RT-AC2), a byte-identical `401` body across unknown/expired/revoked plus a dedicated no-cookie case (RT-AC3), idle timeout and absolute cap (RT-AC4), deactivated account and `revoke_before` driven through the real `/logout-all` endpoint (RT-AC5), genuine concurrent requests via `asyncio.gather`/`real_client` proving the atomic consume for real (RT-AC6), and the `429` rate-limit response.
- **Result:** 213/213 tests pass (186 + 27 new), 97.24% coverage (85% required; `service.py` 99%, `router.py` 100%). Migration `upgrade → downgrade → upgrade` proven against a standalone Postgres container; resulting schema independently confirmed via `\d` on both changed tables.
- Full traceability: `docs/tests/US-007-traceability-matrix.md` (6/6 AC → test mapping, reconciled against actual shipped test names — two stale references found and fixed during reconciliation).

## Risk / rollback

- Per `docs/plans/US-007-implementation-plan.md`'s Risks section: the five-step check order is this story's highest-severity risk (a misordering would silently reopen the resolved-OD-5/OD-3 security guarantees) — mitigated by implementing it as one linear early-return sequence, with a dedicated test asserting a token that is both consumed and belongs to a deactivated account still triggers full reuse-alerting.
- FR-7's atomicity depends entirely on the single `UPDATE ... WHERE consumed_at IS NULL RETURNING` statement — no other code path reads then separately writes `consumed_at`.
- Migration is additive only (5× `ADD COLUMN ... NULL`) — no backfill, no destructive change, clean `downgrade()`.
- Rollback: `alembic downgrade -1` reverses the schema change; reverting the code commit removes the endpoint's behavior. The `UserRepository.get_by_id` addition and the two `RecordingEmailSender` fake updates are safe to keep even on a rollback of this story's endpoint — neither changes behavior outside what this story itself needs.

## `.env.example` alignment

Confirmed — no new setting was introduced by this story; `app/core/config.py` and `.env.example` are both unchanged, matching the plan's stated Validation Strategy (rate limit/grace window/idle timeout are hardcoded constants, not `Settings` fields, same as the pre-existing idle/absolute thresholds).

## Files to stage

```
.secrets.baseline
app/core/cache_keys.py
app/core/email.py
app/modules/users/cache.py
app/modules/users/dependencies.py
app/modules/users/exceptions.py
app/modules/users/models.py
app/modules/users/repository.py
app/modules/users/router.py
app/modules/users/schemas.py
app/modules/users/service.py
migrations/versions/c8eeaa6b5ff6_add_refresh_rotation_columns.py   (new)
tests/integration/modules/users/test_users_router.py
tests/unit/modules/email_verification/test_email_verification_service.py
tests/unit/modules/profile/test_profile_service.py
tests/unit/modules/users/test_users_service.py
docs/catalog/US-2.3-pipeline-status.md                       (new)
docs/decisions/US-2.3-open-decisions.md                      (new)
docs/designs/api/US-007-api-design.md                          (new)
docs/designs/api/US-007-openapi.yaml                            (new)
docs/designs/database/US-007-db-design.md                       (new)
docs/designs/database/US-007-entity-model.md                     (new)
docs/evidence/US-2.3-clarification-report.md                  (new)
docs/impact-analysis/US-007-impact-analysis.md                   (new)
docs/plans/US-007-implementation-plan.md                         (new)
docs/plans/US-007-task-breakdown.md                               (new)
docs/reconciliation/US-007-reconciliation-report.md               (new)
docs/reviews/plans/US-007-plan-review.md                           (new)
docs/reviews/specifications/US-007-spec-review.md
docs/security/US-007-security-review.md                             (new)
docs/specifications/US-007-refresh-token-spec.md
docs/tests/US-007-traceability-matrix.md                             (new)
docs/verification/US-007-verification-report.md                       (new)
docs/workflow/active-story.yaml
```

**Not included — a separate, already-pushed commit:** `docs: add Ukrainian communication instruction, backfill US-2.1 clarification report` (`37a88a4`), which landed directly on `main` before this story's work began; not part of this diff.

---

**This is drafted content only.** Nothing has been staged as a commit, committed, or pushed. Say the word if you'd like it staged, committed, and/or the PR opened via `gh pr create`.
