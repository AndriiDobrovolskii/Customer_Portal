---
artifact_type: test_generation_report
story: US-4.1
version: 5
status: ARCHIVED
created_at: "2026-09-03T13:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/tests/US-4.1-test-strategy.md
    version: 5
  - path: docs/tests/US-4.1-ac-test-matrix.md
    version: 5
  - path: docs/reviews/reconciliation/US-4.1-reconciliation.md
    version: 1
supersedes: 4
---

# Test Generation Report: Support Tickets (Create) (US-4.1)

## Why this pass ran (TEST_WRITING, attempt 5)

`RECONCILIATION` (v1, verdict `CHANGES_REQUIRED`, `test_gap` loop-back)
found the one Fail-forcing gap in an otherwise fully-traced story: ST-AC7's
24h unbound-attachment purge sub-clause had no test, despite
`scripts/purge_unbound_attachments.py` existing since `IMPLEMENTATION` T6
and the implementation plan's own Testing Strategy section already naming
the exact file and pattern to write. `docs/reviews/reconciliation/
US-4.1-reconciliation.md` (v1) has the full finding.

### Files changed this pass

- `tests/integration/scripts/test_purge_unbound_attachments.py` (new) — 4
  integration tests against `AttachmentRepository.find_unbound_older_than`/
  `.purge` (real PostgreSQL, via the `db_session` fixture):
  `test_purge_unbound_attachments_deletes_unbound_attachment_older_than_24h`,
  `test_purge_unbound_attachments_leaves_unbound_attachment_within_24h_untouched`,
  `test_purge_unbound_attachments_leaves_bound_attachment_older_than_24h_untouched`,
  `test_purge_unbound_attachments_purge_of_empty_candidate_list_deletes_nothing`.
  Verified: `ruff check`/`format` clean, `mypy --strict` 0 errors, all 4 pass
  against the real test database.
- `docs/tests/US-4.1-ac-test-matrix.md` — ST-AC7's deferred purge row replaced
  with 4 rows pointing at the new test functions; the corresponding "Gaps Not
  Covered" bullet removed (resolved).
- `docs/tests/US-4.1-test-strategy.md`, `docs/evidence/
  US-4.1-test-generation-report.md` (this file) — bumped to v5.

No application code changed in this pass — a single new test file and this
stage's own three artifacts.

## Why the prior pass ran (TEST_WRITING, attempt 4)

`QUALITY_GATE` (v3, verdict `CHANGES_REQUIRED`, `changes_required_tests`
loop-back) confirmed exactly the ripple `docs/catalog/US-4.1-pipeline-status.md`
had already flagged: `tests/unit/modules/support/test_support_service.py`'s
`FakeUserService` does not implement `UserServiceProtocol
.get_account_status_for_user`, the member `IMPLEMENTATION`'s T5-T7 rework
added for FR-5's account-deactivated `403` gate. 13 `create_ticket`-exercising
tests failed with `AttributeError`; 1 `mypy --strict` error at the
`TicketService(...)` construction call site. `docs/evidence/
US-4.1-quality-gate-report.md` (v3) has the full finding.

### Files changed this pass

- `tests/unit/modules/support/test_support_service.py` —
  1. Added `get_account_status_for_user` to `FakeUserService`, plus a new
     `account_status: str | None = "active"` constructor parameter (mirrors
     the existing `email=...` pattern). All 13 previously-failing tests
     (which never set `account_status`) now pass unchanged against the
     `"active"` default.
  2. Added `AccountDeactivatedError` to the `app.modules.support.exceptions`
     import.
  3. Added two new unit tests, previously missing (the FR-5 gate had
     integration coverage only):
     `test_create_ticket_deactivated_account_raises_before_any_write`
     (asserts `AccountDeactivatedError` is raised and that no
     `idempotency_cache.claim`, `audit_service.record_event`, or
     `ticket_repo.create` call happens — the gate must run before any
     write, per `US-4.1-db-design.md`'s stated ordering) and
     `test_create_ticket_active_account_proceeds` (an explicit
     `account_status="active"` case, distinct from the happy-path test's
     implicit default).
- `docs/tests/US-4.1-test-strategy.md`, `docs/tests/US-4.1-ac-test-matrix.md`,
  `docs/evidence/US-4.1-test-generation-report.md` (this file) — all bumped
  to v4. `US-4.1-ac-test-matrix.md`'s ST-AC5/FR-5 row updated from "currently
  FAILING" to "now passing" (the gate itself was fixed by `IMPLEMENTATION`
  attempt 1, third pass, before this `TEST_WRITING` pass ran); the
  corresponding "Gaps Not Covered" entry removed as no longer applicable.

No application code changed in this pass — test file and this stage's own
artifacts only.

### Verified against the shipped code (this pass)

- `pytest tests/unit/modules/support/test_support_service.py -q` — 16 passed
  (was 3 passed / 13 failed at `QUALITY_GATE` v3; +2 new tests for the FR-5
  gate, +1 net from the constructor fix restoring the 13 previously-failing
  tests).
- `pytest tests/unit -q` (full suite) — 318 passed, 0 failed (was 303 passed
  / 13 failed at `QUALITY_GATE` v3).
- `mypy app tests --strict` — "Success: no issues found in 144 source
  files" (was 1 error at `QUALITY_GATE` v3).
- `ruff check` — all checks passed; `ruff format --check` — all files
  formatted (after one `ruff format` auto-fix to the new test's line-wrap).

### Gaps carried forward unchanged (not this pass's to resolve)

1. **ST-AC3's "unknown category" 422 case.** OD-3 still unresolved.
2. **`scripts/purge_unbound_attachments.py`.** Still untested.
3. **`app/modules/support/schemas.py`'s own dedicated unit test file.** Still
   not written — still redundant with the integration suite.
4. **category enum (OD-3) and BR-007 FK ondelete mechanics.** Still open,
   not this stage's to resolve.

---

## Why this pass ran (TEST_WRITING, attempt 3)

`IMPLEMENTATION_VERIFICATION` (v1, verdict `CHANGES_REQUIRED`,
`changes_required_tests` loop-back) found `GET /v1/support/tickets` had only
2 of the 5 `AGENTS.md` §5 required security cases (`no_token`,
`insufficient_permissions`); `expired`, `malformed`, `revoked` were missing,
and the gap was not recorded in `US-4.1-ac-test-matrix.md` v2's "Gaps Not
Covered" section — i.e. not a deliberate, flagged cut.
`docs/verification/US-4.1-implementation-verification.md` (v1) has the full
finding.

### Files changed this pass

- `tests/integration/modules/support/test_support_router.py` — added
  `test_list_own_tickets_malformed_token_returns_401`,
  `test_list_own_tickets_expired_token_returns_401`,
  `test_list_own_tickets_revoked_session_returns_401`, placed immediately
  after the existing `test_list_own_tickets_no_token_returns_401`, reusing
  `POST`'s own `_expired_token`/`_revoked_session_token`/bare-string-as-
  bearer-token pattern verbatim — no new fixture needed. `GET` now has the
  full 5-case matrix (`no_token`, `malformed`, `expired`, `revoked`,
  `insufficient_permissions` via the existing agent-scope test), matching
  `POST`'s own set.
- `tests/integration/modules/support/test_support_router.py` (also) —
  **fixed `test_list_own_tickets_returns_only_callers_tickets_newest_first`
  (pre-existing since v1), out of this pass's assigned scope but disclosed,
  not silently changed.** Running the full integration file for the first
  time in this story's pipeline (see below) showed this test failing
  nondeterministically: it flushed two same-owner tickets back-to-back with
  no explicit `created_at`, and `Ticket.repository.py`'s
  `order_by(created_at.desc(), id.desc())` — a deliberate tiebreak per the
  model's own comment (`models.py:23`) — sorts same-timestamp rows by a
  random UUID, not insertion order. Fixed by giving `older`/`newer` explicit
  `created_at` values one minute apart. Confirmed via `git stash` that this
  failure pre-dates this pass's edits (present on the unmodified working
  tree too) — not a regression this pass introduced.
- `docs/tests/US-4.1-test-strategy.md`, `docs/tests/US-4.1-ac-test-matrix.md`,
  `docs/evidence/US-4.1-test-generation-report.md` (this file) — all bumped
  to v3.

### Verified against the shipped code (this pass)

`python -m pytest tests/integration/modules/support/test_support_router.py
-v` against real PostgreSQL (`alembic upgrade head`) and real Valkey — this
is the **first time this file has been executed** anywhere in this story's
pipeline; `QUALITY_GATE` v1/v2 both ran `pytest tests/unit` only, and
`IMPLEMENTATION_VERIFICATION` v1 verified `tests/integration` content by
direct code read, not execution. Result: **23 of 24 tests pass** (the 3 new
`GET` security tests included). The one remaining failure —
`test_create_ticket_deactivated_account_returns_403` — is a genuine
`IMPLEMENTATION` gap, not a test defect:

> **Finding (headline of this pass): FR-5's account-deactivated `403` gate is
> unimplemented.** `POST /v1/support/tickets` returns `201` for a caller
> whose account `status="deactivated"`. Confirmed by reading
> `app/modules/support/service.py`, `router.py`, and `dependencies.py` in
> full — none contains any account-status check, and
> `app.modules.users.dependencies.CurrentUserDep`/`get_authenticated_user`
> do not check `User.status` either (already flagged, not silently missed,
> in this story's own history: `API_DESIGN` v3 / `DESIGN_REVIEW` v3 stated
> "FR-5's 403 account-deactivated handling is unchanged from prior versions,
> left as a service-and-router-builder concern" — that concern was never
> actually implemented in `IMPLEMENTATION`'s T5-T7 pass). Confirmed
> pre-existing via `git stash` — not introduced by this pass or by the
> ordering-test fix above. The test itself is left unchanged: it correctly
> asserts FR-5 as written in the spec, and per this skill's own constraint
> ("do not weaken a test to make it pass"), it is reported as a finding, not
> altered. `TEST_WRITING`'s `next_stage` is already `IMPLEMENTATION` — no
> loop-back key is needed to route this fix to the stage that owns
> `service.py`/`router.py`.

**Process finding, not a code defect:** this gap and the ordering-test
flakiness above both survived `QUALITY_GATE` (twice) and
`IMPLEMENTATION_VERIFICATION` (once) undetected because neither stage
actually executed `tests/integration/modules/support/`. `QUALITY_GATE`'s
next run must include `pytest tests/integration/modules/support/` (not only
`tests/unit`) for FR-5's eventual fix — and the ordering-test fix above — to
be genuinely verified rather than re-missed the same way.

### Recorded in `docs/catalog/US-4.1-pipeline-status.md`

The FR-5 gap is recorded there as an open item against the T5-T7
(service-and-router-builder) row, per `continue-flow.md` step 5's
re-validation rule — otherwise the next `IMPLEMENTATION` pass could
re-validate the existing sub-step outputs as current and skip regenerating
`service.py`/`router.py` entirely.

---

## Why this pass ran (TEST_WRITING, attempt 2)

`QUALITY_GATE` (v1, verdict `CHANGES_REQUIRED`) reported the exact failure
this pass fixes: `tests/unit/modules/support/test_support_service.py`'s 12
tests failed with `TypeError: TicketService.__init__() missing 2 required
positional arguments: 'user_service' and 'email_sender'`, plus `mypy --strict`
failures across 6 files from two widened shared Protocols
(`EmailSender.send_ticket_created_email`, `AuditRepositoryProtocol
.record_event`) that this story's `IMPLEMENTATION` added. `story-orchestrator`
routed `changes_required_tests` back to `TEST_WRITING` per
`stage-map.yaml`'s amended `QUALITY_GATE.loop_back`. Full detail:
`docs/evidence/US-4.1-quality-gate-report.md` (v1) and
`docs/catalog/US-4.1-pipeline-status.md` (T2/T3, T5–T7 rows).

## Files changed this pass

- `tests/unit/modules/support/test_support_service.py` (rewritten) — now 12
  test functions (one parametrized ×3 = 14 collected cases; the gate
  report's own failing-test list shows the pre-existing file had 10
  functions / 12 collected cases, not v1's claimed "15" — 3 new email cases
  added this pass, see below). Reconciled against the shipped
  `TicketService`/`TicketIdempotencyCache`/`TicketRepository`/
  `AttachmentRepository` shapes (`US-4.1-test-strategy.md` v2's Scope
  section has the full diff). `FakeTicketRepository`/`FakeAttachmentRepository`
  now return real `app.modules.support.models.Ticket`/`Attachment` ORM
  instances instead of lookalike dataclasses (`mypy --strict` Protocol
  return-type covariance requires this).
- `tests/unit/modules/audit/test_audit_service.py` (extended) — added
  `record_event` to `FakeAuditRepository` (the `AuditRepositoryProtocol`
  member `IMPLEMENTATION` added) and two new tests,
  `test_record_event_writes_without_committing` and
  `test_record_event_actor_role_none_when_no_roles_held`, closing the v1
  Known Gap ("`audit.service`'s own `record_event` unit coverage... not
  added in this pass").
- `tests/unit/modules/admin_users/test_admin_users_service.py`,
  `tests/unit/modules/users/test_users_service.py`,
  `tests/unit/modules/email_verification/test_email_verification_service.py`,
  `tests/unit/modules/profile/test_profile_service.py` (extended) — each
  adds a `send_ticket_created_email` stub to its `EmailSender`-implementing
  fake (`FakeEmailSender`/`RecordingEmailSender`), matching that file's own
  existing convention for unused Protocol members (`NotImplementedError` or
  `pass`, per file). These fakes are not this story's own test surface;
  fixed only because widening the shared `EmailSender` Protocol broke their
  structural conformance under `mypy --strict` (gate report v1, item 2).
- `docs/tests/US-4.1-test-strategy.md`, `docs/tests/US-4.1-ac-test-matrix.md`,
  `docs/evidence/US-4.1-test-generation-report.md` (this file) — all bumped
  to v2.
- `tests/integration/modules/support/test_support_router.py` — **not
  changed**. It never constructs `TicketService` directly (goes through the
  real FastAPI DI chain, `app/modules/support/dependencies.py
  ::get_ticket_service`), so neither deviation reaches it; confirmed by
  inspection, no `TicketService(`/cache-fake reference found in that file.

## What was fixed, mapped to the gate report's failures

1. **12 unit-test failures (`TypeError`, missing `user_service`/
   `email_sender`).** `_make_service`'s `TicketService(...)` call now passes
   all 7 constructor arguments, positional, in
   `dependencies.py::get_ticket_service`'s exact order. New
   `FakeUserService`/`FakeEmailSender` added.
2. **`mypy --strict`, `test_support_service.py`'s own errors (missing
   `user_service`/`email_sender`; all 5 fakes structurally mismatching their
   real Protocols).** Fixed by (1) above plus: `FakeIdempotencyCache`
   rewritten to the real `claim`/`get_envelope`/`resolve`/`release` shape
   (`IdempotencyEnvelope` imported from `app.modules.support.cache`, not
   redefined); `FakeRateLimitCache.record_and_check` changed from
   keyword-only `user_id` to positional, matching
   `TicketCreationRateLimitCacheProtocol`; `FakeAttachmentRepository
   .bind_to_ticket` changed to return the bound `Attachment` (was
   implicitly returning `None`, which would have made every successful
   attachment-bind test raise `AttachmentNotOwnedError` once the
   constructor was fixed — caught by the covariance check, not by a runtime
   failure, since this bug was masked by the constructor `TypeError` in v1);
   `FakeTicketRepository.list_for_requester` dropped its non-Protocol
   `status` keyword (the service itself filters non-`"open"` statuses
   before calling the repository — that call site never passed `status`).
3. **`mypy --strict`, 6 files, widened `EmailSender`/
   `AuditRepositoryProtocol`.** Fixed by the 5 out-of-module fake edits
   listed above (4 `EmailSender`-implementing fakes + `FakeAuditRepository
   .record_event`).
4. **`ruff (lint)`, 4 errors in the old test file (`RUF036`, `RUF015`,
   `RUF059`, `ANN401`).** Resolved by the rewrite: `RUF036`'s
   `claim_result: uuid.UUID | None | Exception` no longer exists (the old
   single-field `claim_or_get` fake is gone); `RUF015`'s
   `list(...)[0]` replaced with `next(iter(...))`; `RUF059`'s unused
   `ticket_repo` unpacking replaced with `_`; `ANN401`'s bare
   `attachment_factory: Any` replaced with
   `Callable[[uuid.UUID, uuid.UUID], dict[uuid.UUID, Attachment]]`.

## New coverage added beyond reconciliation (ST-AC1/FR-1)

`test-strategy` v1 never named `EmailSender`/`UserService` as collaborators
(the plan gap `service-and-router-builder` found and fixed mid-build — see
pipeline-status.md), so no unit test asserted ST-AC1's own stated "a
confirmation email containing the ticket number is queued to the requester."
Three tests close that: the happy-path test now also asserts
`user_service.calls`/`email_sender.sent`;
`test_create_ticket_no_email_on_file_skips_dispatch_without_failing` and
`test_create_ticket_email_dispatch_failure_does_not_fail_the_request` assert
the best-effort dispatch does not block or fail ticket creation. The
rate-limit-exceeded and attachment-not-owned tests were also extended to
assert `idempotency_cache.release_calls` — the mid-build bug fix
(`TicketIdempotencyCache.release`) had no dedicated assertion in v1 beyond an
ad hoc smoke script; it is now asserted directly on every failure path after
a successful claim.

## Verified against the shipped code

`uv run --no-sync ruff check` / `ruff format --check` / `mypy app tests` /
`pytest tests/unit -q` all run clean against the reconciled files:
`ruff check` — all checks passed; `mypy app tests` — "Success: no issues
found in 144 source files"; `pytest tests/unit -q` — 316 passed (was
300 passed / 12 failed before this pass). `pre-commit run --files <changed
files>` also passed `ruff (lint)`, `ruff (format)`, `mypy (strict)`,
`import-linter`, and `unit tests`; `Detect secrets` only regenerated its
baseline's line-number bookkeeping (no new secret finding), a routine,
expected side effect of running the hook standalone outside `QUALITY_GATE`'s
own run.

## Gaps carried forward unchanged (not this pass's to resolve)

1. **ST-AC3's "unknown category" 422 case.** OD-3
   (`docs/decisions/US-4.1-open-decisions.md`) still defers the valid
   `category` value list to a stakeholder decision; unchanged from v1.
2. **`scripts/purge_unbound_attachments.py`.** Still untested; unchanged
   from v1's non-blocking finding.
3. **`app/modules/support/schemas.py`'s own dedicated unit test file.**
   Still not written — still redundant with the integration suite's
   assertions; unchanged from v1.

## Result (attempt 2, superseded by attempt 3 below)

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-4.1
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-4.1-test-strategy.md
    - docs/tests/US-4.1-ac-test-matrix.md
    - docs/evidence/US-4.1-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "ST-AC3's 'unknown category' sub-case has no test — OD-3's category value list remains an unresolved stakeholder decision, not inferable; add the test once OD-3 resolves. Unchanged from v1."
    - "scripts/purge_unbound_attachments.py (FR-7's 24h purge job) has no test; carried forward unchanged from v1 for a follow-up TEST_WRITING pass or for gate-enforcer/reconciliation-reviewer to confirm before HUMAN_PR_APPROVAL."
    - "category enum (OD-3) and BR-007 FK ondelete mechanics remain open, carried forward unchanged — not this stage's to resolve."
    - "This reconciliation pass touched 4 out-of-module test files (admin_users, users, email_verification, profile) only to add a stub for the widened shared EmailSender Protocol member; no behavioral change to those modules' own coverage."
```

## Result (attempt 3)

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-4.1
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-4.1-test-strategy.md
    - docs/tests/US-4.1-ac-test-matrix.md
    - docs/evidence/US-4.1-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "HEADLINE: FR-5's account-deactivated 403 gate is unimplemented — POST /v1/support/tickets returns 201 for a deactivated-status caller. Confirmed by full read of app/modules/support/{service,router,dependencies}.py: no account-status check exists anywhere in the module, and CurrentUserDep does not check User.status. test_create_ticket_deactivated_account_returns_403 (pre-existing, correctly written) fails against the shipped code. Not a test defect; IMPLEMENTATION (service-and-router-builder) must add the check. Recorded as an open item in docs/catalog/US-4.1-pipeline-status.md's T5-T7 row so the next IMPLEMENTATION pass does not short-circuit via continue-flow step 5."
    - "PROCESS GAP: this is the first time tests/integration/modules/support/test_support_router.py has actually been executed in this story's pipeline — QUALITY_GATE v1/v2 ran pytest tests/unit only, and IMPLEMENTATION_VERIFICATION v1 verified integration test content by code read, not execution. Both the FR-5 gap above and the ordering-test flakiness below survived undetected as a result. QUALITY_GATE's next run must execute tests/integration/modules/support/ (not only tests/unit) or the eventual FR-5 fix goes unverified the same way."
    - "Fixed test_list_own_tickets_returns_only_callers_tickets_newest_first (pre-existing since v1, out of this pass's assigned scope but disclosed): flaky due to a same-millisecond created_at tie broken by a random id.desc() tiebreak (deliberate per models.py:23's own comment), not by insertion order as the test assumed. Fixed by giving the two tickets explicit, one-minute-apart created_at values. Confirmed pre-existing via git stash, not a regression from this pass."
    - "ST-AC3's 'unknown category' sub-case has no test — OD-3's category value list remains an unresolved stakeholder decision, not inferable; add the test once OD-3 resolves. Unchanged from v2."
    - "scripts/purge_unbound_attachments.py (FR-7's 24h purge job) has no test; carried forward unchanged for a follow-up TEST_WRITING pass or for gate-enforcer/reconciliation-reviewer to confirm before HUMAN_PR_APPROVAL."
    - "category enum (OD-3) and BR-007 FK ondelete mechanics remain open, carried forward unchanged — not this stage's to resolve."
```

## Result (attempt 4)

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-4.1
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-4.1-test-strategy.md
    - docs/tests/US-4.1-ac-test-matrix.md
    - docs/evidence/US-4.1-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "Fixed the QUALITY_GATE v3-reported fixture gap: FakeUserService now implements get_account_status_for_user (default 'active'), restoring the 13 create_ticket-exercising unit tests to passing and resolving the mypy --strict Protocol-conformance error. Added 2 new unit tests for the FR-5 gate itself (previously integration-only coverage): deactivated-account raises before any write, active-account proceeds."
    - "Verified: pytest tests/unit -q 318 passed (was 303 passed/13 failed); mypy app tests --strict 0 errors (144 files); ruff check/format clean. No application code changed this pass."
    - "ST-AC3's 'unknown category' sub-case has no test — OD-3 unresolved. Unchanged from v3."
    - "scripts/purge_unbound_attachments.py (FR-7's 24h purge job) has no test. Unchanged from v3."
    - "category enum (OD-3) and BR-007 FK ondelete mechanics remain open, carried forward unchanged — not this stage's to resolve."
```
