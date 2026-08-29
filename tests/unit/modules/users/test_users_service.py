import uuid
from datetime import UTC, datetime

import pytest

from app.modules.users.exceptions import DuplicateEmailError, RegistrationValidationError
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserStatus
from app.modules.users.service import UserService

pytestmark = pytest.mark.unit


class FakeUserRepository:
    def __init__(self, *, existing_emails: set[str] | None = None) -> None:
        self.existing_emails = existing_emails or set()
        self.created_with: dict[str, str] | None = None
        self.commit_called = False

    async def create(self, *, email: str, hashed_password: str, status: str) -> User | None:
        if email in self.existing_emails:
            return None
        self.created_with = {"email": email, "hashed_password": hashed_password, "status": status}
        user = User(email=email, hashed_password=hashed_password, status=status)
        user.id = uuid.uuid4()
        user.created_at = datetime.now(UTC)
        return user

    async def commit(self) -> None:
        self.commit_called = True


async def test_register_user_valid_input_returns_pending_verification() -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email="user@example.com", password="Str0ng!Pass")

    # Act
    result = await service.register_user(payload)

    # Assert
    assert result.email == "user@example.com"
    assert result.status == UserStatus.PENDING_VERIFICATION
    assert repository.commit_called is True


async def test_register_user_hashes_password_before_storing() -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email="user@example.com", password="Str0ng!Pass")

    # Act
    await service.register_user(payload)

    # Assert
    assert repository.created_with is not None
    assert repository.created_with["hashed_password"] != "Str0ng!Pass"


async def test_register_user_trims_and_lowercases_email() -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email="  User@Example.com  ", password="Str0ng!Pass")

    # Act
    await service.register_user(payload)

    # Assert
    assert repository.created_with is not None
    assert repository.created_with["email"] == "user@example.com"


@pytest.mark.parametrize("email", [None, "", "   "])
async def test_register_user_missing_email_raises_required(email: str | None) -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email=email, password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(RegistrationValidationError) as exc_info:
        await service.register_user(payload)
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].field == "email"
    assert exc_info.value.errors[0].code == "REQUIRED"


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "missing-domain@", "@missing-local.com", "no-at-sign.com"],
)
async def test_register_user_malformed_email_raises_invalid_format(email: str) -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email=email, password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(RegistrationValidationError) as exc_info:
        await service.register_user(payload)
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].field == "email"
    assert exc_info.value.errors[0].code == "INVALID_FORMAT"


@pytest.mark.parametrize("password", [None, ""])
async def test_register_user_missing_password_raises_required(password: str | None) -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email="user@example.com", password=password)

    # Act & Assert
    with pytest.raises(RegistrationValidationError) as exc_info:
        await service.register_user(payload)
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].field == "password"
    assert exc_info.value.errors[0].code == "REQUIRED"


@pytest.mark.parametrize(
    "password",
    [
        "Sh0rt!",  # too short
        "nouppercase1!",  # no uppercase
        "NOLOWERCASE1!",  # no lowercase
        "NoDigitHere!",  # no digit
        "NoSpecial123",  # no special character
    ],
)
async def test_register_user_weak_password_raises_policy_violation(password: str) -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email="user@example.com", password=password)

    # Act & Assert
    with pytest.raises(RegistrationValidationError) as exc_info:
        await service.register_user(payload)
    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].field == "password"
    assert exc_info.value.errors[0].code == "POLICY_VIOLATION"


async def test_register_user_batches_email_and_password_errors() -> None:
    # Arrange
    repository = FakeUserRepository()
    service = UserService(repository)
    payload = UserCreate(email="not-an-email", password="weak")

    # Act & Assert
    with pytest.raises(RegistrationValidationError) as exc_info:
        await service.register_user(payload)
    fields = {error.field for error in exc_info.value.errors}
    assert fields == {"email", "password"}


async def test_register_user_duplicate_email_raises_duplicate_email_error() -> None:
    # Arrange
    repository = FakeUserRepository(existing_emails={"user@example.com"})
    service = UserService(repository)
    payload = UserCreate(email="User@Example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(DuplicateEmailError):
        await service.register_user(payload)
