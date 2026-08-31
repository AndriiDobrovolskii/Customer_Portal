# PR Draft: US-2.2 — Logout

**Status:** Drafted content only. Pushing the branch or opening the PR requires an explicit separate instruction — this skill never runs `git push`/`gh pr create` on its own.

## Gate confirmation (all four required, all Pass)

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | Pass | Chat report, 2026-09-01 (reverified after the IDOR fix below) — pre-commit hooks green, mypy strict clean (81 files), lint-imports clean (6/6), 186/186 tests, 97.26% coverage, migration cycle proven |
| implementation-verifier | Pass | `docs/verification/US-006-verification-report.md` (found + fixed one gap same-day: this project's own 4-case-per-route security-test pattern was missing an "expired token" case for both routes) |
| security-reviewer | Pass | `docs/security/US-006-security-review.md` (1 Low advisory: CSRF not enforced — disclosed, user-approved OD-4, not a new gap. **2026-09-01 addendum: found + fixed an IDOR** — see below) |
| reconciliation-reviewer | Pass | `docs/reconciliation/US-006-reconciliation-report.md` (found + fixed one gap same-day: LO-AC4's idempotency test didn't independently assert "no additional revocation side effects" — now asserts persisted `revoked_at` unchanged across the repeat call. **2026-09-01 addendum: reconciled against the IDOR fix** — see below) |

## ⚠️ Found and fixed after initial gate Pass, 2026-09-01: IDOR in `/logout`'s refresh-cookie handling

An independent review (not any of the four gates above, which don't have an "authorize the object a lookup returns" item) found that `UserService.logout()` revoked a hash-matched refresh-token family without checking the row's `user_id` against the authenticated caller — an attacker holding their own valid access token plus a *stolen* refresh-token value from any other user could revoke that victim's entire session family with a clean `204`. Fixed same-day in `app/modules/users/service.py`'s `logout()`: the family-revocation branch now requires `existing.user_id == user_id`, treating a cross-user match identically to a lookup-miss (silent skip, still `204`) — the same anti-enumeration shape LO-AC4 already established. Two new regression tests added (unit + integration, both named `test_logout_cross_user_refresh_cookie_does_not_revoke_other_users_family`). Full suite reverified: 186/186 pass, mypy strict clean, `pre-commit run --all-files` green. See the addenda in `docs/security/US-006-security-review.md` and `docs/reconciliation/US-006-reconciliation-report.md` for full detail.

## ⚠️ Commit hygiene flags — read before staging

1. **`.gitignore` fix, deliberately included in this PR.** Same bug class as US-2.1's own PR (see `US-005-pr-description.md` flag #1): `docs/evidence/.gitignore`, `docs/reviews/reconciliation/.gitignore`, and `docs/reviews/security/.gitignore` still carried the old `*`/`!.gitignore` rule that silently excludes a directory's contents — US-2.1's cleanup fixed eleven other directories but missed these three (they'd never held a file until this story's own `us-clarifier` and future pipeline stages needed them). Fixed the same way, using the same wording as the other eleven.
2. **`docs/evidence/US-2.1-clarification-report.md` is deliberately excluded from this PR.** Fixing `docs/evidence/.gitignore` above made this pre-existing, already-written file visible to git for the first time — it's US-2.1's own doc, silently excluded from that story's already-merged PR #2, not this story's to bundle in. Left untracked as a possible separate follow-up commit, mirroring exactly how US-2.1's own PR left US-004's stale docs untracked.
3. **Everything else staged below is this story's own scope** — no unrelated files, no drive-by refactors (`AGENTS.md` §7.8). `pyproject.toml`/`uv.lock` are unchanged (no new dependency was needed).

## Suggested PR title

`feat: implement US-2.2 logout (POST /v1/auth/logout, /v1/auth/logout-all)`

## Summary

- Implements `POST /v1/auth/logout` and `POST /v1/auth/logout-all` per `docs/specifications/US-006-logout-spec.md` (spec review: Pass with Issues, accepted): single-device and account-wide session revocation, idempotent repeat logout, and a shared unauthenticated `401` envelope — no new module, no new error class, no new Valkey surface.
- **Resolved OD-1 (found via `us-clarifier` reading the now-shipped US-2.1 codebase, not stated by the original story):** revokes via the existing `user_sessions.revoked_at` column (already the enforcement point on every authenticated request since US-2.1) instead of the story's originally-specified Valkey `jti_denylist` — no new revocation mechanism, no dual source of truth.
- **Resolved OD-2:** `POST /v1/auth/logout` alone tolerates an already-revoked jti and returns `204` (idempotent, LO-AC4), via a new `get_current_user_allow_revoked` dependency used by exactly one router function — verified via grep that no other route imports it, since a leak here would silently weaken every other route's revocation guarantee.
- **Resolved OD-3:** `refresh_tokens` gains a minimal `revoked_at` column and family-revocation capability now, since US-2.3 (which would normally add this) hasn't shipped yet — same "build the minimal slice ahead of the dependency story" pattern US-2.1 used for the table itself (its own resolved OD-9).
- **Resolved OD-4:** CSRF protection is explicitly descoped from this story (no CSRF mechanism exists anywhere in the codebase yet, and building one is materially bigger than "add a logout endpoint") — tracked as a follow-up, not silently dropped.
- **Resolved OD-5:** `auth_audit_log` gains a dedicated `scope` column (`session`/`all_sessions`) rather than overloading the existing `reason` column, which already has an established "why did this fail" meaning across every other row.
- **Found and fixed, unanticipated by the plan:** a `hash_refresh_token()` helper was needed in `app/core/security.py` to look up a *presented* refresh cookie (extracted from `generate_refresh_token`, which previously only hashed a token it was generating) — added directly, same "unowned shared-infra" pattern as US-2.1's `T0`-style tasks.
- **Found and fixed, unanticipated by the plan:** `tests/conftest.py`'s `client`/`real_client` fixtures used `base_url="http://test"`; httpx silently drops a `Secure`-flagged cookie replayed over plain-`http`, even through in-process `ASGITransport`. This story is the first test suite to chain the login cookie into a second request. Fixed by changing both fixtures to `base_url="https://test"` (no real TLS involved either way) — full suite reverified green.

**Linked docs:** spec `docs/specifications/US-006-logout-spec.md` · open decisions `docs/decisions/US-2.2-open-decisions.md` (6 resolved) · plan `docs/plans/US-006-implementation-plan.md` · task breakdown `docs/plans/US-006-task-breakdown.md`.

## Test plan

- **Unit** (`tests/unit/modules/users/test_users_service.py`, 45 tests total, 6 new): `logout()`'s family-revocation, missing-cookie, and lookup-miss branches; `logout_all()`'s `revoke_before` write; `get_authenticated_user(allow_revoked=True)`'s revoked-vs-unknown-jti distinction (Open Question #2 from the API design).
- **Integration** (`tests/integration/modules/users/test_users_router.py`, 36 tests total, 16 new): full HTTP round trip for LO-AC1–LO-AC5 — `204` + persisted `user_sessions.revoked_at`/`refresh_tokens.revoked_at`/`Set-Cookie` clear (matched, missing-cookie, and stale-cookie variants), `204` + `revoke_before` set + a follow-up call now `401`s, no-token/malformed/expired `401` for both routes, idempotent repeat `/logout` (204, with persisted-state-unchanged assertion added during reconciliation), and the `/logout-all` no-leniency boundary check confirming OD-2's carve-out doesn't leak beyond `/logout`.
- **Result:** 186/186 tests pass (184 + 2 IDOR regression tests added 2026-09-01), 97.26% coverage (85% required). Migration `upgrade → downgrade → upgrade` proven against a standalone Postgres container; resulting schema independently confirmed via `\d` against both changed tables.
- Full traceability: `docs/tests/US-006-traceability-matrix.md` (AC → test function, reconciled against actual shipped test names — one gap found and fixed in-session, see reconciliation report).

## Risk / rollback

- Per `docs/plans/US-006-implementation-plan.md`'s Risks section: the `allow_revoked` leniency is isolated to a single, separately-named dependency function used by exactly one router function (mechanically verified via grep) — the highest-severity risk this story carries, since a leak would silently weaken every other route's revocation guarantee.
- Migration is additive only (`ADD COLUMN ... NULL` × 2, one `CREATE INDEX`) — no backfill, no destructive change, clean `downgrade()`.
- Rollback: `alembic downgrade -1` reverses the schema change; reverting the code commit removes both endpoints' behavior. The `hash_refresh_token()` extraction in `app/core/security.py` and the `conftest.py` `base_url` fix are both safe to keep even on a rollback of this story's endpoints — neither changes behavior outside what this story itself needs.

## `.env.example` alignment

Confirmed — no new setting was introduced by this story (unlike US-2.1's four throttle/TTL settings); `app/core/config.py` and `.env.example` are both unchanged, matching the plan's stated Validation Strategy.

## Files to stage

```
.secrets.baseline
app/core/security.py
app/modules/users/dependencies.py
app/modules/users/models.py
app/modules/users/repository.py
app/modules/users/router.py
app/modules/users/service.py
migrations/versions/9f9d9263bdfc_add_logout_revocation_columns.py   (new)
tests/conftest.py
tests/integration/modules/users/test_users_router.py
tests/unit/modules/users/test_users_service.py
docs/catalog/US-2.2-pipeline-status.md                    (new)
docs/decisions/US-2.2-open-decisions.md                   (new)
docs/designs/api/US-006-api-design.md                      (new)
docs/designs/api/US-006-openapi.yaml                        (new)
docs/designs/database/US-006-db-design.md                   (new)
docs/designs/database/US-006-entity-model.md                 (new)
docs/evidence/.gitignore                                   (fixed)
docs/evidence/US-2.2-clarification-report.md                (new)
docs/impact-analysis/US-006-impact-analysis.md               (new)
docs/plans/US-006-implementation-plan.md                     (new)
docs/plans/US-006-task-breakdown.md                          (new)
docs/reconciliation/US-006-reconciliation-report.md           (new)
docs/reviews/plans/US-006-plan-review.md                      (new)
docs/reviews/reconciliation/.gitignore                       (fixed)
docs/reviews/security/.gitignore                             (fixed)
docs/reviews/specifications/US-006-spec-review.md
docs/security/US-006-security-review.md                       (new)
docs/specifications/US-006-logout-spec.md
docs/tests/US-006-traceability-matrix.md                      (new)
docs/verification/US-006-verification-report.md               (new)
docs/workflow/active-story.yaml
docs/workflow/history.jsonl
docs/workflow/workflow-state.yaml
```

**Deliberately excluded:** `docs/evidence/US-2.1-clarification-report.md` — US-2.1's own doc, only became visible in this session because this story's `.gitignore` fix uncovered it; out of scope for this story's PR (see hygiene flag #2 above).

---

**This is drafted content only.** Nothing has been staged as a commit, committed, or pushed. Say the word if you'd like it staged, committed, and/or the PR opened via `gh pr create`.
