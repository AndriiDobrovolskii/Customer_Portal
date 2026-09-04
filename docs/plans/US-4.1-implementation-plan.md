---
artifact_type: implementation_plan
story: US-4.1
version: 1
status: ARCHIVED
created_at: "2026-09-03T00:30:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.1-spec-review.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.1-design-review.md
    version: 3
  - path: docs/impact-analysis/US-4.1-impact-analysis.md
    version: 1
supersedes: null
---

# Implementation Plan: Support Tickets (Create) (US-4.1)

## Goal

Build a new `app/modules/support/` module implementing self-service ticket
creation and listing (`POST`/`GET /v1/support/tickets`) per
`US-4.1-openapi.yaml` v3: idempotent creation with a non-guessable identifier,
input validation, a per-user creation rate limit, attachment
ownership/binding (IDOR-safe), and a `ticket_created` audit trail entry
written into the existing `audit_log` table in the same transaction as the
ticket insert — resolving the transaction-boundary tension
`impact-analyzer` flagged and left open.

## Architectural Changes

### 1. New module `app/modules/support/`, mirroring `email_verification`'s file set plus a `cache.py` (mirroring `users`'s, since this story needs Valkey gateways `email_verification` does not)

Layering is `router → dependencies → service → repository/cache → models/schemas` (`AGENTS.md` §3), unchanged pattern, no new layer.

- `TicketService.create_ticket()` orchestrates, in the DB design's stated
  order: idempotency gate → rate limit (skipped on replay) → validation →
  attachment binding → `tickets` insert → audit write, all inside one
  transaction, one commit.
- `TicketService.list_own_tickets()` — a direct keyset-paginated read, no
  cross-module call.

### 2. Transaction-boundary resolution (impact-analysis's flagged, unresolved tension)

`impact-analyzer` flagged that `audit.service`'s two existing methods
(`list_audit_logs`, `record_access_denied`) each call
`self._repository.commit()` themselves, while this story's audit write must
land in ticket creation's own transaction. Resolved here, not deferred
further:

- The new `AuditLogService.record_event(...)` method **must not commit**.
  It only builds the row and calls a new `AuditRepository` method that
  does `self._session.add(AuditLog(...))` + `await self._session.flush()`
  — the exact shape `record_self_audit`/`record_access_denied` already use
  before their own (separately-called) `commit()`, just without the
  trailing commit call.
- `support.service.create_ticket()` — not `audit.service` — issues the
  single `await self._repository.commit()` for the whole operation, after
  the ticket insert, the attachment bind, and the audit write have all been
  flushed on the same request-scoped `AsyncSession`. This is safe because
  DI provides one `AsyncSession` per request (`AGENTS.md` §3 "Dependency
  injection"): `TicketRepository`, `AttachmentRepository`, and the injected
  `AuditRepository` collaborator all receive that same session instance,
  so `support.service`'s commit covers all three writes atomically.
- This selects option (a) from `impact-analyzer`'s §2 write-up (no
  self-commit on the new audit method) over option (b) (two separate
  commits with a documented gap window) — a partial failure between the
  ticket insert and the audit write now rolls back both, rather than
  leaving a ticket without its audit entry.
- `AuditLogService`'s two *existing* methods are unchanged — they keep
  self-committing for their own single-write use cases. Only the new
  `record_event` method omits the commit call, since it is the one method
  this codebase calls from *outside* `audit.service`'s own request cycle.

### 3. Idempotency gate, rate limit, attachment binding — as designed, no plan-level deviation

`US-4.1-db-design.md`'s atomic `SET NX EX` claim/replay/bounded-poll gate,
the `ticket_create_rate:{user_id}` `INCR`+`EXPIRE` limiter, and the
ownership/binding check on `attachment_ids` are implemented exactly as
specified — `cache.py` reuses `MfaReplayCache.mark_step_used`'s `SET NX EX`
primitive and `LoginThrottleCache._incr_with_ttl`'s pipelined `INCR`+`EXPIRE`
primitive (both read directly in `app/modules/users/cache.py`), not new
mechanisms. The poll-exhaustion path (design-flagged non-blocking finding)
falls through to an unhandled `500` — no new contract slug is added, per the
DB design's own statement that this is the framework's ordinary default, not
a claim of a new approved response.

### 4. Authorization — as designed, no plan-level deviation

`POST` and `GET`'s customer branch: `CurrentUserDep` only (identity/ownership,
no `tickets:*` scope). `GET`'s staff-rejection branch:
`roles.dependencies.require_scope("tickets:read")` /
`require_scope("tickets:write")`, rejecting with `AgentQueueNotAvailableError`
(403). Both reuse existing dependency factories; no new authorization
mechanism.

### 5. Open Decisions carried into this plan, not resolved here

- **OD-3 (`category` enum)** remains unresolved — `schemas.py` validates
  `category` as a length-capped string only (`max_length=50`), no enum. A
  human decision is still required before an enum/CHECK constraint can be
  added; not this plan's call.
- **BR-007 (FK `ondelete`)** remains `RESTRICT`-by-default on
  `tickets.requester_id`/`attachments.uploaded_by`, per the DB design; no
  change proposed here.
- **Idempotency poll-exhaustion `500`** — confirmed as the implementation
  behavior (see §3 above), not a gap needing further design work.

## Files To Create

### `app/modules/support/`
| File | Contents |
|---|---|
| `__init__.py` | Empty, marks the package. |
| `models.py` | `Ticket` (`tickets`), `Attachment` (`attachments`) — `Mapped[]`/`mapped_column()` only, no `relationship()` (per entity model: no response nests a collection). |
| `schemas.py` | `TicketBase`/`CreateTicketRequest` (`extra="forbid"`, `subject` ≤150, `body` ≤5000, `category` ≤50, `attachment_ids: list[uuid.UUID]`), `TicketRead` (`from_attributes=True`, explicit field list: `id`, `ticket_number`, `status`, `subject`, `body`, `category`, `requester_id`, `created_at`, `updated_at`), `TicketListResponse` (`items`, `next_cursor`, matching `US-3.1`'s `UserListResponse` shape). |
| `repository.py` | `TicketRepository`: `create`, `get_by_id`, `list_for_requester` (keyset, `(requester_id, created_at DESC, id DESC)`). `AttachmentRepository`: `get_by_id`, `bind_to_ticket`, `find_unbound_older_than`, `purge` (delete rows found by the previous call). Verbs match `AGENTS.md` §4's fixed set. |
| `cache.py` | `TicketIdempotencyCache` (`claim_or_get`, `resolve` — the `SET NX EX`/bounded-poll gate) and `TicketCreationRateLimitCache` (`record_and_check`, mirroring `LoginThrottleCache._incr_with_ttl`). Valkey-only, no `sqlalchemy` import (`AGENTS.md` §3 table). |
| `service.py` | `TicketService.create_ticket()`, `TicketService.list_own_tickets()`. Takes `TicketRepository`, `AttachmentRepository`, `TicketIdempotencyCache`, `TicketCreationRateLimitCache`, and an `AuditServiceProtocol` collaborator (service → service, per `AGENTS.md` §3) via `__init__`. |
| `router.py` | `POST /v1/support/tickets`, `GET /v1/support/tickets`, `response_model`/`status_code` on each, per `US-4.1-openapi.yaml`. |
| `dependencies.py` | `TicketServiceDep`; wires `require_scope("tickets:read")`/`require_scope("tickets:write")` for `GET`'s staff-rejection branch (imports `app/modules/roles/dependencies.py`, does not reimplement it). |
| `exceptions.py` | `ValidationFailedError` (422, FR-3 — same `errors: list[FieldError]` shape as `audit/exceptions.py`'s own), `IdempotencyKeyReuseError` (422, FR-4), `AttachmentNotOwnedError` (422, FR-7 — one slug for all three indistinguishable causes), `TicketCreationRateLimitError` (429 + dynamic `Retry-After` header, mirroring `email_verification/exceptions.py`'s `TooManyAttemptsError.__init__`), `AgentQueueNotAvailableError` (403, `GET` staff-rejection). `AccountDeactivatedError` (403, FR-5) reused from `app/modules/users` if already importable there; otherwise a thin re-raise is out of scope for a new module-owned error (module-specific errors live in their owning module, `AGENTS.md` §4 "Exception ownership") — `service-and-router-builder` confirms which applies during IMPLEMENTATION. |

### `scripts/`
| File | Contents |
|---|---|
| `purge_unbound_attachments.py` | Mirrors `scripts/purge_unverified_accounts.py` verbatim in structure: `asyncio.run(main())`, own `AttachmentRepository`/`TicketService`-or-equivalent purge method, exit code 0/non-zero, no in-process scheduler. |

### Migration
| File | Contents |
|---|---|
| `migrations/versions/<rev>_add_support_tickets.py` | New `tickets_number_seq` `SEQUENCE`, `tickets` table, `attachments` table, both new indexes per entity model. Owned by `migration-manager`, not created by this plan directly — listed here because it is a required artifact this story's IMPLEMENTATION stage produces. |

## Files To Modify

| File | Change | Note |
|---|---|---|
| `app/core/cache_keys.py` | Add `idempotency_key(user_id, key) -> f"idempotency:{user_id}:{key}"` and `ticket_create_rate_key(user_id) -> f"ticket_create_rate:{user_id}"`. | Matches existing per-user key builders in this file (`revoke_before_key`, `login_fail_account_key`) — same file, same pattern, no new file. |
| `app/modules/audit/service.py` | Add `AuditLogService.record_event(*, category, event, actor_id, target_id, outcome, payload)`, resolving `actor_role` via the existing `_resolve_actor_role` helper, **no self-commit** (see Architectural Changes §2). Extend `AuditRepositoryProtocol` with the matching method. | This is the only change to this file's public surface; `list_audit_logs`/`record_access_denied` are untouched. |
| `app/modules/audit/repository.py` | Add `AuditRepository.record_event(...)`: builds `AuditLog(...)` (mirrors `record_self_audit`'s literal construction) and `await self._session.flush()` — no `commit()` call. | New `AuditLog(...)` call site; `tests/unit/test_audit_write_call_site_scan.py` already scans this file by AST walk, no test-file edit needed (confirmed by impact-analysis). |
| `app/api/v1/router.py` | Add `from app.modules.support.router import router as support_router` and `router.include_router(support_router)`. | Matches the existing 7-call flat aggregation pattern exactly. |
| `migrations/env.py` | Add `from app.modules.support import models as support_models  # noqa: F401  # registers models`, in the existing alphabetical block. | **Flagged per this plan's own instructions** — `migrations/env.py` is a file `AGENTS.md` §7.9 says to "read, never edit." This is the same one-line model-registration import every one of the 6 existing modules already required and `migration-manager` has performed 6 times before (confirmed by impact-analysis); it does not touch the file's `Rewriter`/guard logic. Called out explicitly here rather than silently bundled — `migration-manager` performs this edit as part of its own stage, following the established precedent, not a new kind of change to this file. |

No other existing file changes. `tests/conftest.py` needs no change (impact-analysis confirmed).

## Risks

1. **Transaction-boundary regression risk.** Removing the `commit()` call
   from a *new* `audit.service` method, while leaving the two existing
   methods self-committing, is an intentional asymmetry (§2 above) — a
   future caller of `record_event` who assumes it commits (copying the
   older methods' pattern) would silently lose the audit write on an
   uncommitted session. Mitigated by a clear docstring on `record_event`
   stating "caller owns the commit" and by `tests/unit/modules/audit/test_audit_service.py`
   gaining a test asserting `record_event` does **not** call
   `repository.commit()` (via a fake repository).
2. **Idempotency bounded-poll adds latency on the mid-flight race path**
   (up to 500 ms) — within the p95 ≤ 400 ms budget for the *first* request,
   but a concurrent second request hitting the poll path could itself
   approach or exceed that budget. Accepted per the DB design's own
   reasoning (this is the expected, not exceptional, case for a genuine
   double-submit); no plan-level mitigation beyond what's designed.
3. **`migrations/env.py` edit** — protected file, flagged above; no
   functional risk (established repeated pattern), but requires
   `migration-manager` to make only the one-line addition, nothing else.
4. **OD-3 still open** — `category` ships with no enum validation. If a
   stakeholder resolves OD-3 before this story reaches `IMPLEMENTATION`,
   this plan (and the schema/DB design) would need a follow-up revision;
   not assumed to happen within this story's timeline.
5. **BR-007 FK gap** — `RESTRICT`-by-default is a deliberate placeholder;
   no migration risk today since no account-deletion job exists yet that
   would hit it.

## Validation Strategy

- `pre-commit run --all-files` — Ruff format/lint, mypy `strict` on
  `app tests`, secret scan. New module must have zero `Any`, explicit
  `-> *Read` annotations on every service method returning a schema.
- `lint-imports` — `support` module and its `models.py`/`schemas.py`/
  `repository.py`/`cache.py`/`service.py`/`router.py`/`dependencies.py`/
  `exceptions.py` layer split must be declared (`exhaustive=true`); no
  `sqlalchemy`/`AsyncSession`/Valkey client import in `router.py`; no
  `fastapi`/`HTTPException` import in `service.py`. `support.repository`
  must not import `app.modules.audit.repository`/`AuditLog` directly
  (service → service only).
- `alembic upgrade → downgrade → upgrade` — proves the new migration,
  including the hand-written `ticket_number_seq` sequence/default, which
  the Rewriter cannot reach and `migration-manager` must guard per
  `AGENTS.md` §4.
- OpenAPI renders and matches `US-4.1-openapi.yaml` v3's endpoint/schema
  shapes (`response_model`/`status_code` declared on both routes).

## Testing Strategy

Per `AGENTS.md` §5, unit tests use hand-written fakes (never `MagicMock`);
integration tests run against real PostgreSQL/Valkey with no
`unittest.mock`. Test files themselves are `test-writer`'s output, not
created by this plan — file list is per `impact-analyzer`'s survey,
restated here for traceability:

- **Unit** — `tests/unit/modules/support/test_support_schemas.py` (`extra="forbid"`, length caps, `attachment_ids` shape); `tests/unit/modules/support/test_support_service.py` (idempotency claim/replay/reuse/mid-flight-poll branches against a fake `TicketIdempotencyCache`; rate-limit ordering relative to idempotency — FR-6 must never fire on a genuine replay; attachment ownership rejection paths with indistinguishable causes; the transaction-boundary contract — `create_ticket` commits exactly once). `tests/unit/modules/audit/test_audit_service.py` gains coverage for `record_event`, including asserting no self-commit (Risk 1).
- **Integration** — `tests/integration/modules/support/test_support_router.py` (FR-1 through FR-7's status codes end-to-end against real PG/Valkey, including the audit-row side effect of a successful `POST` — a genuine cross-module check); `tests/integration/scripts/test_purge_unbound_attachments.py` mirroring `test_anonymize_erased_user.py`'s pattern.
- **Coverage** — 85% floor overall, 90%+ on `service.py`/`router.py`, per `AGENTS.md` §5/§6.
