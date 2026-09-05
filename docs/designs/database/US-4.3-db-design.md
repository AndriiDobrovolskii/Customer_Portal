---
artifact_type: database_design
story: US-4.3
version: 3
status: DRAFT
created_at: "2026-09-06T12:00:00Z"
updated_at: "2026-09-06T17:00:00Z"
produced_by: db-designer
inputs:
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
  - path: docs/reviews/designs/US-4.3-design-review.md
    version: 2
supersedes: docs/designs/database/US-4.3-db-design.md
---

# DB Design: Ticket Resolution (US-4.3 / spec US-4.3)

**Generated:** 2026-09-06 (revised 2026-09-06 after DESIGN_REVIEW CHANGES_REQUIRED v1 (DR-1/DR-2) and v2 (DR-4))
**Source spec:** docs/specifications/US-4.3-spec.md (version 2)
**API design:** docs/designs/api/US-4.3-api-design.md, US-4.3-openapi.yaml (version 2)
**Design review:** docs/reviews/designs/US-4.3-design-review.md (CHANGES_REQUIRED, version 2) — DR-4 (FR-4's reply-driven reopen wrote no `audit_log` entry, contradicting the story's Data Model Notes and project-wide NFR-006) addressed in this revision. DR-1/DR-2 (v1) were confirmed corrected by v2 of the review and needed no further change here. DR-3 (`resolution_note` `maxLength`) remains API-Design-owned. DR-5/DR-6/DR-7 (v2) are Minor/non-blocking and are not addressed in this revision.

## Overview

Four additive, nullable columns on the existing `tickets` table
(`resolved_at`, `resolution_note`, `closed_at`, `closed_by`), one corrected
`CHECK` constraint (see below — the story's own literal text would break its
own FR-2/FR-3), one new partial index for the auto-close job's scan, and
writes into the existing `audit_log` table (no new table — same precedent
`US-4.1-db-design.md` and `US-4.2-db-design.md` already established: this
project's `ticket_audit_log` language always means a new `audit_log` event
type, never a dedicated table). No table is dropped or narrowed. No `attachments`
or `ticket_replies` change.

## Existing table: `tickets` — additive columns only

- **`resolved_at`**: `DateTime(timezone=True)`, `nullable=True`, no default
  (starts `NULL`). Set once by a successful `/resolve` (FR-1). Cleared by a
  successful `/reopen` (FR-5) or by an FR-4 reopening reply — **not** cleared
  by `/close` (FR-2) or the auto-close job (FR-3): neither FR mentions
  clearing it, and keeping it is the only way a closed ticket's "when was
  this resolved" reporting value survives closure. This drives the `CHECK`
  correction below.
- **`resolution_note`**: `String(5000)`, `nullable=True`, no default. Set
  once by a successful `/resolve` (FR-1, FR-10's non-empty requirement is
  enforced at the Pydantic boundary per `US-4.3-api-design.md`, not
  re-enforced here beyond `NOT NULL` when resolved). **Length resolves
  `US-4.3-api-design.md` Open Questions #3** (no `maxLength` stated by any
  FR or the source's Data Model Notes): matches `Ticket.body`'s and
  `TicketReply.body`'s existing `String(5000)` cap exactly — the same
  free-text, customer/agent-visible content category, not a new size
  invented for this column. `schema-builder` should set
  `ResolveTicketRequest.resolution_note`'s Pydantic `max_length` to `5000`
  to match. Like `resolved_at`, it is never cleared once set — no FR
  instructs otherwise, and it remains readable as history after a reopen or
  close.
- **`closed_at`**: `DateTime(timezone=True)`, `nullable=True`, no default.
  Set once, by whichever of `/close` (FR-2) or the auto-close job (FR-3)
  reaches `"closed"` first. Never cleared: `"closed"` is the terminal state
  (State Machine table, `closed | — | (terminal)`) — no code path this story
  builds ever transitions a ticket out of `"closed"`, so unlike
  `resolved_at`, this column's own `CHECK` (below) can stay a true
  biconditional without conflict.
- **`closed_by`**: `Mapped[uuid.UUID | None]`, `nullable=True`, **no
  `ForeignKey`**. Set once, to the acting user's id for `/close` (FR-2,
  requester or agent, OD-7) or to a well-known **system-actor sentinel
  UUID** for the auto-close job (FR-3, OD-7). Deliberately not
  `ForeignKey("users.id")`, unlike every other "acting user" column in this
  module (`requester_id`, `uploaded_by`, `TicketReply.author_id`): a real FK
  would reject the sentinel value outright, since no `users` row exists (or
  should exist) for "the system." This mirrors `audit_log.actor_id`'s
  existing no-FK convention (`US-3.3-db-design.md`) for the identical reason
  — a column that must sometimes hold a non-real-user actor. **Resolves
  OD-7** by picking the "reserved sentinel UUID" branch of its own
  recommendation over the "nullable FK + `closed_by_kind` discriminator"
  branch: the sentinel keeps this to one column (no new discriminator the
  spec doesn't mention) and reuses a pattern this codebase already has,
  rather than inventing one. The sentinel's exact value (e.g.
  `UUID("00000000-0000-0000-0000-000000000000")`) and where it is declared
  as a shared constant are `IMPLEMENTATION_PLANNING`/`service-and-router-builder`
  calls, not decided further here — this design only fixes the column's
  type, nullability, and the requirement that it hold *some* non-null UUID
  whenever `status = "closed"`.
  **Implication for `app/modules/audit/service.py`:** `record_event`'s
  `actor_id: uuid.UUID` parameter is already non-optional and already
  accepts any UUID value, so the same sentinel can be passed there for the
  `ticket_auto_closed` audit write (see below) without any signature change
  — `_resolve_actor_role` will simply resolve no roles for it (empty grant
  list → `actor_role = NULL`), which is an existing, harmless code path
  ("not every event populates every field," `US-3.3-db-design.md`), not a
  new one this story adds.

### `CHECK` constraints (Data Model Notes) — one corrected, one adopted verbatim

The story's own Data Model Notes state two `CHECK` expressions. One is
adopted exactly as written; the other, read literally, would make FR-2 and
FR-3 impossible to satisfy and is corrected here — flagged for
`DESIGN_REVIEW` to confirm, the same posture `US-4.3-api-design.md` already
took for its own two Open Questions.

**`closed_at`/`closed_by` — adopted verbatim, as a true biconditional:**

```python
CheckConstraint(
    "(status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL)",
    name="ck_tickets_closed_requires_closed_fields",
)
```

Safe as a biconditional specifically because `"closed"` is terminal (see
above) — once true, `status = 'closed'` and
`closed_at IS NOT NULL AND closed_by IS NOT NULL` never diverge again for
that row.

**`resolved_at`/`resolution_note` — corrected from a biconditional to a
one-directional implication:**

The story's literal text is
`CHECK ((status = 'resolved') = (resolved_at IS NOT NULL AND resolution_note IS NOT NULL))`.
Read as PostgreSQL boolean equality, this requires the *reverse* direction
too: whenever `status != 'resolved'`, at least one of `resolved_at` /
`resolution_note` must be `NULL`. But FR-2 (`/close` on a currently
`"resolved"` ticket — the State Machine table's "any non-closed → close"
row includes `"resolved"` as a source) and FR-3 (auto-close, source is
always `"resolved"`) both transition straight from `"resolved"` to
`"closed"` **without clearing either field** — neither FR mentions doing
so, and per the column notes above, clearing them would destroy the "when
was this resolved" value a closed ticket's history should retain. Under the
literal biconditional, that transition trips the constraint the instant the
`UPDATE` sets `status = 'closed'` while `resolved_at`/`resolution_note`
remain non-null from the earlier `/resolve` — every FR-2/FR-3 closure of a
resolved ticket would violate its own `CHECK`. (FR-4/FR-5's reopen paths do
not have this problem: both explicitly clear `resolved_at`, which alone
makes the biconditional's RHS `false` and keeps it consistent with the new,
non-`"resolved"` status — `resolution_note` surviving unchanged is
irrelevant once `resolved_at` is `NULL`.)

The fix keeps the constraint's actual intent — a `"resolved"` ticket always
carries both fields — without forcing them to be cleared on every other
transition:

```python
CheckConstraint(
    "status != 'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)",
    name="ck_tickets_resolved_requires_resolution_fields",
)
```

This is a one-directional implication (`status = 'resolved' → both set`),
not a biconditional: it still fails a resolve that somehow omits either
field, but it no longer fails a later close/auto-close that leaves the
already-set fields in place. `DESIGN_REVIEW` should confirm this
correction is intended, not just convenient — same caveat this story's own
API design already carries for its two Open Questions.

## Partial index for the auto-close job's scan (Data Model Notes)

```python
Index(
    "ix_tickets_resolved_at_pending_autoclose",
    "resolved_at",
    postgresql_where=text("status = 'resolved'"),
)
```

Matches the Data Model Notes verbatim ("Partial index `(resolved_at) WHERE
status = 'resolved'` — the auto-close job scans exactly this") and the same
partial-index shape `attachments.ix_attachments_created_at_unbound`
(`US-4.1-db-design.md`) already established in this module for an
identical "batch job scans only the rows it might act on" access pattern.
The job's query is `WHERE status = 'resolved' AND resolved_at <
now() - interval '7 days'` (FR-3's strict `>`, OD-4 as resolved by the
human at `HUMAN_SPEC_APPROVAL`) — this index serves that predicate
directly; no separate plain index on `resolved_at` is added, since every
read of this column outside the job is a single-row lookup by `id` that
doesn't need it.

**DR-1 correction:** version 1 of this design stated the predicate as
`resolved_at <= now() - interval '7 days'`, an inclusive comparison that
contradicted its own cited "FR-3's strict `>`" requirement and collided
with the reply/reopen guard's own inclusive boundary at exactly the 7-day
instant. Corrected to the strict form above (`resolved_at <
now() - interval '7 days'`, equivalently `now() - resolved_at >
interval '7 days'`), matching FR-3's literal text
(`now - resolved_at > 7 days`) and OD-4's human-confirmed assignment.

## Audit trail: writes into the existing `audit_log` table (no new table)

Same architecture `US-4.1-db-design.md` established and `US-4.2-db-design.md`
did not need to revisit: `audit_log` (`app/modules/audit/models.py`,
`US-3.3-db-design.md`) is the write target for every new event type; this
story's four `ticket_audit_log` mentions are four new `event` values on that
one table, written via the existing `app/modules/audit/service.py`
`record_event(...)` generic path (US-4.1's own addition, already
service-to-service per `AGENTS.md` §3 — no new audit-module method is
needed).

| FR | `event` | `actor_id` | `actor_role` | `target_id` | `outcome` | `payload` |
|---|---|---|---|---|---|---|
| FR-1 | `ticket_resolved` | resolving agent's id | resolved via `_resolve_actor_role` | `ticket.id` | `"success"` | `NULL` |
| FR-2 | `ticket_closed` *(name inferred, see below)* | closing user's id (requester or agent) | resolved via `_resolve_actor_role` | `ticket.id` | `"success"` | `NULL` |
| FR-3 | `ticket_auto_closed` | system-actor sentinel UUID (see `closed_by` above) | `NULL` (no role grants resolve for the sentinel) | `ticket.id` | `"success"` | `NULL` |
| FR-4 | `ticket_reopened` *(reused, see DR-4 below)* | replying requester's id | resolved via `_resolve_actor_role` (`self`) | `ticket.id` | `"success"` | `NULL` |
| FR-5 | `ticket_reopened` | reopening user's id (requester or agent) | resolved via `_resolve_actor_role` | `ticket.id` | `"success"` | `NULL` |

- **`category`**: `"tickets"` for all four — the same literal US-4.1 already
  wrote for `ticket_created`, not a new one.
- **FR-2's event name is not literally stated** by the spec (FR-1/FR-3/FR-5
  each name their event explicitly; FR-2 only states the `actor` values).
  `ticket_closed` is inferred directly from the naming pattern every sibling
  FR in this same story already uses (`ticket_<verb, past tense>`) — a
  structural completion of an evident convention, not a new business
  decision. Flagged for `DESIGN_REVIEW` to confirm the literal string, the
  same way this design flags its other two inferences.
- **`payload` is `NULL` for all four events**, matching `US-4.1-db-design.md`'s
  own reasoning for `ticket_created`: `resolution_note` is free-text
  content already stored on `tickets` and reachable via `target_id` —
  duplicating it into `audit_log.payload` would repeat exactly the mistake
  that design's DR-1 finding flagged (columns/payload no requirement asks
  for). No FR requires any of these four events to carry a payload.
  `request_id`/`ip`/`user_agent` are `NULL` for the same reason FR-1 through
  FR-5 never mention capturing them, matching `record_event`'s existing
  `None`-for-all-three call shape (unchanged from US-4.1's usage).
- **FR-4 (reply reopens a resolved ticket) now writes an `audit_log` entry —
  DR-4 correction.** Version 2 of this design left FR-4 unaudited because
  neither the spec's FR-4 text nor the source story's TC-AC4 names a
  `ticket_audit_log` entry for this path (only "a notification is sent").
  `DESIGN_REVIEW` v2 (DR-4, Critical) found that silence insufficient: the
  source story's own normative Data Model Notes state `ticket_audit_log`
  "records every transition, including system-driven ones," and
  `docs/product/non-functional-requirements.md` NFR-006 ("every mutation...
  is audited") applies project-wide without needing a per-FR restatement.
  FR-4 performs the *same* `resolved` → `waiting_on_support` transition
  (`resolved_at` cleared) that FR-5 performs directly and audits as
  `ticket_reopened` — auditing one path and not its functional twin is an
  inconsistency this design introduced, not one the spec asked for. Per the
  review's option (a), this revision reuses `event=ticket_reopened` (not a
  new event string) for FR-4's write, since it is the identical transition
  FR-5 already names — the same "structural completion from a sibling FR"
  reasoning this design already applied to infer `ticket_closed`'s name.
  `actor_id` is always the replying requester's id: FR-4's text is scoped to
  "when the requester posts a reply" only (no agent-reply branch is
  described by any FR), so `actor_role` resolves to `self` via the existing
  `_resolve_actor_role`, with no agent branch to add. **Call-site note:**
  this write is issued from the existing US-4.2 reply-creation service path
  (`POST .../replies`) as part of the same status-transition side effect
  `US-4.3-api-design.md` already documents narratively on that endpoint, in
  the same transaction as the conditional `tickets` `UPDATE` (DR-2's
  window-scoped `WHERE` clause, below) — not new tickets-service code. This
  is a service-layer wiring detail for `IMPLEMENTATION_PLANNING`/
  `service-and-router-builder`; the schema requirement this design fixes is
  only that a fifth `record_event(...)` call site now exists, writing the
  same `event` value FR-5 already writes.
- **Cross-module layering note (unchanged precedent, restated for this
  story):** the tickets service calls `app/modules/audit/service.py`'s
  `record_event(...)` inside the same transaction as its own `tickets`
  `UPDATE`, per `AGENTS.md` §3's "cross-module calls go service → service"
  rule — it does not import `AuditRepository`/`AuditLog` directly. No new
  audit-module code is needed; `record_event` already exists and is
  already used exactly this way by `US-4.1`.
- **No new index on `audit_log`** — `US-3.3-db-design.md`'s existing
  `(occurred_at DESC, actor_id, event)` covering index already supports a
  future "this event type" or "this actor's history" query over these four
  new `event` values the same way it does every other type; no FR in this
  story reads `audit_log` back.

## The `reason` field on `/close` and `/reopen` — not persisted

`US-4.3-api-design.md` (Open Questions #4) carries the source story's
`{"reason"?: str}` field through as accepted-but-unconstrained, since no FR
describes its purpose, persistence, or audit visibility. Consistent with
this skill's own constraint against inventing a column the spec doesn't
support: **no `tickets` column and no `audit_log.payload` entry is added
for it here.** If a future decision persists it, `audit_log.payload`
(`JSONB`, already present on the table) is the natural home — no schema
change would be needed, only a service-layer decision to populate it — not
a new `tickets` column. Deferred, not decided.

## Relationships / loading strategy

No new relationship. `Ticket` continues to declare no `relationship()`
(unchanged, `US-4.1-db-design.md`/`US-4.2-db-design.md` precedent) — every
read this story's three endpoints perform is a single-row lookup by `id`,
and `record_event`'s audit write is an independent single-row insert issued
by the tickets service in the same transaction, not a graph traversal.

## Indexes (summary)

- `tickets`: new partial index `ix_tickets_resolved_at_pending_autoclose` on
  `resolved_at` `WHERE status = 'resolved'` (above). No other new index —
  `closed_at`/`closed_by`/`resolution_note` are never filtered or sorted on
  by any AC.
- No new index on `audit_log` (above).

## Sensitive columns

None of the four new columns hold a password, token, or MFA secret.
`resolution_note` is free-text agent-authored content shown to the
requester, the same category as `Ticket.body`/`TicketReply.body` — plain
text only (no rendering pipeline, consistent with this module's existing
convention), no PII beyond what `tickets` already stores. `closed_by`'s
system-actor sentinel is a fixed, non-secret constant, not user data.

## Concurrency (FR-9)

No new mechanism: the conditional `UPDATE ... WHERE id = :id AND status IN
(...)` pattern the spec's own Assumptions & Defaults #6 cites ("mirrors
US-1.2 FR-1 and US-1.4 FR-1/FR-9") applies unchanged to `/resolve`, `/close`,
and `/reopen` alike, scoped to each endpoint's own valid source-status set
(OD-5 for `/resolve`; the State Machine table's other rows for `/close` and
`/reopen`). No `SELECT ... FOR UPDATE` or other locking construct is
introduced — a losing `UPDATE` simply affects zero rows, which the service
distinguishes from "ticket not found" only by having already resolved the
ticket's existence in the same request (per `US-4.3-api-design.md`'s check
order).

**DR-2 correction — the 7-day window is part of the same conditional
`UPDATE`, not a separate check:** for `/reopen` (FR-5) and for FR-4's
reply-driven transition (the existing `POST .../replies` endpoint's status
side effect, `US-4.2`), the source-status predicate alone is not
sufficient: FR-9's NFR requires "the 7-day window MUST be evaluated by the
database, in the same statement that performs the write, from a single
shared constant." Version 1 of this design left that predicate unstated,
which would have permitted an implementation that reads `resolved_at`,
evaluates the window in application code, and issues a status-only
conditional `UPDATE` — violating the NFR. Both transitions' `WHERE` clause
must therefore read:

```sql
WHERE id = :id
  AND status = 'resolved'
  AND resolved_at >= now() - interval '7 days'
```

(inclusive comparison, OD-4 as resolved by the human at
`HUMAN_SPEC_APPROVAL` — matching FR-4's and FR-5's literal
`now - resolved_at <= 7 days` text) evaluated in the same `UPDATE` statement
that sets `status = 'waiting_on_support'` and clears `resolved_at`. A
losing `UPDATE` here (zero rows affected because the window predicate now
fails) is what makes the auto-close job's own conditional `UPDATE` — scoped
to `status = 'resolved' AND resolved_at < now() - interval '7 days'`,
DR-1 above — mutually exclusive with these two: at exactly the 7-day
boundary instant, the job's strict `<`/`>` and these two transitions'
inclusive `>=`/`<=` can never both match the same row, which is the whole
point of OD-4's strict/inclusive split. `/resolve` and `/close` carry no
window predicate — neither transitions out of a time-boundedly-eligible
`"resolved"` state on the window itself, only on `status IN (...)`.

## Explicitly deferred / not decided here

1. **The system-actor sentinel UUID's literal value and where it is
   declared as a shared constant** — fixed at `IMPLEMENTATION_PLANNING`/
   `service-and-router-builder`, not here; this design only fixes that
   `closed_by` and `record_event`'s `actor_id` argument for FR-3 must both
   receive the same non-null, non-real-user UUID.
2. **`ticket_closed`'s literal event-name string** — inferred here from the
   sibling FRs' naming pattern, not stated by any FR. `DESIGN_REVIEW` v1
   independently confirmed this inference sound, alongside the `CHECK`
   correction above; neither needs further loop-back.
3. **The `reason` field's persistence**, if a future story or revision
   decides it needs one — see above; no schema change would be required,
   only a service-layer decision to write it into `audit_log.payload`.
4. **`US-4.3-api-design.md` Open Questions #1 and #2** (the undefined
   response for a `"resolved"`-but-expired-not-yet-auto-closed ticket, and
   the FR-6 `409` generalization) are API/contract-shape questions, not
   schema ones — this design's columns, constraints, and indexes are
   identical regardless of how either resolves, so they are not repeated
   here; `DESIGN_REVIEW` v1 left Open Questions #1 as an inherited, accepted
   non-blocking Low finding and confirmed #2's generalization reasonable —
   neither is repeated here.
5. **DR-1 and DR-2 (`DESIGN_REVIEW` v1)** — both corrected in the prior
   revision (job predicate strict `<`; `/reopen`'s and FR-4's conditional
   `UPDATE` `WHERE` clause states the 7-day window explicitly) and confirmed
   sound by `DESIGN_REVIEW` v2 — no further change here. DR-3
   (`resolution_note` `maxLength`) was API-Design-owned and was addressed by
   `API_DESIGN`'s own v2 revision, not here.
6. **DR-4 (`DESIGN_REVIEW` v2, this revision)** — corrected above: FR-4 now
   writes `event=ticket_reopened` to `audit_log`, matching FR-5's identical
   transition. DR-5/DR-6/DR-7 (Minor, non-blocking) are left for the next
   natural revision of `API_DESIGN`/`migration-manager` per the review's own
   advisory treatment, not addressed here.
