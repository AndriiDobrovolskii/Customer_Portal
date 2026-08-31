import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_keys import login_fail_account_key, login_fail_ip_key
from app.core.security import decode_access_token, hash_password
from app.main import app
from app.modules.account.models import AccountLifecycleAuditLog
from app.modules.email_verification.models import EmailVerificationToken
from app.modules.users.models import AuthAuditLog, RefreshToken, User, UserSession

pytestmark = pytest.mark.integration

# httpx's ASGITransport defaults to this client address when none is
# configured (see conftest.py's `client`/`real_client` fixtures) — every
# request through them presents this as the source IP.
_TEST_CLIENT_IP = "127.0.0.1"


async def _seed_login_user(
    db_session: AsyncSession,
    *,
    email: str,
    password: str,
    email_verified: bool,
    status: str = "PENDING_VERIFICATION",
    deactivated_at: datetime | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password=await hash_password(password),
        status=status,
    )
    user.email_verified = email_verified
    user.deactivated_at = deactivated_at
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


# --- LI-AC1: successful login (FR-1) --------------------------------------


async def test_login_correct_credentials_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="login.verified@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login.verified@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert: status + body shape
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 900
    assert len(body["access_token"]) > 0
    claims = decode_access_token(body["access_token"])
    assert claims.user_id == user.id

    # Assert: Set-Cookie attributes
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 1
    cookie_header = set_cookie_headers[0]
    assert cookie_header.startswith("refresh_token=")
    assert "Path=/api/v1/auth" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Secure" in cookie_header
    assert "samesite=strict" in cookie_header.lower()

    # Assert: persisted state
    session_result = await db_session.execute(
        select(UserSession).where(UserSession.jti == claims.jti)
    )
    session = session_result.scalar_one()
    assert session.user_id == user.id
    assert session.revoked_at is None

    refresh_result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    assert refresh_result.scalar_one() is not None

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(AuthAuditLog.actor_id == user.id)
    )
    audit_entry = audit_result.scalar_one()
    assert audit_entry.event == "login_succeeded"
    assert audit_entry.ip == _TEST_CLIENT_IP

    user_result = await db_session.execute(select(User).where(User.id == user.id))
    assert user_result.scalar_one().last_login_at is not None


# --- LI-AC2: wrong password (FR-2) ------------------------------------------


async def test_login_wrong_password_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="login.wrongpw@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
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
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/invalid-credentials"

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(AuthAuditLog.actor_id == user.id)
    )
    assert audit_result.scalar_one().reason == "bad_password"


# --- LI-AC3: unknown email, anti-enumeration (FR-3, resolved OD-3) ---------


async def test_login_unknown_email_returns_401_same_shape_as_wrong_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session,
        email="login.shape@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    wrong_password_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login.shape@example.com",
            "password": "WrongPassword1!",  # pragma: allowlist secret
        },
    )

    # Act
    unknown_email_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody.logs.in@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert unknown_email_response.status_code == wrong_password_response.status_code == 401
    assert unknown_email_response.json() == wrong_password_response.json()

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(AuthAuditLog.reason == "unknown_email")
    )
    entry = audit_result.scalar_one()
    assert entry.actor_id is None


# --- LI-AC4: account-state gating (FR-4) -------------------------------------


async def test_login_unverified_returns_403(client: AsyncClient, db_session: AsyncSession) -> None:
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


async def test_login_deactivated_past_grace_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session,
        email="login.deactivated.pastgrace@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="deactivated",
        deactivated_at=datetime.now(UTC) - timedelta(days=31),
    )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login.deactivated.pastgrace@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/account-deactivated"


async def test_login_deactivated_wrong_password_returns_401_not_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange — ordering guarantee (FR-4/DA-AC7).
    await _seed_login_user(
        db_session,
        email="login.deactivated.wrongpw@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="deactivated",
        deactivated_at=datetime.now(UTC) - timedelta(days=31),
    )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login.deactivated.wrongpw@example.com",
            "password": "WrongPassword1!",  # pragma: allowlist secret
        },
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["type"] == "https://portal.internal/errors/invalid-credentials"


# --- DA-AC8 (resolved OD-10): reactivation within the grace period ---------


async def test_login_deactivated_within_grace_reactivates_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="login.reactivate@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="deactivated",
        deactivated_at=datetime.now(UTC) - timedelta(days=5),
    )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login.reactivate@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 200
    assert len(response.json()["access_token"]) > 0

    user_result = await db_session.execute(select(User).where(User.id == user.id))
    persisted = user_result.scalar_one()
    assert persisted.status == "active"
    assert persisted.deactivated_at is None

    audit_result = await db_session.execute(
        select(AccountLifecycleAuditLog).where(AccountLifecycleAuditLog.user_id == user.id)
    )
    account_audit = audit_result.scalar_one()
    assert account_audit.event == "reactivated"
    assert account_audit.actor == "self"


# --- LI-AC5: brute-force throttling (FR-5) -----------------------------------


async def test_login_account_throttled_returns_429(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="login.throttled@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    for _ in range(10):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login.throttled@example.com",
                "password": "WrongPassword1!",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 401

    # Act: the 11th attempt is throttled, even with correct credentials.
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login.throttled@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 429
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/too-many-attempts"
    assert int(response.headers["retry-after"]) > 0

    # Assert: the counter is real, persisted Valkey state with a TTL.
    account_key = login_fail_account_key(user.id)
    assert int(await app.state.valkey_client.get(account_key)) == 10
    assert await app.state.valkey_client.ttl(account_key) > 0


async def test_login_missing_password_returns_422(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/login", json={"email": "login.missing.password@example.com"}
    )

    # Assert
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://portal.internal/errors/validation-failed"
    assert any(error["field"] == "password" for error in body["errors"])


async def test_login_unknown_field_returns_422(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login.unknown.field@example.com",
            "password": "Str0ng!Pass1",
            "isAdmin": True,
        },
    )

    # Assert
    assert response.status_code == 422


async def test_login_empty_password_returns_422_not_401(client: AsyncClient) -> None:
    # Act — resolved OD-8.
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login.empty.password@example.com", "password": ""},
    )

    # Assert
    assert response.status_code == 422


async def test_login_malformed_request_does_not_increment_throttle_counter(
    client: AsyncClient,
) -> None:
    # Act — resolved OD-6.
    response = await client.post(
        "/api/v1/auth/login", json={"email": "login.malformed@example.com"}
    )

    # Assert
    assert response.status_code == 422
    ip_key = login_fail_ip_key(_TEST_CLIENT_IP)
    assert await app.state.valkey_client.get(ip_key) is None
