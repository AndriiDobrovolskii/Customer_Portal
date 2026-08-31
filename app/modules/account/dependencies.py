from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.revocation_cache import RevocationCache
from app.db.dependencies import get_db_session, get_valkey_client
from app.modules.account.repository import AccountRepository
from app.modules.account.service import AccountService


def get_account_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    valkey_client: Annotated[Redis, Depends(get_valkey_client)],
) -> AccountService:
    repository = AccountRepository(session)
    cache = RevocationCache(valkey_client)
    return AccountService(repository, cache)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
