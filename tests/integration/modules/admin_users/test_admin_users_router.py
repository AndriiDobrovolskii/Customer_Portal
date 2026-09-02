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
from app.modules.admin_users.models import InvitationToken
from app.modules.roles.models import AdminAuditLog, Role, UserRole
from app.modules.users.models import User, UserSession

pytestmark = pytest.mark.integration

_READ = ["users:read"]
_WRITE = ["users:write"]
_READ_WRITE = ["users:read", "users:write"]


async def _seed_user(
    db_session: AsyncSession, *, email: str, status: str = "active", display_name: str | None = None
) -> User:
    user = User(
        email=email,
        hashed_password=await hash_password("Str0ng!Pass1") if status != "invited" else "",
        status=status,
        display_name=display_name,
    )
    user.email_verified = status != "invited"
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_session_and_token(
    db_session: AsyncSession, *, user_id: uuid.UUID, scopes: list[str]
) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1))
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=scopes)


async def _assign_role(db_session: AsyncSession, *, user_id: uuid.UUID, role_name: str) -> None:
    result = await db_session.execute(select(Role.id).where(Role.name == role_name))
    role_id = result.scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role_id))
    await db_session.flush()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _expired_token(db_session: AsyncSession, *, user_id: uuid.UUID, scopes: list[str]) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.flush()
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "scopes": scopes,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


# --- GET /v1/admin/users - FR-1/FR-2/FR-3/FR-4 ------------------------------


async def test_list_users_returns_200_and_paginates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="lister@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)
    await _seed_user(db_session, email="target.a@example.com", display_name="Alpha")
    await _seed_user(db_session, email="target.b@example.com", display_name="Beta")

    # Act
    response = await client.get(
        "/api/v1/admin/users", params={"limit": 1}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["next_cursor"] is not None
    assert "hashed_password" not in body["items"][0]


async def test_list_users_q_matches_display_name_via_trigram_index(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="searcher@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)
    await _seed_user(db_session, email="findme@example.com", display_name="Zebra Finder")
    await _seed_user(db_session, email="other@example.com", display_name="Nobody Else")

    # Act
    response = await client.get(
        "/api/v1/admin/users", params={"q": "Zebra"}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 200
    emails = {item["email"] for item in response.json()["items"]}
    assert "findme@example.com" in emails
    assert "other@example.com" not in emails


async def test_list_users_limit_over_max_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="limiter@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)

    # Act
    response = await client.get(
        "/api/v1/admin/users", params={"limit": 5000}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("/validation-failed")


async def test_list_users_insufficient_permission_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="noscope@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=[])

    # Act
    response = await client.get("/api/v1/admin/users", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("/insufficient-permission")


async def test_list_users_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/v1/admin/users")

    # Assert
    assert response.status_code == 401


async def test_list_users_invalid_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/v1/admin/users", headers=_auth_headers("not-a-real-jwt"))

    # Assert
    assert response.status_code == 401


async def test_list_users_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="expiredlist@example.com")
    token = await _expired_token(db_session, user_id=user.id, scopes=_READ)

    # Act
    response = await client.get("/api/v1/admin/users", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 401


# --- GET /v1/admin/users/{id} - FR-22/FR-23 ---------------------------------


async def test_get_user_returns_200_with_etag_accepted_by_patch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="fetcher@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ_WRITE)
    target = await _seed_user(db_session, email="fetched@example.com", display_name="Old")

    # Act
    get_response = await client.get(
        f"/api/v1/admin/users/{target.id}", headers=_auth_headers(token)
    )

    # Assert
    assert get_response.status_code == 200
    etag = get_response.headers["ETag"]
    patch_response = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"display_name": "New", "reason": "correction"},
        headers={**_auth_headers(token), "If-Match": etag},
    )
    assert patch_response.status_code == 200


async def test_get_user_unknown_id_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="fetcher404@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)

    # Act
    response = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 404
    assert response.json()["type"].endswith("/not-found")


async def test_get_user_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}")

    # Assert
    assert response.status_code == 401


# --- POST /v1/admin/users - FR-5/FR-6/FR-7/FR-8 -----------------------------


async def test_create_user_returns_201_and_persists_invitation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="creator@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)

    # Act
    response = await client.post(
        "/api/v1/admin/users",
        json={"email": "invitee1@example.com", "display_name": "Invitee One", "roles": []},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "invited"
    assert "ETag" in response.headers

    user_result = await db_session.execute(select(User).where(User.email == "invitee1@example.com"))
    created = user_result.scalar_one()
    assert created.email_verified is False

    token_result = await db_session.execute(
        select(InvitationToken).where(InvitationToken.user_id == created.id)
    )
    invitation = token_result.scalar_one()
    assert invitation.consumed_at is None

    audit_result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.event == "user_created", AdminAuditLog.target_id == created.id
        )
    )
    assert audit_result.scalar_one().actor_id == admin.id


async def test_create_user_duplicate_email_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="dupcreator@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    # Seeded already lowercase, matching what every real write path
    # (registration, admin creation) normalizes to before storage -
    # BR-001's case-insensitive guarantee holds only comparing normalized
    # values, not an un-normalized seed against a normalized request.
    await _seed_user(db_session, email="existing@example.com")

    # Act: request uses a different case to prove the comparison is
    # genuinely case-insensitive, not just an exact-string match.
    response = await client.post(
        "/api/v1/admin/users",
        json={"email": "Existing@Example.com", "display_name": "X", "roles": []},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("/email-already-registered")


async def test_create_user_password_field_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="pwcreator@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)

    # Act
    response = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "shouldnotexist@example.com",
            "display_name": "X",
            "roles": [],
            "password": "hunter2",  # pragma: allowlist secret
        },
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422


async def test_create_user_privilege_escalation_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: actor holds users:write but no other admin-only scope
    actor = await _seed_user(db_session, email="escalator@example.com")
    token = await _seed_session_and_token(db_session, user_id=actor.id, scopes=_WRITE)

    # Act
    response = await client.post(
        "/api/v1/admin/users",
        json={"email": "escalated@example.com", "display_name": "X", "roles": ["admin"]},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("/privilege-escalation")
    result = await db_session.execute(select(User).where(User.email == "escalated@example.com"))
    assert result.first() is None


async def test_create_user_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        "/api/v1/admin/users", json={"email": "x@example.com", "display_name": "X", "roles": []}
    )

    # Assert
    assert response.status_code == 401


async def test_concurrent_create_user_same_email_exactly_one_succeeds(
    real_client: AsyncClient, cleanup_users: list[str]
) -> None:
    # Arrange: seeded via a real, committed connection so both concurrent
    # requests' independent connections observe the same admin/session row.
    engine = app.state.db_engine
    admin_id = uuid.uuid4()
    admin_email = f"raceadmin.{uuid.uuid4().hex}@example.com"
    email = f"race.{uuid.uuid4().hex}@example.com"
    cleanup_users.append(admin_email)
    async with engine.begin() as connection:
        await connection.execute(
            insert(User).values(
                id=admin_id,
                email=admin_email,
                hashed_password=await hash_password("Str0ng!Pass1"),
                status="active",
                email_verified=True,
            )
        )
        jti = uuid.uuid4()
        await connection.execute(
            insert(UserSession).values(
                jti=jti, user_id=admin_id, expires_at=datetime.now(UTC) + timedelta(hours=1)
            )
        )
    token = encode_access_token(user_id=admin_id, jti=jti, scopes=_WRITE)
    cleanup_users.append(email)

    # Act
    responses = await asyncio.gather(
        real_client.post(
            "/api/v1/admin/users",
            json={"email": email, "display_name": "Racer", "roles": []},
            headers=_auth_headers(token),
        ),
        real_client.post(
            "/api/v1/admin/users",
            json={"email": email, "display_name": "Racer", "roles": []},
            headers=_auth_headers(token),
        ),
    )

    # Assert
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 409]


# --- PATCH /v1/admin/users/{id} - FR-9/FR-10/FR-11/FR-12 --------------------


async def test_patch_user_returns_200_and_persists_audit_rows(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="patcher@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ_WRITE)
    target = await _seed_user(db_session, email="patchee@example.com", display_name="Before")
    get_response = await client.get(
        f"/api/v1/admin/users/{target.id}", headers=_auth_headers(token)
    )
    etag = get_response.headers["ETag"]

    # Act
    response = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"display_name": "After", "reason": "name correction"},
        headers={**_auth_headers(token), "If-Match": etag},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["display_name"] == "After"
    await db_session.refresh(target)
    assert target.display_name == "After"

    audit_result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.event == "user_field_updated", AdminAuditLog.target_id == target.id
        )
    )
    audit = audit_result.scalar_one()
    assert audit.field == "display_name"
    assert audit.old_value == "Before"
    assert audit.new_value == "After"
    assert audit.reason == "name correction"


async def test_patch_user_stale_etag_returns_412(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="stalepatcher@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ_WRITE)
    target = await _seed_user(db_session, email="stalepatchee@example.com", display_name="Original")

    # Act
    response = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"display_name": "Changed", "reason": "r"},
        headers={**_auth_headers(token), "If-Match": '"stale-etag-value"'},
    )

    # Assert
    assert response.status_code == 412
    await db_session.refresh(target)
    assert target.display_name == "Original"


async def test_patch_user_missing_if_match_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="noifmatch@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ_WRITE)
    target = await _seed_user(db_session, email="noifmatchee@example.com")

    # Act
    response = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"display_name": "X", "reason": "r"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 400
    assert response.json()["type"].endswith("/precondition-required")


async def test_patch_user_immutable_field_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="immutablepatcher@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ_WRITE)
    target = await _seed_user(db_session, email="immutablepatchee@example.com")

    # Act
    response = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"roles": ["admin"], "reason": "r"},
        headers={**_auth_headers(token), "If-Match": "*"},
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("/immutable-field")


async def test_patch_user_unknown_id_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="unknownpatcher@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ_WRITE)

    # Act
    response = await client.patch(
        f"/api/v1/admin/users/{uuid.uuid4()}",
        json={"display_name": "X", "reason": "r"},
        headers={**_auth_headers(token), "If-Match": "*"},
    )

    # Assert
    assert response.status_code == 404


async def test_patch_user_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.patch(
        f"/api/v1/admin/users/{uuid.uuid4()}", json={"display_name": "X", "reason": "r"}
    )

    # Assert
    assert response.status_code == 401


# --- POST /v1/admin/users/{id}/deactivate - FR-13..FR-16, FR-17b -----------


async def test_deactivate_user_returns_200_and_persists_all_side_effects(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="deactivator@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    target = await _seed_user(db_session, email="deactivatee@example.com")

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/deactivate",
        json={"reason": "left the company"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "deactivated"

    await db_session.refresh(target)
    assert target.status == "deactivated"
    assert target.deactivated_at is not None

    revoke_raw = await app.state.valkey_client.get(revoke_before_key(target.id))
    assert revoke_raw is not None

    audit_result = await db_session.execute(
        select(AccountLifecycleAuditLog).where(
            AccountLifecycleAuditLog.user_id == target.id,
            AccountLifecycleAuditLog.event == "deactivated",
        )
    )
    audit = audit_result.scalar_one()
    assert audit.actor == f"admin:{admin.id}"
    assert audit.reason == "left the company"


async def test_deactivate_user_already_deactivated_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="deactivator2@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    target = await _seed_user(
        db_session, email="alreadydeactivated@example.com", status="deactivated"
    )

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/deactivate",
        json={"reason": "r"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("/already-deactivated")


async def test_deactivate_user_self_target_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="selfdeactivator@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{admin.id}/deactivate",
        json={"reason": "r"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("/cannot-target-self")


async def test_deactivate_user_last_admin_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: actor has write scope without holding admin itself; target is
    # the sole active admin.
    actor = await _seed_user(db_session, email="lastadmindeactivator@example.com")
    token = await _seed_session_and_token(db_session, user_id=actor.id, scopes=_WRITE)
    target = await _seed_user(db_session, email="soleadmin@example.com")
    await _assign_role(db_session, user_id=target.id, role_name="admin")

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/deactivate",
        json={"reason": "r"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("/last-admin")
    await db_session.refresh(target)
    assert target.status == "active"


async def test_deactivate_user_unknown_id_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="unknowndeactivator@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/deactivate",
        json={"reason": "r"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 404


async def test_deactivate_user_missing_reason_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="noreasondeactivator@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    target = await _seed_user(db_session, email="noreasontarget@example.com")

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/deactivate", json={}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422


async def test_deactivate_user_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/deactivate", json={"reason": "r"}
    )

    # Assert
    assert response.status_code == 401


async def test_concurrent_deactivate_last_two_admins_exactly_one_succeeds(
    real_client: AsyncClient, cleanup_users: list[str]
) -> None:
    # Arrange: two active admins exist; both are targeted concurrently.
    # Per the spec's own Enforcement Matrix (MU-AC16), exactly one may
    # succeed - never both (would leave zero admins). Seeded via a real,
    # committed connection (not the rolled-back db_session), so it MUST
    # clean up afterward via cleanup_users - an admin left behind here
    # would silently inflate every other last-admin check in the suite
    # that runs after it (caught during this story's own T8, 2026-09-02:
    # this exact omission made the roles module's own equivalent
    # concurrency test fail when run after this one).
    engine = app.state.db_engine
    actor_id = uuid.uuid4()
    admin_1_id = uuid.uuid4()
    admin_2_id = uuid.uuid4()
    actor_email = f"deactoractor.{uuid.uuid4().hex}@example.com"
    admin_1_email = f"deactadmin1.{uuid.uuid4().hex}@example.com"
    admin_2_email = f"deactadmin2.{uuid.uuid4().hex}@example.com"
    cleanup_users.extend([actor_email, admin_1_email, admin_2_email])
    async with engine.begin() as connection:
        for email, user_id in (
            (actor_email, actor_id),
            (admin_1_email, admin_1_id),
            (admin_2_email, admin_2_id),
        ):
            await connection.execute(
                insert(User).values(
                    id=user_id,
                    email=email,
                    hashed_password=await hash_password("Str0ng!Pass1"),
                    status="active",
                    email_verified=True,
                )
            )
        admin_role_id = (
            await connection.execute(select(Role.id).where(Role.name == "admin"))
        ).scalar_one()
        await connection.execute(
            insert(UserRole).values(
                [
                    {"user_id": admin_1_id, "role_id": admin_role_id},
                    {"user_id": admin_2_id, "role_id": admin_role_id},
                ]
            )
        )
        actor_jti = uuid.uuid4()
        await connection.execute(
            insert(UserSession).values(
                jti=actor_jti, user_id=actor_id, expires_at=datetime.now(UTC) + timedelta(hours=1)
            )
        )
    actor_token = encode_access_token(user_id=actor_id, jti=actor_jti, scopes=_WRITE)

    # Act
    responses = await asyncio.gather(
        real_client.post(
            f"/api/v1/admin/users/{admin_1_id}/deactivate",
            json={"reason": "concurrent test"},
            headers=_auth_headers(actor_token),
        ),
        real_client.post(
            f"/api/v1/admin/users/{admin_2_id}/deactivate",
            json={"reason": "concurrent test"},
            headers=_auth_headers(actor_token),
        ),
    )

    # Assert
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]


# --- DELETE /v1/admin/users/{id} - FR-17 ------------------------------------


async def test_delete_user_authenticated_returns_405(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: any authenticated caller, no particular scope needed
    user = await _seed_user(db_session, email="deleter@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=[])
    target = await _seed_user(db_session, email="undeletable@example.com")

    # Act
    response = await client.delete(f"/api/v1/admin/users/{target.id}", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 405
    await db_session.refresh(target)
    assert target.status == "active"


async def test_delete_user_missing_token_returns_401_not_405(client: AsyncClient) -> None:
    # Act
    response = await client.delete(f"/api/v1/admin/users/{uuid.uuid4()}")

    # Assert
    assert response.status_code == 401


# --- POST /v1/admin/users/{id}/resend-invite - FR-18..FR-21 ----------------


async def test_resend_invite_returns_202_and_persists_new_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="resender@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    target = await _seed_user(db_session, email="resendee@example.com", status="invited")
    old_token_hash = "a" * 64
    db_session.add(
        InvitationToken(
            user_id=target.id,
            token_hash=old_token_hash,
            issued_at=datetime.now(UTC) - timedelta(hours=1),
            expires_at=datetime.now(UTC) + timedelta(hours=23),
        )
    )
    await db_session.flush()

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/resend-invite", headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 202

    old_result = await db_session.execute(
        select(InvitationToken).where(InvitationToken.token_hash == old_token_hash)
    )
    assert old_result.scalar_one().consumed_at is not None

    all_tokens = await db_session.execute(
        select(InvitationToken).where(InvitationToken.user_id == target.id)
    )
    assert len(all_tokens.scalars().all()) == 2

    audit_result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.event == "invitation_resent", AdminAuditLog.target_id == target.id
        )
    )
    assert audit_result.scalar_one() is not None


async def test_resend_invite_active_target_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="activeresender@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    target = await _seed_user(db_session, email="alreadyactive@example.com", status="active")

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/resend-invite", headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("/invalid-state-transition")


async def test_resend_invite_cooldown_returns_429(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="cooldownresender@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    target = await _seed_user(db_session, email="cooldowntarget@example.com", status="invited")
    db_session.add(
        InvitationToken(
            user_id=target.id,
            token_hash="b" * 64,
            issued_at=datetime.now(UTC) - timedelta(seconds=5),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )
    await db_session.flush()

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/resend-invite", headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_resend_invite_over_hourly_cap_returns_429(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: 5 tokens already issued within the last hour (each with a
    # distinct issued_at older than the 60s cooldown, so only the hourly
    # cap - not the cooldown - is what should trigger).
    admin = await _seed_user(db_session, email="caphitresender@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)
    target = await _seed_user(db_session, email="capped@example.com", status="invited")
    base = datetime.now(UTC) - timedelta(minutes=50)
    for i in range(5):
        db_session.add(
            InvitationToken(
                user_id=target.id,
                token_hash=f"{i}" * 64,
                issued_at=base + timedelta(minutes=i),
                expires_at=base + timedelta(hours=24),
            )
        )
    await db_session.flush()

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{target.id}/resend-invite", headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 429


async def test_resend_invite_unknown_id_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="unknownresender@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_WRITE)

    # Act
    response = await client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/resend-invite", headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 404


async def test_resend_invite_missing_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(f"/api/v1/admin/users/{uuid.uuid4()}/resend-invite")

    # Assert
    assert response.status_code == 401
