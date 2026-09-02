from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Response, status
from pydantic import JsonValue

from app.core.dependencies import get_request_id
from app.modules.admin_users.dependencies import AdminUserServiceDep
from app.modules.admin_users.schemas import (
    CreateUserRequest,
    DeactivateUserRequest,
    ResendInviteResponse,
    UserListResponse,
    UserRead,
)
from app.modules.roles.dependencies import require_scope
from app.modules.users.dependencies import CurrentUserDep

router = APIRouter(prefix="/admin/users", tags=["admin", "users"])


@router.get(
    "",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_scope("users:read"))],
)
async def list_users(
    service: AdminUserServiceDep,
    q: str | None = None,
    status: str | None = None,
    role: str | None = None,
    cursor: str | None = None,
    limit: int = 25,
) -> UserListResponse:
    return await service.list_users(q=q, status=status, role=role, cursor=cursor, limit=limit)


@router.get(
    "/{id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_scope("users:read"))],
)
async def get_user(id: UUID, response: Response, service: AdminUserServiceDep) -> UserRead:
    user, etag = await service.get_user(id)
    response.headers["ETag"] = etag
    return user


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("users:write"))],
)
async def create_user(
    body: CreateUserRequest,
    response: Response,
    current_user: CurrentUserDep,
    service: AdminUserServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
) -> UserRead:
    user, etag = await service.create_user(
        actor_id=current_user.user_id,
        actor_scopes=set(current_user.scopes),
        payload=body,
        request_id=request_id,
    )
    response.headers["ETag"] = etag
    return user


@router.patch(
    "/{id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_scope("users:write"))],
)
async def update_user(
    id: UUID,
    response: Response,
    current_user: CurrentUserDep,
    service: AdminUserServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
    body: Annotated[dict[str, JsonValue], Body()],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> UserRead:
    user, etag = await service.update_user(
        actor_id=current_user.user_id,
        target_id=id,
        raw_body=body,
        if_match=if_match,
        request_id=request_id,
    )
    response.headers["ETag"] = etag
    return user


@router.post(
    "/{id}/deactivate",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_scope("users:write"))],
)
async def deactivate_user(
    id: UUID,
    body: DeactivateUserRequest,
    current_user: CurrentUserDep,
    service: AdminUserServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
) -> UserRead:
    return await service.deactivate_user(
        actor_id=current_user.user_id, target_id=id, reason=body.reason, request_id=request_id
    )


@router.delete(
    "/{id}",
    response_model=None,
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
)
async def delete_user_not_allowed(id: UUID, current_user: CurrentUserDep) -> None:
    """FR-17: always 405 for any authenticated caller, regardless of role
    or permission scope — erasure belongs only to the US-1.4 DA-AC9
    retention job. `current_user` is declared (not just relied on via a
    `dependencies=[...]` scope check) so an anonymous caller still gets
    401 via the shared CurrentUserDep, per MU-AC3 (resolved reading, see
    US-011-api-design.md).
    """
    return None


@router.post(
    "/{id}/resend-invite",
    response_model=ResendInviteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_scope("users:write"))],
)
async def resend_invite(
    id: UUID,
    current_user: CurrentUserDep,
    service: AdminUserServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
) -> ResendInviteResponse:
    return await service.resend_invite(
        actor_id=current_user.user_id, target_id=id, request_id=request_id
    )
