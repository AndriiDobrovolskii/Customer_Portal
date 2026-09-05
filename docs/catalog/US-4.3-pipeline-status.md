---
artifact_type: pipeline_status
story: US-4.3
version: 2
status: APPROVED
created_at: "2026-09-07T02:00:00Z"
updated_at: "2026-09-07T04:00:00Z"
produced_by: story-orchestrator
inputs:
  - path: docs/plans/US-4.3-task-breakdown.md
    version: 1
  - path: docs/tests/US-4.3-test-strategy.md
    version: 2
  - path: docs/tests/US-4.3-ac-test-matrix.md
    version: 2
supersedes: docs/catalog/US-4.3-pipeline-status.md (v1)
---

# IMPLEMENTATION Pipeline Status — US-4.3 (Ticket Resolution)

Tracks the four `IMPLEMENTATION` sub-steps (`docs/workflow/stage-map.yaml`,
`docs/plans/US-4.3-task-breakdown.md`), run in the order the task breakdown
fixes: T1/T2 parallel-eligible, T3 after T2, T4 after T1+T3, T5 after T4, T6
(script form) after T2+T3, T7 (gate-enforcer, `QUALITY_GATE` — not part of
this composite skill).

| Task | Skill | Verdict | Artifacts |
|---|---|---|---|
| T1 | schema-builder | **PASS** | `app/modules/support/schemas.py` (`ResolveTicketRequest`, `CloseTicketRequest`, `ReopenTicketRequest`, `TicketStateRead`) |
| T2 | data-layer-builder | **PASS** | `app/modules/support/models.py` (`Ticket.resolved_at/resolution_note/closed_at/closed_by`, two `CheckConstraint`s, `ix_tickets_resolved_at_pending_autoclose`, `SYSTEM_ACTOR_ID`), `app/modules/support/repository.py` (`TicketRepository.transition_status`, `.auto_close_resolved_past_window`, `_RESOLUTION_WINDOW_DAYS`) |
| T3 | migration-manager | **PASS** | `migrations/versions/242e0dba5ba2_add_ticket_resolution_columns.py` |
| T4 | service-and-router-builder (service) | **PASS** | `app/modules/support/service.py` (`TicketService.resolve_ticket/close_ticket/reopen_ticket`, `_ALLOWED_EVENTS_BY_STATUS`, `TicketReplyService` audit wiring), `app/modules/support/exceptions.py` (`InvalidStateTransitionError`), `app/core/email.py` (`send_ticket_resolved_email`) |
| T5 | service-and-router-builder (router) | **PASS** | `app/modules/support/router.py` (three new routes), `app/modules/support/dependencies.py` (`get_ticket_reply_service` gains `audit_service`) |
| T6 | service-and-router-builder (script form) | **PASS** | `scripts/auto_close_resolved_tickets.py` (new) |
| T7 | gate-enforcer (`QUALITY_GATE`, not part of this composite skill) | not started | — |

**All six code sub-steps are complete and independently verified, and the
composite `IMPLEMENTATION` stage now advances (v2).** v1 routed
`IMPLEMENTATION -> TEST_WRITING` via `changes_required_tests` over two
pre-existing, TEST_WRITING-owned test defects (non-deterministic timestamp
assumptions) — see the resolved section below. `TEST_WRITING` v2 (attempt 2,
PASS) applied the recommended server-side-seed fix to both named tests; no
code under `app/` or `scripts/` changed on this re-entry, so none of T1-T6 was
re-invoked. Re-verification this pass: full repository suite **774/774
passed** under full-suite load (`python -m pytest -q`, the load-dependent
condition that actually discriminated the original flake — the broken version
had already passed 5/5 in isolation), and the fixed tests' premise was
confirmed by reading `tests/conftest.py`'s `db_session`/`client` fixtures:
`client` depends on `db_session`, and the app's `get_db_session` dependency is
overridden to yield that same `AsyncSession`, bound to one
connection-level transaction (app commits via SAVEPOINTs) — so the
HTTP-driven `test_reopen_ticket_at_exactly_7_days_boundary_succeeds` shares
the identical frozen `transaction_timestamp()` as the repository-direct
`test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_untouched`,
not just the latter. T7 (`gate-enforcer`, `QUALITY_GATE`) remains not started
— it is the next stage, not part of this composite skill.

## T1 — schema-builder (PASS)

`ResolveTicketRequest` (`resolution_note: str = Field(min_length=1,
max_length=5000)`), `CloseTicketRequest`/`ReopenTicketRequest` (each `reason:
str | None = None`), `TicketStateRead` (`id`, `ticket_number`, `status`,
`resolved_at`, `closed_at`, `updated_at` only — data-minimization per
API_DESIGN Open Questions #5) added to `app/modules/support/schemas.py`,
matching `US-4.3-openapi.yaml` v2 exactly. `ruff`/`mypy --strict` clean.

## T2 — data-layer-builder (PASS)

Four additive nullable `Ticket` columns, `ck_tickets_closed_requires_closed_fields`
(biconditional, safe since `"closed"` is terminal),
`ck_tickets_resolved_requires_resolution_fields` (one-directional implication,
db-design v3's correction), partial index
`ix_tickets_resolved_at_pending_autoclose`, module-level `SYSTEM_ACTOR_ID`
sentinel (Decision 5) — all in `models.py`. `TicketRepository.transition_status`
(Decision 2 — conditional `UPDATE ... WHERE id = :id AND status IN (...)`,
optional inclusive 7-day window guard) and `.auto_close_resolved_past_window`
(Decision 8 — batch `UPDATE ... RETURNING id` on the strict `<` predicate),
both building their `WHERE` fragment from the single `_RESOLUTION_WINDOW_DAYS
= 7` module constant (Decision 7) via `func.now() - func.make_interval(0, 0,
0, literal(_RESOLUTION_WINDOW_DAYS))` — never a second hardcoded `7`, never
string-interpolated. `update()`/`get_by_id()`/`list_for_requester()` left
byte-for-byte unchanged. `ruff`/`mypy --strict` clean; grep confirmed zero new
`session.query()`.

## T3 — migration-manager (PASS)

Revision `242e0dba5ba2_add_ticket_resolution_columns.py`: four
`add_column`s and two `create_check_constraint`s guarded via
`sa.inspect(op.get_bind())` (the Rewriter in `migrations/env.py` only reaches
`Create/DropTableOp`/`Create/DropIndexOp` — it already auto-guards the partial
index's create/drop). Autogenerate's unrelated `audit_log_default`/trgm-index
noise stripped, same precedent `9132a68b73c8_add_ticket_replies.py` already
set. `migrations/env.py` confirmed zero-diff (`support.models` already
registered wholesale, `AGENTS.md` §7.9 protected file).

**Real `upgrade → downgrade → upgrade` cycle executed against Docker-hosted
Postgres/Valkey (`customer_portal_pg`/`customer_portal_valkey` containers,
started this session) and passed** (three clean `alembic` runs, no errors).
Both `CHECK` expressions and the partial index's `postgresql_where` clause
confirmed to render verbatim via `pg_constraint`/`pg_indexes` — nothing
silently dropped:

```
ck_tickets_closed_requires_closed_fields:    CHECK ((((status)::text = 'closed'::text) = ((closed_at IS NOT NULL) AND (closed_by IS NOT NULL))))
ck_tickets_resolved_requires_resolution_fields: CHECK ((((status)::text <> 'resolved'::text) OR ((resolved_at IS NOT NULL) AND (resolution_note IS NOT NULL))))
ix_tickets_resolved_at_pending_autoclose:    CREATE INDEX ... ON public.tickets USING btree (resolved_at) WHERE ((status)::text = 'resolved'::text)
```

## T4/T5 — service-and-router-builder, service + router (PASS)

**Delivered:**

- `app/modules/support/service.py`: `TicketService.resolve_ticket`/
  `close_ticket`/`reopen_ticket`, each implementing `US-4.3-api-design.md`'s
  check order (lookup/ownership → transition validity 409 → permission
  403/skip → conditional `UPDATE` (409 on race loss) → audit write →
  best-effort email for `resolve_ticket` only). New
  `_ALLOWED_EVENTS_BY_STATUS` table (Decision 4, one explicit status-keyed
  table, verified verbatim by `test_allowed_events_by_status_matches_the_
  plan_s_stated_table`). `TicketRepositoryProtocol` gained `transition_status`.
  `TicketReplyService` gained a required `audit_service: AuditServiceProtocol`
  constructor parameter (Decision 3); `create_reply`'s FR-4 branch split into
  two sub-cases — the ordinary `"waiting_on_customer"` case stays on plain
  `update()`, the `"resolved"` reopening case now goes through
  `transition_status(..., require_resolved_within_window=True)` and writes
  `audit_log` (`event=ticket_reopened`) on success (DR-4) — applying the
  window guard to the ordinary case would silently break FR-2, since `NULL >=
  x` is never true in SQL.
- `app/modules/support/exceptions.py`: new `InvalidStateTransitionError`
  (`type_slug="invalid-state-transition"`, 409, carries `allowed_events:
  list[str]` — additively shaped beyond `admin_users`' same-slug US-3.1
  class, own module subclass per this module's established convention).
- `app/core/email.py`: **plan gap, not an invented requirement** — FR-1's
  `send_ticket_resolved_email` was flagged by `test-writer` as a new
  `EmailSender` Protocol method `implementation_plan.md`'s Files To Modify
  table never lists (`app/core/email.py` absent from that table), matching
  US-4.1's own `get_email_for_user` precedent. Added to the Protocol and
  `LoggingEmailSender`.
- **`app/main.py`, one file outside this skill's normal four-file scope —
  flagged explicitly, not silent scope creep.** FR-6 requires
  `InvalidStateTransitionError`'s `allowed_events` field to actually appear in
  the HTTP response body (`test_support_router.py` asserts
  `body["allowed_events"]` directly), but `problem_error_handler`'s generic
  rendering only special-cased `errors`, never an arbitrary subclass field.
  This is a plan gap nobody flagged upstream (unlike the email one above).
  Fixed via `getattr(exc, "allowed_events", None)` — a duck-typed, generic
  extension of the existing `errors`-rendering pattern — rather than adding a
  field to the shared `ProblemError` base class that only this one subclass
  uses, to keep the blast radius to one `main.py` hunk instead of touching
  every module's error shape.
- Four **unrelated** unit test fakes (`tests/unit/modules/{profile,
  email_verification,admin_users,users}/test_*_service.py`) needed a matching
  `send_ticket_resolved_email` stub — mechanical `mypy --strict` fallout of
  extending the shared `EmailSender` Protocol, same ripple US-4.2's own
  pipeline status recorded when `send_ticket_reply_notification` was added.
  No test logic or assertion changed in any of the four files.
- `app/modules/support/router.py`: three new routes (`POST .../resolve`,
  `/close`, `/reopen`), each `response_model=TicketStateRead`,
  `status_code=200`. Deliberately **no** `require_scope("tickets:write")`
  router dependency on `/resolve` — a scope dependency would run before the
  service can check transition validity, reversing FR-6/FR-7's required
  "state before actor" order; permission is checked inside
  `TicketService.resolve_ticket` itself, after the 409 check, matching
  `create_ticket_reply`'s existing actor-kind-resolved-in-service precedent.
- `app/modules/support/dependencies.py`: `get_ticket_reply_service` gains
  `audit_service: AuditLogServiceDep`, passed through to `TicketReplyService`
  — the only new wiring this story adds (Decision 3). `get_ticket_service`
  unchanged (already has every collaborator the three new methods need,
  Decision 1).
- `scripts/auto_close_resolved_tickets.py` (T6, new): follows
  `purge_unbound_attachments.py`'s shape (`main() -> int`,
  `if __name__ == "__main__":`), extended per Decisions 5/6/8 — builds both a
  Postgres engine (`settings.database_url`) and a Valkey client
  (`Redis.from_url(settings.valkey_url, decode_responses=True)`, mirroring
  `app/main.py`'s `lifespan` construction), calls
  `TicketRepository.auto_close_resolved_past_window`, loops the returned ids
  writing one `AuditLogService.record_event(event="ticket_auto_closed",
  actor_id=SYSTEM_ACTOR_ID, ...)` per id, then issues **one**
  `ticket_repository.commit()` for the whole run (`record_event` itself never
  commits; `ticket_repository`/`audit_repository` share the one session).

**Verified:**

- Self-check (harness requirement): `grep -nE
  "sqlalchemy|AsyncSession|models|repository"` on `router.py` — zero matches.
  `grep -nE "fastapi|starlette|HTTPException"` on `service.py` — zero
  matches.
- `ruff check`/`ruff format --check`: clean across `app`, `scripts`, `tests`.
- `mypy app tests --strict`: `Success: no issues found in 147 source files`
  (the pre-commit hook's own invocation shape — `scripts/` is checked
  separately, matching this repo's existing convention; `mypy
  scripts/auto_close_resolved_tickets.py --strict` also clean on its own).
- `lint-imports` (invoked via `python -c "from importlinter.cli import
  lint_imports..."` — the compiled `.exe` entry point is blocked by Smart App
  Control on this machine, matching this project's known WDAC constraint
  memory): `Contracts: 6 kept, 0 broken`.
- Unit: `tests/unit/` full suite, 319 passed (support module included).
- Integration: `tests/integration/modules/support/` +
  `tests/integration/scripts/` — **115/115 passed** after two implementation
  fixes made during this verification pass (see below). Full repository
  suite: **773/774 passed** (the one failure is the flaky boundary test
  documented below, not a regression — confirmed non-deterministic by
  rerunning it 5× in isolation, 5/5 pass; it only failed once, under the full
  suite's heavier load).

**Two implementation bugs found and fixed during this pass (own-code,
resolved without loop-back):**

1. `func.now() - func.make_interval(days=literal(_RESOLUTION_WINDOW_DAYS))`
   raised `TypeError: Function.__init__() got an unexpected keyword argument
   'days'` at both call sites — SQLAlchemy's generic `func.<name>()` call
   does not support SQL named-argument syntax; `**kwargs` are treated as
   `Function` constructor options, not SQL arguments. Fixed to the positional
   form Postgres's `make_interval(years, months, weeks, days, hours, mins,
   secs)` actually expects: `func.make_interval(0, 0, 0,
   literal(_RESOLUTION_WINDOW_DAYS))`. Caught by
   `test_reopen_ticket_requester_within_window_succeeds` and seven sibling
   integration tests, all passing after the fix.

## Non-blocking findings

- `TicketReplyService`'s FR-4 branch split (ordinary `update()` case vs.
  window-guarded `transition_status()` case for the `"resolved"` source
  status) is `test-writer`'s own collaborator-shape assumption
  (`test_generation_report.md`), not a literal single-branch instruction from
  `implementation_plan.md` — flagged there for `reconciliation-reviewer`,
  restated here for visibility since it shaped this pass's actual code.
- `app/main.py`'s `allowed_events` rendering (above) is a genuine plan gap
  this pass discovered and fixed, not present in any upstream design/plan
  artifact's Files To Modify table — flagged for `reconciliation-reviewer`.

## RESOLVED (v1 BLOCKED, routed via `changes_required_tests`; fixed by TEST_WRITING v2)

**`test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_untouched`**
(`tests/integration/scripts/test_auto_close_resolved_tickets.py`) is
non-deterministically flaky — not an implementation defect. Confirmed:
passes 5/5 in isolation, failed once inside the full 774-test suite run
(more system load between Arrange and Act widens the gap that decides the
outcome).

**Root cause (verified by algebra, not guessed):** the test seeds
`resolved_at = datetime.now(UTC) - timedelta(days=7)` using **Python's**
wall clock at Arrange time, then asserts the auto-close job's strict
predicate (`resolved_at < now() - interval '7 days'`, evaluated against
**Postgres's** `now()`/`transaction_timestamp()` at Act time) does *not*
match. Substituting: the predicate reduces to `python_arrange_time <
pg_now()`. Whether this holds depends entirely on how much real wall-clock
time elapses between the Python clock read and the query — which is
system-load-dependent, not deterministic. The test's own comment assumes
Postgres's transaction-frozen `now()` is always *earlier* than the Arrange
block's Python clock read (true for the *other* boundary tests, which use a
5-minute margin precisely for this reason); at the exact zero-margin
boundary, this assumption can flip either way depending on scheduling
jitter — verified empirically above. This is not fixable by any
implementation choice: the predicate itself is correct (matches
`US-4.3-db-design.md`'s DR-1-corrected strict `<`, and FR-3's literal
text), and this is exactly the "non-deterministic timestamp/ordering
assumption" class of test-file defect `IMPLEMENTATION.loop_back.
changes_required_tests` was added for.

**Recommended fix, preserving the test's exact-boundary intent (not just
widening the margin, which would silently convert it into a
"comfortably inside the window" test and drop the property being proven):**
seed `resolved_at` **server-side, in the same transaction**, e.g.
`resolved_at=text("now() - make_interval(days => 7)")` (or the equivalent
`func.now() - func.make_interval(0, 0, 0, 7)` SQLAlchemy expression this
pass had to fix in `repository.py`) instead of a Python-computed literal.
Since `db_session`'s fixture runs the whole test body in one connection-level
transaction and `transaction_timestamp()` is frozen for that transaction's
lifetime (savepoints do not reset it — confirmed by this session's own
passing run of the *other*, 5-minute-margin boundary tests, which rely on
the same fact), the seed and the predicate would then read the *identical*
frozen `now()`, making `resolved_at < now() - 7d` deterministically false
and the sibling `>=` (inclusive) predicate deterministically true — no
wall-clock race of any kind.

**Its twin is fragile in the opposite direction and must be fixed together:**
`test_reopen_ticket_at_exactly_7_days_boundary_succeeds`
(`tests/integration/modules/support/test_support_router.py`) is the identical
zero-margin construction against the *inclusive* `>=` guard — it passed this
run, but only because `python_arrange_time <= pg_now()` happened to hold;
under different scheduling it would fail the opposite way (asserting `200`
when the window guard's `>=` check narrowly loses). Same server-side-seed fix
cures both; fixing only the one that failed this run would leave the other to
fail unpredictably during a future `QUALITY_GATE`/CI run.

**Decision (v1):** route `IMPLEMENTATION` → `TEST_WRITING` via
`changes_required_tests` for `test-writer` to apply the server-side-seed fix
to both named tests. No code in `app/`/`scripts/` needs to change — T1-T6
are otherwise complete, verified, and expected to need no further change once
re-entered.

**Resolution (v2):** `TEST_WRITING` v2 (attempt 2, PASS) applied exactly this
fix. Confirmed here by a fresh full-suite run (774/774 passed) and by reading
the `db_session`/`client` fixtures to verify both fixed tests share the same
frozen transaction. `IMPLEMENTATION` advances to `QUALITY_GATE`.
