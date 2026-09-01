import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_keys import perm_epoch_key
from app.core.config import get_settings
from app.core.security import encode_access_token, hash_password
from app.main import app
from app.modules.roles.models import AdminAuditLog, Permission, Role, RolePermission, UserRole
from app.modules.users.models import User, UserSession

pytestmark = pytest.mark.integration

_ALL_ADMIN_SCOPES = [
    "users:read",
    "users:write",
    "roles:write",
    "audit:read",
    "tickets:read",
    "tickets:write",
]


async def _seed_active_user(db_session: AsyncSession, *, email: str) -> User:
    user = User(email=email, hashed_password=await hash_password("Str0ng!Pass1"), status="active")
    user.email_verified = True
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_session_and_token(
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    scopes: list[str],
    issued_at: datetime | None = None,
) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            issued_at=issued_at or datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=scopes)


async def _get_role_id(db_session: AsyncSession, name: str) -> uuid.UUID:
    result = await db_session.execute(select(Role.id).where(Role.name == name))
    return result.scalar_one()


async def _assign_role(db_session: AsyncSession, *, user_id: uuid.UUID, role_name: str) -> None:
    role_id = await _get_role_id(db_session, role_name)
    db_session.add(UserRole(user_id=user_id, role_id=role_id))
    await db_session.flush()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


# --- MR-AC3: reading the role catalogue --------------------------------------


async def test_list_role_catalogue_returns_all_four_roles_with_permissions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    reader = await _seed_active_user(db_session, email="cat.reader@example.com")
    token = await _seed_session_and_token(db_session, user_id=reader.id, scopes=["users:read"])

    # Act
    response = await client.get("/api/v1/admin/roles", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    by_name = {role["name"]: role["permissions"] for role in response.json()["roles"]}
    assert set(by_name.keys()) == {"customer", "support_agent", "admin", "auditor"}
    assert sorted(by_name["support_agent"]) == ["tickets:read", "tickets:write"]
    assert by_name["auditor"] == ["audit:read"]
    assert sorted(by_name["admin"]) == sorted(_ALL_ADMIN_SCOPES)
    assert by_name["customer"] == []


async def test_list_role_catalogue_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/v1/admin/roles")

    # Assert
    assert response.status_code == 401


async def test_list_role_catalogue_missing_scope_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: authenticated but with no users:read scope
    user = await _seed_active_user(db_session, email="cat.noscope@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=[])

    # Act
    response = await client.get("/api/v1/admin/roles", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("/insufficient-permission")


async def test_list_role_catalogue_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/v1/admin/roles", headers=_auth_headers("not-a-real-jwt"))

    # Assert
    assert response.status_code == 401


async def test_list_role_catalogue_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="cat.revoked@example.com")
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    token = encode_access_token(user_id=user.id, jti=jti, scopes=["users:read"])

    # Act
    response = await client.get("/api/v1/admin/roles", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 401


# --- MR-AC1: replacing a user's role set --------------------------------------


async def test_replace_user_roles_valid_set_returns_200_and_updates_scopes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_active_user(db_session, email="admin.happy@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="admin")
    admin_token = await _seed_session_and_token(
        db_session, user_id=admin.id, scopes=_ALL_ADMIN_SCOPES
    )
    target = await _seed_active_user(db_session, email="target.happy@example.com")

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["support_agent"]},
        headers=_auth_headers(admin_token),
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["roles"] == ["support_agent"]

    audit_result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.event == "roles_replaced", AdminAuditLog.target_id == target.id
        )
    )
    audit_entry = audit_result.scalar_one()
    assert audit_entry.old_roles == []
    assert audit_entry.new_roles == ["support_agent"]
    assert audit_entry.actor_id == admin.id

    perm_epoch_raw = await app.state.valkey_client.get(perm_epoch_key(target.id))
    assert perm_epoch_raw is not None


async def test_replace_user_roles_repeat_call_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_active_user(db_session, email="admin.repeat@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="admin")
    admin_token = await _seed_session_and_token(
        db_session, user_id=admin.id, scopes=_ALL_ADMIN_SCOPES
    )
    target = await _seed_active_user(db_session, email="target.repeat@example.com")

    # Act
    first = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers(admin_token),
    )
    second = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers(admin_token),
    )

    # Assert
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["roles"] == ["auditor"]


async def test_replace_user_roles_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.put(
        f"/api/v1/admin/users/{uuid.uuid4()}/roles", json={"roles": ["auditor"]}
    )

    # Assert
    assert response.status_code == 401


async def test_replace_user_roles_missing_scope_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: authenticated but with no roles:write scope
    user = await _seed_active_user(db_session, email="put.noscope@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=[])

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{uuid.uuid4()}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("/insufficient-permission")


async def test_replace_user_roles_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_active_user(db_session, email="put.expired@example.com")
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user.id,
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.flush()
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "jti": str(jti),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "scopes": _ALL_ADMIN_SCOPES,
    }
    expired_token = jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{uuid.uuid4()}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers(expired_token),
    )

    # Assert
    assert response.status_code == 401


async def test_replace_user_roles_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.put(
        f"/api/v1/admin/users/{uuid.uuid4()}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers("not-a-real-jwt"),
    )

    # Assert
    assert response.status_code == 401


async def test_replace_user_roles_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_active_user(db_session, email="put.revoked@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="admin")
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=admin.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    token = encode_access_token(user_id=admin.id, jti=jti, scopes=_ALL_ADMIN_SCOPES)

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{uuid.uuid4()}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 401


# --- MR-AC4: unknown role -----------------------------------------------------


async def test_replace_user_roles_unknown_role_returns_422_and_applies_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_active_user(db_session, email="admin.unknown@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="admin")
    admin_token = await _seed_session_and_token(
        db_session, user_id=admin.id, scopes=_ALL_ADMIN_SCOPES
    )
    target = await _seed_active_user(db_session, email="target.unknown@example.com")

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["not_a_real_role"]},
        headers=_auth_headers(admin_token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("/validation-failed")
    result = await db_session.execute(select(UserRole).where(UserRole.user_id == target.id))
    assert result.first() is None


async def test_replace_user_roles_empty_array_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_active_user(db_session, email="admin.empty@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="admin")
    admin_token = await _seed_session_and_token(
        db_session, user_id=admin.id, scopes=_ALL_ADMIN_SCOPES
    )
    target = await _seed_active_user(db_session, email="target.empty@example.com")

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": []},
        headers=_auth_headers(admin_token),
    )

    # Assert
    assert response.status_code == 422


async def test_replace_user_roles_duplicate_role_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_active_user(db_session, email="admin.dup@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="admin")
    admin_token = await _seed_session_and_token(
        db_session, user_id=admin.id, scopes=_ALL_ADMIN_SCOPES
    )
    target = await _seed_active_user(db_session, email="target.dup@example.com")

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["auditor", "auditor"]},
        headers=_auth_headers(admin_token),
    )

    # Assert
    assert response.status_code == 422


# --- MR-AC5: self-modification -------------------------------------------------


async def test_replace_user_roles_self_target_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_active_user(db_session, email="admin.self@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="admin")
    admin_token = await _seed_session_and_token(
        db_session, user_id=admin.id, scopes=_ALL_ADMIN_SCOPES
    )

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{admin.id}/roles",
        json={"roles": ["auditor"]},
        headers=_auth_headers(admin_token),
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("/cannot-target-self")


# --- MR-AC6: privilege escalation ---------------------------------------------


async def test_replace_user_roles_privilege_escalation_returns_403_and_audits(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: actor holds roles:write only, not the other admin scopes
    actor = await _seed_active_user(db_session, email="actor.escalate@example.com")
    actor_token = await _seed_session_and_token(
        db_session, user_id=actor.id, scopes=["roles:write"]
    )
    target = await _seed_active_user(db_session, email="target.escalate@example.com")

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["admin"]},
        headers=_auth_headers(actor_token),
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("/privilege-escalation")
    audit_result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.event == "authz_denied", AdminAuditLog.target_id == target.id
        )
    )
    audit_entry = audit_result.scalar_one()
    assert audit_entry.severity == "high"
    assert audit_entry.actor_id == actor.id


# --- MR-AC7: last administrator protection ------------------------------------


async def test_replace_user_roles_removes_admin_when_another_admin_remains(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: two active admins exist (actor and target) - removing admin
    # from target alone must succeed, since actor remains.
    actor = await _seed_active_user(db_session, email="actor.lastadmin@example.com")
    await _assign_role(db_session, user_id=actor.id, role_name="admin")
    actor_token = await _seed_session_and_token(
        db_session, user_id=actor.id, scopes=_ALL_ADMIN_SCOPES
    )
    target = await _seed_active_user(db_session, email="target.lastadmin@example.com")
    await _assign_role(db_session, user_id=target.id, role_name="admin")

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["support_agent"]},
        headers=_auth_headers(actor_token),
    )

    # Assert: a second admin (actor) remains, so this is not the last-admin case.
    assert response.status_code == 200


async def test_replace_user_roles_sole_admin_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: exactly one active admin exists (the target). The actor
    # authenticates with full admin scopes (needed to pass the privilege
    # check) without itself holding the `admin` role via user_roles, so the
    # last-admin count genuinely evaluates to zero others.
    actor = await _seed_active_user(db_session, email="actor.soleadmin@example.com")
    actor_token = await _seed_session_and_token(
        db_session, user_id=actor.id, scopes=_ALL_ADMIN_SCOPES
    )
    target = await _seed_active_user(db_session, email="target.soleadmin@example.com")
    await _assign_role(db_session, user_id=target.id, role_name="admin")

    # Act
    response = await client.put(
        f"/api/v1/admin/users/{target.id}/roles",
        json={"roles": ["support_agent"]},
        headers=_auth_headers(actor_token),
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("/last-admin")
    result = await db_session.execute(select(UserRole).where(UserRole.user_id == target.id))
    remaining = result.scalars().all()
    assert len(remaining) == 1


async def test_replace_user_roles_concurrent_last_admin_removal_only_one_succeeds(
    real_client: AsyncClient,
) -> None:
    # Arrange: seeded via a real, committed connection so both concurrent
    # requests' independent connections can see the rows, matching
    # test_account_router.py's own concurrency-test precedent.
    engine = app.state.db_engine
    actor_id = uuid.uuid4()
    admin_1_id = uuid.uuid4()
    admin_2_id = uuid.uuid4()
    async with engine.begin() as connection:
        for email, user_id in (
            (f"actor.{uuid.uuid4().hex}@example.com", actor_id),
            (f"admin1.{uuid.uuid4().hex}@example.com", admin_1_id),
            (f"admin2.{uuid.uuid4().hex}@example.com", admin_2_id),
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
    actor_token = encode_access_token(user_id=actor_id, jti=actor_jti, scopes=_ALL_ADMIN_SCOPES)

    # Act: two concurrent requests each try to remove admin from one of the
    # last two admins - only one may succeed if it would leave zero admins,
    # but here each removal targets a *different* admin, so both requests
    # racing against the SAME shared invariant (>= 1 admin must remain)
    # must not both succeed.
    responses = await asyncio.gather(
        real_client.put(
            f"/api/v1/admin/users/{admin_1_id}/roles",
            json={"roles": ["support_agent"]},
            headers=_auth_headers(actor_token),
        ),
        real_client.put(
            f"/api/v1/admin/users/{admin_2_id}/roles",
            json={"roles": ["support_agent"]},
            headers=_auth_headers(actor_token),
        ),
    )

    # Assert: exactly one 200 and one 409 - never both 200 (would leave zero
    # admins) and never both 409 (one removal alone is always safe).
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]


# --- OD-1: permission-catalogue completeness (standalone CI check, not an
# Alembic env.py hook - resolved 2026-09-01) -----------------------------------


async def test_permission_catalogue_completeness(db_session: AsyncSession) -> None:
    # Every scope this module's require_scope() calls reference must exist
    # in the permissions catalogue, and every role_permissions row must
    # reference a real permissions row (guaranteed by the FK, but checked
    # explicitly here as the documented substitute for the env.py hook the
    # source story originally asked for - see docs/decisions/
    # US-3.2-open-decisions.md OD-1).
    referenced_scopes = {"users:read", "roles:write"}
    catalogue_result = await db_session.execute(select(Permission.scope))
    catalogue_scopes = set(catalogue_result.scalars().all())
    assert referenced_scopes.issubset(catalogue_scopes)

    orphan_result = await db_session.execute(
        select(RolePermission)
        .outerjoin(Permission, RolePermission.permission_id == Permission.id)
        .where(Permission.id.is_(None))
    )
    assert orphan_result.first() is None
