import base64
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Literal, NamedTuple

from sqlalchemy import delete, func, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.support.models import Attachment, Ticket, TicketReply

# US-4.3 Decision 7: the single shared constant both transition_status's
# window guard and auto_close_resolved_past_window's predicate build their
# WHERE fragment from - never two independently hardcoded `7`s.
_RESOLUTION_WINDOW_DAYS = 7


class TicketListPage(NamedTuple):
    items: list[Ticket]
    next_cursor: str | None


def _encode_cursor(created_at: datetime, ticket_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{ticket_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_raw, ticket_id_raw = raw.split("|", 1)
        return datetime.fromisoformat(created_at_raw), uuid.UUID(ticket_id_raw)
    except (ValueError, UnicodeDecodeError):
        return None


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, requester_id: uuid.UUID, subject: str, body: str, category: str
    ) -> Ticket:
        """`ticket_number`/`status`/`created_at`/`updated_at` are all
        server-computed (`server_default`/`FetchedValue()`, see models.py) -
        never set here. No expected failure path (no unique constraint this
        insert could violate), so this raises rather than swallowing, unlike
        `create` methods guarding a real uniqueness race elsewhere in this
        codebase.
        """
        ticket = Ticket(requester_id=requester_id, subject=subject, body=body, category=category)
        self._session.add(ticket)
        await self._session.flush()
        return ticket

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        result = await self._session.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def list_for_requester(
        self, *, requester_id: uuid.UUID, cursor: str | None, limit: int
    ) -> TicketListPage | None:
        """FR-2: newest first. Returns None for a malformed cursor,
        resolved to 422 validation-failed at the service layer, matching
        `AdminUserRepository.list_users`'s own precedent.
        """
        stmt = select(Ticket).where(Ticket.requester_id == requester_id)

        if cursor is not None:
            decoded = _decode_cursor(cursor)
            if decoded is None:
                return None
            cursor_created_at, cursor_ticket_id = decoded
            stmt = stmt.where(
                or_(
                    Ticket.created_at < cursor_created_at,
                    (Ticket.created_at == cursor_created_at) & (Ticket.id < cursor_ticket_id),
                )
            )

        stmt = stmt.order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(limit + 1)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)

        return TicketListPage(items=rows, next_cursor=next_cursor)

    async def list_for_agent_queue(
        self,
        *,
        cursor: str | None,
        limit: int,
        status: str | None = None,
        category: str | None = None,
        assignee_id: uuid.UUID | Literal["none"] | None = None,
    ) -> TicketListPage | None:
        """DR-5 (FR-1/FR-2): the agent-branch queue - every ticket regardless
        of requester, oldest-`updated_at` first, stable-tiebroken by `id`.
        This is a **new** method, not an extension of `list_for_requester`
        (which stays byte-for-byte unchanged) - the two serve genuinely
        different callers/orderings/cursor encodings.

        `status=None` (the default, filterless branch, AQ-AC1) emits the
        literal `Ticket.status != "closed"` predicate - never an `.in_([...])`
        enumeration of the four non-closed values - so PostgreSQL's
        partial-index predicate-implication check selects
        `ix_tickets_queue_default_updated_at_id` (US-4.4-db-design.md
        "Indexes"). An explicit `status` value instead filters
        `Ticket.status == status` (including `"closed"`, AQ-AC2), served by
        `ix_tickets_status_updated_at_id`.

        `assignee_id` accepts an already-resolved UUID (a specific agent, or
        the caller's own id for the `me` filter - "me" is resolved to a real
        UUID by the service before this call) or the literal sentinel
        `"none"` (the unassigned filter, `assignee_id IS NULL`), served by
        `ix_tickets_assignee_id_updated_at_id`. `None` means the filter is
        absent entirely.

        Cursor comparison is ascending (`Ticket.updated_at > cursor_updated_at`),
        mirroring `TicketReplyRepository.list_for_ticket`'s oldest-first
        pattern - the reverse of this method's own `list_for_requester`'s
        descending comparison. Returns `None` for a malformed cursor,
        resolved to 422 validation-failed at the service layer, matching
        `list_for_requester`'s own precedent.
        """
        stmt = select(Ticket)

        if status is None:
            stmt = stmt.where(Ticket.status != "closed")
        else:
            stmt = stmt.where(Ticket.status == status)

        if category is not None:
            stmt = stmt.where(Ticket.category == category)

        if assignee_id == "none":
            stmt = stmt.where(Ticket.assignee_id.is_(None))
        elif assignee_id is not None:
            stmt = stmt.where(Ticket.assignee_id == assignee_id)

        if cursor is not None:
            decoded = _decode_cursor(cursor)
            if decoded is None:
                return None
            cursor_updated_at, cursor_ticket_id = decoded
            stmt = stmt.where(
                or_(
                    Ticket.updated_at > cursor_updated_at,
                    (Ticket.updated_at == cursor_updated_at) & (Ticket.id > cursor_ticket_id),
                )
            )

        stmt = stmt.order_by(Ticket.updated_at.asc(), Ticket.id.asc()).limit(limit + 1)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last.updated_at, last.id)

        return TicketListPage(items=rows, next_cursor=next_cursor)

    async def update(
        self,
        ticket_id: uuid.UUID,
        *,
        status: str | None = None,
        first_response_at: datetime | None = None,
    ) -> Ticket | None:
        """Both fields optional; `None` means "leave unchanged" - no FR in
        this story ever clears either one back to `None`
        (US-4.2-implementation-plan.md Architectural Change #3). When both
        are `None`, no `UPDATE` is issued.
        """
        values: dict[str, object] = {}
        if status is not None:
            values["status"] = status
        if first_response_at is not None:
            values["first_response_at"] = first_response_at
        if not values:
            return await self.get_by_id(ticket_id)
        result = await self._session.execute(
            update(Ticket).where(Ticket.id == ticket_id).values(**values).returning(Ticket)
        )
        return result.scalar_one_or_none()

    async def transition_status(
        self,
        ticket_id: uuid.UUID,
        *,
        expected_statuses: Sequence[str],
        new_status: str,
        resolved_at: datetime | None = None,
        clear_resolved_at: bool = False,
        resolution_note: str | None = None,
        closed_at: datetime | None = None,
        closed_by: uuid.UUID | None = None,
        require_resolved_within_window: bool = False,
    ) -> Ticket | None:
        """US-4.3 Decision 2: conditional `UPDATE ... WHERE id = :id AND
        status IN (:expected_statuses)` (optionally `AND resolved_at >=
        now() - interval '7 days'`, DR-2's inclusive window guard). Returns
        `None` on zero rows affected: ticket not found, status was not one
        of `expected_statuses` (FR-6/FR-9), or - when the window guard is
        set - the 7-day window had already elapsed. The caller cannot
        distinguish these from row count alone and must have already
        confirmed the ticket exists via `get_by_id` earlier in the same
        request, per US-4.3-api-design.md's check order.
        """
        values: dict[str, object] = {"status": new_status}
        if resolved_at is not None:
            values["resolved_at"] = resolved_at
        if clear_resolved_at:
            values["resolved_at"] = None
        if resolution_note is not None:
            values["resolution_note"] = resolution_note
        if closed_at is not None:
            values["closed_at"] = closed_at
        if closed_by is not None:
            values["closed_by"] = closed_by

        conditions = [Ticket.id == ticket_id, Ticket.status.in_(expected_statuses)]
        if require_resolved_within_window:
            conditions.append(
                Ticket.resolved_at
                >= func.now() - func.make_interval(0, 0, 0, literal(_RESOLUTION_WINDOW_DAYS))
            )

        result = await self._session.execute(
            update(Ticket).where(*conditions).values(**values).returning(Ticket)
        )
        return result.scalar_one_or_none()

    async def assign_ticket(
        self,
        ticket_id: uuid.UUID,
        *,
        new_assignee_id: uuid.UUID,
        expected_assignee_id: uuid.UUID | None,
    ) -> Ticket | None:
        """DR-3 (FR-3/FR-10): conditional `UPDATE tickets SET assignee_id =
        :new WHERE id = :id AND status != 'closed' AND assignee_id
        IS NOT DISTINCT FROM :expected RETURNING *`. `is_not_distinct_from`
        (not `==`) so a first assignment (`expected_assignee_id=None`)
        correctly matches `assignee_id IS NULL` - SQL's `NULL = NULL` is
        `NULL`, not `true`, so `==` would make every unraced first
        assignment fail with a false-positive `409`.

        Zero rows affected (returns `None`) means either the ticket is
        `closed` (FR-9) or another request already changed `assignee_id`
        since `expected_assignee_id` was read (FR-10, `409
        assignment-conflict`) - the caller cannot distinguish these from row
        count alone and must already know the ticket's status from an
        earlier lookup in the same request.

        `updated_at=Ticket.updated_at` is a self-referential `SET`,
        overriding the column's `onupdate=func.now()` default, so a bare
        ownership change does not disturb `list_for_agent_queue`'s
        oldest-`updated_at`-first ordering (DR-3's load-bearing fix - see
        `unassign_ticket` for the symmetric half of this fix).
        """
        result = await self._session.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.status != "closed",
                Ticket.assignee_id.is_not_distinct_from(expected_assignee_id),
            )
            .values(assignee_id=new_assignee_id, updated_at=Ticket.updated_at)
            .returning(Ticket)
        )
        return result.scalar_one_or_none()

    async def unassign_ticket(self, ticket_id: uuid.UUID) -> Ticket | None:
        """DR-3 (FR-4/OD-3 APPROVED): unconditional `UPDATE tickets SET
        assignee_id = NULL WHERE id = :id AND status != 'closed' RETURNING
        *` - no `assignee_id IS NOT DISTINCT FROM` guard (unlike
        `assign_ticket`): unassigning is idempotent by its own postcondition
        (`assignee_id IS NULL`), so there is no "loser" to detect
        (US-4.4-api-design.md "Concurrency Design").

        Zero rows affected (returns `None`) means the ticket is `closed` -
        OD-3 APPROVED: unassign on a closed ticket is a `409
        invalid-state-transition`, not a silent no-op, enforced by this
        `WHERE` clause excluding closed tickets so the service sees zero
        rows updated and can raise accordingly. The caller must already know
        the ticket exists via an earlier lookup in the same request.

        `updated_at=Ticket.updated_at` is the same self-referential `SET` as
        `assign_ticket`, for the identical reason (DR-3) - a half-applied fix
        on only one of the two methods would still corrupt queue ordering on
        whichever one lacked it.
        """
        result = await self._session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id, Ticket.status != "closed")
            .values(assignee_id=None, updated_at=Ticket.updated_at)
            .returning(Ticket)
        )
        return result.scalar_one_or_none()

    async def auto_close_resolved_past_window(
        self, *, closed_at: datetime, closed_by: uuid.UUID
    ) -> list[uuid.UUID]:
        """US-4.3 Decision 8 (FR-3): single `UPDATE ... WHERE status =
        'resolved' AND resolved_at < now() - interval '7 days' ...
        RETURNING id`, served by `ix_tickets_resolved_at_pending_autoclose`.
        Idempotent and safe to re-run (NFR): a ticket already closed by a
        prior run, or reopened since, no longer matches the `WHERE` clause.
        """
        result = await self._session.execute(
            update(Ticket)
            .where(
                Ticket.status == "resolved",
                Ticket.resolved_at
                < func.now() - func.make_interval(0, 0, 0, literal(_RESOLUTION_WINDOW_DAYS)),
            )
            .values(status="closed", closed_at=closed_at, closed_by=closed_by)
            .returning(Ticket.id)
        )
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self._session.commit()


class AttachmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, attachment_id: uuid.UUID) -> Attachment | None:
        result = await self._session.execute(
            select(Attachment).where(Attachment.id == attachment_id)
        )
        return result.scalar_one_or_none()

    async def bind_to_ticket(
        self, *, attachment_id: uuid.UUID, ticket_id: uuid.UUID
    ) -> Attachment | None:
        """Atomic check-and-bind (FR-7's "belongs to exactly one ticket
        forever"): a conditional UPDATE guarded by `ticket_id IS NULL`, same
        pattern as `UserRepository.consume_refresh_token` - two concurrent
        requests racing to bind the same attachment can never both succeed.
        Returns None if the attachment was already bound (by a prior
        request or a losing concurrent one) - ownership (`uploaded_by`) is
        the caller's responsibility to check via `get_by_id` first.
        """
        result = await self._session.execute(
            update(Attachment)
            .where(Attachment.id == attachment_id, Attachment.ticket_id.is_(None))
            .values(ticket_id=ticket_id)
            .returning(Attachment)
        )
        return result.scalar_one_or_none()

    async def bind_to_reply(
        self, *, attachment_id: uuid.UUID, ticket_reply_id: uuid.UUID
    ) -> Attachment | None:
        """Same atomic check-and-bind pattern as `bind_to_ticket`, guarding
        the independent nullable `ticket_reply_id` column (Resolution OD-1)
        rather than `ticket_id` - the two bindings are separate and this
        story does not touch `ticket_id`.
        """
        result = await self._session.execute(
            update(Attachment)
            .where(Attachment.id == attachment_id, Attachment.ticket_reply_id.is_(None))
            .values(ticket_reply_id=ticket_reply_id)
            .returning(Attachment)
        )
        return result.scalar_one_or_none()

    async def find_unbound_older_than(self, cutoff: datetime) -> list[Attachment]:
        """FR-7's last sentence: the 24h unbound-attachment purge job's
        scan, served by the partial index on `created_at WHERE ticket_id IS
        NULL` (models.py).
        """
        result = await self._session.execute(
            select(Attachment).where(Attachment.ticket_id.is_(None), Attachment.created_at < cutoff)
        )
        return list(result.scalars().all())

    async def purge(self, attachment_ids: list[uuid.UUID]) -> int:
        """Deletes the rows `find_unbound_older_than` found. Returns the
        number of rows actually deleted.
        """
        if not attachment_ids:
            return 0
        result = await self._session.execute(
            delete(Attachment).where(Attachment.id.in_(attachment_ids)).returning(Attachment.id)
        )
        return len(result.scalars().all())

    async def commit(self) -> None:
        await self._session.commit()


class ReplyListPage(NamedTuple):
    items: list[TicketReply]
    next_cursor: str | None


class TicketReplyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        ticket_id: uuid.UUID,
        author_id: uuid.UUID,
        author_kind: str,
        body: str,
        visibility: str,
    ) -> TicketReply:
        """`created_at` is server-computed (`server_default=func.now()`, see
        models.py) - never set here. The CHECK constraint is a service-
        layer-unreachable backstop (US-4.2-db-design.md's layering note), so
        this has no expected failure path to guard - raises rather than
        swallowing, matching `TicketRepository.create`'s own precedent.
        """
        reply = TicketReply(
            ticket_id=ticket_id,
            author_id=author_id,
            author_kind=author_kind,
            body=body,
            visibility=visibility,
        )
        self._session.add(reply)
        await self._session.flush()
        return reply

    async def list_for_ticket(
        self, *, ticket_id: uuid.UUID, cursor: str | None, limit: int
    ) -> ReplyListPage | None:
        """Oldest-first (thread reads chronologically, per the API design's
        `ReplyThreadPage` description) - the reverse ordering of
        `TicketRepository.list_for_requester`'s newest-first ticket list.
        Returns None for a malformed cursor, resolved to 422
        validation-failed at the service layer, matching `list_for_requester`'s
        own precedent.
        """
        stmt = select(TicketReply).where(TicketReply.ticket_id == ticket_id)

        if cursor is not None:
            decoded = _decode_cursor(cursor)
            if decoded is None:
                return None
            cursor_created_at, cursor_reply_id = decoded
            stmt = stmt.where(
                or_(
                    TicketReply.created_at > cursor_created_at,
                    (TicketReply.created_at == cursor_created_at)
                    & (TicketReply.id > cursor_reply_id),
                )
            )

        stmt = stmt.order_by(TicketReply.created_at.asc(), TicketReply.id.asc()).limit(limit + 1)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)

        return ReplyListPage(items=rows, next_cursor=next_cursor)

    async def commit(self) -> None:
        await self._session.commit()
