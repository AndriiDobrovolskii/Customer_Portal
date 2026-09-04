import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.admin_users.exceptions import (
    AlreadyDeactivatedError,
    CannotTargetSelfError,
    EmailAlreadyRegisteredError,
    ImmutableFieldError,
    InvalidStateTransitionError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    TooManyAttemptsError,
    ValidationFailedError,
)
from app.modules.admin_users.models import InvitationToken
from app.modules.admin_users.repository import UserListPage
from app.modules.admin_users.schemas import CreateUserRequest
from app.modules.admin_users.service import AdminUserService, _hash_token
from app.modules.roles.exceptions import LastAdminError, PrivilegeEscalationError
from app.modules.users.models import User

pytestmark = pytest.mark.unit

_FIXED_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "invitee@example.com",
    display_name: str | None = "Jane Doe",
    status: str = "active",
    locale: str | None = None,
    timezone: str | None = None,
    avatar_url: str | None = None,
    created_at: datetime = _FIXED_NOW,
    last_login_at: datetime | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password="",
        status=status,
        email_verified=status != "invited",
        display_name=display_name,
        locale=locale,
        timezone=timezone,
        avatar_url=avatar_url,
    )
    user.id = user_id or uuid.uuid4()
    user.created_at = created_at
    user.last_login_at = last_login_at
    return user


class FakeAdminUserRepository:
    def __init__(
        self,
        *,
        users: dict[uuid.UUID, User] | None = None,
        roles: dict[uuid.UUID, list[str]] | None = None,
        duplicate_email: bool = False,
        list_page: UserListPage | None = None,
        list_returns_none: bool = False,
        latest_invitation_token: InvitationToken | None = None,
        latest_unconsumed_token: InvitationToken | None = None,
        recent_token_count: int = 0,
    ) -> None:
        self.users = users or {}
        self.roles = roles or {}
        self.duplicate_email = duplicate_email
        self.list_page = list_page
        self.list_returns_none = list_returns_none
        self.latest_invitation_token = latest_invitation_token
        self.latest_unconsumed_token = latest_unconsumed_token
        self.recent_token_count = recent_token_count
        self.created_users: list[tuple[str, str, list[uuid.UUID]]] = []
        self.updated_fields: list[tuple[uuid.UUID, dict[str, str | None]]] = []
        self.deactivated: list[uuid.UUID] = []
        self.event_audit_entries: list[dict[str, object]] = []
        self.field_audit_entries: list[dict[str, object]] = []
        self.lifecycle_audit_entries: list[dict[str, object]] = []
        self.invalidated_tokens: list[uuid.UUID] = []
        self.created_tokens: list[tuple[uuid.UUID, str, datetime]] = []
        self.committed = False

    async def list_users(
        self,
        *,
        q: str | None,
        status: str | None,
        role: str | None,
        cursor: str | None,
        limit: int,
    ) -> UserListPage | None:
        if self.list_returns_none:
            return None
        if self.list_page is not None:
            return self.list_page
        items = [(u, self.roles.get(u.id, [])) for u in self.users.values()]
        return UserListPage(items=items, next_cursor=None)

    async def get_with_roles(self, user_id: uuid.UUID) -> tuple[User, list[str]] | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        return user, self.roles.get(user_id, [])

    async def create(
        self, *, email: str, display_name: str, role_ids: list[uuid.UUID]
    ) -> User | None:
        if self.duplicate_email:
            return None
        self.created_users.append((email, display_name, role_ids))
        user = _make_user(email=email, display_name=display_name, status="invited")
        self.users[user.id] = user
        self.roles[user.id] = []
        return user

    async def update_fields(self, user_id: uuid.UUID, fields: dict[str, str | None]) -> User | None:
        self.updated_fields.append((user_id, fields))
        user = self.users.get(user_id)
        if user is None:
            return None
        for field, value in fields.items():
            setattr(user, field, value)
        return user

    async def deactivate_if_active(self, user_id: uuid.UUID) -> datetime | None:
        user = self.users.get(user_id)
        if user is None or user.status != "active":
            return None
        self.deactivated.append(user_id)
        return _FIXED_NOW

    async def create_admin_audit_log_event(
        self, *, event: str, actor_id: uuid.UUID, target_id: uuid.UUID | None, request_id: str
    ) -> None:
        self.event_audit_entries.append(
            {"event": event, "actor_id": actor_id, "target_id": target_id, "request_id": request_id}
        )

    async def create_admin_audit_log_field_change(
        self,
        *,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
        field: str,
        old_value: str | None,
        new_value: str | None,
        reason: str,
        request_id: str,
    ) -> None:
        self.field_audit_entries.append(
            {
                "actor_id": actor_id,
                "target_id": target_id,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "reason": reason,
                "request_id": request_id,
            }
        )

    async def create_account_lifecycle_audit_log_entry(
        self, *, user_id: uuid.UUID, event: str, actor: str, reason: str | None
    ) -> None:
        self.lifecycle_audit_entries.append(
            {"user_id": user_id, "event": event, "actor": actor, "reason": reason}
        )

    async def get_latest_unconsumed_invitation_token(
        self, user_id: uuid.UUID
    ) -> InvitationToken | None:
        return self.latest_unconsumed_token

    async def get_latest_invitation_token(self, user_id: uuid.UUID) -> InvitationToken | None:
        return self.latest_invitation_token

    async def count_invitation_tokens_issued_since(
        self, user_id: uuid.UUID, since: datetime
    ) -> int:
        return self.recent_token_count

    async def invalidate_invitation_token(self, token_id: uuid.UUID) -> None:
        self.invalidated_tokens.append(token_id)

    async def create_invitation_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> InvitationToken:
        self.created_tokens.append((user_id, token_hash, expires_at))
        return InvitationToken(
            id=uuid.uuid4(), user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )

    async def commit(self) -> None:
        self.committed = True


class FakeRoleService:
    def __init__(
        self,
        *,
        role_ids: list[uuid.UUID] | None = None,
        raises_escalation: bool = False,
        raises_last_admin: bool = False,
    ) -> None:
        self.role_ids = role_ids or []
        self.raises_escalation = raises_escalation
        self.raises_last_admin = raises_last_admin
        self.grant_calls: list[tuple[uuid.UUID, set[str], list[str]]] = []
        self.last_admin_calls: list[uuid.UUID] = []

    async def resolve_role_ids_for_grant(
        self,
        *,
        actor_id: uuid.UUID,
        actor_scopes: set[str],
        role_names: list[str],
        request_id: str,
    ) -> list[uuid.UUID]:
        self.grant_calls.append((actor_id, actor_scopes, role_names))
        if self.raises_escalation:
            raise PrivilegeEscalationError()
        return self.role_ids

    async def raise_if_last_admin(self, target_user_id: uuid.UUID) -> None:
        self.last_admin_calls.append(target_user_id)
        if self.raises_last_admin:
            raise LastAdminError()


class FakeRevocationCache:
    def __init__(self) -> None:
        self.set_for: list[tuple[uuid.UUID, int]] = []

    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None:
        self.set_for.append((user_id, ttl_seconds))


class FakeEmailSender:
    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.invitations_sent: list[dict[str, str]] = []

    async def send_invitation_email(self, *, to: str, raw_token: str) -> None:
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.invitations_sent.append({"to": to, "raw_token": raw_token})

    # Unused EmailSender Protocol members - never called by this service.
    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_email_change_notice(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_refresh_reuse_alert(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_password_reset_email(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_password_reset_notice(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_mfa_recovery_used_notice(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_ticket_created_email(self, *, to: str, ticket_number: str) -> None:
        raise NotImplementedError


def _make_service(
    repository: FakeAdminUserRepository | None = None,
    role_service: FakeRoleService | None = None,
    revocation_cache: FakeRevocationCache | None = None,
    email_sender: FakeEmailSender | None = None,
) -> tuple[
    AdminUserService, FakeAdminUserRepository, FakeRoleService, FakeRevocationCache, FakeEmailSender
]:
    repository = repository or FakeAdminUserRepository()
    role_service = role_service or FakeRoleService()
    revocation_cache = revocation_cache or FakeRevocationCache()
    email_sender = email_sender or FakeEmailSender()
    service = AdminUserService(
        repository,
        role_service,
        revocation_cache,
        email_sender=email_sender,
        clock=lambda: _FIXED_NOW,
    )
    return service, repository, role_service, revocation_cache, email_sender


# --- FR-1/FR-4: list_users ---------------------------------------------------


async def test_list_users_returns_filtered_paginated_page() -> None:
    # Arrange
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user}, roles={user.id: ["support_agent"]})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act
    result = await service.list_users(q=None, status=None, role=None, cursor=None, limit=25)

    # Assert
    assert len(result.items) == 1
    assert result.items[0].id == user.id
    assert result.items[0].roles == ["support_agent"]


async def test_list_users_response_excludes_credential_material() -> None:
    # Arrange
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act
    result = await service.list_users(q=None, status=None, role=None, cursor=None, limit=25)

    # Assert
    assert not hasattr(result.items[0], "hashed_password")


async def test_list_users_limit_over_max_returns_422() -> None:
    # Arrange
    service, _, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.list_users(q=None, status=None, role=None, cursor=None, limit=5000)


async def test_list_users_unknown_status_returns_422() -> None:
    # Arrange
    service, _, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.list_users(q=None, status="bogus", role=None, cursor=None, limit=25)


async def test_list_users_malformed_cursor_returns_422() -> None:
    # Arrange
    repository = FakeAdminUserRepository(list_returns_none=True)
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.list_users(q=None, status=None, role=None, cursor="garbage", limit=25)


# --- FR-22/FR-23: get_user ---------------------------------------------------


async def test_get_user_returns_user_and_etag() -> None:
    # Arrange
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act
    result, etag = await service.get_user(user.id)

    # Assert
    assert result.id == user.id
    assert etag


async def test_get_user_unknown_id_returns_404() -> None:
    # Arrange
    service, _, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(NotFoundError):
        await service.get_user(uuid.uuid4())


# --- FR-5/FR-6/FR-7/FR-8: create_user ---------------------------------------


async def test_create_user_returns_created_resource_and_provisions_invitation() -> None:
    # Arrange
    role_id = uuid.uuid4()
    repository = FakeAdminUserRepository()
    role_service = FakeRoleService(role_ids=[role_id])
    email_sender = FakeEmailSender()
    service, _, _, _, _ = _make_service(
        repository=repository, role_service=role_service, email_sender=email_sender
    )
    payload = CreateUserRequest(
        email="New.User@Example.com", display_name="New User", roles=["support_agent"]
    )
    actor_id = uuid.uuid4()

    # Act
    result, etag = await service.create_user(
        actor_id=actor_id, actor_scopes={"tickets:read"}, payload=payload, request_id="req-1"
    )

    # Assert
    assert result.status == "invited"
    assert result.email == "new.user@example.com"
    assert etag
    assert repository.created_users[0][0] == "new.user@example.com"
    assert repository.created_users[0][2] == [role_id]
    assert repository.event_audit_entries[0]["event"] == "user_created"
    assert repository.event_audit_entries[0]["actor_id"] == actor_id
    assert len(email_sender.invitations_sent) == 1
    assert email_sender.invitations_sent[0]["to"] == "new.user@example.com"


async def test_create_user_duplicate_email_returns_409() -> None:
    # Arrange
    repository = FakeAdminUserRepository(duplicate_email=True)
    service, _, _, _, _ = _make_service(repository=repository)
    payload = CreateUserRequest(email="dup@example.com", display_name="Dup", roles=[])

    # Act & Assert
    with pytest.raises(EmailAlreadyRegisteredError):
        await service.create_user(
            actor_id=uuid.uuid4(), actor_scopes=set(), payload=payload, request_id="req-2"
        )


async def test_create_user_privilege_escalation_returns_403() -> None:
    # Arrange
    role_service = FakeRoleService(raises_escalation=True)
    service, repository, _, _, _ = _make_service(role_service=role_service)
    payload = CreateUserRequest(email="escalate@example.com", display_name="X", roles=["admin"])

    # Act & Assert
    with pytest.raises(PrivilegeEscalationError):
        await service.create_user(
            actor_id=uuid.uuid4(),
            actor_scopes={"tickets:read"},
            payload=payload,
            request_id="req-3",
        )
    assert repository.created_users == []


async def test_create_user_email_dispatch_failure_does_not_undo_creation() -> None:
    # Arrange: best-effort email, mirrors UserService.register_user
    email_sender = FakeEmailSender(raises=True)
    service, repository, _, _, _ = _make_service(email_sender=email_sender)
    payload = CreateUserRequest(email="stillcreated@example.com", display_name="X", roles=[])

    # Act
    result, _etag = await service.create_user(
        actor_id=uuid.uuid4(), actor_scopes=set(), payload=payload, request_id="req-4"
    )

    # Assert
    assert result.status == "invited"
    assert repository.committed is True


# --- FR-9/FR-10/FR-11/FR-12: update_user ------------------------------------


async def test_update_user_returns_updated_resource_and_writes_one_audit_row_per_field() -> None:
    # Arrange
    user = _make_user(display_name="Old Name", locale="en-US")
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)
    from app.core.etag import compute_profile_etag

    current_etag = compute_profile_etag(
        {"display_name": "Old Name", "locale": "en-US", "timezone": None, "avatar_url": None}
    )
    actor_id = uuid.uuid4()

    # Act
    result, new_etag = await service.update_user(
        actor_id=actor_id,
        target_id=user.id,
        raw_body={"display_name": "New Name", "reason": "typo fix"},
        if_match=current_etag,
        request_id="req-5",
    )

    # Assert
    assert result.display_name == "New Name"
    assert new_etag != current_etag
    assert len(repository.field_audit_entries) == 1
    entry = repository.field_audit_entries[0]
    assert entry["field"] == "display_name"
    assert entry["old_value"] == "Old Name"
    assert entry["new_value"] == "New Name"
    assert entry["reason"] == "typo fix"
    assert entry["actor_id"] == actor_id


async def test_update_user_multiple_fields_writes_multiple_audit_rows() -> None:
    # Arrange
    user = _make_user(display_name="Old", locale="en-US")
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)
    from app.core.etag import compute_profile_etag

    current_etag = compute_profile_etag(
        {"display_name": "Old", "locale": "en-US", "timezone": None, "avatar_url": None}
    )

    # Act
    await service.update_user(
        actor_id=uuid.uuid4(),
        target_id=user.id,
        raw_body={"display_name": "New", "locale": "en-GB", "reason": "bulk correction"},
        if_match=current_etag,
        request_id="req-6",
    )

    # Assert
    assert len(repository.field_audit_entries) == 2


async def test_update_user_stale_etag_returns_412() -> None:
    # Arrange
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(PreconditionFailedError):
        await service.update_user(
            actor_id=uuid.uuid4(),
            target_id=user.id,
            raw_body={"display_name": "X", "reason": "r"},
            if_match='"stale-value"',
            request_id="req-7",
        )


async def test_update_user_missing_if_match_returns_400() -> None:
    # Arrange
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(PreconditionRequiredError):
        await service.update_user(
            actor_id=uuid.uuid4(),
            target_id=user.id,
            raw_body={"display_name": "X", "reason": "r"},
            if_match=None,
            request_id="req-8",
        )


async def test_update_user_immutable_field_returns_422() -> None:
    # Arrange
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(ImmutableFieldError):
        await service.update_user(
            actor_id=uuid.uuid4(),
            target_id=user.id,
            raw_body={"roles": ["admin"], "reason": "r"},
            if_match="*",
            request_id="req-9",
        )


async def test_update_user_undeclared_field_returns_422_validation_failed() -> None:
    # Arrange: email is not in MU-AC11's immutable list, so it's rejected
    # as an undeclared field (validation-failed), not immutable-field.
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.update_user(
            actor_id=uuid.uuid4(),
            target_id=user.id,
            raw_body={"email": "new@example.com", "reason": "r"},
            if_match="*",
            request_id="req-10",
        )


async def test_update_user_missing_reason_returns_422() -> None:
    # Arrange
    user = _make_user()
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.update_user(
            actor_id=uuid.uuid4(),
            target_id=user.id,
            raw_body={"display_name": "X"},
            if_match="*",
            request_id="req-11",
        )


async def test_update_user_unknown_id_returns_404() -> None:
    # Arrange
    service, _, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(NotFoundError):
        await service.update_user(
            actor_id=uuid.uuid4(),
            target_id=uuid.uuid4(),
            raw_body={"display_name": "X", "reason": "r"},
            if_match="*",
            request_id="req-12",
        )


# --- FR-13/FR-14/FR-15/FR-16/FR-17b: deactivate_user ------------------------


async def test_deactivate_user_returns_200_and_applies_side_effects() -> None:
    # Arrange
    user = _make_user(status="active")
    repository = FakeAdminUserRepository(users={user.id: user})
    revocation_cache = FakeRevocationCache()
    service, _, _, _, _ = _make_service(repository=repository, revocation_cache=revocation_cache)

    # Act
    result = await service.deactivate_user(
        actor_id=uuid.uuid4(), target_id=user.id, reason="left the company", request_id="req-13"
    )

    # Assert
    assert result.status == "deactivated"
    assert repository.lifecycle_audit_entries[0]["event"] == "deactivated"
    assert repository.lifecycle_audit_entries[0]["reason"] == "left the company"
    assert revocation_cache.set_for[0][0] == user.id


async def test_deactivate_user_already_deactivated_returns_409() -> None:
    # Arrange
    user = _make_user(status="deactivated")
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(AlreadyDeactivatedError):
        await service.deactivate_user(
            actor_id=uuid.uuid4(), target_id=user.id, reason="r", request_id="req-14"
        )


async def test_deactivate_user_self_target_returns_409() -> None:
    # Arrange
    actor_id = uuid.uuid4()
    service, _, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(CannotTargetSelfError):
        await service.deactivate_user(
            actor_id=actor_id, target_id=actor_id, reason="r", request_id="req-15"
        )


async def test_deactivate_user_last_admin_returns_409() -> None:
    # Arrange
    user = _make_user(status="active")
    repository = FakeAdminUserRepository(users={user.id: user})
    role_service = FakeRoleService(raises_last_admin=True)
    service, _, _, _, _ = _make_service(repository=repository, role_service=role_service)

    # Act & Assert
    with pytest.raises(LastAdminError):
        await service.deactivate_user(
            actor_id=uuid.uuid4(), target_id=user.id, reason="r", request_id="req-16"
        )
    assert repository.deactivated == []


async def test_deactivate_user_unknown_id_returns_404() -> None:
    # Arrange
    service, _, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(NotFoundError):
        await service.deactivate_user(
            actor_id=uuid.uuid4(), target_id=uuid.uuid4(), reason="r", request_id="req-17"
        )


# --- FR-18/FR-19/FR-20/FR-21: resend_invite ---------------------------------


async def test_resend_invite_returns_and_reissues_token() -> None:
    # Arrange
    user = _make_user(status="invited")
    old_token = InvitationToken(
        id=uuid.uuid4(), user_id=user.id, token_hash="old-hash", expires_at=_FIXED_NOW
    )
    repository = FakeAdminUserRepository(
        users={user.id: user}, latest_unconsumed_token=old_token, latest_invitation_token=None
    )
    email_sender = FakeEmailSender()
    service, _, _, _, _ = _make_service(repository=repository, email_sender=email_sender)
    actor_id = uuid.uuid4()

    # Act
    await service.resend_invite(actor_id=actor_id, target_id=user.id, request_id="req-18")

    # Assert
    assert repository.invalidated_tokens == [old_token.id]
    assert len(repository.created_tokens) == 1
    assert repository.event_audit_entries[0]["event"] == "invitation_resent"
    assert repository.event_audit_entries[0]["actor_id"] == actor_id
    assert len(email_sender.invitations_sent) == 1


async def test_resend_invite_active_target_returns_409() -> None:
    # Arrange
    user = _make_user(status="active")
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError):
        await service.resend_invite(actor_id=uuid.uuid4(), target_id=user.id, request_id="req-19")


async def test_resend_invite_deactivated_target_returns_409() -> None:
    # Arrange
    user = _make_user(status="deactivated")
    repository = FakeAdminUserRepository(users={user.id: user})
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError):
        await service.resend_invite(actor_id=uuid.uuid4(), target_id=user.id, request_id="req-20")


async def test_resend_invite_within_cooldown_returns_429() -> None:
    # Arrange
    user = _make_user(status="invited")
    recent_token = InvitationToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash="h",
        issued_at=_FIXED_NOW - timedelta(seconds=10),
        expires_at=_FIXED_NOW,
    )
    repository = FakeAdminUserRepository(
        users={user.id: user}, latest_invitation_token=recent_token
    )
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError):
        await service.resend_invite(actor_id=uuid.uuid4(), target_id=user.id, request_id="req-21")


async def test_resend_invite_over_hourly_cap_returns_429() -> None:
    # Arrange
    user = _make_user(status="invited")
    repository = FakeAdminUserRepository(users={user.id: user}, recent_token_count=5)
    service, _, _, _, _ = _make_service(repository=repository)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError):
        await service.resend_invite(actor_id=uuid.uuid4(), target_id=user.id, request_id="req-22")


async def test_resend_invite_unknown_id_returns_404() -> None:
    # Arrange
    service, _, _, _, _ = _make_service()

    # Act & Assert
    with pytest.raises(NotFoundError):
        await service.resend_invite(
            actor_id=uuid.uuid4(), target_id=uuid.uuid4(), request_id="req-23"
        )


# --- Helper coverage ---------------------------------------------------------


def test_hash_token_is_deterministic_and_hex() -> None:
    # Arrange & Act
    digest = _hash_token("raw-token-value")

    # Assert
    assert digest == _hash_token("raw-token-value")
    assert len(digest) == 64
    int(digest, 16)  # raises ValueError if not valid hex
