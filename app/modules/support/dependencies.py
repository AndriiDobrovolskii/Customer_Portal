from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, get_email_sender
from app.db.dependencies import get_db_session, get_valkey_client
from app.modules.audit.dependencies import AuditLogServiceDep
from app.modules.support.cache import TicketCreationRateLimitCache, TicketIdempotencyCache
from app.modules.support.exceptions import AgentQueueNotAvailableError
from app.modules.support.repository import AttachmentRepository, TicketRepository
from app.modules.support.service import TicketService
from app.modules.users.dependencies import CurrentUserDep, UserServiceDep


def get_ticket_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    valkey_client: Annotated[Redis, Depends(get_valkey_client)],
    audit_service: AuditLogServiceDep,
    user_service: UserServiceDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> TicketService:
    repository = TicketRepository(session)
    attachment_repository = AttachmentRepository(session)
    idempotency_cache = TicketIdempotencyCache(valkey_client)
    rate_limit_cache = TicketCreationRateLimitCache(valkey_client)
    return TicketService(
        repository,
        attachment_repository,
        idempotency_cache,
        rate_limit_cache,
        audit_service,
        user_service,
        email_sender,
    )


TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]


async def reject_agent_queue_access(current_user: CurrentUserDep) -> None:
    """`GET`'s staff-rejection branch (OD-4, US-4.1-api-design.md's DR-4
    fix): a caller who holds `tickets:read` or `tickets:write` (i.e. is
    `support_agent`/`admin`) is rejected — full agent queue behavior is Out
    of Scope for this story. `current_user.scopes` is the JWT-decoded scope
    list, the same source `roles.dependencies.require_scope` reads directly
    — this is a reject-if-present check rather than `require_scope`'s
    require-if-absent shape, so it can't reuse that factory directly, but
    needs no extra service call either.
    """
    if "tickets:read" in current_user.scopes or "tickets:write" in current_user.scopes:
        raise AgentQueueNotAvailableError
