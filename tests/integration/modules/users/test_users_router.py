import asyncio
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.main import app
from app.modules.email_verification.models import EmailVerificationToken
from app.modules.users.models import User

pytestmark = pytest.mark.integration


async def _seed_login_user(
    db_session: AsyncSession, *, email: str, password: str, email_verified: bool
) -> User:
    user = User(
        email=email,
        hashed_password=await hash_password(password),
        status="PENDING_VERIFICATION",
    )
    user.email_verified = email_verified
    db_session.add(user)
    await db_session.flush()
    return user


async def test_register_valid_input_returns_201_with_location_and_body(
    client: AsyncClient,
) -> None:
    # Arrange
    payload = {"email": "new.user@example.com", "password": "Str0ng!Pass1"}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    body = response.json()
    assert response.status_code == 201
    assert response.headers["location"] == f"/api/v1/users/{body['id']}"
    assert set(body.keys()) == {"id", "email", "status", "createdAt"}
    assert body["email"] == "new.user@example.com"
    assert body["status"] == "PENDING_VERIFICATION"


async def test_register_persists_argon2id_hash_not_plaintext(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    payload = {"email": "hash.check@example.com", "password": "Str0ng!Pass1"}

    # Act
    await client.post("/api/v1/auth/register", json=payload)

    # Assert
    result = await db_session.execute(select(User).where(User.email == "hash.check@example.com"))
    user = result.scalar_one()
    assert user.hashed_password != "Str0ng!Pass1"
    assert user.hashed_password.startswith("$argon2id$")


async def test_register_duplicate_email_same_case_returns_409(client: AsyncClient) -> None:
    # Arrange
    payload = {"email": "dup@example.com", "password": "Str0ng!Pass1"}
    await client.post("/api/v1/auth/register", json=payload)

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    assert response.status_code == 409


async def test_register_duplicate_email_different_case_returns_409(client: AsyncClient) -> None:
    # Arrange
    await client.post(
        "/api/v1/auth/register",
        json={"email": "Case@Example.com", "password": "Str0ng!Pass1"},
    )

    # Act
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "CASE@EXAMPLE.COM", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 409


async def test_register_invalid_email_format_returns_400_with_error_schema(
    client: AsyncClient,
) -> None:
    # Arrange
    payload = {"email": "not-an-email", "password": "Str0ng!Pass1"}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    assert response.status_code == 400
    body = response.json()
    assert body["errors"] == [
        {
            "field": "email",
            "message": body["errors"][0]["message"],
            "code": "INVALID_FORMAT",
        }
    ]


async def test_register_weak_password_returns_400_with_error_schema(client: AsyncClient) -> None:
    # Arrange
    payload = {"email": "weak.pw@example.com", "password": "weak"}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    assert response.status_code == 400
    body = response.json()
    assert body["errors"][0]["field"] == "password"
    assert body["errors"][0]["code"] == "POLICY_VIOLATION"


async def test_register_missing_password_field_returns_400(client: AsyncClient) -> None:
    # Arrange
    payload = {"email": "no.password@example.com"}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "password"


async def test_register_empty_password_returns_400(client: AsyncClient) -> None:
    # Arrange
    payload = {"email": "empty.password@example.com", "password": ""}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "REQUIRED"


async def test_register_unknown_field_returns_422(client: AsyncClient) -> None:
    # Arrange
    payload = {
        "email": "extra.field@example.com",
        "password": "Str0ng!Pass1",
        "isAdmin": True,
    }

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    assert response.status_code == 422


async def test_register_non_string_password_returns_422_without_leaking_value(
    client: AsyncClient,
) -> None:
    # Arrange
    payload = {"email": "non.string.password@example.com", "password": ["Str0ng!Pass1"]}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    assert response.status_code == 422
    assert "Str0ng!Pass1" not in response.text
    assert "input" not in response.json()["detail"][0]


async def test_register_response_never_contains_password_fields(client: AsyncClient) -> None:
    # Arrange
    payload = {"email": "no.leak@example.com", "password": "Str0ng!Pass1"}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    body_text = response.text.lower()
    assert "password" not in body_text
    assert "hash" not in body_text


async def test_register_issues_a_pending_verification_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    payload = {"email": "token.issued@example.com", "password": "Str0ng!Pass1"}

    # Act
    response = await client.post("/api/v1/auth/register", json=payload)

    # Assert
    body = response.json()
    result = await db_session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == uuid.UUID(body["id"])
        )
    )
    tokens = result.scalars().all()
    assert len(tokens) == 1
    token = tokens[0]
    assert token.consumed_at is None
    expected_expiry = token.issued_at + timedelta(hours=24)
    assert abs((token.expires_at - expected_expiry).total_seconds()) < 5
    assert set(body.keys()) == {"id", "email", "status", "createdAt"}


async def test_concurrent_duplicate_registration_only_one_succeeds(
    real_client: AsyncClient, cleanup_users: list[str]
) -> None:
    # Arrange
    email_lower = f"race.{uuid.uuid4().hex}@example.com"
    email_upper = email_lower.upper()
    cleanup_users.append(email_lower)

    # Act
    responses = await asyncio.gather(
        real_client.post(
            "/api/v1/auth/register", json={"email": email_lower, "password": "Str0ng!Pass1"}
        ),
        real_client.post(
            "/api/v1/auth/register", json={"email": email_upper, "password": "Str0ng!Pass1"}
        ),
    )

    # Assert
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [201, 409]

    engine = app.state.db_engine
    async with engine.connect() as connection:
        result = await connection.execute(select(User).where(User.email == email_lower.lower()))
        assert len(result.all()) == 1


# --- VE-AC5: unverified account cannot log in -----------------------------------


async def test_login_correct_password_unverified_returns_403_email_not_verified(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session,
        email="login.unverified@example.com",
        password="Str0ng!Pass1",
        email_verified=False,
    )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login.unverified@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/email-not-verified"


# --- VE-AC6: verified account logs in normally ----------------------------------


async def test_login_correct_password_verified_returns_200_with_access_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session, email="login.verified@example.com", password="Str0ng!Pass1", email_verified=True
    )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login.verified@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


async def test_login_wrong_password_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session, email="login.wrongpw@example.com", password="Str0ng!Pass1", email_verified=True
    )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login.wrongpw@example.com",
            "password": "WrongPassword1!",  # pragma: allowlist secret
        },
    )

    # Assert
    assert response.status_code == 401


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody.logs.in@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 401
