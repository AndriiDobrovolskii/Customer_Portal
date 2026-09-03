import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import get_request_id
from app.modules.audit.dependencies import AuditLogServiceDep, require_audit_read
from app.modules.audit.schemas import AuditLogListResponse
from app.modules.users.dependencies import CurrentUserDep

router = APIRouter(prefix="/admin/audit-logs", tags=["admin", "audit"])


def _get_client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.get(
    "",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_audit_read)],
)
async def list_audit_logs(
    request: Request,
    current_user: CurrentUserDep,
    service: AuditLogServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
    actor_id: uuid.UUID | None = None,
    event: str | None = None,
    target_id: uuid.UUID | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> AuditLogListResponse:
    return await service.list_audit_logs(
        actor_id=current_user.user_id,
        actor_id_filter=actor_id,
        event=event,
        target_id=target_id,
        window_from=from_,
        window_to=to,
        cursor=cursor,
        limit=limit,
        request_id=request_id,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


# No PATCH/PUT/DELETE handler is registered here (AU-AC4/FR-4,
# US-3.3-api-design.md): Starlette returns its default 405 for any other
# method on a path that has at least one method registered — verified
# against app/main.py's actual exception handlers during PLANNING
# (impact-analysis.md), none of which intercept it.
