import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import get_email_sender
from app.main import app
from app.modules.email_verification.models import EmailVerificationToken
from app.modules.users.models import User

pytestmark = pytest.mark.integration


async def _seed_user(db_session: AsyncSession, *, email: str, email_verified: bool = False) -> User:
    user = User(email=email, hashed_password="argon2-hash", status="PENDING_VERIFICATION")
    user.email_verified = email_verified
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_token(
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    raw_token: str | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    consumed_at: datetime | None = None,
) -> str:
    raw_token = raw_token or secrets.token_urlsafe(32)
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(hours=24)),
    )
    if issued_at is not None:
        token.issued_at = issued_at
    token.consumed_at = consumed_at
    db_session.add(token)
    await db_session.flush()
    return raw_token


# --- VE-AC1 --------------------------------------------------------------------


async def test_verify_email_valid_token_returns_200_and_marks_verified(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="verify.success@example.com")
    raw_token = await _seed_token(db_session, user_id=user.id)

    # Act
    response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"email_verified": True}
    await db_session.refresh(user)
    assert user.email_verified is True
    result = await db_session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    token = result.scalar_one()
    assert token.consumed_at is not None


async def test_verify_email_concurrent_double_consume_only_one_succeeds(
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
                status="PENDING_VERIFICATION",
                email_verified=False,
            )
        )
        await connection.execute(
            insert(EmailVerificationToken).values(
                id=uuid.uuid4(),
                user_id=user_id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )

    # Act
    responses = await asyncio.gather(
        real_client.post("/api/v1/auth/verify-email", json={"token": raw_token}),
        real_client.post("/api/v1/auth/verify-email", json={"token": raw_token}),
    )

    # Assert
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 400]
    async with engine.connect() as connection:
        result = await connection.execute(
            select(EmailVerificationToken.consumed_at).where(
                EmailVerificationToken.user_id == user_id
            )
        )
        consumed_at_values = [row[0] for row in result.all()]
        assert len(consumed_at_values) == 1
        assert consumed_at_values[0] is not None


async def test_verify_email_expired_token_returns_400_token_expired(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="verify.expired@example.com")
    raw_token = await _seed_token(
        db_session, user_id=user.id, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )

    # Act
    response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})

    # Assert
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://portal.internal/errors/token-expired"
    await db_session.refresh(user)
    assert user.email_verified is False


# --- VE-AC3 ----------------------------------------------------------------------


async def test_verify_email_consumed_token_returns_400_token_invalid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="verify.consumed@example.com")
    raw_token = await _seed_token(db_session, user_id=user.id)
    first = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert first.status_code == 200

    # Act
    response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})

    # Assert
    assert response.status_code == 400
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


# --- VE-AC4 ------------------------------------------------------------------------


async def test_verify_email_unknown_token_returns_400_token_invalid(client: AsyncClient) -> None:
    # Act
    response = await client.post("/api/v1/auth/verify-email", json={"token": "unknown-token-value"})

    # Assert
    assert response.status_code == 400
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


async def test_verify_email_missing_token_returns_400_token_invalid(client: AsyncClient) -> None:
    # Act
    response = await client.post("/api/v1/auth/verify-email", json={})

    # Assert
    assert response.status_code == 400
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


# --- VE-AC7 -------------------------------------------------------------------------


async def test_resend_within_cooldown_returns_429_with_retry_after(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="resend.cooldown@example.com")
    await _seed_token(db_session, user_id=user.id, issued_at=datetime.now(UTC))

    # Act
    response = await client.post(
        "/api/v1/auth/verify-email/resend", json={"email": "resend.cooldown@example.com"}
    )

    # Assert
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.json()["type"] == "https://portal.internal/errors/too-many-attempts"


# --- VE-AC8 -------------------------------------------------------------------------


async def test_resend_unregistered_email_returns_200_generic_body(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/verify-email/resend", json={"email": "nobody.here@example.com"}
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "message": "If this email is registered and unverified, a verification email has been sent."
    }


@pytest.mark.parametrize("payload", [{}, {"email": "not-an-email"}])
async def test_resend_malformed_email_returns_400_invalid_request(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    # Act
    response = await client.post("/api/v1/auth/verify-email/resend", json=payload)

    # Assert
    assert response.status_code == 400
    assert response.json()["type"] == "https://portal.internal/errors/invalid-request"


async def test_resend_unknown_field_returns_422(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/verify-email/resend",
        json={"email": "extra@example.com", "isAdmin": True},
    )

    # Assert
    assert response.status_code == 422


# --- VE-AC9 -------------------------------------------------------------------------


async def test_resend_already_verified_account_returns_200_generic_body_no_new_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="already.verified@example.com", email_verified=True)

    # Act
    response = await client.post(
        "/api/v1/auth/verify-email/resend", json={"email": "already.verified@example.com"}
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "message": "If this email is registered and unverified, a verification email has been sent."
    }
    result = await db_session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    assert result.first() is None


# --- Round trip via the overridden email sender -------------------------------------


class _RecordingEmailSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        self.sent.append({"to": to, "raw_token": raw_token})


async def test_resend_then_verify_round_trip_via_overridden_email_sender(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_user(db_session, email="round.trip@example.com")
    recorder = _RecordingEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: recorder
    try:
        resend_response = await client.post(
            "/api/v1/auth/verify-email/resend", json={"email": "round.trip@example.com"}
        )
        assert resend_response.status_code == 200
        assert len(recorder.sent) == 1
        raw_token = recorder.sent[0]["raw_token"]

        # Act
        verify_response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    finally:
        app.dependency_overrides.pop(get_email_sender, None)

    # Assert
    assert verify_response.status_code == 200
    assert verify_response.json() == {"email_verified": True}
