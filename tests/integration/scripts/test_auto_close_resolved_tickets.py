import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.revocation_cache import PermissionEpochCache
from app.core.security import hash_password
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditRepository
from app.modules.audit.service import AuditLogService
from app.modules.roles.repository import RoleRepository, UserRoleRepository
from app.modules.roles.service import RoleService
from app.modules.support.models import SYSTEM_ACTOR_ID, Ticket
from app.modules.support.repository import TicketRepository
from app.modules.users.models import User

pytestmark = pytest.mark.integration

_RESOLUTION_WINDOW_DAYS = 7  # implementation_plan.md Decision 7's shared constant


async def _seed_user(db_session: AsyncSession, *, email: str) -> User:
    user = User(email=email, hashed_password=await hash_password("Str0ng!Pass1"), status="active")
    user.email_verified = True
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_resolved_ticket(
    db_session: AsyncSession, *, requester_id: uuid.UUID, resolved_at: datetime
) -> Ticket:
    ticket = Ticket(
        ticket_number=f"CP-2026-{uuid.uuid4().hex[:10]}",
        requester_id=requester_id,
        subject="Cannot log in",
        body="My login keeps failing after the last update.",
        category="billing",
        status="resolved",
        resolved_at=resolved_at,
        resolution_note="Restarted the service.",
    )
    db_session.add(ticket)
    await db_session.flush()
    return ticket


# --- FR-3: auto_close_resolved_past_window ----------------------------------


async def test_auto_close_resolved_past_window_closes_ticket_older_than_7_days(
    db_session: AsyncSession,
) -> None:
    # Arrange: strictly more than 7 days ago (OD-4's strict `<` for the
    # auto-close job, unlike the reply/reopen guard's inclusive `<=`). A
    # 5-minute margin, not 1 second — the predicate is evaluated by Postgres
    # against its own transaction-start now() (frozen for the whole
    # transaction), which is always earlier than this Arrange block's
    # datetime.now(UTC) call by however long fixture setup took; a 1-second
    # margin would make this assertion flaky against that setup gap.
    user = await _seed_user(db_session, email="autoclose-old@example.com")
    ticket = await _seed_resolved_ticket(
        db_session,
        requester_id=user.id,
        resolved_at=datetime.now(UTC) - timedelta(days=_RESOLUTION_WINDOW_DAYS, minutes=5),
    )
    repository = TicketRepository(db_session)
    closed_at = datetime.now(UTC)

    # Act
    closed_ids = await repository.auto_close_resolved_past_window(
        closed_at=closed_at, closed_by=SYSTEM_ACTOR_ID
    )
    await repository.commit()

    # Assert
    assert ticket.id in closed_ids
    result = await db_session.execute(select(Ticket).where(Ticket.id == ticket.id))
    row = result.scalar_one()
    assert row.status == "closed"
    assert row.closed_by == SYSTEM_ACTOR_ID
    assert row.closed_at is not None


async def _seed_resolved_ticket_at_exact_window_boundary(
    db_session: AsyncSession, *, requester_id: uuid.UUID
) -> Ticket:
    """Seeds a ticket whose `resolved_at` is exactly `_RESOLUTION_WINDOW_DAYS`
    ago as computed by Postgres itself, not Python's wall clock. The
    auto-close job's own `now() - make_interval(...)` predicate reads the same
    transaction-frozen `now()` this UPDATE does (`db_session` runs the whole
    test in one transaction), so this seed and that predicate can never
    disagree on which side of the boundary they're on - unlike a
    Python-computed `datetime.now(UTC) - timedelta(...)`, whose comparison
    against Postgres's `now()` depends on real elapsed wall-clock time between
    Arrange and Act.
    """
    ticket = await _seed_resolved_ticket(
        db_session, requester_id=requester_id, resolved_at=datetime.now(UTC)
    )
    await db_session.execute(
        update(Ticket)
        .where(Ticket.id == ticket.id)
        .values(
            resolved_at=func.now() - func.make_interval(0, 0, 0, literal(_RESOLUTION_WINDOW_DAYS))
        )
    )
    await db_session.flush()
    await db_session.refresh(ticket)
    return ticket


async def test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_untouched(
    db_session: AsyncSession,
) -> None:
    # Arrange: OD-4's strict boundary — exactly 7 days ago must NOT be
    # auto-closed (it is still within the reply/reopen guard's own inclusive
    # window), so the two predicates never both match the same row at the
    # exact boundary instant. resolved_at is seeded server-side (see helper
    # docstring) so the boundary comparison is deterministic regardless of
    # wall-clock timing.
    user = await _seed_user(db_session, email="autoclose-boundary@example.com")
    ticket = await _seed_resolved_ticket_at_exact_window_boundary(db_session, requester_id=user.id)
    repository = TicketRepository(db_session)

    # Act
    closed_ids = await repository.auto_close_resolved_past_window(
        closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
    )

    # Assert
    assert ticket.id not in closed_ids
    await db_session.refresh(ticket)
    assert ticket.status == "resolved"


async def test_auto_close_resolved_past_window_leaves_recently_resolved_ticket_untouched(
    db_session: AsyncSession,
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="autoclose-recent@example.com")
    ticket = await _seed_resolved_ticket(
        db_session, requester_id=user.id, resolved_at=datetime.now(UTC) - timedelta(hours=1)
    )
    repository = TicketRepository(db_session)

    # Act
    closed_ids = await repository.auto_close_resolved_past_window(
        closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
    )

    # Assert
    assert ticket.id not in closed_ids


async def test_auto_close_resolved_past_window_leaves_non_resolved_ticket_untouched(
    db_session: AsyncSession,
) -> None:
    # Arrange: an "open" ticket, even with a stale (never-cleared) timestamp
    # column value, must never be matched by the `status = 'resolved'` predicate.
    user = await _seed_user(db_session, email="autoclose-nonresolved@example.com")
    ticket = Ticket(
        ticket_number=f"CP-2026-{uuid.uuid4().hex[:10]}",
        requester_id=user.id,
        subject="Cannot log in",
        body="Body.",
        category="billing",
        status="open",
    )
    db_session.add(ticket)
    await db_session.flush()
    repository = TicketRepository(db_session)

    # Act
    closed_ids = await repository.auto_close_resolved_past_window(
        closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
    )

    # Assert
    assert ticket.id not in closed_ids


async def test_auto_close_resolved_past_window_returns_one_id_per_ticket_not_a_count(
    db_session: AsyncSession,
) -> None:
    # Arrange: FR-3 requires one `ticket_auto_closed` audit entry per ticket
    # closed - the repository must hand the caller each id, not an aggregate
    # count, so the script can loop and write one entry per id.
    user = await _seed_user(db_session, email="autoclose-batch@example.com")
    old = datetime.now(UTC) - timedelta(days=_RESOLUTION_WINDOW_DAYS, hours=1)
    tickets = [
        await _seed_resolved_ticket(db_session, requester_id=user.id, resolved_at=old)
        for _ in range(3)
    ]
    repository = TicketRepository(db_session)

    # Act
    closed_ids = await repository.auto_close_resolved_past_window(
        closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
    )

    # Assert
    assert isinstance(closed_ids, list)
    assert set(closed_ids) == {t.id for t in tickets}


async def test_auto_close_resolved_past_window_is_idempotent_on_rerun(
    db_session: AsyncSession,
) -> None:
    # Arrange: the NFR's own "safe to re-run" requirement - a ticket the
    # first run already closed no longer matches `status = 'resolved'`.
    user = await _seed_user(db_session, email="autoclose-idempotent@example.com")
    ticket = await _seed_resolved_ticket(
        db_session,
        requester_id=user.id,
        resolved_at=datetime.now(UTC) - timedelta(days=_RESOLUTION_WINDOW_DAYS, hours=1),
    )
    repository = TicketRepository(db_session)
    first_run = await repository.auto_close_resolved_past_window(
        closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
    )
    assert ticket.id in first_run

    # Act
    second_run = await repository.auto_close_resolved_past_window(
        closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
    )

    # Assert
    assert second_run == []


async def test_auto_close_resolved_past_window_reopened_ticket_survives(
    db_session: AsyncSession,
) -> None:
    # Arrange: NFR — "a reply that commits first makes the job a no-op." A
    # ticket reopened (status no longer "resolved") since its original
    # `resolved_at` must not be closed even though that stale timestamp is
    # still old enough.
    user = await _seed_user(db_session, email="autoclose-reopened@example.com")
    ticket = await _seed_resolved_ticket(
        db_session,
        requester_id=user.id,
        resolved_at=datetime.now(UTC) - timedelta(days=_RESOLUTION_WINDOW_DAYS, hours=1),
    )
    ticket.status = "waiting_on_support"
    ticket.resolved_at = None
    await db_session.flush()
    repository = TicketRepository(db_session)

    # Act
    closed_ids = await repository.auto_close_resolved_past_window(
        closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
    )

    # Assert
    assert ticket.id not in closed_ids


# --- Full loop: one ticket_auto_closed audit_log row per closed ticket -----


async def test_auto_close_job_writes_one_ticket_auto_closed_audit_row_per_ticket(
    db_session: AsyncSession,
) -> None:
    # Arrange: implementation_plan.md Decision 6/8 — the script's own
    # composition (`TicketRepository` + `AuditLogService`/`RoleService`/
    # `PermissionEpochCache`), reused here against the test's already-
    # provisioned Postgres/Valkey rather than the script's own from-settings
    # engine construction (which reads `get_settings().database_url`/
    # `valkey_url` — not the ephemeral test container's URLs). Proves DESIGN_REVIEW
    # v3's own confirmation: the sentinel actor's empty role-grant list is a
    # harmless, non-raising path through `_resolve_actor_role`.
    user = await _seed_user(db_session, email="autoclose-audit@example.com")
    ticket = await _seed_resolved_ticket(
        db_session,
        requester_id=user.id,
        resolved_at=datetime.now(UTC) - timedelta(days=_RESOLUTION_WINDOW_DAYS, hours=1),
    )
    ticket_repository = TicketRepository(db_session)
    audit_repository = AuditRepository(db_session)
    role_repository = RoleRepository(db_session)
    user_role_repository = UserRoleRepository(db_session)
    permission_epoch_cache = PermissionEpochCache(app.state.valkey_client)
    role_service = RoleService(role_repository, user_role_repository, permission_epoch_cache)
    audit_service = AuditLogService(audit_repository, role_service)
    closed_at = datetime.now(UTC)

    # Act: mirrors scripts/auto_close_resolved_tickets.py's own loop —
    # one auto_close_resolved_past_window call, one record_event per id,
    # one commit for the whole run (Decision 8).
    closed_ids = await ticket_repository.auto_close_resolved_past_window(
        closed_at=closed_at, closed_by=SYSTEM_ACTOR_ID
    )
    for closed_id in closed_ids:
        await audit_service.record_event(
            category="tickets",
            event="ticket_auto_closed",
            actor_id=SYSTEM_ACTOR_ID,
            target_id=closed_id,
            outcome="success",
            payload=None,
        )
    await ticket_repository.commit()

    # Assert
    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.target_id == ticket.id, AuditLog.event == "ticket_auto_closed"
        )
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == SYSTEM_ACTOR_ID
    assert audit_row.outcome == "success"
    ticket_result = await db_session.execute(select(Ticket).where(Ticket.id == ticket.id))
    assert ticket_result.scalar_one().status == "closed"
