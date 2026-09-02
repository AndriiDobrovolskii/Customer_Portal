from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.revocation_cache import RevocationCache
from app.db.dependencies import get_db_session, get_valkey_client
from app.modules.admin_users.repository import AdminUserRepository
from app.modules.admin_users.service import AdminUserService
from app.modules.roles.dependencies import RoleServiceDep


def get_admin_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    valkey_client: Annotated[Redis, Depends(get_valkey_client)],
    role_service: RoleServiceDep,
) -> AdminUserService:
    repository = AdminUserRepository(session)
    revocation_cache = RevocationCache(valkey_client)
    return AdminUserService(repository, role_service, revocation_cache)


AdminUserServiceDep = Annotated[AdminUserService, Depends(get_admin_user_service)]
