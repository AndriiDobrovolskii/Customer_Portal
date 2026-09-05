from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, get_email_sender
from app.db.dependencies import get_db_session, get_valkey_client
from app.modules.audit.dependencies import AuditLogServiceDep
from app.modules.support.cache import (
    TicketCreationRateLimitCache,
    TicketIdempotencyCache,
    TicketReplyRateLimitCache,
)
from app.modules.support.exceptions import AgentQueueNotAvailableError
from app.modules.support.repository import (
    AttachmentRepository,
    TicketReplyRepository,
    TicketRepository,
)
from app.modules.support.service import TicketReplyService, TicketService
from app.modules.users.dependencies import CurrentUserDep, UserServiceDep
from app.modules.users.service import AuthenticatedUser


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


def resolve_actor_kind(current_user: AuthenticatedUser) -> str:
    """US-4.2 implementation-plan Architectural Change #2: the two-value
    `author_kind`/`app.actor_kind` vocabulary, derived from the identical
    check `reject_agent_queue_access` above already uses - not a new
    derivation mechanism, reused here so the router and `get_rls_session`
    never compute it two different ways.
    """
    return "agent" if "tickets:write" in current_user.scopes else "customer"


async def get_rls_session(
    current_user: CurrentUserDep,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[AsyncSession]:
    """US-4.2 implementation-plan Architectural Change #2: a module-scoped
    wrapper around the shared `get_db_session`, used only by the two new
    reply routes - not the shared dependency itself, so no other route in
    this codebase pays for a `SET LOCAL` it never reads (AGENTS.md §7.8).
    `set_config(..., true)` is session-local (`SET LOCAL`-equivalent) but,
    unlike a raw `SET LOCAL app.actor_kind = 'agent'` string, takes its
    value as a bound parameter.
    """
    actor_kind = resolve_actor_kind(current_user)
    await session.execute(
        text("SELECT set_config('app.actor_kind', :actor_kind, true)"),
        {"actor_kind": actor_kind},
    )
    await session.execute(
        text("SELECT set_config('app.actor_id', :actor_id, true)"),
        {"actor_id": str(current_user.user_id)},
    )
    yield session


def get_ticket_reply_service(
    session: Annotated[AsyncSession, Depends(get_rls_session)],
    valkey_client: Annotated[Redis, Depends(get_valkey_client)],
    user_service: UserServiceDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> TicketReplyService:
    ticket_repository = TicketRepository(session)
    reply_repository = TicketReplyRepository(session)
    attachment_repository = AttachmentRepository(session)
    rate_limit_cache = TicketReplyRateLimitCache(valkey_client)
    return TicketReplyService(
        ticket_repository,
        reply_repository,
        attachment_repository,
        rate_limit_cache,
        email_sender,
        user_service,
    )


TicketReplyServiceDep = Annotated[TicketReplyService, Depends(get_ticket_reply_service)]
