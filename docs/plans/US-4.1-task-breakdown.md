---
artifact_type: task_breakdown
story: US-4.1
version: 1
status: DRAFT
created_at: "2026-09-03T01:00:00Z"
updated_at: "2026-09-03T01:00:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/impact-analysis/US-4.1-impact-analysis.md
    version: 1
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
supersedes: null
---

# Task Breakdown — US-4.1 (Support Tickets — Create)

Every task below traces to a file named in `US-4.1-implementation-plan.md`'s
"Files To Create"/"Files To Modify" tables or `US-4.1-impact-analysis.md`'s
§1/§2. Nothing here invents scope.

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | schema-builder | schemas | — | `app/modules/support/schemas.py` | mypy clean on the file; `grep extra="forbid"` present on `CreateTicketRequest`/`TicketBase`; `TicketRead` declares `from_attributes=True` with an explicit field list. |
| T2 | data-layer-builder | models/repository/cache | — | `app/modules/support/models.py`, `repository.py`, `cache.py`, `app/core/cache_keys.py` | mypy clean; `grep -c "session.query("` returns 0; `grep sqlalchemy app/modules/support/cache.py` returns no import. |
| T3 | data-layer-builder | repository | — | `app/modules/audit/repository.py` (add `AuditRepository.record_event(...)`, extend `AuditRepositoryProtocol`) | mypy clean; `grep -A5 "def record_event"` shows no `self._session.commit()`/`.commit()` call in the new method. (Parallel-eligible with T2 — different module, same skill.) |
| T4 | migration-manager | migration | T2 | `migrations/versions/<rev>_add_support_tickets.py`, `migrations/env.py` (one-line `support` model-registration import, same pattern as 6 prior modules) | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all succeed; `grep "from app.modules.support import models"` present in `migrations/env.py`. |
| T5 | service-and-router-builder (service) | service | T3 | `app/modules/audit/service.py` (add `AuditLogService.record_event(...)`, no self-commit, reuses `_resolve_actor_role`) | mypy clean; `grep -A15 "def record_event"` in `service.py` shows no `self._repository.commit()` call; `tests/unit/modules/audit/test_audit_service.py` (test-writer's file) passes once written. |
| T6 | service-and-router-builder (service) | service | T1, T4, T5 | `app/modules/support/service.py`, `exceptions.py`, `scripts/purge_unbound_attachments.py` | `grep -c "fastapi\|starlette\|HTTPException" app/modules/support/service.py` returns 0; `create_ticket` issues exactly one `await self._repository.commit()` (grep count = 1); `python scripts/purge_unbound_attachments.py` exits 0 against a seeded test DB. |
| T7 | service-and-router-builder (router) | router | T6 | `app/modules/support/router.py`, `dependencies.py`, `app/api/v1/router.py` (register `support_router`) | `grep -c "sqlalchemy\|AsyncSession\|repository\." app/modules/support/router.py` returns 0; OpenAPI schema render matches `US-4.1-openapi.yaml` v3 endpoint/schema shapes; `grep "include_router(support_router)"` present in `app/api/v1/router.py`. |
| T8 | gate-enforcer | — | T1–T7 (+ test-writer's TEST_WRITING output) | — | `pre-commit run --all-files`; `mypy app tests` (strict); `lint-imports`; `pytest --cov` ≥85% overall, ≥90% on `support/service.py` and `support/router.py`. |

**Ordering notes:**
- T1 and T2 have no dependency on each other and may run in parallel (schema-builder / data-layer-builder, per this skill's ordering rule).
- T3 is scoped to `data-layer-builder` because it is a repository-layer change (`app/modules/audit/repository.py`), same skill as T2 but a different module/file — sequenced independently of T2, also parallel-eligible with it.
- T4 (migration) must follow T2: Alembic autogenerate needs `Ticket`/`Attachment` registered in `models.py` and the `migrations/env.py` import to see them.
- T5 must follow T3: the new `AuditLogService.record_event` method calls into the new `AuditRepository.record_event` method T3 adds.
- T6 (`support.service`) depends on T1 (needs `schemas.py` for its `-> *Read` return annotations), T4 (the `tickets`/`attachments` tables must exist for repository calls to be meaningful at runtime), and T5 (`create_ticket` calls `AuditLogService.record_event`, which must exist).
- T7 (`support.router`) depends on T6 — a router cannot wire `TicketServiceDep` to a service that doesn't exist yet.
- T8 (`gate-enforcer`) runs once, after every other task and after `test-writer`'s TEST_WRITING stage output exists, per `stage-map.yaml`.

## Non-Blocking Findings

- **`scripts/purge_unbound_attachments.py`'s owning execution skill is not a clean fit.** It is a standalone CLI script (no router, no OpenAPI operation) that calls `TicketService`/`AttachmentRepository` methods — closest in shape to `service-and-router-builder`'s service-layer output, but that skill's own scope is described as "implementing an approved OpenAPI contract," which this script is not part of. Assigned to T6 (bundled with `support.service.py`) as the most reasonable fit among the four execution skills, per `US-4.1-implementation-plan.md`'s own placement of this file directly under the module's service-layer file list. Flagged for `plan-reviewer` to confirm or redirect.
- Carried forward, unchanged, from `ARCHITECTURE_PLANNING`/`IMPACT_ANALYSIS` (not this stage's to resolve): OD-3 (`category` enum still unenumerated), BR-007 FK `ondelete` mechanics still `RESTRICT`-by-default, and the idempotency poll-exhaustion undocumented `500` path (confirmed as intended behavior, not a gap).

## Result

```yaml
result:
  verdict: PASS
  stage: IMPLEMENTATION_PLANNING
  story: US-4.1
  artifact_status: DRAFT
  artifacts:
    - docs/plans/US-4.1-task-breakdown.md
  next_stage: PLAN_REVIEW
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "scripts/purge_unbound_attachments.py has no clean single-skill owner among the four execution skills; assigned to service-and-router-builder (T6) as closest fit, flagged for plan-reviewer to confirm."
    - "OD-3 (category enum), BR-007 FK ondelete mechanics, and the idempotency poll-exhaustion undocumented 500 path remain open, carried forward unchanged for PLAN_REVIEW."
```
