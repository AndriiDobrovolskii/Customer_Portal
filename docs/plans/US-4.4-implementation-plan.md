---
artifact_type: implementation_plan
story: US-4.4
version: 1
status: APPROVED
created_at: "2026-09-08T00:30:00Z"
updated_at: "2026-09-07T15:54:29Z"
produced_by: planner
inputs:
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.4-spec-review.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-db-design.md
    version: 1
  - path: docs/designs/database/US-4.4-entity-model.md
    version: 1
  - path: docs/reviews/designs/US-4.4-design-review.md
    version: 1
  - path: docs/impact-analysis/US-4.4-impact-analysis.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# Implementation Plan: Agent Ticket Queue & Assignment (US-4.4)

**Track:** backend. Built on `impact-analyzer`'s blast-radius survey
(`docs/impact-analysis/US-4.4-impact-analysis.md`, v1) rather than re-deriving
it. Execution order and which execution skill runs each task are
`implementation-planner`'s job, not this plan's.

## Goal

Turn the already-granted-but-rejecting `tickets:read` scope into a working
agent queue on the existing `GET /v1/support/tickets`, add `assign`/`unassign`
ownership endpoints under `tickets:write`, and add the `assignee_id` column
US-4.1/4.2/4.3 deferred — all without widening what a customer caller can see
or touching the US-4.3 resolve/close/reopen state machine, per FR-1..FR-10 of
`docs/specifications/US-4.4-spec.md` (v1, APPROVED).

## Architectural Changes

1. **Single route, two response shapes.** `GET /v1/support/tickets` keeps its
   `operationId`/path/method; the router branches on `tickets:read` presence
   in `current_user.scopes` (no ticket lookup needed to pick the branch). The
   agent branch calls a new service method returning `AgentTicketListResponse`
   (items carry `assignee_id`); the customer branch is untouched (FR-5/FR-6).
   `response_model=TicketListResponse | AgentTicketListResponse` — the first
   `Union`-typed `response_model` in this router; the handler must return a
   concretely-typed instance of one member, with an explicit
   `-> TicketListResponse | AgentTicketListResponse` annotation (mypy strict
   forbids `Any`).

2. **`AgentTicketRead` / `AgentTicketListResponse` / `AgentTicketStateRead` /
   `AssignTicketRequest` as new, distinct schemas** (OD-1's adopted
   resolution). `TicketRead` / `TicketListResponse` / `TicketStateRead` are
   **not** modified — this is what keeps `/close`/`/reopen`'s
   already-shipped, customer-reachable contract byte-identical while still
   satisfying the "(agent shape)" API Contract wording.

3. **Two new endpoints**, `POST` and `DELETE /v1/support/tickets/{id}/assign`,
   sharing one permission gate (`tickets:write` required, `404` for a
   customer / `403 insufficient-permission` for a `tickets:read`-only agent —
   FR-7) evaluated **before** any ticket lookup, a deliberately different
   check order from every existing `resolve`/`close`/`reopen` transition
   method in `service.py` (which check ticket lookup/ownership before
   permission) — because the permission gate here needs no DB row at all.

4. **New cross-module collaborator: `RoleServiceProtocol` in
   `support/service.py`.** FR-8's "does the named `assignee_id` hold
   `tickets:write`" check calls
   `app.modules.roles.service.RoleService.resolve_scopes_for_user(user_id:
   uuid.UUID) -> list[str]` (confirmed present, `app/modules/roles/service.py:94`).
   `support` has no live import into `roles` today (only prose references in
   comments) — this is the first one. It must be:
   - a new `Protocol` in `support/service.py` (mirroring the existing
     `AuditServiceProtocol`/`UserServiceProtocol` shape — never a direct
     `from app.modules.roles.service import RoleService` in `service.py`
     itself, which would violate nothing in `lint-imports` today but would
     defeat the Protocol-based DI convention every other cross-module
     collaborator in this file already follows);
   - wired at `support/dependencies.py` from the already-exported
     `app.modules.roles.dependencies.RoleServiceDep`
     (`app/modules/roles/dependencies.py:27`), the same pattern
     `support/dependencies.py` already uses for
     `app.modules.audit.dependencies`/`app.modules.users.dependencies`.
   - Confirmed by `impact-analyzer` against `pyproject.toml`'s
     `[tool.importlinter]`: Contract 1's per-module layering is wildcarded
     (`containers = ["app.modules.*"]`) and does not restrict which *other*
     module a given module's `dependencies.py` imports; no contract change
     is required.

5. **New repository method + its own cursor/`WHERE`-building routine
   (DR-5, confirmed scoped task).**
   `TicketRepository.list_for_requester` (`app/modules/support/repository.py:60-91`)
   is `(created_at, id)`-descending, single-filter (`requester_id`
   equality) — it **cannot** be extended in place to serve FR-1/FR-2's
   `(updated_at, id)`-ascending (oldest-first), multi-filter (`status`,
   `category`, `assignee_id` incl. `me`/`none`) agent query without changing
   its sort column and filter contract for the *existing* customer-branch
   caller. This is a **new method** (e.g. `list_for_agent_queue`), not a
   parameter added to `list_for_requester`. It may reuse the existing
   generic `_encode_cursor`/`_decode_cursor` helpers (`repository.py:23-34`,
   already `(datetime, uuid.UUID)`-shaped) verbatim for encoding, but needs
   its **own** decode-to-`WHERE` translation: `list_for_requester`'s
   comparison is `Ticket.created_at < cursor_created_at` (strictly
   descending); the agent branch's default ordering is ascending
   (`Ticket.updated_at > cursor_updated_at`, mirroring
   `TicketReplyRepository.list_for_ticket`'s existing ascending-order
   pattern, `repository.py:294-329`, rather than `list_for_requester`'s
   descending one) plus the three new filter predicates. This is its own
   file/method-level task, not an extension task.

6. **New repository write methods for assign/unassign**, not a new parameter
   on `transition_status` (no `status` value is written by either
   operation):
   - `assign_ticket` (name illustrative): conditional
     `UPDATE tickets SET assignee_id = :new WHERE id = :id AND status !=
     'closed' AND assignee_id IS NOT DISTINCT FROM :expected RETURNING *`
     (FR-3/FR-10) — `IS NOT DISTINCT FROM`, not `=`, so the first-assignment
     case (`:expected IS NULL`) is a correct match, matching the exact
     `.returning()` / zero-rows-affected idiom `transition_status` already
     uses (`repository.py:117-162`).
   - `unassign_ticket`: unconditional
     `UPDATE tickets SET assignee_id = NULL WHERE id = :id AND status !=
     'closed' RETURNING *` (FR-4, OD-3's adopted default) — no optimistic
     lock, since unassign's postcondition doesn't depend on the prior value.
   - **Both statements' `.values()` must explicitly include
     `updated_at=Ticket.updated_at`** — see Architectural Change #8 (DR-3)
     below; this is not optional and is called out separately because it is
     easy to omit silently.

7. **New `AssignmentConflictError`** (409, `type_slug=assignment-conflict`,
   first use in this project) for FR-10's lost-race case, distinct from
   `InvalidStateTransitionError` (409, `invalid-state-transition`, reused
   verbatim with `allowed_events=[]`) which continues to cover the
   closed-ticket case for both `assign` (FR-9) and `unassign` (FR-4/OD-3's
   default) — the two `409`s are different failure classes (status-machine
   violation vs. field-level optimistic-concurrency conflict) and keep
   different slugs, per the API design's explicit reasoning.

8. **`reject_agent_queue_access` and `AgentQueueNotAvailableError` are
   removed** (In Scope). `resolve_actor_kind` (`dependencies.py:67-74`),
   which internally reuses the identical scope check, is unaffected and
   stays. The one existing test asserting the retired `403`
   (`tests/integration/modules/support/test_support_router.py::
   test_list_own_tickets_agent_scope_caller_returns_403`, confirmed the sole
   such test) is **updated, not deleted**, per the spec's own NFR.

9. **DR-3 — architectural call on the `updated_at` queue-reset side effect
   (resolved here, not deferred further).** `Ticket.updated_at` carries
   `onupdate=func.now()` (`models.py:85-87`); any Core-style
   `update(Ticket).where(...).values(...)` that omits `updated_at` from its
   `.values()` lets that column default fire, bumping `updated_at` on every
   assign/unassign. Two options were on the table (per this stage's own
   brief):
   - **(a) Accept as-is.** Document that an assign/unassign cycle resets a
     ticket's position in the "longest-waiting" queue.
   - **(b) Design around it.**

   **Decision: (b).** Accepting (a) would let an agent (or two agents in
   collusion, or a single agent gaming their own queue view) clear a ticket
   from the top of the "longest-waiting-first" default view by assigning and
   immediately unassigning it — with **zero** actual work performed on the
   ticket. That directly defeats FR-1/Assumption #8's stated purpose ("the
   longest-waiting ticket surfaces first" — the entire reason the queue
   exists is to prevent exactly this kind of accidental or deliberate
   starvation) and contradicts Out of Scope's own claim that "assignment is
   orthogonal to the state machine": an ownership change silently becoming a
   *de facto* priority-reset mechanism is not orthogonal to anything, it is
   the single most consequential thing that could happen to a ticket's
   visibility. Preserving `updated_at` across assign/unassign is the
   reading that is actually consistent with the spec's own stated intent,
   not a deviation from it.

   **Chosen mechanism — no schema change, no new column.** SQLAlchemy's
   `onupdate=` column default only fires for a column *not* explicitly named
   in a Core `update().values()` call. The new `assign_ticket`/
   `unassign_ticket` repository methods (Architectural Change #6) must
   include `updated_at=Ticket.updated_at` explicitly in their `.values()` —
   a self-referential `SET updated_at = tickets.updated_at`, evaluated
   server-side against the current row (no stale-read race, no interaction
   with the `assignee_id IS NOT DISTINCT FROM :expected` concurrency guard
   already scoping the same statement) — which overrides the column default
   and leaves the value byte-for-byte unchanged. This is a `repository.py`-
   level fix only: no `models.py`/migration/index change (matching how
   `db-design.md` already reasoned that OD-3's schema impact is nil — this
   is the same class of "service/repository-layer-only" fix). No loop-back
   to `SPECIFICATION` is taken (`changes_required_specification` is
   available but not used): this decision keeps FR-1's literal text and its
   own stated rationale intact rather than contradicting it, so it does not
   need spec text to change to be correct — it makes concrete what the spec
   left unstated. This also resolves the design review's own concern
   ("`test-writer` cannot write a determinate test... without an answer") —
   the answer is now determinate: **assign/unassign never change
   `updated_at`**, and this must be its own explicit test case (see Testing
   Strategy).

   If a future story genuinely wants a separate "last agent activity"
   timestamp distinct from "last customer-visible content change," that is
   a new column and a new decision for that story — not built here, not
   needed to satisfy any FR in this one.

   **This supersedes `db-design.md`'s stated consequence, deliberately.**
   `db-design.md`'s "`updated_at`'s write semantics" paragraph and
   `entity-model.md`'s matching line both record, as design fact, that
   assign/unassign *will* bump `updated_at` and that "this design does not
   add a mechanism to suppress it." That was the correct call for `DB_
   DESIGN` to make at the time — inventing a suppression mechanism with no
   FR asking for one would have been scope creep at that stage, which is
   exactly why `design-reviewer` routed the open question to
   `ARCHITECTURE_PLANNING` instead of treating it as a design defect. This
   plan now makes that call, and neither DB artifact needs a revision to
   accommodate it: no column, index, or constraint in `db-design.md`/
   `entity-model.md` changes either way — the entire difference is the
   `.values()` clause of two new repository methods neither artifact names
   at the SQL-statement level. This is the identical containment argument
   `db-design.md` already used for OD-3 ("does not change this column's
   schema either way ... the entire difference is in the service's
   conditional `UPDATE`'s `WHERE` predicate"), applied to one more
   statement-level detail. `IMPLEMENTATION` must build the repository
   methods per this plan, not per `db-design.md`'s literal "no suppression"
   sentence.

   **A second, independent reason for (b):** the agent branch's keyset
   cursor is `(updated_at, id)`-encoded (Architectural Change #5). Under
   option (a), an assign/unassign landing on a ticket mid-pagination would
   move that ticket's sort key while a caller is paging through the list,
   letting it be skipped or re-served across a page boundary — the same
   class of bug cursor pagination exists to prevent. Option (b) keeps the
   cursor's ordering key stable under the one write this story introduces
   that isn't already excluded from the default view (a closed ticket both
   drops out of the default queue and can no longer be assigned/unassigned
   in the first place).

10. **Query literalism required for `ix_tickets_queue_default_updated_at_id`
    (carried from DR-1, confirmed by design-reviewer).** The new
    `list_for_agent_queue`'s default (filterless) `WHERE` clause must be
    written as the literal `Ticket.status != "closed"` — never an
    `Ticket.status.in_([...four values...])` — or PostgreSQL's partial-index
    predicate-implication check will not select the new partial index and
    the Enforcement Matrix's `[gate]` `EXPLAIN` assertion fails. This is an
    invisible-until-tested implementation detail; call it out explicitly in
    the task for whichever skill writes `repository.py`.

## Files To Create

No new module files — every change is additive within
`app/modules/support/` (existing files, layer-by-layer below) and
`app/modules/roles`/`app/modules/audit`/`app/modules/users` need no new
files (their existing collaborators are reused, not extended).

- **One new Alembic migration** under `migrations/versions/` (autogenerated
  filename, `migration-manager`'s task) chaining from the current head
  `242e0dba5ba2` (`add_ticket_resolution_columns`, confirmed by
  `impact-analyzer` to be the only head) — additive only: one nullable FK
  column, three indexes; no expand→migrate→contract cycle required per
  `AGENTS.md` §4.

## Files To Modify

By `AGENTS.md` §3 layer, per `impact-analyzer`'s survey:

- **`app/modules/support/models.py`** — `Ticket.assignee_id: Mapped[uuid.UUID
  | None] = mapped_column(ForeignKey("users.id"), nullable=True)`, no
  `ondelete` override (`RESTRICT`-by-default, same placeholder pattern as
  `requester_id`). `Ticket.__table_args__` (currently lines 37-67) grows
  three `Index(...)` entries: `ix_tickets_queue_default_updated_at_id`
  (partial, `(updated_at, id)`, `WHERE status != 'closed'` — the
  db-designer's own DR-1 addition beyond the story's literal two named
  indexes), `ix_tickets_status_updated_at_id` (`(status, updated_at, id)`),
  `ix_tickets_assignee_id_updated_at_id` (`(assignee_id, updated_at, id)`).
  No `CHECK` constraint added (a closed ticket legitimately retains its last
  `assignee_id`).

- **`app/modules/support/schemas.py`** — add `AgentTicketRead` (every
  `TicketRead` field, lines 24-40, plus `assignee_id`),
  `AgentTicketListResponse` (parallel to `TicketListResponse`, lines 43-45),
  `AgentTicketStateRead` (every `TicketStateRead` field, lines 142-156, plus
  `assignee_id`), `AssignTicketRequest` (`{assignee_id: uuid.UUID}`,
  `extra="forbid"`). `TicketRead`/`TicketListResponse`/`TicketStateRead`
  are **not** touched.

- **`app/modules/support/repository.py`** — new
  `list_for_agent_queue(...)` method + its own ascending, multi-filter
  `WHERE`-building routine and cursor decode comparison (Architectural
  Change #5); new `assign_ticket(...)` conditional-update method and
  `unassign_ticket(...)` unconditional-clear method, both with the explicit
  `updated_at=Ticket.updated_at` override (Architectural Change #6/#9).

- **`app/modules/support/service.py`** —
  - `TicketRepositoryProtocol` (lines 61-94) grows the three new method
    signatures.
  - New `RoleServiceProtocol` (new; FR-8's target-validation collaborator).
  - New `TicketService` method for the agent queue listing (parallel to
    `list_own_tickets`, lines 361-391): `assignee_id=me`/`=none` resolution,
    filter pass-through, `AgentTicketListResponse` construction.
  - New `TicketService.assign_ticket(...)`: permission gate first (no
    lookup) → ticket lookup (`404`) → closed-ticket check (`409`, FR-9) →
    target-validation via `RoleServiceProtocol.resolve_scopes_for_user`
    (`422` if `tickets:write` absent, FR-8) and, per OD-4's adopted default,
    via the already-held `UserServiceProtocol.get_account_status_for_user`
    (`service.py:155-165`, already used by `create_ticket` for the caller's
    own account — reused here against the *target* id) → conditional update
    (`409 assignment-conflict` on race loss, FR-10) → `AuditServiceProtocol
    .record_event(event="ticket_assigned", ...)` (existing generic path,
    no signature change) → one commit.
  - New `TicketService.unassign_ticket(...)`: permission gate → lookup
    (`404`) → closed-ticket check (`409`, OD-3's adopted default) →
    unconditional clear → `record_event(event="ticket_unassigned", ...)` →
    one commit. The idempotent-no-op-audit question (API design Open
    Questions #5) is an implementation-time branch decision within this
    method, not fixed further by this plan — carried forward, non-blocking.

- **`app/modules/support/router.py`** —
  - `list_own_tickets` (lines 58-80): drop
    `dependencies=[Depends(reject_agent_queue_access)]`; branch on
    `tickets:read` presence to call the existing customer-branch service
    method or the new agent-branch one; add `category`, `assignee_id` query
    params; change `response_model`/return annotation to
    `TicketListResponse | AgentTicketListResponse`.
  - New route `POST /{id}/assign` → `AgentTicketStateRead`.
  - New route `DELETE /{id}/assign` → `AgentTicketStateRead`.

- **`app/modules/support/dependencies.py`** — remove
  `reject_agent_queue_access` (lines 53-65) and its
  `AgentQueueNotAvailableError` import; add `RoleServiceDep` wiring
  (`app.modules.roles.dependencies.RoleServiceDep`) into whichever
  factory(ies) construct the service(s) owning `assign_ticket`/
  `unassign_ticket`. Whether the 404-vs-403 permission check becomes a
  reusable `Depends`-based dependency (mirroring
  `reject_agent_queue_access`'s old if/elif shape) or stays inlined in the
  service is left open by the API design (its own Open Questions #1) and is
  not decided by this plan — a genuine `task_breakdown`-level choice for
  `implementation-planner`, not an architectural one this plan needs to
  fix.

- **`app/modules/support/exceptions.py`** — remove
  `AgentQueueNotAvailableError` (lines 72-81); add `AssignmentConflictError`
  (409, `assignment-conflict`, FR-10). No new class for the closed-ticket
  case (`InvalidStateTransitionError` reused with `allowed_events=[]`), the
  permission case (`InsufficientPermissionError`/`TicketNotFoundError`
  reused verbatim), or the target-validation case
  (`ValidationFailedError` reused).

- **`app/modules/support/cache.py`** — **no change**, confirmed by
  `impact-analyzer`: neither `assign` nor `unassign` declares an
  `Idempotency-Key` header or a dedicated rate limit.

- **Not modified, confirmed no impact:** `scripts/auto_close_resolved_
  tickets.py` (never references `assignee_id`); `app/modules/support/
  repository.py`'s existing `list_for_requester`, `update`,
  `transition_status`, `auto_close_resolved_past_window` (no column they
  touch changes).

No protected file (`pyproject.toml`, `migrations/env.py`,
`.pre-commit-config.yaml`) needs any change — flagged per the Planning Rules
even though the answer is "none required," since the migration and
import-linter implications were explicitly checked (`impact-analyzer`
confirmed Contract 1 is unaffected).

## Risks

1. **New `Union` `response_model` on `GET /v1/support/tickets`.** First use
   of this pattern in this router. Risk: an implementer picks a technique
   (e.g. `response_model_exclude_unset`, a custom serializer) that
   accidentally lets a customer-branch response validate against
   `AgentTicketListResponse` and leak `assignee_id` if the wrong instance
   type is returned. Mitigation: the service method for each branch must
   return the concrete Pydantic type for that branch (never a shared dict),
   and the FR-5/AQ-AC5 integration test must assert byte-identical output
   to the existing US-4.1 customer-branch test, not merely "no `assignee_id`
   key."
2. **Cross-module `RoleService` coupling is new for `support`.** Risk: a
   future implementer imports `roles.service.RoleService` directly into
   `support/service.py` instead of going through a `Protocol`, which would
   still pass `lint-imports`' wildcarded Contract 1 today but breaks this
   module's own DI convention (every other cross-module read here —
   `AuditServiceProtocol`, `UserServiceProtocol` — is Protocol-typed).
   Mitigation: name this explicitly as its own task in `task_breakdown` so
   it isn't done ad hoc inline.
3. **`IS NOT DISTINCT FROM` correctness (FR-10).** Using `=` instead of `IS
   NOT DISTINCT FROM` for the first-assignment case (`expected` is `NULL`)
   would make the conditional update never match a currently-unassigned
   ticket (`NULL = NULL` is `NULL`, not `true`, in SQL), silently breaking
   every first assignment as a `409`. This is easy to get wrong and would
   only surface as a functional test failure, not a type error — flag for
   explicit code review at build time.
4. **Partial-index predicate literalism (DR-1/Architectural Change #10).**
   Writing the default queue filter as `status.in_([...])` instead of the
   literal `!= "closed"` silently degrades to a sequential scan; only the
   Enforcement Matrix's `EXPLAIN` `[gate]` (or a migration/query review)
   catches this — no functional test fails.
5. **DR-3 fix must be applied to *both* new write methods identically, and
   proven at the integration layer.** If `assign_ticket` preserves
   `updated_at` but `unassign_ticket` doesn't (or vice versa), the queue
   exhibits an inconsistent, hard-to-diagnose half-fixed behavior worse
   than either pure option. A unit test against a hand-written fake cannot
   catch this (no fake reproduces SQLAlchemy's `onupdate` mechanics); the
   integration test seeding an explicit past `updated_at` and asserting it
   survives both operations (Testing Strategy) is the only real proof —
   plan this as an integration task explicitly, not a unit one.
6. **Migration Rewriter guard-injection caveat repeats.** Two partial
   indexes now exist on `tickets` (`ix_tickets_resolved_at_pending_
   autoclose` from US-4.3, `ix_tickets_queue_default_updated_at_id` new
   here); `migration-manager` must confirm the generated migration file
   actually carries the guard for both, not assume the existing precedent
   generalizes untested.
7. **Contract change for `tickets:read`/`tickets:write` callers on `GET
   /v1/support/tickets`.** Removing `reject_agent_queue_access` changes an
   already-shipped response (`403` → `200` with real data) for exactly the
   caller kind that previously got rejected. This is intentional (In
   Scope/NFR) but is a genuine, not merely additive, contract change for
   that caller kind — the one existing test asserting the old `403` must be
   updated, and any other consumer relying on that `403` (none found in
   this codebase, per `impact-analyzer`) would break silently outside test
   coverage.
8. **OD-3/OD-4 remain unconfirmed at `HUMAN_SPEC_APPROVAL`.** Building
   against their drafting defaults (unassign-on-closed → `409`; deactivated
   assign-target → `422`) risks rework if a human later reverses either.
   Per `db-design.md`'s own analysis (confirmed by `design-reviewer` and
   `impact-analyzer`), reversing either changes **only** a
   `service.py`/`repository.py` conditional-`WHERE`/branch, never a schema
   element — bounded, low-cost rework either way. **Must be confirmed
   before `IMPLEMENTATION` begins**, consistent with the spec's own stated
   gate; not a blocker for this plan.
9. **OD-1's adopted schema-split is the largest single point of rework
   risk if reversed**, per the API design's own assessment (carried
   forward, not re-litigated here) — if `HUMAN_SPEC_APPROVAL` reverses it,
   the `GET` endpoint's `anyOf`/`Union` response collapses to one schema and
   Architectural Changes #1/#2 above would need to be redone. Not expected,
   flagged for completeness.

## Validation Strategy

- `pre-commit run --all-files` (Ruff format+lint, mypy `strict`,
  `lint-imports`, secret scan) must stay green with zero added `# noqa`/
  `# type: ignore`.
- **mypy strict**, specifically: the router's `list_own_tickets` needs an
  explicit `-> TicketListResponse | AgentTicketListResponse` return
  annotation (no `Any`); the new `RoleServiceProtocol`/repository method
  signatures need full annotations including `-> None`/`-> Ticket | None`
  as appropriate, matching this file's existing style.
- **`lint-imports`**: confirm zero broken contracts after adding
  `app.modules.roles.dependencies` to `support/dependencies.py` — already
  checked by `impact-analyzer` against `pyproject.toml`'s `[tool.
  importlinter]` Contract 1 (wildcarded per-module, unaffected) and
  Contract 4 (services import no raw infrastructure — `RoleServiceProtocol`
  is a `Protocol`, not a direct import into `service.py`); re-run the gate
  to prove it, don't just cite the prior analysis.
- **Migration**: `alembic revision --autogenerate`, read the generated file
  before trusting it, confirm the `Rewriter`-injected `if_not_exists`/
  `if_exists` guards on both partial indexes, then
  `upgrade → downgrade → upgrade`.
- **OpenAPI renders** (`AGENTS.md` §6 item 7) — no checked-in test exists
  for this in the codebase (confirmed by `impact-analyzer`); verify by
  running the app at `QUALITY_GATE`, out of this plan's file-level scope.

## Testing Strategy

Per `AGENTS.md` §5's unit/integration split; test files per
`impact-analyzer`'s survey (one-file-per-module convention — no new test
files, only new cases in existing ones):

**Unit — `tests/unit/modules/support/test_support_service.py`**
- `FakeTicketRepository` (line 97) gains the three new
  `TicketRepositoryProtocol` methods.
- New `FakeRoleService` (first cross-module fake into `roles` this file
  needs) exercising `resolve_scopes_for_user`.
- `FakeUserService` (line 339) already exposes
  `get_account_status_for_user`; confirm its fake API supports an arbitrary
  target id (not only the caller's own) before reusing it for OD-4.
- Agent-queue listing: filters (`status`, `category`, `assignee_id`
  including `me`/`none`), ordering, cursor pagination (FR-1/FR-2).
- `assign_ticket`: full check order including 404-before-403 (FR-7),
  closed-ticket 409 (FR-9), target-validation 422 including the OD-4
  deactivated-account variant (FR-8), concurrency-loss 409 (FR-10).
- `unassign_ticket`: success, idempotent no-op, closed-ticket 409 (OD-3's
  adopted default).
- A unit-level case may assert the service passes through to whichever
  repository method unchanged, for branch coverage, but **the load-bearing
  DR-3 assertion belongs in integration, not here** — see below. A
  hand-written `FakeTicketRepository` has no SQLAlchemy column defaults, so
  whether the real statement emits `SET updated_at = now()` or
  `SET updated_at = tickets.updated_at` is invisible to a fake; a unit test
  passes identically whether the DR-3 fix is present or omitted.

**Integration — `tests/integration/modules/support/test_support_router.py`**
- Update (not delete) `test_list_own_tickets_agent_scope_caller_returns_403`
  to assert the new agent-branch `200` behavior (NFR).
- Regression: the existing customer-branch tests (newest-first ordering,
  malformed-cursor 422, the four `401` tests) must still pass unmodified
  once the router changes land — real PostgreSQL, no `unittest.mock`.
- New: `GET /v1/support/tickets` agent branch — `200`, filters, cursor
  pagination, `assignee_id` field presence (AQ-AC1/AQ-AC2); customer branch
  with agent-only query params present, asserting they're silently ignored
  (AQ-AC6).
- New: `POST`/`DELETE /{id}/assign` full HTTP paths — success,
  audit-row-in-same-transaction assertion, 404/403 split, 422, 409
  (AQ-AC3/AQ-AC4/AQ-AC7/AQ-AC8/AQ-AC9).
- New: a genuine two-simultaneous-request concurrency test for AQ-AC10 — no
  existing test in this file exercises true request concurrency; this is a
  new test *pattern*, not only new cases.
- **New, DR-3-driven, load-bearing case — integration, not unit:** seed a
  ticket with an **explicit, distinct past** `updated_at` (per `AGENTS.md`
  §5's frozen-`func.now()` rule: an integration test runs in one
  transaction, so a ticket seeded via `server_default=func.now()` and then
  assigned in the *same* transaction would see `onupdate=func.now()`
  resolve to the identical frozen value — a naive version of this test
  passes whether or not the DR-3 fix is actually applied, proving nothing).
  Assert that exact seeded `updated_at` value is still present, unchanged,
  after a successful `assign` and, in a second case, after a successful
  `unassign` — this is the concrete, determinate proof the design review
  flagged as impossible to write without a decision (see Architectural
  Change #9); it is now possible and required, and it must run against the
  real repository UPDATE, not a fake.
- New: `EXPLAIN`-based (or migration-review) assertion that
  `ix_tickets_queue_default_updated_at_id` is actually selected under the
  literal `status != 'closed'` predicate (Enforcement Matrix `[gate]` if
  enforceable, `[manual]` otherwise).
- Migration `upgrade → downgrade → upgrade` proof (`migration-manager`,
  not a checked-in test).

Coverage floor: 85% overall, 90%+ for `service.py`/`router.py`
(`AGENTS.md` §5) — not a target, a floor; no exclude added to reach it.

## Carried-Forward, Non-Blocking Items For Later Stages

- **OD-3 / OD-4** (unassign-on-closed 409; deactivated-target 422): both
  are the spec's own drafting defaults, already adopted into this plan's
  service-layer design (see Files To Modify → `service.py`). **Must be
  confirmed before `IMPLEMENTATION` begins**, per the spec's own stated
  gate — not re-opened or blocked here; if reversed, rework is bounded to
  `service.py`/`repository.py` per `db-design.md`'s own analysis (Risk 8).
- **DR-4** (project-wide `oneOf`-without-discriminator on Problem schemas):
  explicitly not specific to this story; no action here.
- **API design's own Open Questions #1 (second half)**: whether the
  404-vs-403 permission gate becomes a reusable dependency or stays inlined
  in the service is a `task_breakdown`-level implementation choice, left to
  `implementation-planner`.
- **API design's own Open Questions #5** (idempotent-no-op `unassign` audit
  write): an implementation-time branch inside `unassign_ticket`, not fixed
  further here.
