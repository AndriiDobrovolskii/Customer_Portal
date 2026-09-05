---
artifact_type: implementation_plan
story: US-4.3
version: 1
status: DRAFT
created_at: "2026-09-06T20:00:00Z"
updated_at: "2026-09-06T20:00:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/reviews/specifications/US-4.3-spec-review.md
    version: 3
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/designs/database/US-4.3-db-design.md
    version: 3
  - path: docs/designs/database/US-4.3-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.3-design-review.md
    version: 3
  - path: docs/impact-analysis/US-4.3-impact-analysis.md
    version: 1
supersedes: null
---

# Implementation Plan: Ticket Resolution (US-4.3)

## Goal

Extend the existing `app/modules/support/` module (US-4.1/US-4.2) with three
new ticket-transition endpoints — `POST /v1/support/tickets/{id}/resolve`,
`/close`, `/reopen` — a modification to the already-shipped `POST
.../replies` endpoint's status-transition side effect (FR-4, adds an
`audit_log` write per DESIGN_REVIEW's DR-4), and a new scheduled batch script
(`scripts/auto_close_resolved_tickets.py`, FR-3) that closes tickets resolved
more than 7 days ago with no reply. One Alembic migration (four additive
`tickets` columns, two `CHECK` constraints, one partial index). This is the
first story to require this module's `TicketRepository.update()` to become
conditional, and the first script in this codebase that must combine a
business-conditional batch `UPDATE` with a per-row `audit_log` write.

## Architectural Decisions

`impact-analyzer` left three structural questions open for this stage. Each
is decided below with its rationale — these are the substantive calls this
plan makes, not restatements of the design docs.

### 1. `/resolve`, `/close`, `/reopen` land on `TicketService`, not `TicketReplyService`

`impact-analyzer` flagged this as undecided and noted the authorization shape
`/close`/`/reopen` need (requester-or-agent, actor-kind-dependent ownership
check) structurally matches `TicketReplyService.create_reply`'s existing
pattern, not `TicketService`'s (which today only ever does pure ownership or
pure creation, no ownership branch).

**Decision: all three new methods go on `TicketService`.** Reasons:

- `TicketService.__init__` already receives `audit_service`, `user_service`,
  and `email_sender` — the exact three collaborators FR-1/FR-2/FR-5 need
  (audit write, resolution-note email, notification). **No new constructor
  parameter, no new `dependencies.py` wiring** for this class.
- The actor-kind-dependent ownership check
  (`if actor_kind == "customer" and ticket.requester_id != actor_id: raise
  TicketNotFoundError`) is a two-line inline check, not a shared helper —
  confirmed by direct read that `TicketReplyService.create_reply` and
  `get_ticket_detail` already duplicate this same check inline rather than
  extracting it (this file's own established style). Reusing that style on
  `TicketService`'s three new methods costs three more inline duplicates of
  the same two lines, not a new abstraction — consistent with `AGENTS.md`
  §7.8 ("no opportunistic refactors of untouched code": `TicketReplyService`'s
  existing two call sites are left exactly as they are).
- `TicketReplyService` still gains a new `audit_service` constructor
  parameter regardless of this decision — DR-4's fix to `create_reply`'s
  status-transition branch requires it either way (see Decision 3). Routing
  `/resolve`/`/close`/`/reopen` to `TicketService` instead avoids adding a
  *second* new collaborator wire-up (this class already has everything) and
  keeps `TicketReplyService`'s blast radius limited to the one audit-write
  line DR-4 actually requires.
- REST-resource alignment: these three operations transition a *ticket's*
  state; they are not reply operations that happen to also move ticket
  status (unlike FR-4, which is a side effect of an actual reply). Grouping
  them with `TicketService`'s other ticket-level operations (`create_ticket`,
  `list_own_tickets`) reads more naturally than adding them to the reply
  class.

**Rejected alternative:** host all three on `TicketReplyService` (reusing its
existing ownership-check *pattern*, not literal code, since neither class
extracts it into a shared function). Rejected because it would force wiring
`audit_service` into `get_ticket_reply_service` as a *required* parameter for
methods (`resolve`/`close`/`reopen`) whose own natural home already has it,
while leaving `TicketService`'s already-complete collaborator set unused —
strictly more wiring for no benefit.

### 2. One new repository method, `TicketRepository.transition_status(...)`, not an overload of `update()`

`update()` today is unconditional (`WHERE id = :id`, no status predicate) and
is kept that way — it still serves `create_reply`'s existing
`first_response_at`/status writes (US-4.2, unchanged, no window or
FR-9-style concurrency requirement there). FR-9 requires a *conditional*
`UPDATE ... WHERE id = :id AND status IN (...)` (and, for `/reopen` and
FR-4, also `AND resolved_at >= now() - interval '7 days'`, DR-2), returning
`None` on zero rows affected (race loss or wrong state) rather than the
ticket's current row. Bolting a conditional-guard parameter onto `update()`
would silently change what every existing caller's `None`-returning
"leave unchanged" contract means. Instead, one new method, matching this
repository's own precedent of naming a business-specific conditional update
descriptively rather than forcing it through the generic verb
(`AttachmentRepository.bind_to_ticket`/`bind_to_reply` are exactly this
shape already, `WHERE ... IS NULL` conditional updates with their own
names, not a second `update()`):

```python
async def transition_status(
    self,
    ticket_id: uuid.UUID,
    *,
    expected_statuses: Sequence[str],
    new_status: str,
    resolved_at: datetime | None = None,  # set (FR-1) — mutually exclusive with clear_resolved_at
    clear_resolved_at: bool = False,  # FR-4/FR-5 — explicit clear, since `None` means "leave unchanged" everywhere else in this file
    resolution_note: str | None = None,  # FR-1
    closed_at: datetime | None = None,  # FR-2
    closed_by: uuid.UUID | None = None,  # FR-2
    require_resolved_within_window: bool = False,  # DR-2 — adds the inclusive 7-day guard (FR-4, FR-5 only)
) -> Ticket | None:
    """Conditional UPDATE ... WHERE id = :id AND status IN (:expected_statuses)
    [AND resolved_at >= now() - interval '7 days' if require_resolved_within_window].
    Returns None on zero rows affected: ticket not found, status was not
    one of expected_statuses (FR-6/FR-9), or (when the window guard is set)
    the 7-day window had already elapsed. The service cannot distinguish
    these from row count alone — same as every prior conditional-UPDATE
    method in this repository (bind_to_ticket, bind_to_reply) — and must
    have already confirmed the ticket exists via get_by_id earlier in the
    same request, per US-4.3-api-design.md's check order.
    """
```

Used by `/resolve` (`expected_statuses=["open","waiting_on_support",
"waiting_on_customer"]`, OD-5), `/close` (`expected_statuses=["open",
"waiting_on_support","waiting_on_customer","resolved"]`), `/reopen`
(`expected_statuses=["resolved"]`, `require_resolved_within_window=True`),
and `TicketReplyService.create_reply`'s FR-4 branch (same as `/reopen`'s
predicate, reusing this one method — not a second copy).

### 3. `TicketReplyService.create_reply`'s FR-4 branch needs a new, required `audit_service` constructor parameter

Confirmed by direct read: `TicketReplyService.__init__` has no
`audit_service` parameter today. DR-4 requires FR-4's reply-driven reopen
(the `elif ticket.status in ("waiting_on_customer", "resolved"):
status_update = "waiting_on_support"` branch, `service.py:515-518`) to also
write `audit_log` (`event=ticket_reopened`, `actor=self`). Add
`audit_service: AuditServiceProtocol` as a new required constructor
parameter (matching `TicketService`'s existing pattern, not optional like
`user_service`, since every reply that reopens a ticket must be audited —
no code path may skip it). `get_ticket_reply_service`
(`dependencies.py:101-118`) gains `audit_service: AuditLogServiceDep` and
passes it through — the only new wiring this story adds to
`TicketReplyService`.

### 4. `allowed_events` is one explicit table, keyed by status, shared by all three endpoints

The spec's own NFR requires "one explicit transition table in a single
module." One module-level constant in `service.py`:

```python
_ALLOWED_EVENTS_BY_STATUS: dict[str, list[str]] = {
    "open": ["resolve", "close"],
    "waiting_on_support": ["resolve", "close"],
    "waiting_on_customer": ["resolve", "close"],
    "resolved": ["close", "reopen"],
    "closed": [],
}
```

Event names are the endpoint verbs (`resolve`/`close`/`reopen`), not
`audit_log`'s past-tense event strings (`ticket_resolved`/...) — these are
two different vocabularies for two different audiences (a client deciding
what it may retry vs. an audit record of what happened), and nothing in the
spec's Error Envelope Schema states which the API-facing field uses.
`InvalidStateTransitionError` is raised with
`allowed_events=_ALLOWED_EVENTS_BY_STATUS[ticket.status]`; the same table
also names the source-status set each `transition_status` call passes as
`expected_statuses`, so there is exactly one place that ever states "which
statuses this event is legal from" (`FR-6`'s generalization,
`US-4.3-api-design.md` Open Questions #2). This table is not itself the
window-boundary check — a `"resolved"` ticket outside the 7-day window still
reports `allowed_events=["close", "reopen"]` per this status-only table; the
window's own undefined-response gap (Open Questions #1, DR-5) is unaffected
by this table and is not resolved here — see Risks.

### 5. System-actor sentinel constant lives in `models.py`, not `service.py`

`closed_by`'s system-actor sentinel (OD-7) and the auto-close job's
`audit_log.actor_id` must be the same value. The auto-close **script**
bypasses `TicketService` entirely (matching `purge_unbound_attachments.py`'s
established precedent: talk to the repository directly, since the job needs
no idempotency/rate-limit/most-of-`TicketService`'s-collaborators) and so
never imports `service.py`. Declaring the constant in `models.py` — next to
the `closed_by` column it exists to satisfy — lets both the script (which
imports `models`/`repository` only) and `service.py` (which already imports
`models`) reference the one value without the script importing a module it
otherwise has no reason to touch:

```python
# app/modules/support/models.py, module level, near Ticket
SYSTEM_ACTOR_ID: Final = uuid.UUID("00000000-0000-0000-0000-000000000000")
```

### 6. The auto-close script needs a Valkey connection too, not just Postgres — first purge-style script to need one

`record_event`'s `actor_role` resolution calls `RoleService.get_role_grants_for_user`,
which needs `PermissionEpochCache` (Valkey-backed), even though the sentinel
actor resolves to no role grants (confirmed sound by `DESIGN_REVIEW` v3: an
existing, harmless empty-list path). `purge_unbound_attachments.py` and
`purge_unverified_accounts.py` need only `create_engine_and_sessionmaker` —
this script additionally constructs a Valkey client via
`Redis.from_url(settings.valkey_url, decode_responses=True)`, mirroring
`app/main.py`'s `lifespan` construction exactly (there is no
script-callable helper for this today — `get_valkey_client` reads from
`request.app.state`, unusable outside a request). The script builds
`AuditRepository(session)`, `RoleRepository(session)`,
`UserRoleRepository(session)`, `PermissionEpochCache(valkey_client)`,
`RoleService(role_repository, user_role_repository, permission_epoch_cache)`,
`AuditLogService(audit_repository, role_service)` directly — heavier
wiring than any prior script, but no new abstraction: every one of these
classes and their constructors already exists.

### 7. The 7-day window constant is declared once, in `repository.py`, and used by both predicates

`_RESOLUTION_WINDOW_DAYS = 7` (module level, `repository.py`, next to
`transition_status`) is the single shared constant the spec's NFR requires
("evaluated ... from a single shared constant"). Both
`transition_status`'s inclusive guard (`resolved_at >= now() - interval
'7 days'`, used when `require_resolved_within_window=True`) and the new
`auto_close_resolved_past_window`'s strict guard (`resolved_at < now() -
interval '7 days'`) build their `WHERE` fragment from this one constant —
never two independently hardcoded `7`s. The interval arithmetic itself uses
a bound parameter for the day count (e.g. `func.now() -
func.make_interval(days=literal(_RESOLUTION_WINDOW_DAYS))`, or equivalent),
never string-interpolated SQL text, per `AGENTS.md` §7's "no string
interpolation, ever" — exact SQLAlchemy expression is
`data-layer-builder`'s call, not fixed further here.

### 8. `auto_close_resolved_past_window` returns the affected ticket ids, not a count

FR-3 requires one `ticket_auto_closed` audit entry **per ticket** closed
(`target_id` = that ticket's id), not one aggregate entry for the whole
batch run. New repository method:

```python
async def auto_close_resolved_past_window(
    self, *, closed_at: datetime, closed_by: uuid.UUID
) -> list[uuid.UUID]:
    """Single UPDATE ... WHERE status = 'resolved' AND resolved_at <
    now() - interval '7 days' (Decision 7's shared constant) ... RETURNING
    id. Idempotent and safe to re-run (NFR): a ticket already closed by a
    prior run, or reopened since, no longer matches the WHERE clause.
    Served by ix_tickets_resolved_at_pending_autoclose.
    """
```

The script loops the returned ids, calling `audit_service.record_event(...)`
once per id (`event="ticket_auto_closed"`, `actor_id=SYSTEM_ACTOR_ID`,
`target_id=<id>`), then issues **one** `repository.commit()` for the whole
run — one business operation, one commit (`AGENTS.md` §3), even though it
covers many tickets and many audit rows.

### 9. `InvalidStateTransitionError` is a new module-owned exception class

Confirmed by direct read: this module has no `409` exception today
(`TicketClosedError` uses a different slug, `"ticket-closed"`, and carries
no `allowed_events` field). New class in `support/exceptions.py`, additively
shaped per `US-4.3-api-design.md` (adds `allowed_events: list[str]` beyond
`app/modules/admin_users/exceptions.py`'s same-slug US-3.1 class) — not
imported from there, matching this module's established
`AccountDeactivatedError`/`InsufficientPermissionError` module-ownership
convention.

## Files To Modify

| File | Change |
|---|---|
| `app/modules/support/models.py` | Four additive, nullable `Ticket` columns (`resolved_at`, `resolution_note`, `closed_at`, `closed_by`, per db-design v3). Two new `CheckConstraint`s, one new partial `Index` (`ix_tickets_resolved_at_pending_autoclose`) in `Ticket.__table_args__`. New module-level `SYSTEM_ACTOR_ID` constant (Decision 5). |
| `app/modules/support/repository.py` | `TicketRepository`: new `transition_status(...)` (Decision 2), new `auto_close_resolved_past_window(...)` (Decision 8), new `_RESOLUTION_WINDOW_DAYS` constant (Decision 7). Existing `update()`, `get_by_id()`, `list_for_requester()` unchanged. |
| `app/modules/support/service.py` | `TicketService`: three new methods, `resolve_ticket`, `close_ticket`, `reopen_ticket` (Decision 1), each implementing `US-4.3-api-design.md`'s check order (lookup/ownership → transition validity `409` → permission `403`/skip → `transition_status` call → audit write → best-effort email). New `_ALLOWED_EVENTS_BY_STATUS` table (Decision 4). `TicketRepositoryProtocol`: add `transition_status`. `TicketReplyService`: new required `audit_service: AuditServiceProtocol` constructor parameter (Decision 3); `create_reply`'s FR-4 branch (`elif ticket.status in (...)`) switches from `self._ticket_repository.update(...)` to `self._ticket_repository.transition_status(..., require_resolved_within_window=True)` and, on success, writes `audit_log` (`event=ticket_reopened`, `actor_id=actor_id`). |
| `app/modules/support/router.py` | Three new routes: `POST /support/tickets/{id}/resolve`, `/close`, `/reopen` — `response_model=TicketStateRead`, `status_code=200`, using `TicketServiceDep` and `resolve_actor_kind(current_user)` (already-existing helper, no new dependency). |
| `app/modules/support/dependencies.py` | `get_ticket_reply_service`: add `audit_service: AuditLogServiceDep` parameter, pass through to `TicketReplyService(...)` (Decision 3). `get_ticket_service`/`TicketServiceDep`: unchanged — already provides every collaborator the three new methods need (Decision 1). |
| `app/modules/support/schemas.py` | New `ResolveTicketRequest` (`resolution_note: str = Field(min_length=1, max_length=5000)`), `CloseTicketRequest`/`ReopenTicketRequest` (each `reason: str \| None = None`, accepted, unconstrained per api-design Open Questions #4), `TicketStateRead` (`id`, `ticket_number`, `status`, `resolved_at`, `closed_at`, `updated_at` only, per api-design Open Questions #5's data-minimization scope). |
| `app/modules/support/exceptions.py` | New `InvalidStateTransitionError` (`type_slug="invalid-state-transition"`, `status=409`, carries `allowed_events: list[str]`) — Decision 9. `InsufficientPermissionError`/`TicketNotFoundError` reused unchanged (both already exist with the exact shape FR-7/FR-8 need). |
| **New file** `scripts/auto_close_resolved_tickets.py` | FR-3's cron entry point, following `purge_unbound_attachments.py`'s shape (standalone `main() -> int`, `if __name__ == "__main__":` + `SystemExit(asyncio.run(main()))`), extended per Decisions 5/6/8: builds both a DB engine and a Valkey client, calls `TicketRepository.auto_close_resolved_past_window`, loops the returned ids writing one `AuditLogService.record_event(...)` each, commits once. |
| **New Alembic revision** under `migrations/versions/` | Four `ALTER TABLE tickets ADD COLUMN ...` (additive, nullable, no backfill), two `CHECK` constraints, one partial `Index` (all autogeneratable per db-design v3; `migration-manager` still reads the generated file to confirm the partial index's `postgresql_where` clause and both `CHECK` expressions render verbatim, since a silently-dropped clause is not an error). |

`migrations/env.py` — confirmed by direct read (`env.py:22`,
`from app.modules.support import models as support_models  # noqa: F401`):
`support.models` is already registered as a whole module. **Zero-diff
expected** — flagged per `AGENTS.md` §7.9 as a protected file, but
`migration-manager` should confirm rather than assume, same posture
`US-4.2-implementation-plan.md` already took for the identical situation.

No other existing file changes. `app/api/v1/router.py` needs no change — the
three new routes are added to the same `support_router` object already
registered there (US-4.1).

## Risks

1. **Two undefined-response gaps carried forward, not resolved by this
   plan** (`US-4.3-api-design.md` Open Questions #1, `DESIGN_REVIEW` DR-5):
   a `"resolved"` ticket outside the 7-day window but not yet auto-closed
   has no stated response for `/resolve`, `/reopen`, or a reply attempt.
   This plan's `_ALLOWED_EVENTS_BY_STATUS` table (Decision 4) is status-only
   and does not encode the window, so today's design produces `200` for
   `/reopen`/the reply path in that exact gap window (the status-based
   check passes; only `transition_status`'s own conditional `UPDATE`
   discovers the window has lapsed, returning `None`/409-via-race-handling)
   — meaning a request in that gap gets the *same* `409` a genuine
   concurrent-race loser gets (Decision 2's method already returns `None`
   for both), which is a defensible default but not one any FR states.
   Flagged, not silently decided here — narrow exposure (bounded by the
   auto-close job's own run frequency), consistent with `API_DESIGN`'s own
   treatment.
2. **`_ALLOWED_EVENTS_BY_STATUS` (Decision 4) is new, unreviewed
   business-facing content.** No design document specifies the literal
   `allowed_events` values (only that the field must exist and be
   accurate) — this plan derives the table directly from the normative
   State Machine table + OD-5's resolve-eligible set + FR-2's non-closed
   scope, but `implementation-planner`/`test-writer` should treat this
   table itself as something worth an explicit test per status value, not
   just per endpoint.
3. **`TicketReplyService` gaining a required `audit_service` parameter
   (Decision 3) changes an existing class's constructor shape.** Any test
   or fixture instantiating `TicketReplyService` directly (not through
   `get_ticket_reply_service`) must be updated to pass a fake
   `AuditServiceProtocol` — confirmed in scope by `impact-analyzer`'s own
   Test-Surface Impact section (`test_support_service.py` "needs a
   new/extended case for `TicketReplyService.create_reply`'s FR-4 audit
   write, since that method's existing tests do not yet exercise an
   `audit_service` collaborator").
4. **`migrations/env.py`** — protected file (`AGENTS.md` §7.9); confirmed
   zero-diff expected above, `migration-manager` verifies rather than
   assumes.
5. **DR-6 (Minor, non-blocking, carried) — new partial index's
   `CREATE INDEX CONCURRENTLY` mechanics.** `impact-analyzer` already
   restated this as advisory-only (no live-traffic concern comparable to
   US-4.2's own carried finding); `migration-manager` confirms against
   `AGENTS.md` §4 rather than this plan assuming it.
6. **The auto-close script is the first in this codebase needing both a
   Postgres and a Valkey connection (Decision 6).** If
   `PermissionEpochCache`'s Valkey dependency is unreachable at run time
   (e.g. a cron environment that only provisions the database
   connection), the job fails entirely rather than degrading — worth an
   explicit operational note (`documentation-and-adrs`, out of this plan's
   scope) that the auto-close cron's environment must provide
   `VALKEY_URL` the same way it must provide `DATABASE_URL`.
7. **`TicketReplyService.create_reply`'s existing FR-4 branch changes which
   repository method it calls** (Decision 2: `update()` →
   `transition_status(..., require_resolved_within_window=True)`). This is
   a behavior change to already-shipped code, not purely additive: a reply
   arriving after the 7-day window on a `"resolved"` ticket today silently
   reopens it (US-4.2's own shipped behavior, no window check at all);
   after this story, that same reply's status write becomes a no-op
   (`transition_status` returns `None`) per DR-2's NFR. This is required
   by FR-4's own text ("resolved 7 days ago or less") and is not a
   regression — but `reconciliation-reviewer` should confirm this
   narrowing is traced to FR-4, not an unreviewed side effect of Decision 2's
   method reuse.

## Validation Strategy

- `pre-commit run --all-files` — Ruff format/lint, mypy `strict` on `app
  tests`, secret scan. No `Any`; explicit `-> *Read`/`-> None`/`-> Ticket |
  None` annotations on every new/changed method, including
  `transition_status` and `auto_close_resolved_past_window`.
- `lint-imports` — no new file outside the existing `support` layer set;
  `scripts/auto_close_resolved_tickets.py` follows the same
  script-is-not-a-layer precedent `purge_unbound_attachments.py` already
  established (imports `repository`/`models` directly, plus — new for this
  story — `app.modules.audit.repository`/`service` and
  `app.modules.roles.repository`/`service`, all service/repository-layer
  imports a standalone script is not barred from making).
- `alembic upgrade → downgrade → upgrade` — proves the four additive
  columns, both `CHECK` constraints (including the corrected
  one-directional `resolved`/`resolution_note` implication), and the
  partial index's `postgresql_where` clause survive a reversal and
  reapplication.
- OpenAPI renders and matches `US-4.3-openapi.yaml` v2's three endpoints
  and `TicketStateRead`/`*TicketRequest` schemas exactly.
- Coverage: 85% floor overall, 90%+ on `service.py`/`router.py`
  (`AGENTS.md` §5/§6) — no exclusion for the auto-close script's new
  Valkey-wiring path or the FR-4 audit-write branch.

## Testing Strategy

Per `AGENTS.md` §5: unit tests use hand-written fakes (never `MagicMock`);
integration tests run against real PostgreSQL/Valkey, no
`unittest.mock`/`monkeypatch` on infrastructure. Test files are
`test-writer`'s output; restated here for traceability against
`impact-analyzer`'s survey.

- **Unit** — `test_support_service.py` gains cases for: `resolve_ticket`/
  `close_ticket`/`reopen_ticket`'s full check-order (404 before 409 before
  403, per FR-6/FR-7's "state before actor" NFR), each status in
  `_ALLOWED_EVENTS_BY_STATUS` producing the correct `allowed_events` list
  (Risk 2), the concurrency-loss path (`transition_status` returning `None`
  → 409, FR-9), and each method's audit write. `TicketReplyService`'s
  existing FR-4 test(s) extended to assert the new `ticket_reopened` audit
  write and the new `require_resolved_within_window` guard (Risk 3, Risk
  7) — using a fake `AuditServiceProtocol`, not `MagicMock`.
  `test_support_repository`-equivalent (or wherever this module's
  repository-level tests live) gains cases for `transition_status`'s
  status-set and window-guard predicates, and
  `auto_close_resolved_past_window`'s `RETURNING id` batch behavior and
  idempotency (re-running against already-closed rows returns `[]`).
  `test_support_schemas.py` gains cases for `ResolveTicketRequest`'s
  `resolution_note` length validation (FR-10) and the two `reason`-carrying
  schemas' acceptance.
- **Integration** — `test_support_router.py` gains end-to-end cases for
  `/resolve` (FR-1, FR-6, FR-7, FR-9, FR-10), `/close` (FR-2), `/reopen`
  (FR-5, FR-6), and FR-4's now-modified `POST .../replies` behavior
  (a reply on a `"resolved"` ticket within the 7-day window, asserting
  both the status change and the new audit-log row). A dedicated
  boundary-instant test at exactly 7 days (OD-4: the job's strict `<`
  and the guard's inclusive `>=` must never both match the same row) —
  no existing test in this codebase exercises this pairing.
- **New test surface** — a test module for
  `scripts/auto_close_resolved_tickets.py` (no existing script test file to
  extend, per `impact-analyzer`'s own finding), and a migration proof
  (`migration-manager`'s own upgrade/downgrade/upgrade cycle) covering the
  two `CHECK` constraints and the partial index specifically.
- **Coverage** — 85% floor overall, 90%+ on `service.py`/`router.py`,
  `AGENTS.md` §5/§6. No exclusion for the new audit-write branch or the
  script's Valkey-wiring path (Risk 6).
