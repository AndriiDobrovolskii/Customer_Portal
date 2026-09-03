import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_keys import login_fail_account_key, login_fail_ip_key
from app.core.config import get_settings
from app.core.security import (
    decode_access_token,
    encode_access_token,
    hash_password,
    hash_refresh_token,
)
from app.main import app
from app.modules.account.models import AccountLifecycleAuditLog
from app.modules.email_verification.models import EmailVerificationToken
from app.modules.roles.models import Role, UserRole
from app.modules.users.models import (
    AuthAuditLog,
    PasswordResetToken,
    RefreshToken,
    User,
    UserSession,
)

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


# --- US-2.2 (spec US-2.2): logout / logout-all -------------------------------


_LOGOUT_TEST_PASSWORD = "Str0ng!Pass1"  # pragma: allowlist secret


async def _login(
    client: AsyncClient, db_session: AsyncSession, *, email: str, password: str | None = None
) -> tuple[User, str]:
    """Seeds an active/verified user, logs in through the real endpoint (so
    the client's cookie jar picks up the refresh cookie exactly as a real
    browser would), and returns (user, access_token).
    """
    password = password or _LOGOUT_TEST_PASSWORD
    user = await _seed_login_user(
        db_session, email=email, password=password, email_verified=True, status="active"
    )
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return user, response.json()["access_token"]


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


# --- LO-AC1: logout on the current device (FR-1) -----------------------------


async def test_logout_returns_204_and_revokes_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, access_token = await _login(client, db_session, email="logout.happy@example.com")
    claims = decode_access_token(access_token)
    refresh_result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    refresh_token_row = refresh_result.scalar_one()

    # Act
    response = await client.post("/api/v1/auth/logout", headers=_auth_headers(access_token))

    # Assert: status + Set-Cookie clear
    assert response.status_code == 204
    assert response.content == b""
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 1
    assert "refresh_token=" in set_cookie_headers[0]
    assert "Max-Age=0" in set_cookie_headers[0]

    # Assert: persisted state
    session_result = await db_session.execute(
        select(UserSession).where(UserSession.jti == claims.jti)
    )
    assert session_result.scalar_one().revoked_at is not None

    await db_session.refresh(refresh_token_row)
    assert refresh_token_row.revoked_at is not None

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(AuthAuditLog.event == "logout", AuthAuditLog.actor_id == user.id)
    )
    audit_entry = audit_result.scalar_one()
    assert audit_entry.scope == "session"


async def test_logout_no_refresh_cookie_returns_204_no_set_cookie(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    _, access_token = await _login(client, db_session, email="logout.nocookie@example.com")
    client.cookies.clear()

    # Act
    response = await client.post("/api/v1/auth/logout", headers=_auth_headers(access_token))

    # Assert
    assert response.status_code == 204
    assert response.headers.get_list("set-cookie") == []


async def test_logout_stale_refresh_cookie_returns_204_indistinguishable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    _, access_token = await _login(client, db_session, email="logout.stalecookie@example.com")
    client.cookies.set("refresh_token", "never-issued-value", path="/api/v1/auth")

    # Act
    response = await client.post("/api/v1/auth/logout", headers=_auth_headers(access_token))

    # Assert: identical shape to the matched-cookie happy path — 204, cookie
    # cleared (one was presented), no error revealing the mismatch.
    assert response.status_code == 204
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 1
    assert "Max-Age=0" in set_cookie_headers[0]


async def test_logout_cross_user_refresh_cookie_does_not_revoke_other_users_family(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: victim logs in first; their raw refresh-token cookie value is
    # captured from the shared jar (simulating a leaked/stolen token). An
    # unrelated attacker then logs in with their own credentials.
    await _login(client, db_session, email="logout.idor.victim@example.com")
    victim_refresh_token = client.cookies.get("refresh_token")
    assert victim_refresh_token is not None
    victim_row = (
        await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(victim_refresh_token)
            )
        )
    ).scalar_one()

    _, attacker_access_token = await _login(
        client, db_session, email="logout.idor.attacker@example.com"
    )
    client.cookies.set("refresh_token", victim_refresh_token, path="/api/v1/auth")

    # Act: attacker's own access token, paired with the victim's stolen
    # refresh cookie.
    response = await client.post(
        "/api/v1/auth/logout", headers=_auth_headers(attacker_access_token)
    )

    # Assert: 204, indistinguishable from a lookup-miss (advisor-found IDOR,
    # fixed 2026-09-01) — the victim's own refresh-token family is untouched.
    assert response.status_code == 204
    await db_session.refresh(victim_row)
    assert victim_row.revoked_at is None


# --- LO-AC2: logout everywhere (FR-2) ----------------------------------------


async def test_logout_all_returns_204_and_revokes_every_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    _, access_token = await _login(client, db_session, email="logout.all@example.com")

    # Act
    response = await client.post("/api/v1/auth/logout-all", headers=_auth_headers(access_token))

    # Assert
    assert response.status_code == 204
    assert response.content == b""

    # A second request with the same pre-logout-all token is now rejected.
    follow_up = await client.patch("/api/v1/profile", json={}, headers=_auth_headers(access_token))
    assert follow_up.status_code == 401


# --- LO-AC3: unauthenticated logout request rejected (FR-3) -----------------


async def test_logout_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post("/api/v1/auth/logout")

    # Assert
    assert response.status_code == 401


async def test_logout_invalid_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post("/api/v1/auth/logout", headers=_auth_headers("not-a-real-jwt"))

    # Assert
    assert response.status_code == 401


async def _make_expired_token(db_session: AsyncSession, *, user_id: uuid.UUID) -> str:
    settings = get_settings()
    jti = uuid.uuid4()
    db_session.add(
        UserSession(jti=jti, user_id=user_id, expires_at=datetime.now(UTC) - timedelta(hours=2))
    )
    await db_session.flush()
    token: str = jwt.encode(
        {"sub": str(user_id), "jti": str(jti), "exp": datetime.now(UTC) - timedelta(hours=1)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token


async def test_logout_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange — an expired token fails to decode at all (FR-3), so it never
    # reaches the allow_revoked leniency (resolved OD-2) that a merely
    # *revoked* token gets.
    user = await _seed_login_user(
        db_session,
        email="logout.expired@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    expired_token = await _make_expired_token(db_session, user_id=user.id)

    # Act
    response = await client.post("/api/v1/auth/logout", headers=_auth_headers(expired_token))

    # Assert
    assert response.status_code == 401


async def test_logout_all_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="logout.all.expired@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    expired_token = await _make_expired_token(db_session, user_id=user.id)

    # Act
    response = await client.post("/api/v1/auth/logout-all", headers=_auth_headers(expired_token))

    # Assert
    assert response.status_code == 401


# --- LO-AC4 (resolved OD-2): idempotent repeat logout ------------------------


async def test_logout_repeat_call_same_token_returns_204_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    _, access_token = await _login(client, db_session, email="logout.repeat@example.com")
    claims = decode_access_token(access_token)
    first_response = await client.post("/api/v1/auth/logout", headers=_auth_headers(access_token))
    assert first_response.status_code == 204
    session_result = await db_session.execute(
        select(UserSession).where(UserSession.jti == claims.jti)
    )
    revoked_at_after_first_call = session_result.scalar_one().revoked_at
    assert revoked_at_after_first_call is not None

    # Act: same access token, presented again
    second_response = await client.post("/api/v1/auth/logout", headers=_auth_headers(access_token))

    # Assert: identical response shape (LO-AC4)
    assert second_response.status_code == 204
    assert second_response.content == b""

    # Assert: no additional revocation side effect (LO-AC4) — the session's
    # revocation timestamp is untouched by the repeat call, not re-written.
    session_result_2 = await db_session.execute(
        select(UserSession).where(UserSession.jti == claims.jti)
    )
    assert session_result_2.scalar_one().revoked_at == revoked_at_after_first_call


# --- LO-AC5 (resolved OD-2 boundary): leniency is /logout-only --------------


async def test_protected_endpoint_rejects_revoked_access_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    _, access_token = await _login(client, db_session, email="logout.thenprofile@example.com")
    await client.post("/api/v1/auth/logout", headers=_auth_headers(access_token))

    # Act
    response = await client.patch("/api/v1/profile", json={}, headers=_auth_headers(access_token))

    # Assert
    assert response.status_code == 401


async def test_logout_all_does_not_share_logout_leniency_rejects_revoked_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: revoke the session via a plain /logout call first
    _, access_token = await _login(client, db_session, email="logout.all.boundary@example.com")
    first_logout = await client.post("/api/v1/auth/logout", headers=_auth_headers(access_token))
    assert first_logout.status_code == 204

    # Act: the same now-revoked token is presented to /logout-all
    response = await client.post("/api/v1/auth/logout-all", headers=_auth_headers(access_token))

    # Assert: no leniency here — 401, not 204
    assert response.status_code == 401


# --- US-2.3 (spec US-2.3): refresh token rotation ----------------------------

_REFRESH_TEST_PASSWORD = "Str0ng!Pass1"  # pragma: allowlist secret


async def _login_for_refresh(
    client: AsyncClient, db_session: AsyncSession, *, email: str
) -> tuple[User, str]:
    """Seeds an active/verified user, logs in through the real endpoint, and
    returns (user, raw_refresh_token) — the raw cookie value is also left in
    the client's cookie jar, exactly as a browser would carry it forward.
    """
    user = await _seed_login_user(
        db_session,
        email=email,
        password=_REFRESH_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": _REFRESH_TEST_PASSWORD}
    )
    assert response.status_code == 200
    raw_refresh_token = client.cookies.get("refresh_token")
    assert raw_refresh_token is not None
    return user, raw_refresh_token


async def _seed_refresh_token_row(
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
    consumed_at: datetime | None = None,
    revoked_at: datetime | None = None,
    last_used_at: datetime | None = None,
    issued_at: datetime | None = None,
) -> str:
    """Directly seeds a refresh_tokens row for full control over its state
    (idle/absolute/revoked/consumed), returning the raw presented value.
    """
    raw_token = f"raw-refresh-{uuid.uuid4()}"
    row = RefreshToken(
        token_hash=hash_refresh_token(raw_token),
        family_id=family_id or uuid.uuid4(),
        user_id=user_id,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=30)),
        last_used_at=last_used_at,
    )
    db_session.add(row)
    await db_session.flush()
    row.issued_at = issued_at or datetime.now(UTC)
    if consumed_at is not None:
        row.consumed_at = consumed_at
    if revoked_at is not None:
        row.revoked_at = revoked_at
    await db_session.flush()
    return raw_token


def _set_refresh_cookie(client: AsyncClient, raw_token: str) -> None:
    client.cookies.set("refresh_token", raw_token, path="/api/v1/auth")


# --- RT-AC1: successful rotation (FR-1) --------------------------------------


async def test_refresh_returns_200_and_rotates_cookie(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, old_raw_token = await _login_for_refresh(
        client, db_session, email="refresh.happy@example.com"
    )
    old_row = (
        await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(old_raw_token))
        )
    ).scalar_one()

    # Act
    response = await client.post("/api/v1/auth/refresh")

    # Assert: status + body shape (no token_type, unlike login)
    assert response.status_code == 200
    body = response.json()
    # mfa_enrollment_deadline (US-2.5 FR-6/OD-4) is always present, null
    # when the account isn't in a privileged-role grace period.
    assert set(body.keys()) == {"access_token", "expires_in", "mfa_enrollment_deadline"}
    assert body["mfa_enrollment_deadline"] is None
    assert body["expires_in"] == 900
    claims = decode_access_token(body["access_token"])
    assert claims.user_id == user.id

    # Assert: Set-Cookie rotates the value, same attributes as /login
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 1
    cookie_header = set_cookie_headers[0]
    assert cookie_header.startswith("refresh_token=")
    assert f"refresh_token={old_raw_token}" not in cookie_header
    assert "Path=/api/v1/auth" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Secure" in cookie_header

    # Assert: persisted state
    await db_session.refresh(old_row)
    assert old_row.consumed_at is not None
    new_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.token_hash != old_row.token_hash
        )
    )
    new_row = new_result.scalar_one()
    assert new_row.family_id == old_row.family_id
    assert new_row.expires_at == old_row.expires_at

    # Assert: a new user_sessions row backs the new access token
    session_result = await db_session.execute(
        select(UserSession).where(UserSession.jti == claims.jti)
    )
    assert session_result.scalar_one().revoked_at is None


# --- RT-AC2: reuse detection (FR-2) -------------------------------------------


async def test_refresh_reuse_returns_401_and_revokes_family(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: rotate once (consuming the original token), then replay it.
    user, old_raw_token = await _login_for_refresh(
        client, db_session, email="refresh.reuse@example.com"
    )
    user_id = user.id
    old_row = (
        await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(old_raw_token))
        )
    ).scalar_one()
    family_id = old_row.family_id
    first_refresh = await client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200

    # Backdate consumption past the 10s concurrency grace window (RT-AC6) —
    # otherwise this immediate replay would read as a race, not reuse, per
    # FR-7's own deliberate design (a real attacker replaying within that
    # window is indistinguishable from a legitimate double-render).
    db_session.expire_all()
    await db_session.refresh(old_row)
    old_row.consumed_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.flush()

    # Act: replay the already-consumed original token
    _set_refresh_cookie(client, old_raw_token)
    response = await client.post("/api/v1/auth/refresh")

    # Assert
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"

    # expire_all(): the test's session already holds `old_row` in its
    # identity map from the query above; without expiring, a second query
    # for the same rows would return the pre-request cached objects instead
    # of the app's committed changes (expire_on_commit=False, per conftest).
    db_session.expire_all()
    family_result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    )
    for row in family_result.scalars().all():
        assert row.revoked_at is not None

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(
            AuthAuditLog.event == "refresh_reuse_detected", AuthAuditLog.actor_id == user_id
        )
    )
    audit_entry = audit_result.scalar_one()
    assert audit_entry.severity == "high"


# --- RT-AC3: unknown / expired / revoked-by-logout, indistinguishable (FR-3) -


async def test_refresh_no_cookie_returns_401(client: AsyncClient) -> None:
    # Arrange: this project's per-protected-route "no token" security case
    # (AGENTS.md §5) — this route's equivalent credential is the cookie,
    # not a Bearer token, so "no token" means no cookie at all.
    # Act
    response = await client.post("/api/v1/auth/refresh")

    # Assert
    assert response.status_code == 401
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


async def test_refresh_unknown_expired_revoked_return_identical_401_body(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="refresh.threecases@example.com",
        password=_REFRESH_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    expired_raw = await _seed_refresh_token_row(
        db_session, user_id=user.id, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    revoked_raw = await _seed_refresh_token_row(
        db_session, user_id=user.id, revoked_at=datetime.now(UTC)
    )

    # Act
    _set_refresh_cookie(client, "never-issued-token-value")
    unknown_response = await client.post("/api/v1/auth/refresh")
    _set_refresh_cookie(client, expired_raw)
    expired_response = await client.post("/api/v1/auth/refresh")
    _set_refresh_cookie(client, revoked_raw)
    revoked_response = await client.post("/api/v1/auth/refresh")

    # Assert: identical status + body across all three (resolved OD-3)
    assert unknown_response.status_code == expired_response.status_code == 401
    assert revoked_response.status_code == 401
    assert unknown_response.json() == expired_response.json() == revoked_response.json()


# --- RT-AC4: idle timeout and absolute cap (FR-4, FR-5) ----------------------


async def test_refresh_idle_timeout_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="refresh.idle@example.com",
        password=_REFRESH_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_refresh_token_row(
        db_session, user_id=user.id, last_used_at=datetime.now(UTC) - timedelta(days=15)
    )

    # Act
    _set_refresh_cookie(client, raw_token)
    response = await client.post("/api/v1/auth/refresh")

    # Assert
    assert response.status_code == 401
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


async def test_refresh_absolute_cap_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: expired family, even though it was used very recently.
    user = await _seed_login_user(
        db_session,
        email="refresh.absolutecap@example.com",
        password=_REFRESH_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_refresh_token_row(
        db_session,
        user_id=user.id,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        last_used_at=datetime.now(UTC),
    )

    # Act
    _set_refresh_cookie(client, raw_token)
    response = await client.post("/api/v1/auth/refresh")

    # Assert
    assert response.status_code == 401


# --- RT-AC5: account eligibility (FR-6) --------------------------------------


async def test_refresh_deactivated_account_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="refresh.deactivated@example.com",
        password=_REFRESH_TEST_PASSWORD,
        email_verified=True,
        status="deactivated",
    )
    raw_token = await _seed_refresh_token_row(db_session, user_id=user.id)

    # Act
    _set_refresh_cookie(client, raw_token)
    response = await client.post("/api/v1/auth/refresh")

    # Assert
    assert response.status_code == 401


async def test_refresh_revoke_before_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: logout-all sets revoke_before to now; the pre-existing refresh
    # cookie was issued before that moment.
    _, access_token = await _login(client, db_session, email="refresh.revokebefore@example.com")

    # Act
    logout_all_response = await client.post(
        "/api/v1/auth/logout-all", headers=_auth_headers(access_token)
    )
    assert logout_all_response.status_code == 204
    response = await client.post("/api/v1/auth/refresh")

    # Assert
    assert response.status_code == 401


# --- RT-AC6: atomic concurrent handling (FR-7) -------------------------------


async def test_refresh_concurrent_requests_exactly_one_succeeds(
    real_client: AsyncClient, db_session: AsyncSession, cleanup_users: list[str]
) -> None:
    # Arrange
    email = f"refresh.race.{uuid.uuid4().hex}@example.com"
    cleanup_users.append(email)
    await _seed_login_user(
        db_session,
        email=email,
        password=_REFRESH_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    login_response = await real_client.post(
        "/api/v1/auth/login", json={"email": email, "password": _REFRESH_TEST_PASSWORD}
    )
    assert login_response.status_code == 200
    raw_refresh_token = login_response.cookies.get("refresh_token")
    assert raw_refresh_token is not None
    row = (
        await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(raw_refresh_token)
            )
        )
    ).scalar_one()
    family_id = row.family_id

    # Act: two simultaneous requests carrying the same, still-unconsumed token
    real_client.cookies.set("refresh_token", raw_refresh_token, path="/api/v1/auth")
    responses = await asyncio.gather(
        real_client.post("/api/v1/auth/refresh"),
        real_client.post("/api/v1/auth/refresh"),
    )

    # Assert: exactly one 200, one 401 — and the family was NOT revoked
    # (a same-family retry inside the grace window is a race, not an attack).
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 401]

    engine = app.state.db_engine
    async with engine.connect() as connection:
        result = await connection.execute(
            select(RefreshToken).where(RefreshToken.family_id == family_id)
        )
        for persisted_row in result.all():
            assert persisted_row.revoked_at is None


# --- Resolved OD-1: per-family rate limit ------------------------------------


async def test_refresh_rate_limit_exceeded_returns_429(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: the client's cookie jar carries the rotated cookie forward on
    # every call, so 60 successful rotations share one family_id throughout.
    await _login_for_refresh(client, db_session, email="refresh.ratelimit@example.com")
    for _ in range(60):
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 200

    # Act: the 61st request within the trailing hour is throttled.
    response = await client.post("/api/v1/auth/refresh")

    # Assert
    assert response.status_code == 429
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/too-many-attempts"
    assert int(response.headers["retry-after"]) > 0


# --- US-2.4 (spec US-2.4): password reset ------------------------------------

_RESET_TEST_PASSWORD = "OldStr0ng!Pass1"  # pragma: allowlist secret
_RESET_NEW_PASSWORD = "BrandNewStr0ngPass1!"  # pragma: allowlist secret
_RESET_SHORT_PASSWORD = "Sh0rt!"  # pragma: allowlist secret
_RESET_RACE_PASSWORD = "AnotherStr0ngPass2!"  # pragma: allowlist secret


async def _seed_reset_token_row(
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    expires_at: datetime | None = None,
    consumed_at: datetime | None = None,
) -> str:
    """Directly seeds a password_reset_tokens row for full control over its
    state (expired/consumed), returning the raw presented value.
    """
    raw_token = f"raw-reset-{uuid.uuid4()}"
    row = PasswordResetToken(
        user_id=user_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=30)),
    )
    if consumed_at is not None:
        row.consumed_at = consumed_at
    db_session.add(row)
    await db_session.flush()
    return raw_token


# --- PR-AC1: requesting a reset (FR-1) ---------------------------------------


async def test_password_reset_request_returns_202_with_generic_body(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session,
        email="reset.request@example.com",
        password=_RESET_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )

    # Act
    response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset.request@example.com"}
    )

    # Assert
    assert response.status_code == 202
    assert response.json() == {"message": "If an account exists, an email has been sent"}

    token_result = await db_session.execute(select(PasswordResetToken))
    assert len(token_result.scalars().all()) == 1
    audit_result = await db_session.execute(
        select(AuthAuditLog).where(AuthAuditLog.event == "password_reset_requested")
    )
    assert audit_result.scalar_one() is not None


# --- PR-AC3: anti-enumeration (FR-3, resolved OD-3) --------------------------


async def test_password_reset_request_unknown_email_returns_202_identical_body(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session,
        email="reset.known@example.com",
        password=_RESET_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )

    # Act
    known_response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset.known@example.com"}
    )
    unknown_response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset.unknown@example.com"}
    )

    # Assert: identical status and body regardless of account existence.
    assert known_response.status_code == unknown_response.status_code == 202
    assert known_response.json() == unknown_response.json()

    # No token was created for the unknown email.
    token_result = await db_session.execute(select(PasswordResetToken))
    assert len(token_result.scalars().all()) == 1


# --- PR-AC2: completing the reset (FR-2) -------------------------------------


async def test_password_reset_confirm_returns_200_and_persists_new_password_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="reset.confirm@example.com",
        password=_RESET_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token_row(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_token,
            "new_password": _RESET_NEW_PASSWORD,
        },
    )

    # Assert
    assert response.status_code == 200
    assert response.content == b""

    await db_session.refresh(user)
    assert user.hashed_password != await hash_password(_RESET_TEST_PASSWORD)
    assert user.hashed_password.startswith("$argon2id$")

    token_result = await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        )
    )
    assert token_result.scalar_one().consumed_at is not None

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(
            AuthAuditLog.event == "password_reset_completed", AuthAuditLog.actor_id == user.id
        )
    )
    assert audit_result.scalar_one() is not None


async def test_password_reset_confirm_revokes_all_sessions_and_refresh_families(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: a real prior login, so there's an actual session/refresh
    # token to prove got revoked.
    email = "reset.revoke@example.com"
    user = await _seed_login_user(
        db_session, email=email, password=_RESET_TEST_PASSWORD, email_verified=True, status="active"
    )
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": _RESET_TEST_PASSWORD}
    )
    assert login_response.status_code == 200
    old_access_token = login_response.json()["access_token"]
    raw_token = await _seed_reset_token_row(db_session, user_id=user.id)

    # Act
    confirm_response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_token,
            "new_password": _RESET_NEW_PASSWORD,
        },
    )
    assert confirm_response.status_code == 200

    # Assert: the old access token no longer authenticates anything.
    follow_up = await client.patch(
        "/api/v1/profile", json={}, headers=_auth_headers(old_access_token)
    )
    assert follow_up.status_code == 401

    # Assert: the old refresh cookie no longer rotates either.
    refresh_follow_up = await client.post("/api/v1/auth/refresh")
    assert refresh_follow_up.status_code == 401


# --- PR-AC4: expired, consumed, or unknown token (FR-4) ----------------------


async def test_password_reset_confirm_expired_token_returns_400_token_expired(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="reset.expired@example.com",
        password=_RESET_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token_row(
        db_session, user_id=user.id, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )

    # Act
    response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_token,
            "new_password": _RESET_NEW_PASSWORD,
        },
    )

    # Assert
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/token-expired"


async def test_password_reset_confirm_unknown_token_returns_400_token_invalid(
    client: AsyncClient,
) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": "never-issued-token",
            "new_password": _RESET_NEW_PASSWORD,
        },
    )

    # Assert
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


async def test_password_reset_confirm_consumed_token_returns_400_token_invalid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="reset.consumed@example.com",
        password=_RESET_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token_row(
        db_session, user_id=user.id, consumed_at=datetime.now(UTC) - timedelta(minutes=5)
    )

    # Act
    response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_token,
            "new_password": _RESET_NEW_PASSWORD,
        },
    )

    # Assert
    assert response.status_code == 400
    assert response.json()["type"] == "https://portal.internal/errors/token-invalid"


# --- PR-AC5: weak or reused password (FR-5, resolved OD-1) -------------------


async def test_password_reset_confirm_weak_password_returns_422_token_not_consumed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="reset.weak@example.com",
        password=_RESET_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token_row(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_token,
            "new_password": _RESET_SHORT_PASSWORD,
        },  # pragma: allowlist secret
    )

    # Assert
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://portal.internal/errors/password-policy"
    assert any(error["code"] == "min_length" for error in body["errors"])

    # Assert: the token survives — a retry with the same link still works.
    token_result = await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        )
    )
    assert token_result.scalar_one().consumed_at is None

    retry_response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_token,
            "new_password": _RESET_NEW_PASSWORD,
        },
    )
    assert retry_response.status_code == 200


# --- PR-AC6: request flooding (FR-6, resolved OD-2) --------------------------


async def test_password_reset_request_flooding_returns_429_with_retry_after(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    await _seed_login_user(
        db_session,
        email="reset.flood@example.com",
        password=_RESET_TEST_PASSWORD,
        email_verified=True,
        status="active",
    )
    first = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset.flood@example.com"}
    )
    assert first.status_code == 202

    # Act: a second request for the same account inside the 60s cooldown.
    response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset.flood@example.com"}
    )

    # Assert
    assert response.status_code == 429
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://portal.internal/errors/too-many-attempts"
    assert int(response.headers["retry-after"]) > 0


# --- Spec-review resolution (accepted 2026-09-01): atomic consumption -------


async def test_password_reset_confirm_concurrent_same_token_exactly_one_succeeds(
    real_client: AsyncClient, db_session: AsyncSession, cleanup_users: list[str]
) -> None:
    # Arrange
    email = f"reset.race.{uuid.uuid4().hex}@example.com"
    cleanup_users.append(email)
    user = await _seed_login_user(
        db_session, email=email, password=_RESET_TEST_PASSWORD, email_verified=True, status="active"
    )
    raw_token = await _seed_reset_token_row(db_session, user_id=user.id)

    # Act: two simultaneous confirm calls against the same, still-unconsumed
    # token, via real_client's own independent DB connections.
    responses = await asyncio.gather(
        real_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "token": raw_token,
                "new_password": _RESET_NEW_PASSWORD,
            },
        ),
        real_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "token": raw_token,
                "new_password": _RESET_RACE_PASSWORD,
            },
        ),
    )

    # Assert: exactly one 200, one 400 (token-invalid) — never both succeed.
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 400]

    # Verified through db_session, not a fresh engine connection: the app's
    # get_db_session is overridden to this exact session for the duration of
    # the test (join_transaction_mode="create_savepoint"), so nothing here
    # is ever a real cross-connection commit — a genuinely separate
    # connection can't see any of this test's writes at all, seeded row
    # included, which is why RT-AC6's own equivalent check queries the same
    # way in spirit but happens to pass vacuously on an empty result.
    result = await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        )
    )
    assert result.scalar_one().consumed_at is not None


# --- MR-AC2 (US-3.2/spec US-3.2): login/refresh carry the scopes claim,
# stale access tokens after a role change ------------------------------------


async def test_login_response_access_token_carries_current_scopes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    email = "login.scopes@example.com"
    password = "Str0ng!Pass1"
    user = await _seed_login_user(
        db_session, email=email, password=password, email_verified=True, status="active"
    )
    role_id = (
        await db_session.execute(select(Role.id).where(Role.name == "support_agent"))
    ).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=role_id))
    await db_session.flush()

    # Act
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})

    # Assert
    assert response.status_code == 200
    claims = decode_access_token(response.json()["access_token"])
    assert sorted(claims.scopes) == ["tickets:read", "tickets:write"]


async def test_stale_access_token_after_role_change_returns_401_then_refresh_carries_new_scopes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: target logs in first (no roles yet, so no scopes)
    target_email = "target.stale@example.com"
    target, target_access_token = await _login(client, db_session, email=target_email)

    # An admin actor grants the target account the auditor role via a
    # second, independent client (this test's `client` fixture's cookie
    # jar must stay bound to the target's session, not the admin's).
    admin = await _seed_login_user(
        db_session,
        email="admin.stale@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    admin_role_id = (
        await db_session.execute(select(Role.id).where(Role.name == "admin"))
    ).scalar_one()
    db_session.add(UserRole(user_id=admin.id, role_id=admin_role_id))
    await db_session.flush()
    admin_jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=admin_jti, user_id=admin.id, expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
    )
    await db_session.flush()
    admin_token = encode_access_token(
        user_id=admin.id,
        jti=admin_jti,
        scopes=[
            "users:read",
            "users:write",
            "roles:write",
            "audit:read",
            "tickets:read",
            "tickets:write",
        ],
    )
    grant_response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers(admin_token),
    )
    assert grant_response.status_code == 200

    # Act: the target's OLD access token (issued before the grant) is now stale.
    stale_response = await client.get(
        "/api/v1/admin/roles", headers=_auth_headers(target_access_token)
    )

    # Assert
    assert stale_response.status_code == 401
    assert stale_response.json()["type"].endswith("/token-stale")

    # Act: refreshing (using the target's own cookie, still in the jar from
    # its login) issues a new access token carrying the updated scopes.
    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    new_claims = decode_access_token(refresh_response.json()["access_token"])
    assert new_claims.scopes == ["audit:read"]


# --- US-2.6 (spec US-2.6): Active Session Management -------------------------


async def _seed_refresh_token(
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
    issued_at: datetime | None = None,
    last_used_at: datetime | None = None,
    ip: str | None = "203.0.113.10",
    user_agent: str | None = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
    revoked: bool = False,
    expires_at: datetime | None = None,
) -> RefreshToken:
    token = RefreshToken(
        token_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        family_id=family_id or uuid.uuid4(),
        user_id=user_id,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=30)),
        ip=ip,
        user_agent=user_agent,
        last_used_at=last_used_at,
        issued_at=issued_at or datetime.now(UTC),
    )
    db_session.add(token)
    await db_session.flush()
    if revoked:
        token.revoked_at = datetime.now(UTC)
        await db_session.flush()
    return token


# --- SM-AC5: unauthenticated (FR-5) ------------------------------------------


async def test_list_sessions_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/v1/auth/sessions")

    # Assert: no session metadata leaks in an unauthenticated response
    assert response.status_code == 401
    assert "sessions" not in response.text


async def test_list_sessions_invalid_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/v1/auth/sessions", headers=_auth_headers("not-a-real-jwt"))

    # Assert
    assert response.status_code == 401


async def test_list_sessions_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="sessions.list.expired@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    expired_token = await _make_expired_token(db_session, user_id=user.id)

    # Act
    response = await client.get("/api/v1/auth/sessions", headers=_auth_headers(expired_token))

    # Assert
    assert response.status_code == 401


# --- SM-AC1: listing sessions (FR-1) -----------------------------------------


async def test_get_sessions_returns_200_and_correct_family_shapes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, access_token = await _login(client, db_session, email="sessions.list@example.com")
    other_1 = await _seed_refresh_token(db_session, user_id=user.id, ip="198.51.100.5")
    other_2 = await _seed_refresh_token(db_session, user_id=user.id, ip="198.51.100.6")

    # Act
    response = await client.get("/api/v1/auth/sessions", headers=_auth_headers(access_token))

    # Assert: status + body shape
    assert response.status_code == 200
    body = response.json()
    family_ids = {entry["family_id"] for entry in body["sessions"]}
    assert len(body["sessions"]) == 3
    assert {str(other_1.family_id), str(other_2.family_id)}.issubset(family_ids)
    current_entries = [entry for entry in body["sessions"] if entry["is_current"]]
    assert len(current_entries) == 1
    # The real login's own family is the current one - neither directly-
    # seeded "other device" family is.
    assert current_entries[0]["family_id"] not in {str(other_1.family_id), str(other_2.family_id)}
    for entry in body["sessions"]:
        assert set(entry.keys()) == {
            "family_id",
            "created_at",
            "last_used_at",
            "location",
            "device_label",
            "is_current",
        }
        assert "token" not in entry and "hash" not in entry and "ip" not in entry


async def test_get_sessions_p95_latency_within_budget_at_cap(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: 20 live families - the documented cap (NFR).
    user, access_token = await _login(client, db_session, email="sessions.perf@example.com")
    for _ in range(19):
        await _seed_refresh_token(db_session, user_id=user.id)

    # Act
    start = time.monotonic()
    response = await client.get("/api/v1/auth/sessions", headers=_auth_headers(access_token))
    elapsed_ms = (time.monotonic() - start) * 1000

    # Assert
    assert response.status_code == 200
    assert len(response.json()["sessions"]) == 20
    assert elapsed_ms <= 200


# --- SM-AC3/SM-AC5: revoke security cases ------------------------------------


async def test_revoke_session_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.delete(f"/api/v1/auth/sessions/{uuid.uuid4()}")

    # Assert
    assert response.status_code == 401


async def test_revoke_session_invalid_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.delete(
        f"/api/v1/auth/sessions/{uuid.uuid4()}", headers=_auth_headers("not-a-real-jwt")
    )

    # Assert
    assert response.status_code == 401


async def test_revoke_session_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_login_user(
        db_session,
        email="sessions.revoke.expired@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    expired_token = await _make_expired_token(db_session, user_id=user.id)

    # Act
    response = await client.delete(
        f"/api/v1/auth/sessions/{uuid.uuid4()}", headers=_auth_headers(expired_token)
    )

    # Assert
    assert response.status_code == 401


# --- SM-AC2: revoking another device (FR-2) ----------------------------------


async def test_delete_session_returns_204_and_persists_revocation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, access_token = await _login(client, db_session, email="sessions.revoke@example.com")
    target = await _seed_refresh_token(db_session, user_id=user.id)
    own_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.family_id != target.family_id
        )
    )
    own_family = own_result.scalar_one()

    # Act
    response = await client.delete(
        f"/api/v1/auth/sessions/{target.family_id}", headers=_auth_headers(access_token)
    )

    # Assert: status
    assert response.status_code == 204
    assert response.content == b""

    # Assert: persisted state - target revoked, caller's own family untouched
    await db_session.refresh(target)
    assert target.revoked_at is not None
    await db_session.refresh(own_family)
    assert own_family.revoked_at is None

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(
            AuthAuditLog.event == "session_revoked", AuthAuditLog.target_family == target.family_id
        )
    )
    entry = audit_result.scalar_one()
    assert entry.actor_id == user.id


# --- SM-AC3: another user's session returns 404 ------------------------------


async def test_delete_other_users_session_returns_404_and_leaves_untouched(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    _, access_token = await _login(client, db_session, email="sessions.caller@example.com")
    victim = await _seed_login_user(
        db_session,
        email="sessions.victim@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    victim_family = await _seed_refresh_token(db_session, user_id=victim.id)

    # Act
    response = await client.delete(
        f"/api/v1/auth/sessions/{victim_family.family_id}", headers=_auth_headers(access_token)
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["type"].endswith("/not-found")
    await db_session.refresh(victim_family)
    assert victim_family.revoked_at is None


# --- OD-1/FR-6: own current session rejected with 409 ------------------------


async def test_delete_own_current_session_returns_409_and_persists_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, access_token = await _login(client, db_session, email="sessions.current@example.com")
    current_result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    current_family = current_result.scalar_one()

    # Act
    response = await client.delete(
        f"/api/v1/auth/sessions/{current_family.family_id}", headers=_auth_headers(access_token)
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("/current-session")
    await db_session.refresh(current_family)
    assert current_family.revoked_at is None


# --- FR-7: live-session cap eviction ------------------------------------------


async def test_login_creates_21st_family_evicts_oldest_persisted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: 20 live families already at the cap, the oldest clearly first.
    user = await _seed_login_user(
        db_session,
        email="sessions.cap@example.com",
        password="Str0ng!Pass1",
        email_verified=True,
        status="active",
    )
    oldest = await _seed_refresh_token(
        db_session, user_id=user.id, issued_at=datetime.now(UTC) - timedelta(days=30)
    )
    for offset in range(1, 20):
        await _seed_refresh_token(
            db_session,
            user_id=user.id,
            issued_at=datetime.now(UTC) - timedelta(days=30 - offset),
        )

    # Act
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "sessions.cap@example.com", "password": "Str0ng!Pass1"},
    )

    # Assert
    assert response.status_code == 200
    await db_session.refresh(oldest)
    assert oldest.revoked_at is not None

    audit_result = await db_session.execute(
        select(AuthAuditLog).where(
            AuthAuditLog.event == "session_evicted", AuthAuditLog.target_family == oldest.family_id
        )
    )
    assert audit_result.scalar_one() is not None

    live_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    assert len(live_result.scalars().all()) == 20


async def _seed_committed_active_user(*, email: str, password: str) -> uuid.UUID:
    """Commits directly via the app's real engine, bypassing the rollback-
    wrapped `db_session` fixture - `real_client` requests use independent,
    genuinely-committed sessions (see conftest.py), so seed data must be
    committed the same way to be visible to them.
    """
    user_id = uuid.uuid4()
    hashed = await hash_password(password)
    engine = app.state.db_engine
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, status, email_verified) "
                "VALUES (:id, :email, :hashed_password, 'active', true)"
            ),
            {"id": user_id, "email": email, "hashed_password": hashed},
        )
    return user_id


async def test_concurrent_logins_at_cap_boundary_never_exceed_cap(
    real_client: AsyncClient, cleanup_users: list[str]
) -> None:
    """Spec-review resolution: two logins racing at the 20-family cap
    boundary must not both skip eviction - the row lock
    (`lock_live_refresh_tokens_for_user`) must serialize them so the live
    count never transiently exceeds the cap.
    """
    # Arrange
    email = "sessions.concurrent.cap@example.com"
    password = "Str0ng!Pass1"
    cleanup_users.append(email)
    await _seed_committed_active_user(email=email, password=password)
    settings = get_settings()
    for _ in range(settings.max_live_sessions_per_user):
        seed_response = await real_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert seed_response.status_code == 200

    # Act: two concurrent logins, both racing past the cap
    responses = await asyncio.gather(
        real_client.post("/api/v1/auth/login", json={"email": email, "password": password}),
        real_client.post("/api/v1/auth/login", json={"email": email, "password": password}),
    )
    assert all(response.status_code == 200 for response in responses)

    # Assert: the row lock serialized both evictions - the cap is never
    # transiently exceeded, and exactly one eviction happened per login.
    engine = app.state.db_engine
    async with engine.connect() as connection:
        user_id = (
            await connection.execute(
                text("SELECT id FROM users WHERE email = :email"), {"email": email}
            )
        ).scalar_one()
        live_count = (
            await connection.execute(
                text(
                    "SELECT COUNT(DISTINCT family_id) FROM refresh_tokens "
                    "WHERE user_id = :user_id AND revoked_at IS NULL AND expires_at > now()"
                ),
                {"user_id": user_id},
            )
        ).scalar_one()
        evicted_count = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM auth_audit_log "
                    "WHERE actor_id = :user_id AND event = 'session_evicted'"
                ),
                {"user_id": user_id},
            )
        ).scalar_one()

    assert live_count == settings.max_live_sessions_per_user
    assert evicted_count == 2
