import uuid

import pytest

from app.modules.roles.exceptions import (
    CannotTargetSelfError,
    LastAdminError,
    PrivilegeEscalationError,
    ValidationFailedError,
)
from app.modules.roles.models import Permission, Role
from app.modules.roles.service import RoleService

pytestmark = pytest.mark.unit


def _fake_permission(scope: str) -> Permission:
    permission = Permission(id=uuid.uuid4(), scope=scope)
    return permission


def _fake_role(name: str, permission_scopes: list[str]) -> Role:
    role = Role(id=uuid.uuid4(), name=name)
    role.permissions = [_fake_permission(scope) for scope in permission_scopes]
    return role


_CUSTOMER = _fake_role("customer", [])
_SUPPORT_AGENT = _fake_role("support_agent", ["tickets:read", "tickets:write"])
_ADMIN = _fake_role(
    "admin",
    ["users:read", "users:write", "roles:write", "audit:read", "tickets:read", "tickets:write"],
)
_AUDITOR = _fake_role("auditor", ["audit:read"])
_CATALOGUE = {role.name: role for role in (_CUSTOMER, _SUPPORT_AGENT, _ADMIN, _AUDITOR)}


class FakeRoleRepository:
    def __init__(self, roles: dict[str, Role] | None = None) -> None:
        self.roles = roles if roles is not None else dict(_CATALOGUE)

    async def list_all_with_permissions(self) -> list[Role]:
        return list(self.roles.values())

    async def get_by_names(self, names: list[str]) -> list[Role]:
        return [self.roles[name] for name in names if name in self.roles]


class FakeUserRoleRepository:
    def __init__(
        self,
        *,
        current_roles: dict[uuid.UUID, list[str]] | None = None,
        active_admin_ids: set[uuid.UUID] | None = None,
    ) -> None:
        self.current_roles = current_roles or {}
        self.active_admin_ids = active_admin_ids or set()
        self.replaced: list[tuple[uuid.UUID, list[uuid.UUID]]] = []
        self.audit_entries: list[dict[str, object]] = []
        self.committed = False

    async def list_role_names_for_user(self, user_id: uuid.UUID) -> list[str]:
        return self.current_roles.get(user_id, [])

    async def count_active_admins_excluding(
        self, *, admin_role_id: uuid.UUID, excluding_user_id: uuid.UUID
    ) -> int:
        return len(self.active_admin_ids - {excluding_user_id})

    async def replace_for_user(self, *, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> None:
        self.replaced.append((user_id, role_ids))

    async def create_admin_audit_log_entry(
        self,
        *,
        event: str,
        actor_id: uuid.UUID,
        target_id: uuid.UUID | None,
        old_roles: list[str] | None,
        new_roles: list[str] | None,
        severity: str | None,
        request_id: str,
    ) -> None:
        self.audit_entries.append(
            {
                "event": event,
                "actor_id": actor_id,
                "target_id": target_id,
                "old_roles": old_roles,
                "new_roles": new_roles,
                "severity": severity,
                "request_id": request_id,
            }
        )

    async def commit(self) -> None:
        self.committed = True


class FakePermissionEpochCache:
    def __init__(self) -> None:
        self.set_for: list[tuple[uuid.UUID, int]] = []

    async def set_perm_epoch(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None:
        self.set_for.append((user_id, ttl_seconds))


def _make_service(
    role_repository: FakeRoleRepository | None = None,
    user_role_repository: FakeUserRoleRepository | None = None,
    permission_epoch_cache: FakePermissionEpochCache | None = None,
) -> tuple[RoleService, FakeRoleRepository, FakeUserRoleRepository, FakePermissionEpochCache]:
    role_repository = role_repository or FakeRoleRepository()
    user_role_repository = user_role_repository or FakeUserRoleRepository()
    permission_epoch_cache = permission_epoch_cache or FakePermissionEpochCache()
    service = RoleService(role_repository, user_role_repository, permission_epoch_cache)
    return service, role_repository, user_role_repository, permission_epoch_cache


async def test_list_catalogue_maps_roles_to_permissions() -> None:
    # Arrange
    service, _, _, _ = _make_service()

    # Act
    result = await service.list_catalogue()

    # Assert
    by_name = {role.name: role.permissions for role in result.roles}
    assert by_name["customer"] == []
    assert by_name["support_agent"] == ["tickets:read", "tickets:write"]
    assert by_name["auditor"] == ["audit:read"]
    assert sorted(by_name["admin"]) == [
        "audit:read",
        "roles:write",
        "tickets:read",
        "tickets:write",
        "users:read",
        "users:write",
    ]


async def test_resolve_scopes_for_user_flattens_and_dedupes_across_roles() -> None:
    # Arrange: a user holding two roles whose scopes overlap on tickets:read
    user_id = uuid.uuid4()
    user_role_repository = FakeUserRoleRepository(
        current_roles={user_id: ["support_agent", "auditor"]}
    )
    service, _, _, _ = _make_service(user_role_repository=user_role_repository)

    # Act
    scopes = await service.resolve_scopes_for_user(user_id)

    # Assert
    assert scopes == ["audit:read", "tickets:read", "tickets:write"]


async def test_replace_user_roles_valid_set_returns_200_and_updates_scopes() -> None:
    # Arrange
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()
    user_role_repository = FakeUserRoleRepository(current_roles={target_id: ["customer"]})
    permission_epoch_cache = FakePermissionEpochCache()
    service, _, _, _ = _make_service(
        user_role_repository=user_role_repository, permission_epoch_cache=permission_epoch_cache
    )

    # Act
    result = await service.replace_user_roles(
        actor_id=actor_id,
        actor_scopes={"roles:write", "tickets:read", "tickets:write"},
        target_id=target_id,
        requested_role_names=["support_agent"],
        request_id="req-1",
    )

    # Assert
    assert result.roles == ["support_agent"]
    assert user_role_repository.committed is True
    assert permission_epoch_cache.set_for[0][0] == target_id
    audit = user_role_repository.audit_entries[0]
    assert audit["event"] == "roles_replaced"
    assert audit["old_roles"] == ["customer"]
    assert audit["new_roles"] == ["support_agent"]


async def test_replace_user_roles_self_target_rejected() -> None:
    # Arrange
    actor_id = uuid.uuid4()
    service, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(CannotTargetSelfError):
        await service.replace_user_roles(
            actor_id=actor_id,
            actor_scopes={"roles:write"},
            target_id=actor_id,
            requested_role_names=["support_agent"],
            request_id="req-2",
        )


async def test_replace_user_roles_empty_array_rejected() -> None:
    # Arrange
    service, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.replace_user_roles(
            actor_id=uuid.uuid4(),
            actor_scopes={"roles:write"},
            target_id=uuid.uuid4(),
            requested_role_names=[],
            request_id="req-3",
        )


async def test_replace_user_roles_duplicate_role_rejected() -> None:
    # Arrange
    service, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.replace_user_roles(
            actor_id=uuid.uuid4(),
            actor_scopes={"roles:write"},
            target_id=uuid.uuid4(),
            requested_role_names=["support_agent", "support_agent"],
            request_id="req-4",
        )


async def test_replace_user_roles_unknown_role_rejected() -> None:
    # Arrange
    service, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.replace_user_roles(
            actor_id=uuid.uuid4(),
            actor_scopes={"roles:write"},
            target_id=uuid.uuid4(),
            requested_role_names=["not_a_real_role"],
            request_id="req-5",
        )


async def test_replace_user_roles_privilege_escalation_rejected_and_audited() -> None:
    # Arrange: actor holds roles:write but not the admin-only scopes
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()
    user_role_repository = FakeUserRoleRepository()
    service, _, _, _ = _make_service(user_role_repository=user_role_repository)

    # Act & Assert
    with pytest.raises(PrivilegeEscalationError):
        await service.replace_user_roles(
            actor_id=actor_id,
            actor_scopes={"roles:write"},
            target_id=target_id,
            requested_role_names=["admin"],
            request_id="req-6",
        )
    audit = user_role_repository.audit_entries[0]
    assert audit["event"] == "authz_denied"
    assert audit["severity"] == "high"
    assert user_role_repository.committed is True
    assert user_role_repository.replaced == []


async def test_replace_user_roles_rejects_removing_last_admin() -> None:
    # Arrange: target is the sole active admin; requested set drops admin
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()
    user_role_repository = FakeUserRoleRepository(
        current_roles={target_id: ["admin"]}, active_admin_ids=set()
    )
    service, _, _, _ = _make_service(user_role_repository=user_role_repository)

    # Act & Assert
    with pytest.raises(LastAdminError):
        await service.replace_user_roles(
            actor_id=actor_id,
            actor_scopes={
                "users:read",
                "users:write",
                "roles:write",
                "audit:read",
                "tickets:read",
                "tickets:write",
            },
            target_id=target_id,
            requested_role_names=["support_agent"],
            request_id="req-7",
        )
    assert user_role_repository.replaced == []


async def test_replace_user_roles_allows_removing_admin_when_another_admin_remains() -> None:
    # Arrange: a second active admin exists besides the target
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()
    other_admin_id = uuid.uuid4()
    user_role_repository = FakeUserRoleRepository(
        current_roles={target_id: ["admin"]}, active_admin_ids={other_admin_id}
    )
    service, _, _, _ = _make_service(user_role_repository=user_role_repository)

    # Act
    result = await service.replace_user_roles(
        actor_id=actor_id,
        actor_scopes={
            "users:read",
            "users:write",
            "roles:write",
            "audit:read",
            "tickets:read",
            "tickets:write",
        },
        target_id=target_id,
        requested_role_names=["support_agent"],
        request_id="req-8",
    )

    # Assert
    assert result.roles == ["support_agent"]
    assert len(user_role_repository.replaced) == 1
