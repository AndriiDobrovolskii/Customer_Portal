---
artifact_type: test_strategy
story: US-4.1
version: 5
status: DRAFT
created_at: "2026-09-03T13:00:00Z"
updated_at: "2026-09-04T04:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.1-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-4.1-plan-review.md
    version: 1
  - path: docs/reviews/reconciliation/US-4.1-reconciliation.md
    version: 1
supersedes: 4
---

# Test Strategy: Support Tickets (Create) (US-4.1)

## Scope (v5 — purge-sweep gap-fill pass)

Routed from `RECONCILIATION` (v1, `CHANGES_REQUIRED`, `test_gap` loop-back,
attempt 5): ST-AC7's verbatim text includes "unbound attachments older than
24 hours are purged by a scheduled job." `scripts/purge_unbound_attachments.py`
exists (built at `IMPLEMENTATION` T6), but no test exercised it across four
prior `TEST_WRITING` passes — not blocked by any open decision, just
undelivered work the implementation plan's own Testing Strategy section
(`docs/plans/US-4.1-implementation-plan.md`) already named:
`tests/integration/scripts/test_purge_unbound_attachments.py`, mirroring
`tests/integration/scripts/test_anonymize_erased_user.py`'s pattern.

The script's `main()` builds its own engine/session from `get_settings()`
rather than accepting an injected session — unlike `anonymize_erased_user`'s
own testable function, `main()` itself is not unit-of-work-testable against
the `db_session` fixture without a settings override. Following
`test_anonymize_erased_user.py`'s own precedent (which tests
`anonymize_erased_user()` directly, not that script's `main()`), this pass
tests the two `AttachmentRepository` methods `main()` composes
(`find_unbound_older_than`, `purge`) directly against the real `db_session`
fixture — the same repository code path the script actually runs, without
needing to fork a subprocess or monkeypatch `get_settings()` (forbidden in
`tests/integration/` per `AGENTS.md` §5 in any case). Four integration tests
added to `tests/integration/scripts/test_purge_unbound_attachments.py`: the
24h-cutoff purge itself, a within-window survivor, a bound-attachment
non-candidate (regardless of age), and `purge([])`'s no-op path. No unit-level
counterpart needed — `AttachmentRepository` has no business-rule branching to
isolate from the database; the SQL predicate itself is what needs proving.

No application code changed this pass; only the new test file and this
stage's own three artifacts.

## Scope (v4 — fixture-reconciliation pass)

Routed from `QUALITY_GATE` (v3, `CHANGES_REQUIRED`, `changes_required_tests`
loop-back, attempt 4): `IMPLEMENTATION` attempt 1 (third pass) added
`UserServiceProtocol.get_account_status_for_user` to gate FR-5's
account-deactivated `403` check in `service.py`, but
`tests/unit/modules/support/test_support_service.py`'s `FakeUserService` was
never updated to implement it — 13 `create_ticket`-exercising unit tests
failed with `AttributeError`, plus one `mypy --strict` Protocol-conformance
error at the `TicketService(...)` construction call site. `app/` itself and
`tests/integration/modules/support/` (24/24) were unaffected — this was a
test-fixture gap only, confirmed by `QUALITY_GATE` v3's own report
(`docs/evidence/US-4.1-quality-gate-report.md`).

Fixed by adding `get_account_status_for_user` to `FakeUserService`, defaulting
to `"active"` (mirroring the existing `email=...` constructor-parameter
pattern) so the 13 previously-failing tests pass unchanged. Also added two new
unit tests — `test_create_ticket_deactivated_account_raises_before_any_write`
and `test_create_ticket_active_account_proceeds` — since the FR-5 gate
previously had integration coverage only (`test_create_ticket_deactivated_
account_returns_403`, added attempt 3) and no unit-level assertion that the
check runs before any idempotency/repository/audit write, per
`US-4.1-db-design.md`'s stated ordering.

## Scope (v3 — security-case completion pass)

Routed from `IMPLEMENTATION_VERIFICATION` (v1, `CHANGES_REQUIRED`,
`changes_required_tests` loop-back): `GET /v1/support/tickets` had only 2 of
the 5 required `AGENTS.md` §5 security cases (`no_token`,
`insufficient_permissions`); `expired`, `malformed`, `revoked` were missing
and the gap was not recorded in v2's "Gaps Not Covered" section. This pass
adds the three missing cases to `tests/integration/modules/support
/test_support_router.py`, reusing the exact `_expired_token`/
`_revoked_session_token`/malformed-string-as-bearer-token helpers `POST`'s
own five-case block already established in the same file — no new fixture
needed.

Running the full integration file for the first time in this story's
pipeline (neither `QUALITY_GATE` nor `IMPLEMENTATION_VERIFICATION` executed
`tests/integration/`; both verified by direct code read or `tests/unit`
results only) surfaced two further, unrelated defects, both out of this
pass's own assigned scope but disclosed rather than silently worked around:

1. **`test_list_own_tickets_returns_only_callers_tickets_newest_first`
   (pre-existing, v1) was flaky, not a regression.** `Ticket.repository.py`
   orders `created_at.desc(), id.desc()` — the model's own comment
   (`models.py:23`) states `id` is a deliberate tiebreak for same-`created_at`
   rows. The test flushed two rows back-to-back with no explicit
   `created_at`, so on a tie the tiebreak (`id.desc()`, a random UUID) does
   not match the test's insertion-order assumption, and it fails
   nondeterministically. Fixed in this pass by giving `older`/`newer`
   explicit, one-minute-apart `created_at` values — a test-file fix, not an
   app-behavior change, since the app's ordering is correct as designed.
2. **`test_create_ticket_deactivated_account_returns_403` (pre-existing, v1)
   now reproducibly fails: `201`, not `403`.** Confirmed by reading
   `app/modules/support/{service,router,dependencies}.py` in full — no
   deactivated-account check exists anywhere in the support module.
   `CurrentUserDep`/`get_authenticated_user` do not encode account-active
   status (already noted as a known gap in `API_DESIGN` v3 / `DESIGN_REVIEW`
   v3's history: "FR-5's 403 account-deactivated handling is unchanged from
   prior versions, left as a service-and-router-builder concern"). That
   concern was never actually picked up — FR-5's deactivated-account gate is
   an unimplemented requirement, not a test defect. The test is left
   unchanged (it correctly asserts the spec); this is reported as this
   stage's headline finding for `IMPLEMENTATION` to fix, since `next_stage`
   for `TEST_WRITING` is already `IMPLEMENTATION`. **This gap has not been
   run — and therefore not caught — by any stage so far**: `QUALITY_GATE` v1
   and v2 both ran `pytest tests/unit` only, and
   `IMPLEMENTATION_VERIFICATION` v1 verified by direct code read, not by
   executing `tests/integration`. `QUALITY_GATE`'s next run must execute
   `tests/integration/modules/support/` (not only `tests/unit`) or this fix
   will go unverified the same way the original gap did.

## Scope (v2 — reconciliation pass)

`app/modules/support/` now exists (`IMPLEMENTATION` T1–T7 complete). This
version reconciles the unit suite against the **shipped** collaborator shapes,
which deviated from v1's design assumptions in two ways `QUALITY_GATE` (v1,
`CHANGES_REQUIRED`) confirmed as blocking, both flagged in advance by
`data-layer-builder`/`service-and-router-builder` as deliberate, not silent:

1. `TicketService.__init__` takes two additional collaborators v1 did not
   anticipate — `user_service` (`UserServiceProtocol.get_email_for_user`) and
   `email_sender` (`EmailSender.send_ticket_created_email`) — added mid-build
   to satisfy ST-AC1's "a confirmation email containing the ticket number is
   queued to the requester," which v1's design assumptions omitted from the
   collaborator list (a plan gap, `US-4.1-implementation-plan.md` never named
   an email path — see `docs/catalog/US-4.1-pipeline-status.md` T5-T7 row).
2. `TicketIdempotencyCache` shipped as four gateway-compliant, raise-nothing
   methods (`claim`/`get_envelope`/`resolve`/`release`) instead of v1's single
   raising `claim_or_get`. `AGENTS.md` §3 ("Repositories and gateways return
   `None` or empty and raise nothing") and `US-4.1-db-design.md` v3's own
   wording ("the service GETs the existing envelope and branches") both place
   the hash-mismatch/poll-exhaustion branching in `TicketService`, not the
   cache — this is what shipped. A `release` method (not in any design
   artifact) was also added mid-build: a claimed-but-failed idempotency key
   with no release path would stay stuck at `ticket_id: null` for its full
   24h TTL, poll-exhausting every retry with the same key.

The 20 integration tests in `test_support_router.py` assert externally
observable HTTP/DB behavior only, which is unchanged by either deviation —
reconciled here for construction/fixture details only, no functional
rewrite. This version also fixes the widened shared Protocols'
(`EmailSender`, `AuditRepositoryProtocol`) 4 out-of-module fake breakages
`QUALITY_GATE` v1 reported (mypy strict, 6 files) and adds the previously
carried-forward `audit.service.record_event` unit coverage (Known Gap in v1,
below) now that the method is exercised by a real caller.

## Unit vs. Integration split (`AGENTS.md` §5)

- **Unit** (`tests/unit/modules/support/test_support_service.py`) — every
  branch of `TicketService.create_ticket()`/`list_own_tickets()` in isolation:
  the idempotency claim/replay/reuse/poll-exhaustion outcomes, the rate-limit
  gate and its required ordering *after* the idempotency gate (a replay must
  never touch the rate limit — DB design's explicit requirement), the three
  indistinguishable attachment-ownership failure causes, and the
  transaction-boundary contract (`create_ticket` commits exactly once,
  covering the ticket insert + attachment bind + audit write together).
  Repositories/caches/the audit-service collaborator are hand-written fakes
  implementing the same duck-typed Protocols `service.py` will define —
  never `MagicMock`.
- **Integration** (`tests/integration/modules/support/test_support_router.py`)
  — the full HTTP round trip against real PostgreSQL/Valkey (`alembic upgrade
  head`, `AsyncClient(transport=ASGITransport(app=app))`, no
  `unittest.mock`/`MagicMock`/`monkeypatch` on DB/cache/repository/service):
  every FR-1–FR-7 status code, the audit-row side effect of a successful
  `POST` (a genuine cross-module check against `app.modules.audit.models
  .AuditLog`), and the full authentication/authorization matrix for both
  routes.

## Fixtures / fakes needed

- Unit: `FakeTicketRepository`, `FakeAttachmentRepository`,
  `FakeIdempotencyCache`, `FakeRateLimitCache`, `FakeAuditService`,
  `FakeUserService`, `FakeEmailSender` — all defined locally in the test
  file, matching this codebase's existing pattern
  (`FakeAuditRepository`/`FakeRoleService` in
  `tests/unit/modules/audit/test_audit_service.py`). `FakeTicketRepository`/
  `FakeAttachmentRepository` return real `app.modules.support.models.Ticket`/
  `Attachment` ORM instances (constructed directly, never flushed), not
  lookalike dataclasses — `mypy --strict`'s Protocol return-type covariance
  check requires this, matching `admin_users`' `_make_user` building a real
  `User` for the same reason.
- Integration: this project's existing `client`/`db_session` fixtures
  (`tests/conftest.py`); local seed helpers (`_seed_user`,
  `_seed_session_and_token`, `_assign_role`, `_expired_token`,
  `_revoked_session_token`, `_seed_attachment`) mirroring
  `tests/integration/modules/audit/test_audit_router.py`'s established
  helpers verbatim (same JWT/`UserSession` seeding, same `support_agent`
  role name from `migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`).

## Shipped contract this test suite is written against (v2)

`service.py`/`cache.py` now exist. This suite is reconciled against the
shipped shapes verbatim (superseding v1's pre-`IMPLEMENTATION` design
assumptions):

- `TicketService.__init__(repository, attachment_repository,
  idempotency_cache, rate_limit_cache, audit_service, user_service,
  email_sender)` — positional, this exact order
  (`app/modules/support/dependencies.py::get_ticket_service`).
  `create_ticket(*, requester_id, idempotency_key, subject, body, category,
  attachment_ids) -> TicketRead` and `list_own_tickets(*, requester_id,
  status, cursor, limit) -> TicketListResponse`.
- `TicketIdempotencyCacheProtocol`: `claim(*, user_id, key, request_hash,
  ttl_seconds) -> bool` (`True` = this call claimed the key);
  `get_envelope(*, user_id, key) -> IdempotencyEnvelope | None`;
  `resolve(*, user_id, key, request_hash, ticket_id, ttl_seconds) -> None`;
  `release(*, user_id, key) -> None`. All four raise nothing
  (`AGENTS.md` §3) — `TicketService._resolve_idempotency_replay` owns the
  hash-mismatch (`IdempotencyKeyReuseError`) and poll-exhaustion
  (bare `RuntimeError`) branching, and `create_ticket`'s `except Exception`
  wrapper calls `release` on any failure after a successful `claim` and
  before `resolve`.
- `TicketCreationRateLimitCacheProtocol.record_and_check(user_id, *,
  window_seconds) -> int` (positional `user_id`, not keyword-only) and
  `get_retry_after_seconds(user_id) -> int`, mirroring
  `app/modules/users/cache.py`'s `LoginThrottleCache` shape.
- `AttachmentRepositoryProtocol.bind_to_ticket(*, attachment_id, ticket_id)
  -> Attachment | None` (`None` = lost a concurrent bind race, treated
  identically to any other not-owned cause) and
  `TicketRepositoryProtocol.list_for_requester(*, requester_id, cursor,
  limit) -> TicketListPage | None` — no `status` parameter; `TicketService`
  filters non-`"open"` statuses itself before calling the repository.
- `UserServiceProtocol.get_email_for_user(user_id) -> str | None` and
  `EmailSender.send_ticket_created_email(*, to, ticket_number) -> None` — the
  FR-1 plan-gap collaborators. Dispatch is best-effort after commit: no email
  on file skips it, and a dispatch failure is caught and logged, never
  propagated (the ticket is already committed by that point).
- `AuditServiceProtocol.record_event(*, category, event, actor_id, target_id,
  outcome, payload)` on `app/modules/audit/service.py::AuditLogService` —
  asserted here as the collaborator `support.service` calls; the method's own
  behavior (no self-commit) is now also covered directly in
  `tests/unit/modules/audit/test_audit_service.py` (added this pass — see
  Known Gaps below, v1 carried this as undone).

## Known gaps — not tested here, and why

- **`category`'s "unknown category" 422 case (part of ST-AC3/FR-3).** OD-3
  (`docs/decisions/US-4.1-open-decisions.md`) is explicit that the valid
  `category` value list is a stakeholder decision, not one this harness may
  infer. No enum exists anywhere in the approved contract to reject an
  "unknown" value against, so no test asserts this sub-case. The other three
  ST-AC3 sub-cases (empty subject, oversized subject, oversized body) are
  covered — they need no enum, only the length caps already fixed by the
  contract (`CreateTicketRequest.subject`/`.body` `maxLength`/`minLength`,
  `US-4.1-openapi.yaml` v3).
- **`app/modules/audit/service.py`'s own `record_event` unit coverage**
  (the plan's Risk 1 — asserting the new method does not self-commit) — was
  a v1 gap, now closed: `test_record_event_writes_without_committing` and
  `test_record_event_actor_role_none_when_no_roles_held` added to
  `tests/unit/modules/audit/test_audit_service.py` this pass.
- **`scripts/purge_unbound_attachments.py`** (FR-7's last sentence, the
  24-hour unbound-attachment purge job) has no test in this pass, though the
  implementation plan's own Testing Strategy names
  `tests/integration/scripts/test_purge_unbound_attachments.py`. Not one of
  the seven ST-AC's own literal assertions (it's stated in FR-7's prose, not
  its own `[gate]`-marked AC), and not implicated by any of ST-AC1–ST-AC7's
  `Covered by` column. Flagged as a non-blocking, deferred item — the script
  itself is real in-scope work per the plan and impact-analysis, just not
  covered by this `TEST_WRITING` pass.
- **`app/modules/support/schemas.py`'s own unit tests** (`extra="forbid"`,
  field-level length caps in isolation) are not written as a separate file;
  the same assertions are proven end-to-end by the integration suite's
  ST-AC3 cases and, for `attachment_ids` shape, by the ST-AC7 cases. No
  coverage gap results — schema-level unit tests would be redundant with the
  integration tests already asserting the same contract boundary.

## Statement-count ceiling (`AGENTS.md` §5)

`GET /v1/support/tickets` returns a flat list of `TicketRead` rows with no
nested collection (`US-4.1-entity-model.md`'s "no `relationship()`" statement)
— there is no lazy-loading regression surface for a statement-count
assertion to guard against, unlike a nested-data list endpoint. No such
assertion is added, consistent with the rule's own scope ("list endpoints
returning nested data").

## Coverage floor

85% minimum overall, 90%+ on `support/service.py` and `support/router.py`,
per `AGENTS.md` §5/§6 and the implementation plan's own Testing Strategy —
enforced by `gate-enforcer` (T8), not measured by this stage.
