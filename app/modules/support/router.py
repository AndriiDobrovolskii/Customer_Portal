import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, status

from app.modules.support.dependencies import (
    TicketReplyServiceDep,
    TicketServiceDep,
    reject_agent_queue_access,
    resolve_actor_kind,
)
from app.modules.support.schemas import (
    CreateReplyRequest,
    CreateTicketRequest,
    ReplyRead,
    TicketDetailRead,
    TicketListResponse,
    TicketRead,
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
    response_model=TicketListResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(reject_agent_queue_access)],
)
async def list_own_tickets(
    current_user: CurrentUserDep,
    service: TicketServiceDep,
    status: _TicketStatus | None = None,
    cursor: str | None = None,
    limit: int = 100,
) -> TicketListResponse:
    """FR-2. Authorization is two-branch: this route body only handles the
    customer-facing branch (identity/ownership only, `CurrentUserDep`); the
    staff-rejection branch is the `reject_agent_queue_access` dependency
    above (US-4.1-api-design.md). Parameter named `status`, shadowing the
    `fastapi.status` module import only within this function's own scope —
    same precedent as `app/modules/admin_users/router.py::list_users`.
    """
    return await service.list_own_tickets(
        requester_id=current_user.user_id, status=status, cursor=cursor, limit=limit
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
