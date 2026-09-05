---
artifact_type: implementation_report
story: US-4.3
version: 1
status: DRAFT
created_at: "2026-09-07T05:00:00Z"
updated_at: "2026-09-07T05:00:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
  - path: docs/plans/US-4.3-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.3-task-breakdown.md
    version: 1
  - path: docs/tests/US-4.3-ac-test-matrix.md
    version: 2
supersedes: null
---

# Implementation Report — US-4.3 (Ticket Resolution)

Aggregates all six `IMPLEMENTATION` builder sub-steps
(`docs/catalog/US-4.3-pipeline-status.md` v2) against `task_breakdown` v1's
T1–T6. `QUALITY_GATE`'s own gate results are in the paired
`docs/evidence/US-4.3-quality-gate-report.md`, not repeated here.

## What was built

**New endpoints** (`app/modules/support/router.py`):
- `POST /api/v1/support/tickets/{id}/resolve` — `response_model=TicketStateRead`, `status_code=200`. FR-1/FR-6/FR-7/FR-9.
- `POST /api/v1/support/tickets/{id}/close` — `response_model=TicketStateRead`, `status_code=200`. FR-2/FR-6/FR-7/FR-9.
- `POST /api/v1/support/tickets/{id}/reopen` — `response_model=TicketStateRead`, `status_code=200`. FR-5/FR-6/FR-7/FR-9.
- Existing `POST .../tickets/{id}/replies` (US-4.2) gains a status side-effect: a customer reply on a `"resolved"` ticket within the 7-day window now transitions it to `"waiting_on_support"` and writes an audited `ticket_reopened` event (FR-4/DR-4).

**Schemas** (`app/modules/support/schemas.py`): `ResolveTicketRequest` (`resolution_note: str`, `min_length=1, max_length=5000`), `CloseTicketRequest`/`ReopenTicketRequest` (each `reason: str | None = None`, accepted but not persisted), `TicketStateRead` (`id`, `ticket_number`, `status`, `resolved_at`, `closed_at`, `updated_at` only — data-minimization). All three inbound schemas `extra="forbid"`.

**Data layer** (`app/modules/support/models.py`, `repository.py`):
- Four additive nullable `Ticket` columns: `resolved_at`, `resolution_note` (`String(5000)`), `closed_at`, `closed_by` (no `ForeignKey`, mirrors `audit_log.actor_id`'s existing no-FK sentinel convention).
- Two `CheckConstraint`s: `ck_tickets_closed_requires_closed_fields` (biconditional), `ck_tickets_resolved_requires_resolution_fields` (one-directional implication — corrected from the story's literal biconditional, which would fail every FR-2/FR-3 closure of an already-resolved ticket).
- Partial index `ix_tickets_resolved_at_pending_autoclose` (`WHERE status = 'resolved'`).
- Module-level `SYSTEM_ACTOR_ID` sentinel (OD-7, the auto-close job's actor).
- `TicketRepository.transition_status(...)` — one conditional `UPDATE ... WHERE id = :id AND status IN (...)` (optionally `AND resolved_at >= now() - interval '7 days'`) serving `/resolve`, `/close`, `/reopen`, and FR-4's reply-driven reopen alike; `.auto_close_resolved_past_window(...)` — batch `UPDATE ... WHERE status = 'resolved' AND resolved_at < now() - interval '7 days' ... RETURNING id`, idempotent. Both build their window predicate from one `_RESOLUTION_WINDOW_DAYS = 7` constant, never a second hardcoded `7`. Existing `update()`/`get_by_id()`/`list_for_requester()` left byte-for-byte unchanged.

**Migration** (`migrations/versions/242e0dba5ba2_add_ticket_resolution_columns.py`): four `add_column`s and two `create_check_constraint`s, each guarded via `sa.inspect(op.get_bind())` (the Rewriter in `migrations/env.py` only reaches `Create/DropTableOp`/`Create/DropIndexOp`); partial index create/drop uses `if_not_exists=True`/`if_exists=True`. Real `downgrade()`. Proven via `upgrade → downgrade → upgrade` by `migration-manager` at T3, re-proven fresh during `QUALITY_GATE` (see quality-gate report §5). `migrations/env.py` confirmed zero-diff.

**Service layer** (`app/modules/support/service.py`, `exceptions.py`, `app/core/email.py`): `TicketService.resolve_ticket`/`close_ticket`/`reopen_ticket`, each following the check order lookup/ownership → transition validity (409) → permission (403) → conditional `UPDATE` (409 on race loss) → audit write → best-effort email (`resolve_ticket` only). New `_ALLOWED_EVENTS_BY_STATUS` table (one explicit status-keyed transition table, satisfying FR-6's single-source-of-truth NFR). New `InvalidStateTransitionError` (409, `type_slug="invalid-state-transition"`, carries `allowed_events: list[str]`). `TicketReplyService` gained a required `audit_service: AuditServiceProtocol` constructor parameter; its `create_reply` FR-4 branch splits into the ordinary `"waiting_on_customer"` case (unchanged `update()`) and the `"resolved"`-reopening case (`transition_status(..., require_resolved_within_window=True)` + `ticket_reopened` audit write) — applying the window guard to the ordinary case would silently break FR-2 since `NULL >= x` is never true in SQL. `EmailSender` Protocol/`LoggingEmailSender` gained `send_ticket_resolved_email` (a plan gap `implementation_plan.md`'s Files To Modify table never listed, matching US-4.1's `get_email_for_user` precedent).

**Router/dependencies** (`app/modules/support/router.py`, `dependencies.py`): three new routes, no `require_scope("tickets:write")` dependency on `/resolve` — permission is checked inside the service after the 409 transition check, preserving FR-6/FR-7's required "state before actor" order, matching `create_ticket_reply`'s existing precedent. `get_ticket_reply_service` gains `audit_service: AuditLogServiceDep`; `get_ticket_service` unchanged (already has every collaborator the three new methods need).

**`app/main.py`** (one file outside `service-and-router-builder`'s normal four-file scope, flagged not silent): `problem_error_handler` gained a generic `getattr(exc, "allowed_events", None)` addition so FR-6's `allowed_events` field actually reaches the HTTP response body — a plan gap nobody flagged upstream, fixed as a duck-typed extension of the existing `errors`-rendering pattern rather than adding a field to the shared `ProblemError` base class.

**Script** (`scripts/auto_close_resolved_tickets.py`, new, T6, FR-3): follows `purge_unbound_attachments.py`'s shape (`main() -> int`); the first script in this codebase needing both a Postgres engine and a Valkey client (`RoleService.get_role_grants_for_user`'s actor_role resolution via `PermissionEpochCache`). Calls `TicketRepository.auto_close_resolved_past_window`, writes one `ticket_auto_closed` audit event per closed id (`actor_id=SYSTEM_ACTOR_ID`), one `commit()` for the whole run.

**Test fallout** (four files, mechanical): `tests/unit/modules/{profile,email_verification,admin_users,users}/test_*_service.py` each needed a matching `send_ticket_resolved_email` stub — `EmailSender` Protocol-extension ripple, same class US-4.2's own pipeline status recorded; no test logic or assertion changed in any of the four.

## Task Breakdown status (task_breakdown v1)

| Task | Skill | Status | Notes |
|---|---|---|---|
| T1 | schema-builder | PASS | `ruff`/`mypy --strict` clean; schemas match `US-4.3-openapi.yaml` v2 exactly. |
| T2 | data-layer-builder | PASS | `ruff`/`mypy --strict` clean; zero new `session.query()`. |
| T3 | migration-manager | PASS | Real `upgrade → downgrade → upgrade` cycle proven; both `CHECK`s and the partial index confirmed to render verbatim via `pg_constraint`/`pg_indexes`. |
| T4 | service-and-router-builder (service) | PASS | One own-code bug found and fixed during verification: `func.make_interval` needed positional args, not kwargs (SQLAlchemy's generic `func.<name>()` does not accept named SQL arguments). |
| T5 | service-and-router-builder (router) | PASS | `grep` self-check: zero `sqlalchemy|AsyncSession|models|repository` matches in `router.py`; zero `fastapi|starlette|HTTPException` matches in `service.py`. |
| T6 | service-and-router-builder (script form) | PASS | `mypy scripts/auto_close_resolved_tickets.py --strict` clean on its own, matching this repo's existing separate-invocation convention for `scripts/`. |
| T7 | gate-enforcer | PASS | See `docs/evidence/US-4.3-quality-gate-report.md`. |

One test-file-only defect (two non-deterministic exact-7-day-boundary tests) was found and fixed via the `changes_required_tests` loop-back to `TEST_WRITING` (v1 → v2, attempt 2) — full detail in `workflow-state.yaml`'s `IMPLEMENTATION`/`TEST_WRITING` re-entry notes and `docs/catalog/US-4.3-pipeline-status.md`. No application code under `app/` or `scripts/` was changed by that fix; T1–T6 needed no re-invocation on re-entry.

## Final verification snapshot (captured fresh at QUALITY_GATE)

- 774/774 tests passed (full repository suite); 96.29% combined coverage (`support/service.py` 94%, `support/router.py` 100%).
- `pre-commit run --all-files`, `mypy app tests`, `lint-imports` (6/6 contracts kept) all clean.
- Migration `upgrade → downgrade → upgrade` re-proven.
- OpenAPI renders successfully in-process.

Full command output: `docs/evidence/US-4.3-quality-gate-report.md`.

## Carried-forward, non-blocking items (not resolved by this stage)

- DR-5/DR-6/DR-7/DR-8 (`docs/reviews/designs/US-4.3-design-review.md`) and API_DESIGN Open Questions #1/#2 — all Minor/advisory, restated against concrete files by `IMPACT_ANALYSIS`/`ARCHITECTURE_PLANNING`, not addressed by any IMPLEMENTATION sub-step.
- `TicketReplyService`'s FR-4 branch split is `test-writer`'s own collaborator-shape assumption, not a literal single-branch instruction from `implementation_plan.md` — flagged for `reconciliation-reviewer`.
- `app/main.py`'s `allowed_events` rendering fix is a genuine plan gap this pass discovered, absent from any upstream design/plan artifact's Files To Modify table — flagged for `reconciliation-reviewer`.
