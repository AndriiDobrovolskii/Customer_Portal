---
artifact_type: task_breakdown
story: US-4.3
version: 1
status: ARCHIVED
created_at: "2026-09-06T21:00:00Z"
updated_at: "2026-09-06T21:00:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/designs/database/US-4.3-db-design.md
    version: 3
  - path: docs/designs/database/US-4.3-entity-model.md
    version: 3
  - path: docs/impact-analysis/US-4.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.3-implementation-plan.md
    version: 1
supersedes: null
---

# Task Breakdown — US-4.3 (Ticket Resolution)

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | schema-builder | schemas | — (parallel with T2) | `app/modules/support/schemas.py` (new `ResolveTicketRequest` — `resolution_note: str = Field(min_length=1, max_length=5000)`; `CloseTicketRequest`/`ReopenTicketRequest` — each `reason: str \| None = None`, unconstrained per api-design v2 Open Questions #4; new `TicketStateRead` — `id`, `ticket_number`, `status`, `resolved_at`, `closed_at`, `updated_at` only) | mypy `strict` clean; grep confirms `extra="forbid"` on all three inbound `*TicketRequest` schemas; `TicketStateRead` declares `from_attributes=True` with an explicit field list that excludes `closed_by`/`resolution_note` (api-design v2 Open Questions #5's data-minimization scope). |
| T2 | data-layer-builder | models / repository | — (parallel with T1) | `app/modules/support/models.py` (four additive nullable `Ticket` columns — `resolved_at`, `resolution_note` `String(5000)`, `closed_at`, `closed_by` no-FK; two new `CheckConstraint`s — `ck_tickets_closed_requires_closed_fields`, `ck_tickets_resolved_requires_resolution_fields`; new partial `Index` `ix_tickets_resolved_at_pending_autoclose`; new module-level `SYSTEM_ACTOR_ID` constant, Decision 5), `app/modules/support/repository.py` (`TicketRepository`: new `transition_status(...)` — Decision 2, conditional `UPDATE ... WHERE id = :id AND status IN (...)` with the optional inclusive 7-day window guard; new `auto_close_resolved_past_window(...)` — Decision 8, batch `UPDATE ... RETURNING id` on the strict `<` predicate; new module-level `_RESOLUTION_WINDOW_DAYS = 7` constant, Decision 7, shared by both predicates via bound-parameter interval arithmetic, never string-interpolated) | mypy `strict` clean; grep confirms zero `session.query()` additions; grep diff confirms `TicketRepository.update()`, `get_by_id()`, `list_for_requester()` are byte-for-byte unchanged (Decision 2 requires `update()` stay unconditional); `transition_status` and `auto_close_resolved_past_window` both reference `_RESOLUTION_WINDOW_DAYS`, never a second hardcoded `7`. |
| T3 | migration-manager | migration | T2 | `migrations/versions/<hash>_add_ticket_resolution_columns.py` (four `ALTER TABLE tickets ADD COLUMN ...`, two `CHECK` constraints, one partial index, all additive/autogeneratable) | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` against real Postgres; read the generated file and confirm the partial index's `postgresql_where` clause and both `CHECK` expressions render verbatim (a silently-dropped clause is not an error — plan's own caveat); confirm `migrations/env.py` diff is zero (`support.models` already registered wholesale, `AGENTS.md` §7.9 protected file). |
| T4 | service-and-router-builder (service) | service | T1, T3 | `app/modules/support/service.py` (`TicketService`: new `resolve_ticket`/`close_ticket`/`reopen_ticket` methods implementing api-design v2's check order — lookup/ownership → transition validity `409` → permission `403` → `transition_status` call → audit write → best-effort email; new `_ALLOWED_EVENTS_BY_STATUS` table, Decision 4; `TicketRepositoryProtocol` gains `transition_status`; `TicketReplyService`: new required `audit_service: AuditServiceProtocol` constructor parameter, Decision 3; `create_reply`'s FR-4 branch switches from `update()` to `transition_status(..., require_resolved_within_window=True)` and writes `audit_log` — `event=ticket_reopened` — on success), `app/modules/support/exceptions.py` (new `InvalidStateTransitionError` — `type_slug="invalid-state-transition"`, `status=409`, carries `allowed_events: list[str]`, Decision 9) | grep confirms zero `fastapi`/`starlette`/`HTTPException` imports in `service.py`; mypy `strict` clean with explicit `-> *Read`/`-> None` annotations on every new/changed method; each of the five `_ALLOWED_EVENTS_BY_STATUS` keys produces the exact `allowed_events` list the plan's Decision 4 table states; grep confirms every `TicketReplyService(...)` call site (test fixtures included) now passes `audit_service` — Risk 3. |
| T5 | service-and-router-builder (router) | router | T4 | `app/modules/support/router.py` (three new routes — `POST /support/tickets/{id}/resolve`, `/close`, `/reopen`, `response_model=TicketStateRead`, `status_code=200`, using `TicketServiceDep`/`resolve_actor_kind`), `app/modules/support/dependencies.py` (`get_ticket_reply_service` gains `audit_service: AuditLogServiceDep`, passed through to `TicketReplyService(...)` — the only new wiring `TicketReplyService` needs, Decision 3; `get_ticket_service`/`TicketServiceDep` unchanged) | grep confirms zero `sqlalchemy`/`models`/`repository`/`AsyncSession`/Valkey imports in `router.py`; OpenAPI render (`app.openapi()`) matches `US-4.3-openapi.yaml` v2's three endpoint and `TicketStateRead`/`*TicketRequest` schema shapes exactly; `lint-imports` passes (`router → dependencies` only). |
| T6 | service-and-router-builder (service script form — see Assignment note) | service (script form) | T2, T3 | **New file** `scripts/auto_close_resolved_tickets.py` (FR-3's cron entry point, following `purge_unbound_attachments.py`'s `main() -> int` shape; builds a DB engine and, per Decision 6, a Valkey client mirroring `app/main.py`'s `lifespan` construction; calls `TicketRepository.auto_close_resolved_past_window`; loops the returned ids writing one `AuditLogService.record_event(event="ticket_auto_closed", actor_id=SYSTEM_ACTOR_ID, target_id=<id>)` per id, Decision 8; issues one `repository.commit()` for the whole run) | Standalone execution against real Postgres+Valkey closes only `"resolved"` tickets whose `resolved_at` is strictly more than 7 days old (`_RESOLUTION_WINDOW_DAYS`, T2), writes exactly one `ticket_auto_closed` audit_log row per closed ticket with `actor_id=SYSTEM_ACTOR_ID`; a second immediate re-run returns an empty id list (idempotency, NFR) and writes no further audit rows; `lint-imports` confirms the script imports `repository`/`models` plus `app.modules.audit.*`/`app.modules.roles.*` only, never `service.py`. |
| T7 | gate-enforcer | — | T1–T6 | — | `pre-commit run --all-files`; `mypy app tests` strict; `lint-imports`; `pytest --cov` against the 85% overall / 90%+ `service.py`/`router.py` floors (`AGENTS.md` §5/§6), including the new audit-write branch and the script's Valkey-wiring path (Risk 6, no exclusion). |

**Parallel-eligible:** T1 and T2 have no dependency on each other and may run
in parallel. T6 is also parallel-eligible with T4/T5 in principle — its code
depends only on T2's repository method and `SYSTEM_ACTOR_ID`, never on
`service.py` or `router.py` (Decision 5/6: the script bypasses `TicketService`
entirely) — but both branches must complete before `gate-enforcer` (T7), and
T6's own live-execution verification needs T3's migration applied either way.

## Assignment note — T6 (non-blocking, carried to `plan-reviewer`)

`scripts/auto_close_resolved_tickets.py` does not fit any of the four
execution skills' stated file footprint (it is not a schema, a
model/repository/cache change, a migration, or a `service.py`/`router.py`
change within `app/modules/support/`). This breakdown assigns it to
**service-and-router-builder, service form**, following the identical
precedent this project already established for `scripts/verify_audit_chain.py`
and `scripts/anonymize_erased_user.py` (`docs/plans/US-3.3-task-breakdown.md`
T6/T6b, OD-15, resolved 2026-09-02: "closest fit, no execution skill's stated
contract covers `scripts/`"). The script's own logic — a business-conditional
batch update paired with per-row audit writes — is service-layer business
logic in shape, even though it runs standalone and talks to the repository
directly rather than through `TicketService`. If `plan-reviewer` or the
`HUMAN_PLAN_APPROVAL` gate judges this assignment wrong, the correct loop-back
is `changes_required_sequencing` (stays within
`IMPLEMENTATION_PLANNING`/`PLAN_REVIEW`) — the *what* is already settled by
`implementation_plan` v1; only the *who* was open.

## Notes

- Ordering follows `AGENTS.md` §3 and this project's migration-before-model-use
  rule: T3 must complete and be proven before T4/T5/T6 run against the live
  schema, even though T4/T5's code only imports `repository.py` (T2), not the
  migration file itself.
- No `test-writer` tasks appear in this breakdown — `TEST_WRITING` is a
  separate stage that runs before `IMPLEMENTATION` per `stage-map.yaml` and
  supplies `test_strategy`/`ac_test_matrix` as inputs to T7's gate, rather than
  being sequenced as an `IMPLEMENTATION` sub-step (consistent with
  `docs/plans/US-4.2-task-breakdown.md`'s identical omission).
- Risks 1 and 2 from `implementation_plan` v1 (the undefined resolved-but-
  expired-window response; `_ALLOWED_EVENTS_BY_STATUS` being new,
  unreviewed business-facing content) are not separate tasks — both are
  already reflected in T4's design (the table's literal values; the
  window-guard's `None`-return-to-409 fallthrough) and are carried forward as
  documented, non-blocking gaps per this project's established pattern.
- Risk 3 (`TicketReplyService`'s new required `audit_service` parameter
  breaking any direct-instantiation test fixture) is T4's own verification
  item, not a fifth task — `impact-analyzer`'s Test-Surface Impact section
  already scopes the fixture updates to `TEST_WRITING`.
