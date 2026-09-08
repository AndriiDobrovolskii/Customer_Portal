import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# US-4.3 Decision 5: `closed_by`'s system-actor sentinel (OD-7) and the
# auto-close job's `audit_log.actor_id` must be the same value. Declared here
# (not service.py) so scripts/auto_close_resolved_tickets.py, which imports
# models/repository only, need not import service.py just for this constant.
SYSTEM_ACTOR_ID: Final = uuid.UUID("00000000-0000-0000-0000-000000000000")


class Ticket(Base):
    """`ticket_number` is server-computed from a hand-written migration's
    `ticket_number_seq` SEQUENCE + column DEFAULT expression
    (`server_default=FetchedValue()`, same style as `AuditLog.previous_hash`)
    — never set by application code. `requester_id` carries no `ondelete`
    (defaults to `RESTRICT`): BR-007's account-erasure job mechanics are
    pending legal/DPO sign-off, so this is a deliberate placeholder, not an
    oversight (US-4.1-db-design.md).
    """

    __tablename__ = "tickets"
    __table_args__ = (
        # FR-2 keyset pagination, "this customer's tickets, newest first";
        # `id` breaks ties within the same `created_at` value.
        Index(
            "ix_tickets_requester_id_created_at_id",
            "requester_id",
            "created_at",
            "id",
        ),
        # US-4.3 FR-3: the auto-close job's scan - partial index so it never
        # scans tickets that aren't currently resolved.
        Index(
            "ix_tickets_resolved_at_pending_autoclose",
            "resolved_at",
            postgresql_where=text("status = 'resolved'"),
        ),
        # US-4.3: `"closed"` is terminal (US-4.3-db-design.md), so this stays
        # a true biconditional without ever conflicting with a later update.
        CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL)",
            name="ck_tickets_closed_requires_closed_fields",
        ),
        # US-4.3: one-directional implication, not a biconditional - FR-2/
        # FR-3 both transition a resolved ticket to closed without clearing
        # resolved_at/resolution_note (US-4.3-db-design.md "CHECK
        # constraints" - the literal biconditional would break both).
        CheckConstraint(
            "status != 'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)",
            name="ck_tickets_resolved_requires_resolution_fields",
        ),
        # US-4.4 FR-1 (AQ-AC1): the default, filterless agent queue - every
        # ticket not "closed", ordered oldest-updated first. Partial so the
        # index only ever holds rows the default query (and any non-closed
        # status=X filter) can match. Predicate MUST be written as the
        # literal `status != 'closed'` (never `.in_([...])`) - PostgreSQL's
        # partial-index predicate-implication check reliably proves a `<>`
        # comparison but not a semantically-equivalent `IN`-list
        # (US-4.4-db-design.md "Indexes"), so `list_for_agent_queue`'s
        # default branch must match this predicate form exactly.
        Index(
            "ix_tickets_queue_default_updated_at_id",
            "updated_at",
            "id",
            postgresql_where=text("status != 'closed'"),
        ),
        # US-4.4 FR-2 (AQ-AC2): an explicit status=X filter, any of the five
        # values including "closed".
        Index(
            "ix_tickets_status_updated_at_id",
            "status",
            "updated_at",
            "id",
        ),
        # US-4.4 FR-2: assignee_id=<uuid>/assignee_id=me (equality) and
        # assignee_id=none (IS NULL - a btree index serves this directly,
        # NULLs are indexed and sortable). No separate single-column index on
        # assignee_id - this composite index's leading column already serves
        # that lookup (same precedent as ticket_replies.ticket_id).
        Index(
            "ix_tickets_assignee_id_updated_at_id",
            "assignee_id",
            "updated_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, server_default=FetchedValue()
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(String(5000), nullable=False)
    # No enum/CHECK — OD-3's valid value list is an unresolved stakeholder
    # decision, not an inferable one.
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # Stamped once, on the first public agent reply (FR-1) - a plain
    # timestamp for later reporting, no SLA target evaluated. No index: no
    # AC filters or sorts by this column (US-4.2-db-design.md).
    first_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # US-4.3 FR-1: set once by /resolve; cleared by /reopen (FR-5) or an
    # FR-4 reopening reply; not cleared by /close or the auto-close job.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # US-4.3 FR-1: set once by /resolve; never cleared. Length matches
    # Ticket.body/TicketReply.body's existing String(5000) cap.
    resolution_note: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    # US-4.3 FR-2/FR-3: set once, by /close or the auto-close job. Never
    # cleared - "closed" is terminal.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # US-4.3 FR-2/FR-3, OD-7: the acting user's id (/close) or SYSTEM_ACTOR_ID
    # (auto-close job). Deliberately no ForeignKey, unlike every other
    # "acting user" column here - a real FK would reject the sentinel value,
    # since no `users` row exists for "the system" (mirrors
    # audit_log.actor_id's existing no-FK convention).
    closed_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # US-4.4 FR-3/FR-4: set by a successful POST .../assign (including
    # re-assignment), cleared by a successful DELETE .../assign. No
    # `ondelete` override (RESTRICT-by-default) - the identical BR-007
    # account-erasure placeholder already used for requester_id/uploaded_by
    # (US-4.1-db-design.md). No CHECK ties this to `status`: a ticket closed
    # while assigned keeps its assignee_id after closure (US-4.4-db-design.md
    # "No CHECK constraint ties assignee_id to status").
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class TicketReply(Base):
    """No `relationship()` to `Ticket`/`User` - matches this module's
    existing precedent of direct repository queries over ORM graph
    traversal (US-4.2-entity-model.md "Relationships"). Row Level Security
    (`ENABLE`/`FORCE ROW LEVEL SECURITY` + the two command-scoped policies
    below) is hand-written DDL added by `migration-manager` in the Alembic
    migration itself - SQLAlchemy has no construct for it, so it is not
    represented here.
    """

    __tablename__ = "ticket_replies"
    __table_args__ = (
        # FR-5/BR-015 write-side backstop - a service-layer-unreachable
        # constraint, not the primary enforcement path (US-4.2-db-design.md's
        # layering note: the service's own check raises 403 before any
        # insert is attempted).
        CheckConstraint(
            "visibility = 'public' OR author_kind = 'agent'",
            name="ck_ticket_replies_visibility_agent_only",
        ),
        # GET thread-fetch keyset pagination (Resolution OD-3), oldest-first;
        # `id` breaks ties within the same `created_at` value. Deliberately
        # no separate single-column index on `ticket_id` - this composite
        # index's leading column already serves that lookup.
        Index(
            "ix_ticket_replies_ticket_id_created_at_id",
            "ticket_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Values "customer" | "agent"; no default - the service always states
    # this explicitly, matching `Ticket.category`'s no-default precedent.
    author_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(String(5000), nullable=False)
    # Values "public" | "internal"; default per Resolution OD-6 (both actor
    # kinds default to "public" when omitted).
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="public")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Attachment(Base):
    """Minimal ownership/binding tracking only (OD-1) — no upload mechanic
    columns (filename, MIME type, size, storage key), which belong to a
    future upload story. `ticket_id` is nullable (unbound) and, once set, is
    never cleared or reassigned by any code path this story builds — service-
    enforced immutability, not a DB trigger/constraint (US-4.1-db-design.md).
    """

    __tablename__ = "attachments"
    __table_args__ = (
        # 24h unbound-attachment purge job scan (FR-7's last sentence) — a
        # partial index so the job never scans already-bound rows.
        Index(
            "ix_attachments_created_at_unbound",
            "created_at",
            postgresql_where=text("ticket_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tickets.id"), nullable=True, index=True
    )
    # Reply-level binding (Resolution OD-1), independent of `ticket_id` -
    # added alongside it, not instead of it. NULL until bound, never cleared
    # or reassigned once set (service-enforced, not DB-enforced - same gap
    # as `ticket_id` itself, US-4.2-db-design.md).
    ticket_reply_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ticket_replies.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
