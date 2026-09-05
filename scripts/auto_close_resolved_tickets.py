"""Cron entry point — auto-close tickets resolved more than 7 days ago with no reply (FR-3).

Not wired to any in-process scheduler. Invoke externally, e.g. a daily
cron line:

    0 5 * * *  cd /srv/customer-portal && .venv/bin/python scripts/auto_close_resolved_tickets.py

Exit code 0 on success (including zero closed); non-zero on failure, so
cron can alert on it. Talks to `TicketRepository` directly rather than
`TicketService` (same precedent as `purge_unbound_attachments.py`) — the
auto-close sweep needs no idempotency/rate-limit concerns. Unlike every
prior purge-style script, this one also needs a Valkey connection: the
per-ticket `AuditLogService.record_event` write resolves `actor_role` via
`RoleService.get_role_grants_for_user`, and `RoleService`'s constructor
requires a `PermissionEpochCache` even though this particular call path
never dereferences it (implementation_plan.md Decision 6) — an empty grant
list for the system-actor sentinel resolves to `actor_role=None`, an
existing, harmless code path (DESIGN_REVIEW v3).
"""

import asyncio
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.revocation_cache import PermissionEpochCache
from app.db.session import create_engine_and_sessionmaker
from app.modules.audit.repository import AuditRepository
from app.modules.audit.service import AuditLogService
from app.modules.roles.repository import RoleRepository, UserRoleRepository
from app.modules.roles.service import RoleService
from app.modules.support.models import SYSTEM_ACTOR_ID
from app.modules.support.repository import TicketRepository

logger = logging.getLogger(__name__)


async def main() -> int:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    valkey_client: Redis = Redis.from_url(settings.valkey_url, decode_responses=True)
    try:
        async with session_factory() as session:
            ticket_repository = TicketRepository(session)
            audit_repository = AuditRepository(session)
            role_repository = RoleRepository(session)
            user_role_repository = UserRoleRepository(session)
            permission_epoch_cache = PermissionEpochCache(valkey_client)
            role_service = RoleService(
                role_repository, user_role_repository, permission_epoch_cache
            )
            audit_service = AuditLogService(audit_repository, role_service)

            closed_ids = await ticket_repository.auto_close_resolved_past_window(
                closed_at=datetime.now(UTC), closed_by=SYSTEM_ACTOR_ID
            )
            for ticket_id in closed_ids:
                await audit_service.record_event(
                    category="tickets",
                    event="ticket_auto_closed",
                    actor_id=SYSTEM_ACTOR_ID,
                    target_id=ticket_id,
                    outcome="success",
                    payload=None,
                )
            # One business operation, one commit (AGENTS.md §3). record_event
            # deliberately never commits itself; ticket_repository and
            # audit_repository share this same session, so this single call
            # commits the batch UPDATE and every audit_log insert together.
            await ticket_repository.commit()
        logger.info("auto_close_resolved_tickets complete: closed %d ticket(s)", len(closed_ids))
    finally:
        await engine.dispose()
        await valkey_client.aclose()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main()))
