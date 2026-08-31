import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from app.db.dependencies import get_db_session
from app.db.session import create_engine_and_sessionmaker
from app.main import app


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def valkey_container() -> Iterator[RedisContainer]:
    # RedisContainer speaks the Redis wire protocol Valkey implements; the
    # real Valkey image is used (not a redis-branded one) so this is real
    # Valkey per AGENTS.md §5, not a compatible substitute.
    with RedisContainer(image="valkey/valkey:7.2-alpine") as container:
        yield container


@pytest.fixture(scope="session", autouse=True)
async def _valkey(valkey_container: RedisContainer) -> AsyncIterator[None]:
    # Same test-only entry point rationale as _database below: ASGITransport
    # never runs the app's `lifespan`, so app.state.valkey_client is wired
    # here instead. get_client() on the container returns a sync client;
    # the app needs redis.asyncio, constructed directly from the same host/port.
    # An async fixture (not asyncio.run() in a sync one) so teardown closes
    # the client on the same event loop that opened its connections —
    # asyncio.run() here raised "Event loop is closed" against a transport
    # bound to pytest-asyncio's session loop.
    client: Redis = Redis(
        host=valkey_container.get_container_host_ip(),
        port=int(valkey_container.get_exposed_port(valkey_container.port)),
        decode_responses=True,
    )
    app.state.valkey_client = client
    yield
    await client.aclose()


@pytest.fixture(autouse=True)
async def _flush_valkey() -> AsyncIterator[None]:
    """Per-test isolation for Valkey, mirroring db_session's per-test
    rollback: AGENTS.md §5 requires Valkey flushed or namespaced per test."""
    yield
    await app.state.valkey_client.flushdb()


@pytest.fixture(scope="session", autouse=True)
def _database(postgres_url: str) -> Iterator[None]:
    # httpx's ASGITransport never runs the app's `lifespan`, so the engine and
    # session factory that lifespan would normally set on app.state are wired
    # here instead — same objects, same app.state attributes, test-only entry
    # point. See ARCHITECTURE.md §3.6 (singletons live on app.state).
    os.environ["DATABASE_URL"] = postgres_url
    engine, session_factory = create_engine_and_sessionmaker(postgres_url)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield

    command.downgrade(alembic_cfg, "base")
    asyncio.run(engine.dispose())


@pytest.fixture
async def db_connection() -> AsyncIterator[AsyncConnection]:
    engine = app.state.db_engine
    async with engine.connect() as connection:
        yield connection


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """A session bound to a connection-level transaction that is always rolled back.

    The app commits via SAVEPOINTs (join_transaction_mode="create_savepoint"), so
    request-scoped commit() calls in service code work unmodified, but nothing
    survives past the outer rollback below — each test is fully isolated.
    """
    transaction = await db_connection.begin()
    session = AsyncSession(
        bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await session.close()
        await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as async_client:
        yield async_client


@pytest.fixture
async def real_client() -> AsyncIterator[AsyncClient]:
    """A client that hits the real, uncontained request-scoped session.

    Used only where the test needs genuine concurrent, independently-committed
    transactions (e.g. proving a DB-level unique constraint under a race) —
    the db_session/client fixtures share one connection and can't express that.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as async_client:
        yield async_client


@pytest.fixture
async def cleanup_users() -> AsyncIterator[list[str]]:
    emails_to_delete: list[str] = []
    yield emails_to_delete
    if not emails_to_delete:
        return
    engine = app.state.db_engine
    async with engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM users WHERE lower(email) = ANY(:emails)"),
            {"emails": [email.lower() for email in emails_to_delete]},
        )
