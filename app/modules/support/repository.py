import base64
import uuid
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.support.models import Attachment, Ticket


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
