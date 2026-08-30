import uuid
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from app.core.security import hash_password
from app.modules.account.exceptions import AlreadyDeactivatedError, InvalidPasswordError
from app.modules.account.schemas import DeactivateAccountRequest
from app.modules.account.service import AccountService
from app.modules.users.models import User

pytestmark = pytest.mark.unit


class FakeAccountRepository:
    def __init__(self, *, user: User | None = None, already_deactivated: bool = False) -> None:
        self.user = user
        self.already_deactivated = already_deactivated
        self.deactivate_called_for: uuid.UUID | None = None
        self.audit_entries: list[dict[str, str | uuid.UUID]] = []
        self.commit_called = False

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.user

    async def deactivate_if_not_already(self, user_id: uuid.UUID) -> datetime | None:
        self.deactivate_called_for = user_id
        if self.already_deactivated:
            return None
        return datetime.now(UTC)

    async def create_audit_log_entry(self, *, user_id: uuid.UUID, event: str, actor: str) -> None:
        self.audit_entries.append({"user_id": user_id, "event": event, "actor": actor})

    async def commit(self) -> None:
        self.commit_called = True


class FakeRevocationCache:
    def __init__(self) -> None:
        self.set_for: list[tuple[uuid.UUID, int]] = []

    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None:
        self.set_for.append((user_id, ttl_seconds))


async def _seed_user(*, password: str) -> User:
    user = User(
        email="user@example.com", hashed_password=await hash_password(password), status="active"
    )
    user.id = uuid.uuid4()
    return user


async def test_deactivate_account_correct_password_deactivates() -> None:
    # Arrange
    user = await _seed_user(password="Str0ng!Pass")  # pragma: allowlist secret
    repository = FakeAccountRepository(user=user)
    cache = FakeRevocationCache()
    service = AccountService(repository, cache)
    password = SecretStr("Str0ng!Pass")  # pragma: allowlist secret
    payload = DeactivateAccountRequest(current_password=password)

    # Act
    result = await service.deactivate_account(user_id=user.id, payload=payload)

    # Assert
    assert result.status == "deactivated"
    assert repository.deactivate_called_for == user.id
    assert repository.commit_called is True
    assert repository.audit_entries == [
        {"user_id": user.id, "event": "deactivated", "actor": "self"}
    ]
    assert cache.set_for == [(user.id, 900)]


async def test_deactivate_account_wrong_password_raises_invalid_password() -> None:
    # Arrange
    user = await _seed_user(password="Str0ng!Pass")  # pragma: allowlist secret
    repository = FakeAccountRepository(user=user)
    cache = FakeRevocationCache()
    service = AccountService(repository, cache)
    password = SecretStr("WrongPassword1!")  # pragma: allowlist secret
    payload = DeactivateAccountRequest(current_password=password)

    # Act & Assert
    with pytest.raises(InvalidPasswordError):
        await service.deactivate_account(user_id=user.id, payload=payload)
    assert repository.deactivate_called_for is None
    assert repository.commit_called is False
    assert cache.set_for == []


async def test_deactivate_account_already_deactivated_raises_already_deactivated() -> None:
    # Arrange
    user = await _seed_user(password="Str0ng!Pass")  # pragma: allowlist secret
    repository = FakeAccountRepository(user=user, already_deactivated=True)
    cache = FakeRevocationCache()
    service = AccountService(repository, cache)
    password = SecretStr("Str0ng!Pass")  # pragma: allowlist secret
    payload = DeactivateAccountRequest(current_password=password)

    # Act & Assert
    with pytest.raises(AlreadyDeactivatedError):
        await service.deactivate_account(user_id=user.id, payload=payload)
    assert repository.commit_called is False
    assert cache.set_for == []
