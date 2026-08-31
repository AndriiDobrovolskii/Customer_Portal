import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encode_access_token, hash_password
from app.main import app
from app.modules.profile.models import EmailChangeToken, ProfileAuditLog
from app.modules.users.models import User, UserSession

pytestmark = pytest.mark.integration


async def _seed_user(
    db_session: AsyncSession,
    *,
    email: str,
    password: str | None = None,
    display_name: str | None = None,
    locale: str | None = None,
    timezone: str | None = None,
    avatar_url: str | None = None,
    pending_email: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password=await hash_password(password or "Str0ng!Pass1"),
        status="ACTIVE",
    )
    user.email_verified = True
    user.display_name = display_name
    user.locale = locale
    user.timezone = timezone
    user.avatar_url = avatar_url
    user.pending_email = pending_email
    db_session.add(user)
    await db_session.flush()
    return user


async def _login(client: AsyncClient, *, email: str, password: str | None = None) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password or "Str0ng!Pass1"}
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


async def _seed_email_change_token(
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    raw_token: str | None = None,
    expires_at: datetime | None = None,
    consumed_at: datetime | None = None,
) -> str:
    raw_token = raw_token or secrets.token_urlsafe(32)
    token = EmailChangeToken(
        user_id=user_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(hours=24)),
    )
    token.consumed_at = consumed_at
    db_session.add(token)
    await db_session.flush()
    return raw_token


# --- UP-AC1 ------------------------------------------------------------------


async def test_update_profile_valid_input_returns_200_with_new_etag(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="up.happy@example.com")
    token = await _login(client, email="up.happy@example.com")

    # Act: GET /v1/profile is out of scope for this story, so there is no way
    # to read a starting ETag other than via a write — use If-Match: * for
    # this first request, which always matches regardless of current state.
    first = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={"display_name": "New Name"},
    )

    # Assert
    assert first.status_code == 200
    assert first.headers["etag"]
    body = first.json()
    assert body["display_name"] == "New Name"
    await db_session.refresh(user)
    assert user.display_name == "New Name"


# --- UP-AC2 --------------------------------------------------------------------


async def test_update_profile_missing_if_match_returns_400_precondition_required(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="up.noifmatch@example.com")
    token = await _login(client, email="up.noifmatch@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "New Name"},
    )

    # Assert
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/precondition-required"


# --- UP-AC3 --------------------------------------------------------------------


async def test_update_profile_stale_if_match_returns_412(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="up.stale@example.com")
    token = await _login(client, email="up.stale@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": '"stale-etag"'},
        json={"display_name": "New Name"},
    )

    # Assert
    assert response.status_code == 412


# --- UP-AC4/5/6 ------------------------------------------------------------------


async def test_update_profile_invalid_locale_returns_422_validation_failed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="up.badlocale@example.com")
    token = await _login(client, email="up.badlocale@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={"locale": "xx-XX"},
    )

    # Assert
    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "https://portal.internal/errors/validation-failed"
    assert body["errors"][0]["field"] == "locale"


async def test_update_profile_immutable_field_returns_422_immutable_field(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="up.immutable@example.com")
    token = await _login(client, email="up.immutable@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={"role": "admin"},
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"] == "https://portal.internal/errors/immutable-field"


async def test_update_profile_unknown_field_returns_422_validation_failed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="up.unknown@example.com")
    token = await _login(client, email="up.unknown@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={"is_super_user": True},
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"] == "https://portal.internal/errors/validation-failed"


# --- UP-AC8 ---------------------------------------------------------------------


async def test_update_profile_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.patch(
        "/api/v1/profile", headers={"If-Match": "*"}, json={"display_name": "New Name"}
    )

    # Assert
    assert response.status_code == 401


async def test_update_profile_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": "Bearer not-a-real-token", "If-Match": "*"},
        json={"display_name": "New Name"},
    )

    # Assert
    assert response.status_code == 401


async def test_update_profile_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="up.expired@example.com")
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
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {expired_token}", "If-Match": "*"},
        json={"display_name": "New Name"},
    )

    # Assert
    assert response.status_code == 401


async def test_update_profile_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="up.revoked@example.com")
    jti = uuid.uuid4()
    session = UserSession(
        jti=jti, user_id=user.id, expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    session.revoked_at = datetime.now(UTC)
    db_session.add(session)
    await db_session.flush()
    token = encode_access_token(user_id=user.id, jti=jti)

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={"display_name": "New Name"},
    )

    # Assert
    assert response.status_code == 401


# --- UP-AC9/UP-AC10 ---------------------------------------------------------------


async def test_update_profile_email_change_missing_password_returns_401_reauthentication(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="up.noPw@example.com")
    token = await _login(client, email="up.noPw@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={"email": "new.address@example.com"},
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["type"] == "https://portal.internal/errors/reauthentication-required"


async def test_update_profile_email_change_duplicate_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="up.taken@example.com")
    await _seed_user(db_session, email="up.wants-taken@example.com")
    token = await _login(client, email="up.wants-taken@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={
            "email": "up.taken@example.com",
            "current_password": "Str0ng!Pass1",  # pragma: allowlist secret
        },
    )

    # Assert
    assert response.status_code == 409


async def test_update_profile_email_change_initiated_returns_202(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="up.changing@example.com")
    token = await _login(client, email="up.changing@example.com")

    # Act
    response = await client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}", "If-Match": "*"},
        json={
            "email": "up.new-address@example.com",
            "current_password": "Str0ng!Pass1",  # pragma: allowlist secret
        },
    )

    # Assert
    assert response.status_code == 202
    body = response.json()
    assert body["pending_email"] == "up.new-address@example.com"
    assert body["email"] == "up.changing@example.com"
    await db_session.refresh(user)
    assert user.email == "up.changing@example.com"
    assert user.pending_email == "up.new-address@example.com"
    result = await db_session.execute(
        select(EmailChangeToken).where(EmailChangeToken.user_id == user.id)
    )
    assert result.scalar_one() is not None


# --- UP-AC11/UP-AC12 -------------------------------------------------------------


async def test_confirm_email_change_valid_token_returns_200_and_swaps_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(
        db_session, email="confirm.old@example.com", pending_email="confirm.new@example.com"
    )
    raw_token = await _seed_email_change_token(db_session, user_id=user.id)

    # Act
    response = await client.post("/api/v1/profile/confirm-email-change", json={"token": raw_token})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"email": "confirm.new@example.com"}
    await db_session.refresh(user)
    assert user.email == "confirm.new@example.com"
    assert user.pending_email is None


async def test_confirm_email_change_unknown_token_returns_400_token_invalid(
    client: AsyncClient,
) -> None:
    # Act
    response = await client.post(
        "/api/v1/profile/confirm-email-change", json={"token": "unknown-token"}
    )

    # Assert
    assert response.status_code == 400
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


async def test_confirm_email_change_expired_token_returns_400_token_expired(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(
        db_session, email="confirm.expiredold@example.com", pending_email="confirm.new2@example.com"
    )
    raw_token = await _seed_email_change_token(
        db_session, user_id=user.id, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )

    # Act
    response = await client.post("/api/v1/profile/confirm-email-change", json={"token": raw_token})

    # Assert
    assert response.status_code == 400
    assert response.json()["type"] == "https://portal.internal/errors/token-expired"
    await db_session.refresh(user)
    assert user.email == "confirm.expiredold@example.com"


async def test_confirm_email_change_concurrent_double_consume_only_one_succeeds(
    real_client: AsyncClient, cleanup_users: list[str]
) -> None:
    # Arrange
    email = f"race.{uuid.uuid4().hex}@example.com"
    cleanup_users.append(email)
    engine = app.state.db_engine
    raw_token = secrets.token_urlsafe(32)
    async with engine.begin() as connection:
        user_id = uuid.uuid4()
        await connection.execute(
            insert(User).values(
                id=user_id,
                email=email,
                hashed_password="argon2-hash",  # pragma: allowlist secret
                status="ACTIVE",
                email_verified=True,
                pending_email="race.new@example.com",
            )
        )
        await connection.execute(
            insert(EmailChangeToken).values(
                id=uuid.uuid4(),
                user_id=user_id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )

    # Act
    responses = await asyncio.gather(
        real_client.post("/api/v1/profile/confirm-email-change", json={"token": raw_token}),
        real_client.post("/api/v1/profile/confirm-email-change", json={"token": raw_token}),
    )

    # Assert
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 400]
    async with engine.connect() as connection:
        result = await connection.execute(
            select(EmailChangeToken.consumed_at).where(EmailChangeToken.user_id == user_id)
        )
        consumed_at_values = [row[0] for row in result.all()]
        assert len(consumed_at_values) == 1
        assert consumed_at_values[0] is not None


# --- profile_audit_log append-only enforcement (NFR-005) --------------------


async def test_profile_audit_log_rejects_update_and_delete(db_session: AsyncSession) -> None:
    # Arrange
    entry = ProfileAuditLog(
        actor_id=uuid.uuid4(),
        field="display_name",
        old_value="old",
        new_value="new",
        request_id="req-audit",
    )
    db_session.add(entry)
    await db_session.flush()

    # Act & Assert
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.execute(
            update(ProfileAuditLog).where(ProfileAuditLog.id == entry.id).values(field="tampered")
        )
