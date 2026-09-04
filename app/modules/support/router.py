from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, status

from app.modules.support.dependencies import TicketServiceDep, reject_agent_queue_access
from app.modules.support.schemas import CreateTicketRequest, TicketListResponse, TicketRead
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
