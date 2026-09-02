import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.security as security
from app.core.config import get_settings
from app.core.crypto import encrypt_mfa_secret
from app.core.security import (
    current_totp_step,
    decode_access_token,
    encode_access_token,
    generate_totp_secret,
    hash_password,
)
from app.modules.roles.models import Role, UserRole
from app.modules.users.models import MfaRecoveryCode, User, UserSession

pytestmark = pytest.mark.integration

_MFA_PASSWORD = "Str0ng!Pass1"  # pragma: allowlist secret


async def _seed_user(
    db_session: AsyncSession,
    *,
    email: str,
    password: str = _MFA_PASSWORD,
    mfa_enabled: bool = False,
    with_secret: bool = False,
) -> tuple[User, bytes]:
    secret = generate_totp_secret()
    user = User(email=email, hashed_password=await hash_password(password), status="active")
    user.email_verified = True
    user.mfa_enabled = mfa_enabled
    user.mfa_secret_encrypted = encrypt_mfa_secret(secret) if (with_secret or mfa_enabled) else None
    db_session.add(user)
    await db_session.flush()
    return user, secret


async def _assign_role(
    db_session: AsyncSession, *, user_id: uuid.UUID, role_name: str, granted_at: datetime
) -> None:
    result = await db_session.execute(select(Role.id).where(Role.name == role_name))
    role_id = result.scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role_id, granted_at=granted_at))
    await db_session.flush()


def _totp_code(secret: bytes) -> str:
    return security._hotp(secret, current_totp_step())


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


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


async def _make_revoked_token(db_session: AsyncSession, *, user_id: uuid.UUID) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=[])


async def _make_enrollment_scoped_token(db_session: AsyncSession, *, user_id: uuid.UUID) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1))
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=[], mfa_enrollment_required=True)


async def _login(
    client: AsyncClient, *, email: str, password: str = _MFA_PASSWORD
) -> dict[str, Any]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return dict(response.json())


async def _login_with_mfa(
    client: AsyncClient, *, email: str, secret: bytes, password: str = _MFA_PASSWORD
) -> dict[str, Any]:
    """For an `mfa_enabled` user: completes the full login -> challenge ->
    verify flow and returns the final body carrying a real access_token.
    """
    challenge = await _login(client, email=email, password=password)
    response = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "code": _totp_code(secret)},
    )
    assert response.status_code == 200
    return dict(response.json())


# --- MF-AC1 / FR-1: POST /v1/auth/mfa/enroll -------------------------------


async def test_mfa_enroll_returns_200_and_persists_encrypted_secret(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="enroll1@example.com")
    login_body = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/enroll",
        json={"current_password": _MFA_PASSWORD},
        headers=_auth_headers(login_body["access_token"]),
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert "secret" in body
    await db_session.refresh(user)
    assert user.mfa_secret_encrypted is not None
    assert user.mfa_secret_encrypted != body["secret"].encode()
    assert user.mfa_enabled is False


async def test_enroll_mfa_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/mfa/enroll", json={"current_password": _MFA_PASSWORD}
    )

    # Assert
    assert response.status_code == 401


async def test_enroll_mfa_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/mfa/enroll",
        json={"current_password": _MFA_PASSWORD},
        headers=_auth_headers("not-a-real-jwt"),
    )

    # Assert
    assert response.status_code == 401


async def test_enroll_mfa_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="enrollexpired@example.com")
    expired_token = await _make_expired_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/enroll",
        json={"current_password": _MFA_PASSWORD},
        headers=_auth_headers(expired_token),
    )

    # Assert
    assert response.status_code == 401


async def test_enroll_mfa_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="enrollrevoked@example.com")
    revoked_token = await _make_revoked_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/enroll",
        json={"current_password": _MFA_PASSWORD},
        headers=_auth_headers(revoked_token),
    )

    # Assert
    assert response.status_code == 401


async def test_enroll_mfa_wrong_password_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="enroll2@example.com")
    login_body = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/enroll",
        json={"current_password": "WrongPassword1!"},  # pragma: allowlist secret
        headers=_auth_headers(login_body["access_token"]),
    )

    # Assert
    assert response.status_code == 401


async def test_enroll_mfa_accepts_enrollment_scoped_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: US-2.5 reconciliation gap #2 - FR-6 names both
    # /mfa/enroll and /mfa/activate as accepting an enrolment-scoped
    # token; both full-flow tests below only exercise /mfa/activate with
    # one, leaving /mfa/enroll's acceptance unproven.
    user, _ = await _seed_user(db_session, email="enrollscoped@example.com")
    scoped_token = await _make_enrollment_scoped_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/enroll",
        json={"current_password": _MFA_PASSWORD},
        headers=_auth_headers(scoped_token),
    )

    # Assert
    assert response.status_code == 200


# --- MF-AC2 / FR-2: POST /v1/auth/mfa/activate -----------------------------


async def test_mfa_activate_returns_200_and_persists_enabled_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, secret = await _seed_user(db_session, email="activate1@example.com", with_secret=True)
    login_body = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/activate",
        json={"code": _totp_code(secret)},
        headers=_auth_headers(login_body["access_token"]),
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert len(body["recovery_codes"]) == 10
    await db_session.refresh(user)
    assert user.mfa_enabled is True
    result = await db_session.execute(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
    )
    assert len(result.scalars().all()) == 10


async def test_activate_mfa_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post("/api/v1/auth/mfa/activate", json={"code": "123456"})

    # Assert
    assert response.status_code == 401


async def test_activate_mfa_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/mfa/activate",
        json={"code": "123456"},
        headers=_auth_headers("not-a-real-jwt"),
    )

    # Assert
    assert response.status_code == 401


async def test_activate_mfa_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="activateexpired@example.com", with_secret=True)
    expired_token = await _make_expired_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/activate",
        json={"code": "123456"},
        headers=_auth_headers(expired_token),
    )

    # Assert
    assert response.status_code == 401


async def test_activate_mfa_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="activaterevoked@example.com", with_secret=True)
    revoked_token = await _make_revoked_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/activate",
        json={"code": "123456"},
        headers=_auth_headers(revoked_token),
    )

    # Assert
    assert response.status_code == 401


async def test_activate_mfa_wrong_code_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="activate2@example.com", with_secret=True)
    login_body = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/activate",
        json={"code": "000000"},
        headers=_auth_headers(login_body["access_token"]),
    )

    # Assert
    assert response.status_code == 401


# --- MF-AC3: login challenge / MF-AC4/MF-AC5/MF-AC7: POST /v1/auth/mfa/verify -


async def test_login_mfa_enabled_returns_challenge_no_tokens(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="challenge1@example.com", mfa_enabled=True)

    # Act
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": _MFA_PASSWORD}
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["mfa_required"] is True
    assert "mfa_token" in body
    assert "access_token" not in body
    assert "refresh_token" not in client.cookies


async def test_login_then_mfa_verify_completes_as_standard_login(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, secret = await _seed_user(db_session, email="challenge2@example.com", mfa_enabled=True)
    challenge = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "code": _totp_code(secret)},
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    claims = decode_access_token(body["access_token"])
    assert claims.user_id == user.id
    assert "refresh_token" in response.cookies


async def test_verify_mfa_replayed_code_rejected_against_real_valkey(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: US-2.5 reconciliation gap #6 - MfaReplayCache.mark_step_used
    # (app/modules/users/cache.py) is a Valkey SET NX; unit tests only ever
    # exercise a hand-written fake. This proves the real backend rejects
    # reusing an already-accepted TOTP step across two separate mfa_tokens
    # (a fresh login challenge each time, same time step both times).
    user, secret = await _seed_user(db_session, email="verifyreplay@example.com", mfa_enabled=True)
    first_challenge = await _login(client, email=user.email)
    code = _totp_code(secret)
    first = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": first_challenge["mfa_token"], "code": code},
    )
    assert first.status_code == 200

    # Act: a second login issues a new mfa_token, but the same code (same
    # 30-second step) was already accepted once.
    second_challenge = await _login(client, email=user.email)
    response = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": second_challenge["mfa_token"], "code": code},
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["type"].endswith("mfa-invalid-code")


async def test_verify_mfa_incorrect_code_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="verifywrong@example.com", mfa_enabled=True)
    challenge = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": challenge["mfa_token"], "code": "000000"}
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["type"].endswith("mfa-invalid-code")


async def test_verify_mfa_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": "never-issued", "code": "123456"}
    )

    # Assert
    assert response.status_code == 401


async def test_verify_mfa_already_consumed_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: consume the mfa_token once by completing a real login.
    user, secret = await _seed_user(db_session, email="consumedtoken@example.com", mfa_enabled=True)
    challenge = await _login(client, email=user.email)
    first = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "code": _totp_code(secret)},
    )
    assert first.status_code == 200

    # Act: presenting the same (now-consumed) mfa_token again.
    second = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": challenge["mfa_token"], "code": _totp_code(secret)},
    )

    # Assert
    assert second.status_code == 401


async def test_verify_mfa_rejects_normal_access_token_as_mfa_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: a normal bearer access token, not an issued mfa_token.
    user, _ = await _seed_user(db_session, email="bearernotmfa@example.com")
    login_body = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": login_body["access_token"], "code": "123456"},
    )

    # Assert
    assert response.status_code == 401


async def test_mfa_verify_fifth_failure_returns_429_fixed_counter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="lockout@example.com", mfa_enabled=True)
    challenge = await _login(client, email=user.email)
    payload = {"mfa_token": challenge["mfa_token"], "code": "000000"}

    # Act: 4 failures, then the 5th returns 429.
    for _ in range(4):
        response = await client.post("/api/v1/auth/mfa/verify", json=payload)
        assert response.status_code == 401

    fifth = await client.post("/api/v1/auth/mfa/verify", json=payload)

    # Assert
    assert fifth.status_code == 429

    # And the token is now genuinely dead, not just rate-limited.
    sixth = await client.post("/api/v1/auth/mfa/verify", json=payload)
    assert sixth.status_code == 401


async def test_mfa_verify_recovery_code_login_persists_consumption(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="recovery1@example.com", mfa_enabled=True)
    raw_code = "recovery-code-abc123"
    db_session.add(MfaRecoveryCode(user_id=user.id, code_hash=await hash_password(raw_code)))
    await db_session.flush()
    challenge = await _login(client, email=user.email)

    # Act
    response = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": challenge["mfa_token"], "code": raw_code}
    )

    # Assert
    assert response.status_code == 200
    result = await db_session.execute(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
    )
    stored = result.scalar_one()
    assert stored.consumed_at is not None
    await db_session.refresh(user)
    assert user.mfa_reenrollment_required is True


# --- MF-AC6/FR-8: DELETE /v1/auth/mfa ---------------------------------------


async def test_mfa_disable_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.request(
        "DELETE", "/api/v1/auth/mfa", json={"current_password": _MFA_PASSWORD, "code": "123456"}
    )

    # Assert
    assert response.status_code == 401


async def test_mfa_disable_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.request(
        "DELETE",
        "/api/v1/auth/mfa",
        json={"current_password": _MFA_PASSWORD, "code": "123456"},
        headers=_auth_headers("not-a-real-jwt"),
    )

    # Assert
    assert response.status_code == 401


async def test_mfa_disable_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="disableexpired@example.com", mfa_enabled=True)
    expired_token = await _make_expired_token(db_session, user_id=user.id)

    # Act
    response = await client.request(
        "DELETE",
        "/api/v1/auth/mfa",
        json={"current_password": _MFA_PASSWORD, "code": "123456"},
        headers=_auth_headers(expired_token),
    )

    # Assert
    assert response.status_code == 401


async def test_mfa_disable_rejects_enrollment_scoped_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: US-2.5 reconciliation gap #3 - DELETE /v1/auth/mfa is
    # explicitly NOT on FR-6's enrolment-endpoint allow-list (unlike
    # /mfa/enroll and /mfa/activate), and it's the MFA-adjacent route a
    # future maintainer is most likely to mistakenly add to that allow-list
    # by analogy. The full-flow tests below only prove an unrelated route
    # (/logout-all) is blocked - this proves the specific route the matrix
    # calls out.
    user, secret = await _seed_user(db_session, email="disablescoped@example.com", with_secret=True)
    scoped_token = await _make_enrollment_scoped_token(db_session, user_id=user.id)

    # Act
    response = await client.request(
        "DELETE",
        "/api/v1/auth/mfa",
        json={"current_password": _MFA_PASSWORD, "code": _totp_code(secret)},
        headers=_auth_headers(scoped_token),
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("mfa-enrollment-required")


async def test_mfa_disable_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, _ = await _seed_user(db_session, email="disablerevoked@example.com", mfa_enabled=True)
    revoked_token = await _make_revoked_token(db_session, user_id=user.id)

    # Act
    response = await client.request(
        "DELETE",
        "/api/v1/auth/mfa",
        json={"current_password": _MFA_PASSWORD, "code": "123456"},
        headers=_auth_headers(revoked_token),
    )

    # Assert
    assert response.status_code == 401


async def test_mfa_disable_privileged_role_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, secret = await _seed_user(db_session, email="disablepriv@example.com", mfa_enabled=True)
    await _assign_role(db_session, user_id=user.id, role_name="admin", granted_at=datetime.now(UTC))
    login_body = await _login_with_mfa(client, email=user.email, secret=secret)

    # Act
    response = await client.request(
        "DELETE",
        "/api/v1/auth/mfa",
        json={"current_password": _MFA_PASSWORD, "code": _totp_code(secret)},
        headers=_auth_headers(login_body["access_token"]),
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("mfa-required-for-role")


async def test_mfa_disable_returns_204_and_persists_full_purge(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, secret = await _seed_user(db_session, email="disable1@example.com", mfa_enabled=True)
    db_session.add(MfaRecoveryCode(user_id=user.id, code_hash="dummy-hash"))
    await db_session.flush()
    login_body = await _login_with_mfa(client, email=user.email, secret=secret)

    # Act
    response = await client.request(
        "DELETE",
        "/api/v1/auth/mfa",
        json={"current_password": _MFA_PASSWORD, "code": _totp_code(secret)},
        headers=_auth_headers(login_body["access_token"]),
    )

    # Assert
    assert response.status_code == 204
    await db_session.refresh(user)
    assert user.mfa_enabled is False
    assert user.mfa_secret_encrypted is None
    result = await db_session.execute(
        select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
    )
    assert result.scalars().all() == []

    # Other sessions were revoked (revoke_before) - the same access token
    # issued at login is now rejected.
    check = await client.post(
        "/api/v1/auth/logout-all", headers=_auth_headers(login_body["access_token"])
    )
    assert check.status_code == 401


# --- Cross-cutting: enrolment-scoped-token full flow ------------------------


async def test_full_enrollment_scoping_flow_role_grant_to_resolution(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: an admin role granted well past the 14-day grace period.
    user, secret = await _seed_user(db_session, email="scopedflow@example.com", with_secret=True)
    old_grant = datetime.now(UTC) - timedelta(days=30)
    await _assign_role(db_session, user_id=user.id, role_name="admin", granted_at=old_grant)

    # Act 1: login issues an enrolment-scoped access token.
    login_body = await _login(client, email=user.email)
    scoped_token = login_body["access_token"]
    claims = decode_access_token(scoped_token)
    assert claims.mfa_enrollment_required is True

    # Act 2: the scoped token is rejected on a non-enrollment route.
    blocked = await client.post("/api/v1/auth/logout-all", headers=_auth_headers(scoped_token))
    assert blocked.status_code == 403
    assert blocked.json()["type"].endswith("mfa-enrollment-required")

    # Act 3: the same scoped token IS accepted on the enrollment routes.
    activate_response = await client.post(
        "/api/v1/auth/mfa/activate",
        json={"code": _totp_code(secret)},
        headers=_auth_headers(scoped_token),
    )
    assert activate_response.status_code == 200

    # Act 4: the old scoped token is now stale.
    stale_check = await client.post("/api/v1/auth/logout-all", headers=_auth_headers(scoped_token))
    assert stale_check.status_code == 401
    assert stale_check.json()["type"].endswith("token-stale")

    # "Refresh then issues a working, unscoped token" (FR-2's exit condition
    # completed) is proven at the unit level instead
    # (test_rotate_refresh_token_reissues_normal_token_when_condition_resolved)
    # rather than chased here: the `db_session` fixture wraps the whole test
    # in one outer transaction, so Postgres server-side `now()` (this
    # story's `UserSession.issued_at` server_default) returns the same
    # transaction-start value for every session created in this test — the
    # same limitation that kept US-3.2's own MR-AC2 integration coverage
    # scoped to "perm_epoch key exists in Valkey" rather than a full
    # stale-token-then-refresh round trip.


async def test_full_enrollment_scoping_flow_recovery_code_to_resolution(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user, secret = await _seed_user(
        db_session, email="scopedrecovery@example.com", mfa_enabled=True
    )
    raw_code = "recovery-full-flow"
    db_session.add(MfaRecoveryCode(user_id=user.id, code_hash=await hash_password(raw_code)))
    await db_session.flush()

    # Act 1: consume a recovery code.
    challenge = await _login(client, email=user.email)
    verify_response = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": challenge["mfa_token"], "code": raw_code}
    )
    assert verify_response.status_code == 200

    # Act 2: the very next login is enrolment-scoped, no grace period.
    challenge2 = await _login(client, email=user.email)
    verify2 = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": challenge2["mfa_token"], "code": _totp_code(secret)},
    )
    scoped_token = verify2.json()["access_token"]
    assert decode_access_token(scoped_token).mfa_enrollment_required is True

    # Act 3: blocked elsewhere, allowed on activate, resolves the same way.
    blocked = await client.post("/api/v1/auth/logout-all", headers=_auth_headers(scoped_token))
    assert blocked.status_code == 403

    activate_response = await client.post(
        "/api/v1/auth/mfa/activate",
        json={"code": _totp_code(secret)},
        headers=_auth_headers(scoped_token),
    )
    assert activate_response.status_code == 200
    await db_session.refresh(user)
    assert user.mfa_reenrollment_required is False
