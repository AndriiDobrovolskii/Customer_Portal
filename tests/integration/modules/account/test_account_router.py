import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_keys import revoke_before_key
from app.core.config import get_settings
from app.core.security import encode_access_token, hash_password
from app.main import app
from app.modules.account.models import AccountLifecycleAuditLog
from app.modules.users.models import User, UserSession

pytestmark = pytest.mark.integration


async def _seed_active_user(
    db_session: AsyncSession, *, email: str, password: str | None = None
) -> User:
    user = User(
        email=email,
        hashed_password=await hash_password(password or "Str0ng!Pass1"),
        status="active",
    )
    user.email_verified = True
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_session_and_token(
    db_session: AsyncSession, *, user_id: uuid.UUID, issued_at: datetime | None = None
) -> str:
    jti = uuid.uuid4()
    # issued_at set explicitly (wall clock), not left to the column's
    # server_default=func.now(): Postgres now() returns the *transaction*
    # start time, which is frozen for this whole test under the db_session
    # fixture's SAVEPOINT-per-commit isolation — two sessions seeded in the
    # same test would otherwise get an identical issued_at, indistinguishable
    # from the revoke_before write it must be compared against.
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            issued_at=issued_at or datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=[])


async def test_deactivate_correct_password_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="deactivate.ok@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "deactivated"
    assert body["deactivated_at"]

    result = await db_session.execute(select(User).where(User.id == user.id))
    persisted = result.scalar_one()
    assert persisted.status == "deactivated"
    assert persisted.deactivated_at is not None

    audit_rows = await db_session.execute(
        select(AccountLifecycleAuditLog).where(AccountLifecycleAuditLog.user_id == user.id)
    )
    audit_entries = audit_rows.scalars().all()
    assert len(audit_entries) == 1
    assert audit_entries[0].event == "deactivated"
    assert audit_entries[0].actor == "self"

    revoke_before = await app.state.valkey_client.get(revoke_before_key(user.id))
    assert revoke_before is not None


async def test_deactivate_wrong_password_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="deactivate.wrongpw@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "WrongPassword1!"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/invalid-credentials"

    result = await db_session.execute(select(User).where(User.id == user.id))
    assert result.scalar_one().status == "active"


async def test_deactivate_already_deactivated_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="deactivate.repeat@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    first = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )
    assert first.status_code == 200
    # The second session's issued_at must be unambiguously later than the
    # revoke_before write, not just "the next wall-clock read" — Windows'
    # clock resolution (~15ms) can make two back-to-back datetime.now(UTC)
    # calls compare equal, which would make this test flaky against the
    # inclusive `issued_at <= revoke_before` fail-closed check. Anchoring
    # explicitly off the persisted revoke_before value removes that race.
    raw_revoke_before = await app.state.valkey_client.get(revoke_before_key(user.id))
    assert raw_revoke_before is not None
    revoke_before = datetime.fromisoformat(raw_revoke_before)
    second_token = await _seed_session_and_token(
        db_session, user_id=user.id, issued_at=revoke_before + timedelta(milliseconds=50)
    )

    # Act
    response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {second_token}"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"] == "https://portal.internal/errors/already-deactivated"


async def test_deactivate_then_reuse_old_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="deactivate.oldtoken@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    deactivate_response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )
    assert deactivate_response.status_code == 200

    # Act: reuse the pre-deactivation token against any authenticated route
    response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 401


async def test_deactivate_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/account/deactivate",
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 401


async def test_deactivate_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 401


async def test_deactivate_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="deactivate.expired@example.com")
    settings = get_settings()
    jti = uuid.uuid4()
    db_session.add(
        UserSession(jti=jti, user_id=user.id, expires_at=datetime.now(UTC) - timedelta(hours=2))
    )
    await db_session.flush()
    expired_token = jwt.encode(
        {"sub": str(user.id), "jti": str(jti), "exp": datetime.now(UTC) - timedelta(hours=1)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    # Act
    response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {expired_token}"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 401


async def test_deactivate_revoked_session_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="deactivate.revoked@example.com")
    jti = uuid.uuid4()
    session = UserSession(
        jti=jti, user_id=user.id, expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    session.revoked_at = datetime.now(UTC)
    db_session.add(session)
    await db_session.flush()
    token = encode_access_token(user_id=user.id, jti=jti, scopes=[])

    # Act
    response = await client.post(
        "/api/v1/account/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 401


async def test_deactivate_concurrent_requests_only_one_succeeds(real_client: AsyncClient) -> None:
    # Arrange: seeded via a real, committed connection (not the rolled-back
    # db_session fixture) so both concurrent requests' independent
    # connections can see the row, matching the users-router concurrency
    # test's precedent.
    email = f"race.{uuid.uuid4().hex}@example.com"
    user_id = uuid.uuid4()
    engine = app.state.db_engine
    async with engine.begin() as connection:
        await connection.execute(
            insert(User).values(
                id=user_id,
                email=email,
                hashed_password=await hash_password("Str0ng!Pass1"),
                status="active",
                email_verified=True,
            )
        )
        jti = uuid.uuid4()
        await connection.execute(
            insert(UserSession).values(
                jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1)
            )
        )
    token = encode_access_token(user_id=user_id, jti=jti, scopes=[])

    # Act
    responses = await asyncio.gather(
        real_client.post(
            "/api/v1/account/deactivate",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
        ),
        real_client.post(
            "/api/v1/account/deactivate",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "Str0ng!Pass1"},  # pragma: allowlist secret
        ),
    )

    # Assert
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 409]

    async with engine.connect() as connection:
        result = await connection.execute(select(User.status).where(User.id == user_id))
        assert result.scalar_one() == "deactivated"
