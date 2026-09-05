---
artifact_type: test_strategy
story: US-4.2
version: 3
status: DRAFT
created_at: "2026-09-05T17:00:00Z"
updated_at: "2026-09-05T22:45:00Z"
produced_by: test-writer
inputs:
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/plans/US-4.2-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-4.2-plan-review.md
    version: 2
supersedes: docs/tests/US-4.2-test-strategy.md (v2)
---

# Test Strategy: Ticket Replies (US-4.2)

## Revision Note (v3)

Corrects v2's own prediction. v2 stated the three direct-RLS integration
tests "are expected to keep failing for the same reason (superuser bypass)
until T4 lands, then pass unchanged" — this did not hold: once T4
(`migration-manager`) landed `app_runtime` and `tests/conftest.py`'s
`_database` fixture began serving requests through it, all three failed for
a *new* reason. `_seed_reply()`'s internal-visibility inserts run through the
shared `db_session` with no `app.actor_kind` GUC set, which
`ticket_replies_write`'s own `WITH CHECK (visibility = 'public' OR
current_setting('app.actor_kind', true) = 'agent')` policy now genuinely
enforces (previously silently bypassed by the superuser role — RLS bypass
covers `INSERT`'s `WITH CHECK`, not only `SELECT`'s `USING`, a distinction
neither v1 nor v2 of this document anticipated). Routed via `HUMAN_REDIRECTED`
(`docs/workflow/history.jsonl`, 2026-09-05T22:30:00Z) from `IMPLEMENTATION`
T4's `BLOCKED` verdict (`docs/catalog/US-4.2-pipeline-status.md` v3, T4
section).

**Fix:** each of the three tests' Arrange block now runs
`await db_session.execute(text("SET LOCAL app.actor_kind = 'agent'"))`
before seeding its internal-visibility reply.
`test_no_actor_kind_set_defaults_to_hiding_internal_reply` additionally runs
`await db_session.execute(text("RESET app.actor_kind"))` immediately after
seeding, before its Act phase — `SET LOCAL` persists for the rest of the
transaction (this fixture's whole test body is one savepoint-based
transaction, never rolled back mid-test), so without the explicit `RESET`
the seeding GUC would still be `'agent'` during the Act SELECT, defeating
the test's own "no GUC set at all" premise. Verified empirically: all three
tests pass individually and together; the full `support` suite shows the
identical pass/fail set as before minus these three (no other regression);
the full non-`support` integration suite (261 tests) is unaffected. No
application code, no other test, no other file changed — this is
`tests/integration/modules/support/test_support_router.py` only.

## Revision Note (v2)

`implementation_plan` advanced to v2 (adds Architectural Change #12: a
dedicated non-superuser `app_runtime` PostgreSQL role, provisioned by a new
`scripts/db/provision_runtime_role.sql` and wired into `tests/conftest.py`'s
`_database` fixture by `task_breakdown` v2's new T4) since this pass last ran
against v1/v1/v1. `implementation_plan` v2's own Testing Strategy section
states this change is "**Unaffected by v2** — the runtime-role change is
infrastructure, not service logic" for the unit suite, and "**no test
rewrite needed**" for the integration suite: the three direct-RLS tests
below (`test_internal_reply_hidden_from_customer_context_by_rls_alone`,
`test_agent_context_sees_internal_reply_via_rls`,
`test_no_actor_kind_set_defaults_to_hiding_internal_reply`) were already
written against the RLS policy's *behavior*, not against which role serves
the connection — they are expected to keep failing for the same reason
(superuser bypass) until T4 lands, then pass unchanged, exactly as
`docs/catalog/US-4.2-pipeline-status.md` v2 and the `HUMAN_REDIRECTED`
transition (`docs/workflow/workflow-state.yaml`, 2026-09-05T18:30:00Z)
anticipated.

Verified this pass: all 60 (`test_support_router.py`) / 42
(`test_support_service.py`) / 12 (`test_support_schemas.py`) test functions
from v1 are present on disk unchanged (grep count match against the v1
`test-generation-report`'s figures) — no test file was touched. Every
row below and in `US-4.2-ac-test-matrix.md` is carried forward verbatim.
Only this section, the front matter, and the new "Full-suite regression
pass" note below are new in v2.

**One new testing implication, not a new test case:** `implementation_plan`
v2 Risk 7 / Testing Strategy requires a **full-suite regression re-run** —
every other module's already-existing integration tests
(`tests/integration/modules/{users,roles,admin_users,audit,profile}/...`)
must pass once `tests/conftest.py` serves requests through `app_runtime`
instead of the container's bootstrap superuser, as the actual proof
`scripts/db/provision_runtime_role.sql`'s `GRANT` list is complete. This is
a re-run of pre-existing tests this story does not own or modify, not new
AC-derived content for `test-writer` to author — `task_breakdown` v2 T4/T7
(migration-manager / gate-enforcer) own executing and evidencing it. Noted
here only so `IMPLEMENTATION`/`QUALITY_GATE` re-entry has the traceability
link back to why it's required.

## Scope

Written **before** `IMPLEMENTATION` (`app/modules/support/{schemas,models,
repository,cache,service,router,dependencies,exceptions}.py` do not yet carry
any reply-related symbol; `app/core/{email,config,cache_keys}.py` do not yet
carry the reply-related additions either). Every test added this pass is
written against the approved contract (`US-4.2-openapi.yaml` v3,
`US-4.2-entity-model.md` v3, `US-4.2-implementation-plan.md` v1) and is
expected to fail at collection/import time until `IMPLEMENTATION`'s T1-T5
land — this is the intended TDD-red state, not a defect in this pass. Per
this skill's own Result Envelope contract, `PASS` requires only that every
acceptance criterion have a test function that exists and asserts its stated
behavior — not that application code exists yet.

## Unit vs. Integration split (`AGENTS.md` §5)

- **Unit** (`tests/unit/modules/support/test_support_service.py`, extended;
  `tests/unit/modules/support/test_support_schemas.py`, new) — every branch of
  the new reply-handling service method(s) in isolation: the full actor-kind ×
  status-gating matrix (implementation-plan §4's table, all seven rows
  including the deliberate no-op branch), FR-5's visibility rejection
  (asserted to come from the service's own check, never a caught
  `IntegrityError`, per db-design v3's explicit layering note), FR-4's
  ownership/scope branching (including API_DESIGN OQ-2's not-yet-reachable
  "neither owner nor agent" case), attachment reply-binding ownership/IDOR
  paths (all three indistinguishable causes), the 30/hour rate limit and its
  independence from ticket-creation's 5/hour limit (Risk 6), `first_response_at`
  stamped exactly once, both new email dispatches best-effort-after-commit,
  and the new schemas' `extra="forbid"`/length-cap/defaulting behavior.
- **Integration**
  (`tests/integration/modules/support/test_support_router.py`, extended) —
  TR-AC1 through TR-AC7 end-to-end against real PostgreSQL/Valkey, the full
  four-case authentication matrix (no token, malformed, expired, revoked) on
  both new routes, the reply-rate-limit boundary, all attachment-IDOR cases,
  GET's cursor pagination (oldest-first, unlike ticket listing's newest-first),
  and — the highest-risk item in this story — the NFR's own RLS-specific test:
  a customer-context connection with the application filter deliberately
  disabled, proving the database alone hides `visibility='internal'` rows
  (Risk 1/Risk 2's stated mitigation). A migration proof of the RLS DDL itself
  (`upgrade → downgrade → upgrade`) is `migration-manager`'s own concern (T3),
  not duplicated here.

## Shipped-contract assumption this suite is written against (test-writer's own design choice)

`docs/plans/US-4.2-implementation-plan.md`'s Architectural Change #4 leaves the
service's file-internal split open ("new method(s) on `TicketService` ... or a
new `TicketReplyService` sharing the same file/module — final split is
`service-and-router-builder`'s call, not fixed here"). This suite is written
against a **new `TicketReplyService` class**, not new methods on the existing
`TicketService`, so that this pass adds zero risk to the 12 already-passing
`TicketService`/`test_support_service.py` tests (no shared constructor, no
touched fake). If `service-and-router-builder` instead extends `TicketService`,
a reconciliation `TEST_WRITING` pass updates this file the same way US-4.1's v2
pass reconciled `test_support_service.py` against its own shipped collaborator
shapes (`docs/tests/US-4.1-test-strategy.md` "Scope (v2)").

Concretely, this suite assumes:

- `TicketReplyService.__init__(ticket_repository, reply_repository,
  attachment_repository, rate_limit_cache, email_sender)` — positional, in
  this order.
- `create_reply(*, ticket_id, actor_id, actor_kind, body, visibility,
  attachment_ids) -> ReplyRead` and `get_ticket_detail(*, ticket_id, actor_id,
  actor_kind, cursor, limit) -> TicketDetailRead`, where `actor_kind:
  Literal["customer", "agent"]` is derived by the router from
  `"tickets:write" in current_user.scopes` — the single check
  implementation-plan §2 states is reused verbatim for both the RLS `SET
  LOCAL app.actor_kind` GUC and this service-level branching, for both new
  routes. This conflates GET's own `tickets:read` mention in
  `US-4.2-api-design.md` with the plan's `tickets:write`-based derivation;
  under the shipped role seed the two scopes always travel together
  (`support_agent`/`admin`), so this is not independently observable at
  integration level today — flagged as a design-documented assumption, not a
  silent invention, exactly the kind of gap `service-and-router-builder`
  either confirms or corrects.
- `TicketRepository.update(ticket_id, *, status: str | None = None,
  first_response_at: datetime | None = None) -> Ticket | None` — additive
  method on the existing `TicketRepository` fake (`FakeTicketRepository`),
  zero risk to the 12 existing ticket-creation tests, which never call it.
- `AttachmentRepository.bind_to_reply(*, attachment_id, ticket_reply_id) ->
  Attachment | None` — additive, mirrors `bind_to_ticket`'s existing
  conditional-`UPDATE` shape against the independent nullable column.
- `TicketReplyRepository.create(*, ticket_id, author_id, author_kind, body,
  visibility) -> TicketReply` and `list_for_ticket(*, ticket_id, cursor,
  limit) -> ReplyListPage | None` (a `NamedTuple`, mirroring
  `TicketListPage`), oldest-first.
- `TicketReplyRateLimitCache.record_and_check(user_id, *, window_seconds) ->
  int` / `.get_retry_after_seconds(user_id) -> int` — identical shape to
  `TicketCreationRateLimitCache`, a distinct Valkey key
  (`ticket_reply_rate_key`, distinct from `ticket_create_rate_key`).
- `EmailSender.send_ticket_reply_notification(*, to, ticket_number)` (FR-1,
  requester) and `.send_ticket_reply_queue_notification(*, ticket_number)`
  (FR-2, queue — no `to` parameter, per implementation-plan §8).
- Exceptions: `TicketNotFoundError` (404), `InsufficientPermissionError` (403,
  module-owned copy per implementation-plan §6), `TicketClosedError` (409),
  `TicketReplyRateLimitError` (429 + `Retry-After`, mirrors
  `TicketCreationRateLimitError`'s `__init__(*, retry_after_seconds)` shape).

## Fixtures / fakes needed

- Unit: `FakeTicketReplyRepository`, `FakeTicketReplyRateLimitCache` (new,
  local to `test_support_service.py`, following this file's existing
  hand-written-fake convention); `FakeTicketRepository.update()` and
  `FakeAttachmentRepository.bind_to_reply()` (additive extensions to the
  existing fakes); `FakeEmailSender.send_ticket_reply_notification()` /
  `.send_ticket_reply_queue_notification()` (additive). All return/record
  against real `app.modules.support.models.TicketReply`/`Ticket`/`Attachment`
  ORM instances, not lookalike dataclasses, matching this file's existing
  `mypy --strict` Protocol-covariance convention.
- Integration: existing `client`/`db_session`/`db_connection` fixtures; new
  local helpers `_seed_ticket`, `_seed_reply`, `_reply_payload`, `_seed_agent`
  (a `support_agent`-role user with a `tickets:read`+`tickets:write` token,
  mirroring `_seed_user`/`_assign_role`'s existing pattern); reuses
  `_seed_attachment`, `_expired_token`, `_revoked_session_token`,
  `_auth_headers` verbatim from the existing US-4.1 test surface in the same
  file.

## RLS test design (NFR, Risk 1, Risk 2)

Three integration tests query `ticket_replies` directly via the shared
`db_session` fixture, executing `SET LOCAL app.actor_kind = '<value>'` (or
omitting it) themselves — bypassing the repository, the service, and the
`get_rls_session` dependency entirely, per the NFR's literal instruction
("application filter deliberately disabled"):

1. `app.actor_kind = 'customer'` → only `visibility='public'` rows return.
2. `app.actor_kind = 'agent'` → `visibility='internal'` rows also return.
3. GUC never set this transaction → internal rows are hidden (db-design v3's
   "fail-closed by construction": `current_setting(..., true)` returns `NULL`,
   and `NULL = 'agent'` is not true).

These three, plus `test_get_ticket_detail_hides_internal_reply_from_customer_
but_shows_to_agent` (the application-level, full-HTTP-round-trip version),
together prove FR-3/TR-AC3's "holds even if the application layer forgets to
filter" claim at both layers independently — the NFR's own stated intent.

## Statement-count ceiling (`AGENTS.md` §5)

`GET /v1/support/tickets/{id}` returns nested data (`replies:
ReplyThreadPage`), unlike US-4.1's flat `TicketListResponse`
(`US-4.1-test-strategy.md`'s own "no such assertion is added" note does not
carry over here). This project has no existing statement-counting harness to
reuse (`tests/integration/modules/audit/test_audit_router.py` made the same
observation for its own list-pagination rule and chose a more directly
applicable check instead of building one). Rather than assert a brittle
absolute statement count this pass cannot verify against real application code
yet, `test_get_ticket_detail_reply_thread_statement_count_independent_of_reply
_count` compares the statement count for a 2-reply ticket against a 20-reply
ticket via a local `sqlalchemy.event.listen(... "before_cursor_execute" ...)`
counter and asserts they are equal — the precise claim the rule exists to
protect (no per-reply query / N+1 regression), independent of how many other
statements the auth/session middleware issues.

## Known gaps — not tested here, and why

- **API_DESIGN OQ-2's "neither owner nor agent" POST branch** — asserted at
  the unit level only (`actor_kind` injected directly), not at integration
  level. `US-4.2-api-design.md` itself states this is "currently unreachable
  in practice under the shipped role seed" (`tickets:read`/`tickets:write`
  are always granted together) — there is no real JWT scope combination that
  reaches this branch via HTTP today. The analogous GET-side case IS
  integration-tested (`test_get_ticket_detail_agent_lacking_tickets_read_
  returns_404`) by withholding both scopes from an agent-role user, since
  GET's authorization does not depend on ownership as an alternate path the
  way POST's does when `actor_kind="agent"` bypasses the ownership check
  entirely — POST's specific "agent-shaped but missing exactly tickets:write"
  combination has no way to exist under the shipped seed (a `support_agent`
  role either has both ticket scopes or neither).
- **The migration's RLS DDL proof itself** (`upgrade → downgrade → upgrade`
  actually dropping/recreating the policies) is `migration-manager`'s own
  responsibility (task T3), not duplicated in this test suite — this suite's
  three RLS tests prove the policy's *behavior* once migrated, not the
  migration's own reversibility.
- **`author_kind`-to-role mapping edge cases** (a hypothetical `admin` caller
  vs. `support_agent`) — `US-4.2-entity-model.md`'s own "Known Gaps" section
  defers this mapping to `service-and-router-builder`; this suite tests
  `actor_kind` as an already-resolved `"customer"`/`"agent"` value at the unit
  level and exercises only `support_agent` at the integration level (the role
  the shipped seed grants both ticket scopes to), matching
  `test_support_router.py`'s own existing `support_agent`-only convention for
  US-4.1's agent-branch tests.

## Coverage floor

85% minimum overall, 90%+ on `support/service.py` and `support/router.py`, per
`AGENTS.md` §5/§6 and the implementation plan's own Testing Strategy —
enforced by `gate-enforcer`, not measured by this stage.
