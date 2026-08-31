from collections.abc import AsyncIterator

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session


async def get_valkey_client(request: Request) -> Redis:
    # Unlike get_db_session, no per-request object is created here: the
    # redis-py client already manages its own connection pool internally
    # and is safe to share across concurrent requests.
    valkey_client: Redis = request.app.state.valkey_client
    return valkey_client
