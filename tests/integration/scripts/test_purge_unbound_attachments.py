from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.support.models import Attachment, Ticket
from app.modules.support.repository import AttachmentRepository
from app.modules.users.models import User

pytestmark = pytest.mark.integration

_PURGE_AFTER_HOURS = 24  # FR-7's last sentence, mirrored from scripts/purge_unbound_attachments.py


async def _seed_user(db_session: AsyncSession, *, email: str) -> User:
    user = User(email=email, hashed_password=await hash_password("Str0ng!Pass1"), status="active")
    user.email_verified = True
    db_session.add(user)
    await db_session.flush()
    return user


async def test_purge_unbound_attachments_deletes_unbound_attachment_older_than_24h(
    db_session: AsyncSession,
) -> None:
    # Arrange: FR-7's last sentence — unbound and past the 24h cutoff.
    user = await _seed_user(db_session, email="purge-old-unbound@example.com")
    old_unbound = Attachment(
        uploaded_by=user.id,
        ticket_id=None,
        created_at=datetime.now(UTC) - timedelta(hours=_PURGE_AFTER_HOURS, minutes=1),
    )
    db_session.add(old_unbound)
    await db_session.flush()
    cutoff = datetime.now(UTC) - timedelta(hours=_PURGE_AFTER_HOURS)
    repository = AttachmentRepository(db_session)

    # Act
    candidates = await repository.find_unbound_older_than(cutoff)
    purged_count = await repository.purge([a.id for a in candidates])
    await repository.commit()

    # Assert
    assert old_unbound.id in [a.id for a in candidates]
    assert purged_count == 1
    result = await db_session.execute(select(Attachment).where(Attachment.id == old_unbound.id))
    assert result.scalar_one_or_none() is None


async def test_purge_unbound_attachments_leaves_unbound_attachment_within_24h_untouched(
    db_session: AsyncSession,
) -> None:
    # Arrange: unbound but not yet past the cutoff — must survive the sweep.
    user = await _seed_user(db_session, email="purge-recent-unbound@example.com")
    recent_unbound = Attachment(
        uploaded_by=user.id,
        ticket_id=None,
        created_at=datetime.now(UTC) - timedelta(hours=_PURGE_AFTER_HOURS) + timedelta(minutes=1),
    )
    db_session.add(recent_unbound)
    await db_session.flush()
    cutoff = datetime.now(UTC) - timedelta(hours=_PURGE_AFTER_HOURS)
    repository = AttachmentRepository(db_session)

    # Act
    candidates = await repository.find_unbound_older_than(cutoff)

    # Assert
    assert recent_unbound.id not in [a.id for a in candidates]
    result = await db_session.execute(select(Attachment).where(Attachment.id == recent_unbound.id))
    assert result.scalar_one_or_none() is not None


async def test_purge_unbound_attachments_leaves_bound_attachment_older_than_24h_untouched(
    db_session: AsyncSession,
) -> None:
    # Arrange: FR-7 — once bound, an attachment is immutable and never
    # purged, no matter its age.
    user = await _seed_user(db_session, email="purge-old-bound@example.com")
    ticket = Ticket(
        requester_id=user.id, subject="Bound attachment case", body="body", category="billing"
    )
    db_session.add(ticket)
    await db_session.flush()
    old_bound = Attachment(
        uploaded_by=user.id,
        ticket_id=ticket.id,
        created_at=datetime.now(UTC) - timedelta(hours=_PURGE_AFTER_HOURS, minutes=1),
    )
    db_session.add(old_bound)
    await db_session.flush()
    cutoff = datetime.now(UTC) - timedelta(hours=_PURGE_AFTER_HOURS)
    repository = AttachmentRepository(db_session)

    # Act
    candidates = await repository.find_unbound_older_than(cutoff)

    # Assert
    assert old_bound.id not in [a.id for a in candidates]
    result = await db_session.execute(select(Attachment).where(Attachment.id == old_bound.id))
    assert result.scalar_one_or_none() is not None


async def test_purge_unbound_attachments_purge_of_empty_candidate_list_deletes_nothing(
    db_session: AsyncSession,
) -> None:
    # Arrange: the script's own no-candidates path (repository.purge([])).
    repository = AttachmentRepository(db_session)

    # Act
    purged_count = await repository.purge([])

    # Assert
    assert purged_count == 0
