from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_request_id
from app.modules.roles.dependencies import RoleServiceDep, require_scope
from app.modules.roles.schemas import (
    ReplaceUserRolesRequest,
    ReplaceUserRolesResponse,
    RoleCatalogueResponse,
)
from app.modules.users.dependencies import CurrentUserDep

router = APIRouter(prefix="/admin", tags=["admin", "roles"])


@router.get(
    "/roles",
    response_model=RoleCatalogueResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_scope("users:read"))],
)
async def list_role_catalogue(service: RoleServiceDep) -> RoleCatalogueResponse:
    return await service.list_catalogue()


@router.put(
    "/users/{id}/roles",
    response_model=ReplaceUserRolesResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_scope("roles:write"))],
)
async def replace_user_roles(
    id: UUID,
    body: ReplaceUserRolesRequest,
    current_user: CurrentUserDep,
    service: RoleServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
) -> ReplaceUserRolesResponse:
    return await service.replace_user_roles(
        actor_id=current_user.user_id,
        actor_scopes=set(current_user.scopes),
        target_id=id,
        requested_role_names=body.roles,
        request_id=request_id,
    )
