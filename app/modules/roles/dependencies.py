from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.revocation_cache import PermissionEpochCache
from app.db.dependencies import get_db_session, get_valkey_client
from app.modules.roles.exceptions import InsufficientPermissionError
from app.modules.roles.repository import RoleRepository, UserRoleRepository
from app.modules.roles.service import RoleService
from app.modules.users.dependencies import CurrentUserDep
from app.modules.users.service import AuthenticatedUser


def get_role_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    valkey_client: Annotated[Redis, Depends(get_valkey_client)],
) -> RoleService:
    role_repository = RoleRepository(session)
    user_role_repository = UserRoleRepository(session)
    permission_epoch_cache = PermissionEpochCache(valkey_client)
    return RoleService(role_repository, user_role_repository, permission_epoch_cache)


RoleServiceDep = Annotated[RoleService, Depends(get_role_service)]


def require_scope(scope: str) -> Callable[[AuthenticatedUser], Awaitable[None]]:
    """Cross-cutting scope-check factory, first introduced by this module.

    Not part of the original US-012 API design (which described the
    requirement in prose only); every `/v1/admin/*` route this story adds
    needs one, so it's built once here rather than duplicated per route.
    """

    async def _check(current_user: CurrentUserDep) -> None:
        if scope not in current_user.scopes:
            raise InsufficientPermissionError

    return _check
