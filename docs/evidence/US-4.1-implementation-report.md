---
artifact_type: implementation_report
story: US-4.1
version: 5
status: ARCHIVED
created_at: "2026-09-04T00:10:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.1-task-breakdown.md
    version: 1
  - path: docs/tests/US-4.1-ac-test-matrix.md
    version: 5
supersedes: docs/evidence/US-4.1-implementation-report.md (v4)
---

# Implementation Report — US-4.1 (attempt 5)

No built scope changed this pass — `RECONCILIATION` v1 (`CHANGES_REQUIRED`,
`test_gap`) routed to `TEST_WRITING` attempt 5 (v5), which added
`tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests
exercising `AttachmentRepository.find_unbound_older_than`/`.purge`), a
test-only change closing ST-AC7's last untested clause, not an
application-code change. This version exists solely to record the current
`ac_test_matrix` input version (v5) and reflect `QUALITY_GATE` v5's fresh PASS
run (`docs/evidence/US-4.1-quality-gate-report.md` v5) covering the now-complete
suite: `mypy app tests` 0 errors (145 files), `pytest` 603/603 passed (318 unit
+ 285 integration), coverage 96.18% (≥85% threshold), migration cycle
re-proven fresh. Everything below (T1–T7, the T5-T7 FR-5 rework) is otherwise
unchanged from v4/v3.

# Implementation Report — US-4.1 (attempt 4, content unchanged)

No built scope changed this pass — `TEST_WRITING` attempt 4 (v4) only added
`get_account_status_for_user` to `FakeUserService`, a test-fixture change, not
an application-code change. This version exists solely to record the current
`ac_test_matrix` input version (v4) and reflect `QUALITY_GATE` v4's fresh PASS
run (`docs/evidence/US-4.1-quality-gate-report.md` v4) covering the reconciled
suite: `mypy app tests` 0 errors, `pytest` 599/599 passed (318 unit + 281
integration), coverage 95.94% (≥85% threshold, runnable in this environment
this attempt), migration cycle re-proven fresh. Everything below (T1–T7, the
T5-T7 FR-5 rework) is otherwise unchanged from v3.

# Implementation Report — US-4.1 (attempt 3, content unchanged)

Aggregate of what `IMPLEMENTATION`'s four builder sub-steps actually built, per
`docs/catalog/US-4.1-pipeline-status.md` (T1–T7, including the T5-T7 third
pass below) and this stage's own re-inspection of the diff. Consumed by
`implementation-verifier`, `security-reviewer`, and `reconciliation-reviewer`.

Everything in v2 (schemas, models/repository/cache, migration, the original
service/router/exceptions build, the audit/email/user-lookup cross-module
additions, the idempotency-shape deviation) is unchanged and not repeated here
except where this pass modified it — see v2 (superseded) for that detail.

## T5-T7 rework this pass: FR-5 account-deactivated 403 gate

`TEST_WRITING` attempt 3 (test-writer, PASS, v3) found
`test_create_ticket_deactivated_account_returns_403` reproducibly returning
`201`, not `403`: no account-status check existed anywhere in
`app/modules/support/`, and `CurrentUserDep` never checks account status
itself (a session survives its own account's deactivation unless separately
revoked — confirmed by reading `app/modules/users/service.py::get_authenticated_user`,
which never queries `User.status`). No prior art existed in this codebase for
a per-request (non-login) account-status re-check.

Added this pass:

| File | Change |
|---|---|
| `app/modules/users/service.py` | `UserService.get_account_status_for_user(user_id) -> str \| None` — mirrors `get_email_for_user`'s exact minimal read-only cross-module pattern. |
| `app/modules/support/exceptions.py` | `AccountDeactivatedError(ProblemError)` — `type_slug="account-deactivated"`, `status=403`; its own module-owned exception class, not a cross-module import of `users.exceptions.AccountDeactivatedError`, though it renders the same `type_slug`/`status` since it's the same condition. |
| `app/modules/support/service.py` | `TicketService.create_ticket` now checks account status first, before the idempotency claim or any cache/DB write. `UserServiceProtocol` (locally defined structural Protocol) widened with the new member. |
| `app/modules/support/router.py` | Unchanged — the exception propagates through the existing generic `ProblemError` handler, same as every other support-module exception. |
| `app/modules/support/dependencies.py` | Unchanged — `TicketServiceDep` already injected `UserServiceDep` (added in the prior T5-T7 pass for FR-1's email). |

Deliberately not mirrored: login's own deactivation gate (`users/service.py`)
includes OD-10's auto-reactivation grace-period logic; ticket creation has no
such precedent, so this is a plain authorization-style gate, not a business
one.

## Confirmed test ripple (this pass's own predicted consequence)

`tests/unit/modules/support/test_support_service.py`'s `FakeUserService` does
not implement the new `get_account_status_for_user` member — 13 of its
`create_ticket`-exercising tests fail with `AttributeError` at runtime, and
`mypy --strict` reports the same gap as a `Protocol` conformance error at the
one call site that constructs `TicketService` with it (line 293). Same class
of ripple as the earlier `EmailSender`/`get_email_for_user` widening this
story already resolved once (at `TEST_WRITING` attempt 2). Confirmed directly
at `QUALITY_GATE` this run (see `US-4.1-quality-gate-report.md` v3): `mypy app
tests` 1 error, `pytest tests/unit` 13 failed / 303 passed, all 13 in this one
file, all the same root cause. `tests/integration/modules/support/` is
unaffected: 24/24 passed, including the FR-5 test itself, which never
constructs `TicketService` directly — only through the real FastAPI DI chain.

**Not fixed by this skill** — `QUALITY_GATE` reports, it does not fix.
Routed `changes_required_tests` → `TEST_WRITING`; the fix is a
`FakeUserService` fixture update (add `get_account_status_for_user`,
mirroring its existing `email=...` constructor-parameter pattern), not an
application-code change.

## Verified this pass (service-and-router-builder, T5-T7 third pass)

`ruff check`/`format` clean on all 4 changed files; `mypy --strict` clean (10
files under `app/modules/support` + `app/modules/users/service.py`, in
isolation before the whole-tree ripple above was surfaced);
`lint-imports` 6/6 kept; `tests/integration/modules/support/test_support_router.py`
24/24 passed (was 23/24 — the FR-5 test now passes, no regression on the
other 23); full non-support unit suite 302/302 passed
(`--deselect tests/unit/modules/support/test_support_service.py`), 0
regressions.

## Open items carried forward

- OD-3 (category enum) — still open, no DB-level `CHECK`/`ENUM` constraint.
- BR-007 FK `ondelete` mechanics — still pending legal/DPO sign-off.
- The idempotency poll-exhaustion path's undocumented 500 — confirmed as
  implementation behavior, not a further gap.
- Two Spec Drift items from `RECONCILIATION` v1: `ticket_number`'s guessable
  format (traced to an approved, `DESIGN_REVIEW`-passed design decision, not
  undisclosed drift) and the `ticket_audit_log` vs. `audit_log` wording gap
  (traces to `DESIGN_REVIEW`'s own DR-1 fix).
- The `ticket_number` guessability advisory from `SECURITY_REVIEW` v1 (Low,
  non-§7, not currently exploitable).
- **Resolved as of attempt 5 (`TEST_WRITING` v5):**
  `scripts/purge_unbound_attachments.py`'s missing test — no longer carried.
- **Resolved as of attempt 4 (`TEST_WRITING` v4):** the `FakeUserService`
  ripple from the T5-T7 rework below — no longer carried.

All of the above (except the two now-resolved items) carry for
`RECONCILIATION`'s re-run and `HUMAN_PR_APPROVAL`.
