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
    def __init__(
        self,
        *,
        user: User | None = None,
        already_deactivated: bool = False,
        reactivation_succeeds: bool = False,
    ) -> None:
        self.user = user
        self.already_deactivated = already_deactivated
        self.reactivation_succeeds = reactivation_succeeds
        self.deactivate_called_for: uuid.UUID | None = None
        self.reactivate_called_with: tuple[uuid.UUID, datetime] | None = None
        self.audit_entries: list[dict[str, str | uuid.UUID]] = []
        self.commit_called = False

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.user

    async def deactivate_if_not_already(self, user_id: uuid.UUID) -> datetime | None:
        self.deactivate_called_for = user_id
        if self.already_deactivated:
            return None
        return datetime.now(UTC)

    async def reactivate_if_within_grace(
        self, user_id: uuid.UUID, *, grace_period_cutoff: datetime
    ) -> bool:
        self.reactivate_called_with = (user_id, grace_period_cutoff)
        return self.reactivation_succeeds

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
    # TTL must cover the longest-lived credential this key gates, not just
    # the access token (2026-09-01 fix — see service.py's comment).
    assert cache.set_for == [(user.id, 2_592_000)]


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


# --- DA-AC8 (resolved OD-10): reactivate_account, called cross-module from
# users/service.py's login flow. -----------------------------------------


async def test_reactivate_account_within_grace_reactivates() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeAccountRepository(reactivation_succeeds=True)
    cache = FakeRevocationCache()
    service = AccountService(repository, cache)

    # Act
    reactivated = await service.reactivate_account(user_id)

    # Assert
    assert reactivated is True
    assert repository.reactivate_called_with is not None
    called_user_id, grace_period_cutoff = repository.reactivate_called_with
    assert called_user_id == user_id
    assert grace_period_cutoff < datetime.now(UTC)
    assert repository.audit_entries == [
        {"user_id": user_id, "event": "reactivated", "actor": "self"}
    ]
    assert repository.commit_called is True


async def test_reactivate_account_past_grace_does_not_reactivate() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeAccountRepository(reactivation_succeeds=False)
    cache = FakeRevocationCache()
    service = AccountService(repository, cache)

    # Act
    reactivated = await service.reactivate_account(user_id)

    # Assert
    assert reactivated is False
    assert repository.audit_entries == []
    assert repository.commit_called is False


async def test_reactivate_account_already_active_is_noop() -> None:
    # Arrange — the repository's atomic WHERE clause matches zero rows for
    # an already-active account, same as a past-grace one: both report False.
    user_id = uuid.uuid4()
    repository = FakeAccountRepository(reactivation_succeeds=False)
    cache = FakeRevocationCache()
    service = AccountService(repository, cache)

    # Act
    reactivated = await service.reactivate_account(user_id)

    # Assert
    assert reactivated is False
    assert repository.commit_called is False
