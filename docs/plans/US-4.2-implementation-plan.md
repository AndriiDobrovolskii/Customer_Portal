---
artifact_type: implementation_plan
story: US-4.2
version: 2
status: ARCHIVED
created_at: "2026-09-05T14:00:00Z"
updated_at: "2026-09-05T19:00:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/reviews/specifications/US-4.2-spec-review.md
    version: 6
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.2-design-review.md
    version: 3
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
supersedes: docs/plans/US-4.2-implementation-plan.md (v1)
---

# Implementation Plan: Ticket Replies (US-4.2)

## Revision Note (v2)

v1 (2026-09-05T14:00:00Z) planned §2's RLS session-context mechanism on the
assumption — inherited from `db_design` v3 §"Row-Level Security" — that
`FORCE ROW LEVEL SECURITY` alone closes the gap between the application's
single connecting role and the policies' intended guarantee. `IMPLEMENTATION`
T3 (`migration-manager`) proved that assumption false against this codebase's
actual `DATABASE_URL`: the configured role (`postgres`) is a PostgreSQL
**superuser** (`rolsuper=True`, `rolbypassrls=True`), which bypasses RLS
unconditionally — `FORCE ROW LEVEL SECURITY` only closes the table-owner
exemption, never the superuser one. Two of the story's own direct-RLS
integration tests failed against this role; a scratch `NOSUPERUSER` role
proved the `CREATE POLICY` predicates themselves are correct (full detail:
`docs/catalog/US-4.2-pipeline-status.md` v2, T3 section). `story-orchestrator`
recorded a `HUMAN_REDIRECTED` transition (`docs/workflow/workflow-state.yaml`,
`docs/workflow/history.jsonl`, 2026-09-05T18:30:00Z) routing
`IMPLEMENTATION` → `ARCHITECTURE_PLANNING` (`loop_back.blocked_by_architecture`)
per the human's explicit direction: **provision a dedicated non-superuser
runtime database role**, rather than revise `db_design`/`entity_model`'s RLS
claim in place.

This revision adds that provisioning as **Architectural Change #12** below,
and updates Files To Create/Modify, Risks, and Validation/Testing Strategy
accordingly. Nothing else in v1 changes: Architectural Changes #1–#11, the
status-gating table, and the file footprint for T1/T2/T4/T5 are carried
forward verbatim — `db_design` v3/`entity_model` v3's RLS **policy SQL**
(§"Row-Level Security") was never wrong and needs no revision; only the
*deployment* assumption of who connects was. T1 (`schema-builder`) and T2
(`data-layer-builder`) remain `PASS` and untouched by this revision. T3's
migration file (`migrations/versions/9132a68b73c8_add_ticket_replies.py`) is
addressed explicitly under Architectural Change #12 below — it does not need
to be regenerated.

## Goal

Extend the existing `app/modules/support/` module (US-4.1) with threaded
ticket replies: `POST /v1/support/tickets/{id}/replies` (agent public reply,
agent internal note, customer reply, including the one reopening transition
Resolution OD-8 defines) and a new `GET /v1/support/tickets/{id}` returning a
ticket plus its cursor-paginated reply thread. This is the first story in
this codebase to add PostgreSQL Row-Level Security, the first to need a
session-scoped `SET LOCAL` context (`app.actor_kind` / `app.actor_id`), and —
per this revision — the first to require the running application to connect
through anything other than the single superuser role every prior story has
used.

## Architectural Changes

### 1. Extend `app/modules/support/`, no new module

Same layering as US-4.1 (`AGENTS.md` §3): `router → dependencies → service →
repository/cache → models/schemas`. `TicketReplyRepository` and an extended
`AttachmentRepository` sit alongside the existing `TicketRepository`; no new
layer, no new module.

### 2. RLS session context — new dependency scoped to this module, not the shared `get_db_session`

`impact-analyzer` flagged two placements with different blast radii and left
the choice to this stage. **Decision: a new, module-scoped dependency**,
`support/dependencies.py::get_rls_session`, wrapping `app/db/dependencies.py`'s
existing `get_db_session` — issuing `SET LOCAL app.actor_kind = :kind` and
`SET LOCAL app.actor_id = :id` on the same session before it is handed to the
repository — used **only** by the two new routes (`POST .../replies`,
`GET /v1/support/tickets/{id}`). The existing `POST`/`GET` list routes keep
using the plain `get_db_session` unchanged.

Rejected alternative: modifying the shared `app/db/dependencies.py::get_db_session`
to always set these GUCs. That would run `SET LOCAL` on every request in the
application (registration, login, admin routes, audit — none of which read
`app.actor_kind`), a blast radius `AGENTS.md` §7.8's "no opportunistic scope
changes" rules out for a change only two routes need. The module-scoped
wrapper touches exactly the two files this story already owns
(`support/dependencies.py`, `support/router.py`) and no file outside
`app/modules/support/`.

`author_kind`/`app.actor_kind`'s two-value vocabulary (`"customer"` |
`"agent"`) is derived once, in this same dependency, from the identical check
`support/dependencies.py::reject_agent_queue_access` already uses today
(`"tickets:write" in current_user.scopes`) — not a new derivation mechanism,
reused verbatim per db-design v3's own note that this derivation "is not
new — only its use for `author_kind`/`app.actor_kind` is."

### 3. New `TicketRepository.update()` method — fixed verb, not a bespoke name

`AGENTS.md` §4's repository verbs are fixed (`get_by_*`, `get_with_*`,
`list_*`, `exists_by_*`, `create`, `update`, `delete`). Today's
`TicketRepository` has no `update` at all (confirmed by impact-analysis).
Add one method, not two: `TicketRepository.update(ticket_id, *, status:
str | None = None, first_response_at: datetime | None = None) -> Ticket |
None`, applying only the fields passed (both optional, `None` means "leave
unchanged" — never used to null out a value, since neither field is ever
cleared by any FR in this story). Returns `None` if the ticket no longer
exists (defensive; no FR exercises this path today since the id was already
loaded earlier in the same request). Used by FR-1 (`first_response_at`
stamp), FR-2/FR-6 (status transitions).

### 4. Status-gating switch lives in `service.py`, matching the API design's table exactly — no undefined transition is invented

`TicketReplyService`'s (see §6) status-gating logic implements exactly the
table in `US-4.2-api-design.md` §"Status-transition side effects":

| Actor | Ticket status before | Result |
|---|---|---|
| Agent, public reply, not `"closed"` | `"resolved"` | status unchanged (OD-5) |
| Agent, public reply, not `"closed"` | anything else | → `"waiting_on_customer"` |
| Agent, internal note, not `"closed"` | any | status unchanged (not customer-facing) |
| Customer | `"waiting_on_customer"` | → `"waiting_on_support"` |
| Customer | `"resolved"` | → `"waiting_on_support"` (reopens, OD-8) |
| Customer | any other status (`"open"`, `"waiting_on_support"`) | **no status write** |
| Any actor | `"closed"` | `409 ticket-closed`, no reply created |

The "any other status" row is **not** a new business rule this plan invents —
it is the absence of one: neither FR-2 nor any AC defines a transition for
that case (API design's own Open Question #1, carried non-blocking through
DESIGN_REVIEW and IMPACT_ANALYSIS), so the reply is still accepted (`201`,
same as every other non-`"closed"` case) but the service performs no status
`UPDATE` — it falls through the same `status: str | None = None` "leave
unchanged" branch `TicketRepository.update()` already provides for every
other no-op case in this table. If a future story needs different behavior
here, that is a spec change, not a silent addition made now.

### 5. `author_kind` → `visibility` CHECK backstop; FR-5's `403` is a service-layer check, never a caught `IntegrityError`

Per db-design v3's explicit layering note: the service always runs its own
`visibility == "internal" and author_kind == "customer"` check before any
insert and raises the domain exception directly. The DB `CHECK` constraint
is unreachable in normal operation and is never relied on as the FR-5
implementation path (i.e. `service.py` must not wrap the insert in a
try/except that translates `IntegrityError` into `403`).

### 6. `InsufficientPermissionError` — module-owned copy, not a cross-module import (follows the `AccountDeactivatedError` precedent)

`impact-analyzer` left this undecided. **Decision:** `support/exceptions.py`
gets its own `InsufficientPermissionError` (`type_slug=
"insufficient-permission"`, `status=403`), the same slug/shape as
`app/modules/roles/exceptions.py`'s class of the same name, but **not
imported from there** — matching this module's own established precedent
(`AccountDeactivatedError`, US-4.1, whose docstring states "own subclass per
module ... never importing users.exceptions' identically-shaped one
directly, per module ownership"). `require_scope("tickets:write")` /
`require_scope("tickets:read")` (agent branch, `roles.dependencies`) still
raise the `roles` module's own class when the *scope* check fails at the
router-dependency layer — that call site is unchanged from how US-4.1 already
uses it. The **new** module-owned class is what `service.py` raises for
FR-5's business-rule check (customer attempting `visibility: "internal"`),
a condition the `roles` module has no reason to know about.

### 7. New `TicketReplyRateLimitCache` — separate Valkey counter from ticket creation's

`app/modules/support/cache.py` gets a new class parallel to
`TicketCreationRateLimitCache` (30/user/hour, not 5/user/hour), keyed by a
new `app/core/cache_keys.py::ticket_reply_rate_key(user_id)` function — a
distinct Valkey key from `ticket_create_rate_key`, so a reply never consumes
a ticket-creation rate-limit slot or vice versa. Same `INCR`+`EXPIRE`
pipeline shape as the existing class; no new mechanism.

### 8. `EmailSender` gets two new methods, one implementation to update

`app/core/email.py`'s `EmailSender` Protocol adds
`send_ticket_reply_notification(*, to: str, ticket_number: str)` (FR-1,
requester) and `send_ticket_reply_queue_notification(*, ticket_number: str)`
(FR-2, queue — no `to` parameter; the recipient is the fixed queue address
read from settings inside `LoggingEmailSender`/a real implementation, not
passed by the caller, since the service should not need to know the queue's
address to ask for it to be notified). `LoggingEmailSender` is the only
implementation in this codebase (confirmed by impact-analysis) and gets both
methods, following `send_ticket_created_email`'s existing style (log only,
never log `to` or message content). Both dispatches happen best-effort,
after commit, wrapped in the same `try/except Exception: logger.exception(...)`
pattern `create_ticket` already uses — a failed send must not undo an
already-committed reply.

### 9. New `Settings.support_queue_email` field

`app/core/config.py` gets one new field, `support_queue_email: str =
"support-queue@portal.internal"` (Resolution OD-2's own example value as the
default) — read via `get_settings()` only, per `AGENTS.md` §4's "Config &
secrets" rule; no `os.getenv` call anywhere in `support/service.py`.
`.env.example` gains the matching entry.

### 10. New `GET /v1/support/tickets/{id}` route enforces its own `limit` bound; the existing list route's gap is left alone

Impact-analysis's carried finding: today's `GET /support/tickets` accepts a
bare `limit: int = 100` with no `Query(ge=1, le=100)`. The **new** route
declares `limit: Annotated[int, Query(ge=1, le=100)] = 50` per
`US-4.2-openapi.yaml`'s `minimum: 1`/`maximum: 100`/`default: 50` — closing
the gap for this story's own endpoint. Fixing the sibling `GET /support/tickets`
route's pre-existing gap is out of this story's scope (`AGENTS.md` §7.8: no
opportunistic changes to code this story doesn't otherwise touch) and is not
included in this plan.

### 11. Attachment reply-binding: a new `bind_to_reply` method, not an overload of `bind_to_ticket`

`AttachmentRepository.bind_to_ticket`'s existing conditional-`UPDATE`
(`WHERE ticket_id IS NULL`) is left untouched — it is still used by
`create_ticket`. A new `bind_to_reply(*, attachment_id: uuid.UUID,
ticket_reply_id: uuid.UUID) -> Attachment | None` method uses the identical
pattern (`WHERE ticket_reply_id IS NULL`) against the new column, since
`ticket_id` and `ticket_reply_id` are independent nullable bindings
(db-design v3) — an attachment reply-bound by this story still has `ticket_id
IS NULL` (it was never bound to the ticket directly), so a single method
branching on which column to check would need a parameter dictating that
branch anyway; two small, single-purpose methods match this file's existing
one-method-per-binding-target style better than one parameterized method.

### 12. NEW (v2) — Dedicated non-superuser runtime database role, so `FORCE ROW LEVEL SECURITY` actually forces anything

**Decision (human-directed, 2026-09-05T18:30:00Z):** introduce a second
PostgreSQL role, `app_runtime` — `LOGIN`, `NOSUPERUSER`, `NOBYPASSRLS`,
`NOCREATEDB`, `NOCREATEROLE` — that the **running application** connects as.
The existing role (`postgres`, referred to below as the *owner role*) keeps
running Alembic migrations and owns every table, exactly as today; only the
role the app uses to **serve requests** changes. This is the only way
`FORCE ROW LEVEL SECURITY` (Architectural Change §2's session context depends
on it) closes the gap the owner-role exemption *and* the superuser exemption
both need closed — no table-level or policy-level setting can substitute
for connecting as a non-superuser role, confirmed by
`docs/catalog/US-4.2-pipeline-status.md` v2's own scratch-role proof.

**Why this is broader than "just the RLS routes":** the application has one
engine, one connection role, for every request it serves (`app/main.py`'s
`lifespan`) — there is no per-route role switch available in this codebase's
connection-pooling model, and adding one now (e.g. two separate engines, one
per role, selected per-route) would be a second new mechanism on top of the
first, for no benefit: `app_runtime` needs the same CRUD privileges on every
existing table the app already reads/writes today, RLS-guarded or not, since
every other module (`users`, `roles`, `admin_users`, `audit`, `profile`,
`account`, `email_verification`) keeps running through the same single
engine. **Decision: switch the whole application's runtime connection to
`app_runtime`, not just the two new routes' sessions.** This is the honest
scope of "provision a dedicated non-superuser runtime role" — narrowing it to
only the support module's two routes would require a second engine/session
factory selected per-route, a heavier and more error-prone mechanism than
granting one role the same privileges the app already exercises everywhere,
minus `SUPERUSER`/`BYPASSRLS`/ownership.

**What does NOT change:** the owner role keeps running migrations
(`migrations/env.py` already reads `get_settings().database_url` — this
setting's *meaning* narrows to "the role Alembic uses," but its value and
every reader of it besides `app/main.py` stay untouched, so `env.py` itself
needs no edit, confirmed at IMPLEMENTATION time per the existing zero-diff
expectation in Files To Modify). The owner role also keeps `CREATE
TABLE`/`ALTER TABLE`/DDL privileges the app itself never needs and must
never have (least privilege).

**Settings / config wiring:**
- `app/core/config.py`: new field `runtime_database_url: str` — the
  connection string the **application** uses at request time, distinct from
  `database_url` (which narrows to "the migration/owner role's URL," value
  unchanged). Given a dev-only default following the exact precedent already
  set by `jwt_secret_key`/`mfa_secret_encryption_key` ("Dev-only default;
  every real deployment MUST override this via env"), since embedding any
  real credential in a committed default is never acceptable regardless of
  precedent.
- `.env.example`: new `RUNTIME_DATABASE_URL=...` entry, matching.
- `app/main.py`: the **one** application-code line that changes:
  `create_engine_and_sessionmaker(settings.database_url)` in `lifespan()` →
  `create_engine_and_sessionmaker(settings.runtime_database_url)`. Nothing
  else in `app/main.py`, `app/db/session.py`, or `app/db/dependencies.py`
  changes — all three stay role-agnostic, exactly as designed today; only
  which URL is handed in changes.

**Role/privilege provisioning is cluster administration, not a schema
migration — a new operational artifact, not an Alembic revision.**
`AGENTS.md` §4 scopes migrations to schema DDL; `CREATE ROLE` and granting
privileges across the whole schema are cluster/database-level concerns
Alembic's single-database, single-`op.execute()` model isn't built for, and
mixing them into `migrations/versions/9132a68b73c8_add_ticket_replies.py`
(or a new revision) would make a schema migration silently depend on
role-creation succeeding, which is a operational deploy step, not a
versioned-with-the-schema one. **New file:** `scripts/db/provision_runtime_role.sql`
— idempotent (`DO $$ ... EXCEPTION WHEN duplicate_object THEN NULL; END $$;`
for the `CREATE ROLE`, since PostgreSQL has no `CREATE ROLE IF NOT EXISTS`),
covering:
1. `CREATE ROLE app_runtime WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB
   NOCREATEROLE PASSWORD '<set via deploy secret, never committed>';`
2. `GRANT CONNECT ON DATABASE customer_portal TO app_runtime;` and
   `GRANT USAGE ON SCHEMA public TO app_runtime;`
3. `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO
   app_runtime;` plus `GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public
   TO app_runtime;` — covers every table that exists **at the time the
   script runs**, RLS-guarded or not.
4. `ALTER DEFAULT PRIVILEGES FOR ROLE <owner_role> IN SCHEMA public GRANT
   SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;` (and the
   matching `... ON SEQUENCES ...`) — so every table a **future** migration
   creates (run by the owner role) is automatically covered without rerunning
   this script; re-running it anyway is harmless (statements 2–4 are
   naturally idempotent in PostgreSQL).

Run once per environment (local dev, CI, staging, production) by a human or
the deploy pipeline, against the owner-role connection, **after** migrations
have been applied at least once (so statement 3's blanket grant already
covers this story's own new `ticket_replies` table without relying on
ordering against this specific migration). Documenting this operational step
belongs to `documentation-and-adrs`, out of this plan's own remit — flagged
here so `IMPLEMENTATION_PLANNING` schedules the script's creation and the one
line in `app/main.py` as an explicit task, not an afterthought.

**Test infrastructure — `tests/conftest.py`'s `_database` fixture must run
the same provisioning, per test session, against the ephemeral
`testcontainers` PostgreSQL:** today's fixture upgrades the container to
`head` and then points `app.state.db_engine`/`db_session_factory` — the
objects `get_db_session` serves every test request from — at the **container's
own bootstrap role**, which PostgreSQL always creates as a superuser (no
`testcontainers-postgres` configuration changes that). Left unchanged, the
two direct-RLS integration tests TR-AC3 requires would keep failing in CI for
the same reason T3 found them failing locally — the fixture, not just the
deployed app, must stop serving requests as a superuser. After
`command.upgrade(alembic_cfg, "head")`, the fixture must: (a) execute
`scripts/db/provision_runtime_role.sql`'s statements against the existing
owner-role `engine` (a raw connection, once per test session); (b) build a
**second** engine/session_factory from a connection URL substituting
`app_runtime`'s credentials (same container host/port/database), and assign
*that* — not the owner-role one — to `app.state.db_engine`/`db_session_factory`,
matching exactly what `app/main.py`'s `lifespan` does in a real deployment.
The owner-role `engine` itself is kept alive only for this provisioning step
and for `cleanup_users`' admin-level `DELETE` (unaffected — `app_runtime`
also has `DELETE`, so no other fixture needs to change).

**Does `IMPLEMENTATION` T3 need to re-run?** No. The migration file
(`migrations/versions/9132a68b73c8_add_ticket_replies.py`) and its already-proven
`upgrade → downgrade → upgrade` cycle prove the **DDL** — table, columns,
`CREATE POLICY`/`ENABLE`/`FORCE ROW LEVEL SECURITY` — is correct and
reversible; that was never in question. What was unproven, and is fixed by
this architectural change alone, is *which role serves requests*. T3's own
verdict becomes re-verifiable, not re-runnable: once `app_runtime` exists and
`tests/conftest.py` is wired to serve requests through it, the two
already-written integration tests that failed against the superuser role
(`test_internal_reply_hidden_from_customer_context_by_rls_alone`,
`test_no_actor_kind_set_defaults_to_hiding_internal_reply`) must be re-run —
no new migration-manager cycle, no test rewrite, per the human's own stated
expectation ("expected to pass unchanged once the deployment role changes").

## Files To Create

### Migration

| File | Contents |
|---|---|
| `migrations/versions/<rev>_add_ticket_replies.py` | `CREATE TABLE ticket_replies` (with the `CHECK` constraint and composite `(ticket_id, created_at, id)` index, autogeneratable); `ALTER TABLE tickets ADD COLUMN first_response_at`; `ALTER TABLE attachments ADD COLUMN ticket_reply_id` + its index; hand-written `ENABLE ROW LEVEL SECURITY` / `FORCE ROW LEVEL SECURITY` / two `CREATE POLICY` statements (db-design v3's literal SQL), each guarded per `AGENTS.md` §4. Owned by `migration-manager`. **Already written and DDL-proven as `9132a68b73c8_add_ticket_replies.py` — this row is retained for traceability, not re-created; see Architectural Change #12's "Does T3 need to re-run?" above.** |

### Role provisioning (NEW, v2)

| File | Contents |
|---|---|
| `scripts/db/provision_runtime_role.sql` | Idempotent `CREATE ROLE app_runtime` + schema/table/sequence grants + `ALTER DEFAULT PRIVILEGES`, per Architectural Change #12. Not an Alembic migration; run out-of-band against each environment's owner-role connection. |

## Files To Modify

| File | Change | Note |
|---|---|---|
| `app/modules/support/models.py` | New `TicketReply` class (`ticket_replies`: `id`, `ticket_id` FK, `author_id` FK, `author_kind`, `body`, `visibility`, `created_at`, `CheckConstraint(...)`, composite index). Additive `Ticket.first_response_at: Mapped[datetime \| None]`. Additive `Attachment.ticket_reply_id: Mapped[uuid.UUID \| None]` with `index=True`. No `relationship()` on any of the three (db-design v3, entity model v3 — direct repository queries only). | T2, already `PASS`. |
| `app/modules/support/repository.py` | New `TicketReplyRepository`: `create(...)`, `list_for_ticket(ticket_id, cursor, limit)` (keyset, mirrors `list_for_requester`'s cursor-encode/decode helpers, ascending order — oldest-first per `ReplyThreadPage`). `TicketRepository`: new `update()` method (§3 above). `AttachmentRepository`: new `bind_to_reply()` method (§11 above); existing methods unchanged. | T2, already `PASS`. |
| `app/modules/support/cache.py` | New `TicketReplyRateLimitCache` (§7 above). Existing classes unchanged. | T2, already `PASS`. |
| `app/core/cache_keys.py` | New `ticket_reply_rate_key(user_id) -> f"ticket_reply_rate:{user_id}"`, matching this file's existing per-user key-builder pattern. | T2, already `PASS`. |
| `app/modules/support/service.py` | New method(s) on `TicketService` (or a new `TicketReplyService` sharing the same file/module — final split is `service-and-router-builder`'s call, not fixed here, since either shape satisfies the same collaborator/protocol contract) implementing FR-1/FR-2/FR-3/FR-5/FR-6/FR-7 exactly as tabled in §4 above: actor-kind branch, status-gating switch, FR-5 visibility check, `body` length validation (reuse `ValidationFailedError`/`FieldError`), attachment-ownership loop reused against the new `bind_to_reply`, the new 30/hour rate limit, `first_response_at` stamping, and the two post-commit email dispatches. New Protocols: `TicketReplyRepositoryProtocol`, extended `AttachmentRepositoryProtocol` (add `bind_to_reply`), extended `TicketRepositoryProtocol` (add `update`), a reply-rate-limit-cache Protocol. New method for `GET`'s composition: loads the ticket, checks ownership/scope, calls `list_for_ticket`, returns `TicketDetailRead`. | T4, not started. |
| `app/modules/support/router.py` | Two new routes: `POST /support/tickets/{id}/replies`, `GET /support/tickets/{id}` — both using `get_rls_session`-backed collaborators (§2), `response_model`/`status_code` declared on each, `limit: Annotated[int, Query(ge=1, le=100)] = 50` on the `GET` route (§10). Agent-branch authorization uses `require_scope("tickets:write")` / `require_scope("tickets:read")` (`app.modules.roles.dependencies`) — first import of that factory into this module. | T5, not started. |
| `app/modules/support/dependencies.py` | New `get_rls_session` dependency (§2 above); new service provider wiring for the reply-handling collaborators; `TicketReplyServiceDep` (or extended `TicketServiceDep`, per the service.py split decided during IMPLEMENTATION). | T5, not started. |
| `app/modules/support/schemas.py` | New `CreateReplyRequest`, `ReplyRead`, `ReplyThreadPage`, `TicketDetailRead` (`openapi` v3 `components.schemas`, field lists exactly as specified there). Existing `TicketRead`/`TicketListResponse`/`CreateTicketRequest` unchanged — `TicketDetailRead` is additive, not a rename. | T1, already `PASS`. |
| `app/modules/support/exceptions.py` | New `TicketNotFoundError` (404, FR-4 — this module's own copy, following the `AccountDeactivatedError`/`admin_users.NotFoundError` precedent); new module-owned `InsufficientPermissionError` (403, §6 above); new `TicketClosedError` (409, FR-6, `type_slug="ticket-closed"` — new slug, first use in this codebase); new `TicketReplyRateLimitError` (429 + `Retry-After`, mirroring `TicketCreationRateLimitError`'s `__init__` shape but a distinct class/detail text). | T5, not started. |
| `app/core/email.py` | `EmailSender` Protocol: two new methods (§8 above). `LoggingEmailSender`: matching implementations, log-only, never logging `to`/body content. | T4, not started. |
| `app/core/config.py` | New `support_queue_email: str = "support-queue@portal.internal"` field (§9 above). **NEW (v2):** new `runtime_database_url: str` field (§12 above), dev-only default, mirroring `jwt_secret_key`. | T4/T5 for OD-2's field; new runtime-role wiring is a separate, cross-cutting task (§12). |
| `.env.example` | New `SUPPORT_QUEUE_EMAIL=support-queue@portal.internal` entry. **NEW (v2):** new `RUNTIME_DATABASE_URL=...` entry (§12). | — |
| **`app/main.py`** (NEW, v2) | `lifespan()`'s `create_engine_and_sessionmaker(settings.database_url)` → `create_engine_and_sessionmaker(settings.runtime_database_url)` — the one line that switches the running application to the new role. | §12. Not previously in this plan's footprint — first file this story touches outside `app/modules/support/` and `app/core/`. |
| **`tests/conftest.py`** (NEW, v2) | `_database` fixture: after `command.upgrade(alembic_cfg, "head")`, run `scripts/db/provision_runtime_role.sql`'s statements against the owner-role `engine`, then build a second engine/session_factory from an `app_runtime`-credentialed URL and assign it to `app.state.db_engine`/`db_session_factory` instead of the owner-role one. | §12. Shared test infrastructure, not scoped to one module — flagged for `IMPLEMENTATION_PLANNING` to assign explicitly, since it doesn't fit any of the four builder skills' usual file footprint. |
| `migrations/env.py` | One-line `# noqa: F401` model-registration import (no new columns/classes need a *separate* import — `TicketReply` lives in the already-imported `app/modules/support/models.py`, so this may in fact need **no** change at all). **Flagged per this skill's own instructions** as a file `AGENTS.md` §7.9 protects, even though the actual diff here is expected to be zero-line (verify during IMPLEMENTATION before assuming any edit is needed). **NEW (v2) confirmation:** `env.py` reads `get_settings().database_url` (the owner-role URL) — Architectural Change #12 does not touch this, since Alembic must keep running as the owner role; still zero-diff expected. | Protected file (§7.9). |

No other existing file changes. `app/api/v1/router.py` needs no change — the
two new routes are added to the same `support_router` object already
registered there (US-4.1).

## Risks

1. **RLS is new to this codebase.** `FORCE ROW LEVEL SECURITY` is mandatory
   (the application's single DB role owns the table) — omitting it makes
   every policy a silent no-op for every request. Mitigated by: db-design
   v3's explicit call-out, a migration-proof `upgrade → downgrade → upgrade`
   cycle, and a dedicated test querying through a customer-context connection
   with the application-layer filter deliberately disabled (the NFR's own
   requirement, `test-writer`'s to write).
2. **`SET LOCAL` session-context dependency is a new mechanism with no
   precedent in this codebase.** If `get_rls_session` is not wired onto
   *every* code path that touches `ticket_replies` (both new routes, and any
   future one), the RLS policy's fail-closed behavior means internal notes
   would become invisible to agents too (over-hiding), not leaked — a
   safe-direction bug, but still a functional regression. Mitigated by
   scoping the dependency narrowly (§2) so there are exactly two call sites
   to get right, both created by this same story.
3. **API_DESIGN Open Question #1 (customer reply on `"open"`/`"waiting_on_support"`).**
   Not resolved by any FR/AC; this plan's §4 makes the conservative choice
   (no status write, reply still accepted) rather than inventing a
   transition. If a stakeholder later decides a transition is needed there,
   that is a spec revision, not a bug in this plan.
4. **`migrations/env.py`** — protected file (`AGENTS.md` §7.9); flagged
   per §"Files To Modify" above. Expected zero-diff since `support/models.py`
   is already registered by US-4.1; `migration-manager` confirms this rather
   than assuming it.
5. **Carried DESIGN_REVIEW finding DR-2 — resolved, not a live risk.**
   `docs/catalog/US-4.2-pipeline-status.md` v2 confirms plain `CREATE INDEX`
   (no `CONCURRENTLY`) was correct: no production write path populates
   `attachments` yet. Retained here only for traceability; `migration-manager`
   need not revisit it.
6. **Two rate limits, two Valkey keys, same window shape.** Risk of an
   implementation accidentally sharing one counter between ticket creation
   and replies (silently exhausting one user-facing limit against the
   other's traffic). Mitigated by the distinct key-builder function (§7) and
   a unit test asserting the two keys never collide for the same user.
7. **NEW (v2) — Switching the application's entire runtime connection role
   is a blast radius wider than this story's own module.** Every request
   this application serves, in every module, now runs under `app_runtime`
   instead of `postgres`. A privilege the app actually needs but this plan's
   `GRANT` list omits would surface as a runtime failure in an unrelated
   module (e.g. `users` registration), not in `support`. Mitigated by:
   granting the same CRUD (`SELECT`/`INSERT`/`UPDATE`/`DELETE` + sequence
   `USAGE`/`SELECT`) the app already exercises on every table today — no new
   restriction beyond removing `SUPERUSER`/`BYPASSRLS`/ownership, which the
   app's own code never relies on (it never issues DDL, never bypasses its
   own `WHERE` clauses on purpose) — and by running the **entire** existing
   test suite (not just `support`'s) against the new role as part of
   Validation Strategy below, before this change is considered proven.
8. **NEW (v2) — Role/privilege provisioning is now a required per-environment
   step outside the application's own control.** If `scripts/db/provision_runtime_role.sql`
   is never run against a given environment (a fresh staging DB, a new
   engineer's local Postgres), `runtime_database_url`'s dev-only default
   references a role that doesn't exist; `create_async_engine` doesn't
   connect eagerly, so the failure surfaces on the **first real query**, not
   at startup — a worse failure mode than a config-load-time error. Mitigated
   for this repository's own CI/local-dev path by making `tests/conftest.py`
   run the same script automatically every test session (Architectural
   Change #12), so the harness's own test suite never depends on a human
   remembering the step; documenting the step for real deployments is
   `documentation-and-adrs`'s job, flagged but out of this plan's scope.

## Validation Strategy

- `pre-commit run --all-files` — Ruff format/lint, mypy `strict` on `app
  tests`, secret scan. No `Any`, explicit `-> *Read` annotations on every
  service method returning a schema, including the two new ones. **NEW
  (v2):** secret scan must not flag `scripts/db/provision_runtime_role.sql`'s
  password placeholder as a real committed credential — use an obvious
  non-secret placeholder token, never a plausible-looking password string.
- `lint-imports` — unchanged module boundary, still `exhaustive=true`; no
  new file added outside the existing `support` layer set, so no new
  contract entry is needed. `support.router` gaining an import from
  `app.modules.roles.dependencies` must still satisfy `router → dependencies`
  only (it's a `Depends(...)` factory call, the same shape as the existing
  `reject_agent_queue_access` import path — not a layering violation).
- `alembic upgrade → downgrade → upgrade` — proves the new table, the two
  additive columns, and — the highest-risk part — that the RLS `CREATE
  POLICY`/`ENABLE`/`FORCE` statements are actually reversible
  (`downgrade()` drops the policies and disables RLS, not `pass`). Already
  executed and passed for `9132a68b73c8` (T3) — no re-run required by this
  revision (Architectural Change #12).
- OpenAPI renders and matches `US-4.2-openapi.yaml` v3's endpoint/schema
  shapes (`response_model`/`status_code` declared on both new routes).
- **NEW (v2) — the full existing test suite, not just `support`'s, must pass
  against the new `app_runtime`-connected `tests/conftest.py` fixture**
  before this architectural change is considered proven (Risk 7): every
  other module's integration tests are the actual evidence that
  `app_runtime`'s privilege grant is complete, not a review of the `GRANT`
  statements by inspection.
- Manual/integration confirmation that `FORCE ROW LEVEL SECURITY` actually
  blocks the owning application role — the one guarantee unit tests and a
  schema diff alone cannot prove. **This is now the two already-written
  direct-RLS integration tests re-run against the `app_runtime`-connected
  fixture (Architectural Change #12), not a new test.**

## Testing Strategy

Per `AGENTS.md` §5: unit tests use hand-written fakes (never `MagicMock`);
integration tests run against real PostgreSQL/Valkey, no
`unittest.mock`/`monkeypatch` on infrastructure. Test files are
`test-writer`'s output; restated here for traceability against
impact-analyzer's survey.

- **Unit** — `tests/unit/modules/support/test_support_schemas.py` (new
  schemas: `extra="forbid"` on `CreateReplyRequest`, length caps, defaulting
  behavior). `tests/unit/modules/support/test_support_service.py` gains
  cases for: the full actor-kind × status-gating matrix in §4 (including the
  deliberate no-op branch), FR-5's visibility rejection (asserting it is
  raised from the service check, not from a caught `IntegrityError`),
  attachment reply-binding ownership/race paths, the new rate limit's
  independence from the ticket-creation limit (Risk 6), `first_response_at`
  stamped exactly once, and both email dispatches best-effort-after-commit
  (a failure in either must not raise past the return). **Unaffected by v2**
  — the runtime-role change is infrastructure, not service logic.
- **Integration** — `tests/integration/modules/support/test_support_router.py`
  gains TR-AC1 through TR-AC7 end-to-end against real PG/Valkey, plus the
  NFR's own RLS-specific test (customer-context connection, application
  filter deliberately disabled, confirming the database layer alone hides
  `visibility='internal'` rows). Already written
  (`test_internal_reply_hidden_from_customer_context_by_rls_alone`,
  `test_no_actor_kind_set_defaults_to_hiding_internal_reply`,
  `test_agent_context_sees_internal_reply_via_rls`) — **no test rewrite
  needed**; they are expected to pass once `tests/conftest.py`'s fixture
  change (Architectural Change #12) serves requests through `app_runtime`
  instead of the container's bootstrap superuser. A migration proof (via
  `migration-manager`'s own upgrade/downgrade/upgrade cycle) covering the RLS
  DDL specifically — already executed for T3, not repeated by this revision.
- **NEW (v2) — full-suite regression pass.** Every other module's existing
  integration test file (`tests/integration/modules/{users,roles,admin_users,
  audit,profile}/...`) must be re-run once `tests/conftest.py` switches to
  `app_runtime`, as the actual proof the provisioning script's `GRANT` list
  is complete (Risk 7) — not a new test file, a re-run of what already
  exists.
- **Coverage** — 85% floor overall, 90%+ on `service.py`/`router.py`, per
  `AGENTS.md` §5/§6. No coverage exclusion for the new RLS-guarded code
  path — it is exercised by the dedicated RLS integration test above.
