import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, status

from app.modules.support.dependencies import (
    TicketReplyServiceDep,
    TicketServiceDep,
    resolve_actor_kind,
)
from app.modules.support.schemas import (
    AgentTicketListResponse,
    AgentTicketStateRead,
    AssignTicketRequest,
    CloseTicketRequest,
    CreateReplyRequest,
    CreateTicketRequest,
    ReopenTicketRequest,
    ReplyRead,
    ResolveTicketRequest,
    TicketDetailRead,
    TicketListResponse,
    TicketRead,
    TicketStateRead,
)
from app.modules.users.dependencies import CurrentUserDep

router = APIRouter(prefix="/support/tickets", tags=["support", "tickets"])

_TicketStatus = Literal["open", "waiting_on_support", "waiting_on_customer", "resolved", "closed"]


@router.post(
    "",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    body: CreateTicketRequest,
    current_user: CurrentUserDep,
    service: TicketServiceDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> TicketRead:
    """FR-1/FR-4/FR-5/FR-6/FR-7. Authorization: identity/ownership only
    (`CurrentUserDep`) — deliberately no `tickets:*` scope requirement
    (US-4.1-api-design.md DR-4 fix). FR-5's account-deactivated `403` is
    raised by the service, not this dependency chain — see
    `TicketService.create_ticket`.
    """
    return await service.create_ticket(
        requester_id=current_user.user_id,
        idempotency_key=idempotency_key,
        subject=body.subject,
        body=body.body,
        category=body.category,
        attachment_ids=body.attachment_ids,
    )


@router.get(
    "",
    response_model=TicketListResponse | AgentTicketListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_own_tickets(
    current_user: CurrentUserDep,
    service: TicketServiceDep,
    status: _TicketStatus | None = None,
    category: str | None = None,
    assignee_id: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
) -> TicketListResponse | AgentTicketListResponse:
    """FR-1/FR-2/FR-5/FR-6 (US-4.4). Single route, two branches selected
    purely by whether the caller's token carries `tickets:read` — no ticket
    lookup or ownership check is needed to pick the branch
    (US-4.4-api-design.md "Two Branches, One Route"). The former staff-
    rejection dependency (`reject_agent_queue_access`) is retired — there is
    no `403` on this route any more; a caller holding neither `tickets:read`
    nor an owned ticket simply receives an empty customer-branch page.
    `category`/`assignee_id` are agent-branch-only filters — the customer
    branch ignores both, never validating them even when malformed (FR-6).
    Parameter named `status`, shadowing the `fastapi.status` module import
    only within this function's own scope — same precedent as
    `app/modules/admin_users/router.py::list_users`.
    """
    if "tickets:read" in current_user.scopes:
        return await service.list_agent_queue(
            agent_id=current_user.user_id,
            status=status,
            category=category,
            assignee_id=assignee_id,
            cursor=cursor,
            limit=limit,
        )
    return await service.list_own_tickets(
        requester_id=current_user.user_id, status=status, cursor=cursor, limit=limit
    )


# =============================================================================
# US-4.4 (Agent Ticket Queue & Assignment)
# =============================================================================


@router.post(
    "/{id}/assign",
    response_model=AgentTicketStateRead,
    status_code=status.HTTP_200_OK,
)
async def assign_ticket(
    id: uuid.UUID,
    body: AssignTicketRequest,
    current_user: CurrentUserDep,
    service: TicketServiceDep,
) -> AgentTicketStateRead:
    """FR-3/FR-7/FR-8/FR-9/FR-10. Authorization/check-order is enforced by
    `TicketService.assign_ticket` itself (US-4.4-api-design.md's stated
    permission-gate-first order, task_breakdown.md's resolution of that
    design's Open Questions #1: inline in the service, not a reusable
    `Depends`) — this router passes the caller's full scope list through
    rather than a single derived `actor_kind`, since the 404-vs-403 split
    needs three-way information (`resolve_actor_kind`'s existing two-value
    vocabulary cannot express "tickets:read only").
    """
    return await service.assign_ticket(
        ticket_id=id,
        actor_id=current_user.user_id,
        actor_scopes=current_user.scopes,
        assignee_id=body.assignee_id,
    )


@router.delete(
    "/{id}/assign",
    response_model=AgentTicketStateRead,
    status_code=status.HTTP_200_OK,
)
async def unassign_ticket(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TicketServiceDep,
) -> AgentTicketStateRead:
    """FR-4/FR-7. Same permission-gate shape as `assign_ticket` above."""
    return await service.unassign_ticket(
        ticket_id=id,
        actor_id=current_user.user_id,
        actor_scopes=current_user.scopes,
    )


# =============================================================================
# US-4.2 (Ticket Replies)
# =============================================================================


@router.post(
    "/{id}/replies",
    response_model=ReplyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket_reply(
    id: uuid.UUID,
    body: CreateReplyRequest,
    current_user: CurrentUserDep,
    service: TicketReplyServiceDep,
) -> ReplyRead:
    """FR-1/FR-2/FR-4/FR-5/FR-6/FR-7. Path parameter named `id`, matching
    `US-4.2-openapi.yaml`'s declared parameter name exactly (same precedent
    as `app/modules/admin_users/router.py::get_user`). Authorization is
    actor-kind-dependent (US-4.2-api-design.md): the agent branch
    (`tickets:write`) and the customer/ownership branch are both resolved by
    `resolve_actor_kind` and enforced by `TicketReplyService.create_reply`
    itself, which raises 404 (never 403) for a caller who is neither the
    requester nor an agent - unlike `require_scope`'s 403, this endpoint
    must never confirm the ticket id exists to an unauthorized caller.
    """
    return await service.create_reply(
        ticket_id=id,
        actor_id=current_user.user_id,
        actor_kind=resolve_actor_kind(current_user),
        body=body.body,
        visibility=body.visibility,
        attachment_ids=body.attachment_ids,
    )


@router.get(
    "/{id}",
    response_model=TicketDetailRead,
    status_code=status.HTTP_200_OK,
)
async def get_ticket_detail(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TicketReplyServiceDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TicketDetailRead:
    """FR-3/FR-4/GET Thread Pagination. Same actor-kind-dependent
    authorization as `create_ticket_reply` above; internal-visibility
    replies are excluded from a customer caller's response both by RLS
    (FR-3, database layer) and by never being written to a row that
    layer would return in the first place.
    """
    return await service.get_ticket_detail(
        ticket_id=id,
        actor_id=current_user.user_id,
        actor_kind=resolve_actor_kind(current_user),
        cursor=cursor,
        limit=limit,
    )


# =============================================================================
# US-4.3 (Ticket Resolution)
# =============================================================================


@router.post(
    "/{id}/resolve",
    response_model=TicketStateRead,
    status_code=status.HTTP_200_OK,
)
async def resolve_ticket(
    id: uuid.UUID,
    body: ResolveTicketRequest,
    current_user: CurrentUserDep,
    service: TicketServiceDep,
) -> TicketStateRead:
    """FR-1/FR-6/FR-7/FR-9/FR-10. Check order (state before actor) is
    enforced by `TicketService.resolve_ticket` itself, not this router or a
    `require_scope` dependency — a scope dependency here would run before
    the service can check transition validity, reversing FR-6/FR-7's
    required order (US-4.3-api-design.md).
    """
    return await service.resolve_ticket(
        ticket_id=id,
        actor_id=current_user.user_id,
        actor_kind=resolve_actor_kind(current_user),
        resolution_note=body.resolution_note,
    )


@router.post(
    "/{id}/close",
    response_model=TicketStateRead,
    status_code=status.HTTP_200_OK,
)
async def close_ticket(
    id: uuid.UUID,
    body: CloseTicketRequest,
    current_user: CurrentUserDep,
    service: TicketServiceDep,
) -> TicketStateRead:
    """FR-2/FR-8. `body.reason` is accepted but not persisted anywhere
    (US-4.3-db-design.md).
    """
    return await service.close_ticket(
        ticket_id=id,
        actor_id=current_user.user_id,
        actor_kind=resolve_actor_kind(current_user),
    )


@router.post(
    "/{id}/reopen",
    response_model=TicketStateRead,
    status_code=status.HTTP_200_OK,
)
async def reopen_ticket(
    id: uuid.UUID,
    body: ReopenTicketRequest,
    current_user: CurrentUserDep,
    service: TicketServiceDep,
) -> TicketStateRead:
    """FR-5/FR-6/FR-8. `body.reason` is accepted but not persisted anywhere,
    same as `close_ticket`.
    """
    return await service.reopen_ticket(
        ticket_id=id,
        actor_id=current_user.user_id,
        actor_kind=resolve_actor_kind(current_user),
    )
