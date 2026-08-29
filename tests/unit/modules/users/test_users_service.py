import uuid
from datetime import UTC, datetime

import pytest

from app.core.security import decode_access_token, hash_password
from app.modules.users.exceptions import (
    DuplicateEmailError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    RegistrationValidationError,
)
from app.modules.users.models import User, UserSession
from app.modules.users.schemas import LoginRequest, UserCreate, UserStatus
from app.modules.users.service import UserService

pytestmark = pytest.mark.unit


class FakeUserRepository:
    def __init__(self, *, existing_emails: set[str] | None = None) -> None:
        self.existing_emails = existing_emails or set()
        self.created_with: dict[str, str] | None = None
        self.commit_called = False
        self.users_by_email: dict[str, User] = {}
        self.sessions_by_jti: dict[uuid.UUID, UserSession] = {}

    async def create(self, *, email: str, hashed_password: str, status: str) -> User | None:
        if email in self.existing_emails:
            return None
        self.created_with = {"email": email, "hashed_password": hashed_password, "status": status}
        user = User(email=email, hashed_password=hashed_password, status=status)
        user.id = uuid.uuid4()
        user.created_at = datetime.now(UTC)
        return user

    async def get_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email.lower())

    async def create_session(
        self, *, user_id: uuid.UUID, jti: uuid.UUID, expires_at: datetime
    ) -> UserSession:
        session = UserSession(jti=jti, user_id=user_id, expires_at=expires_at)
        self.sessions_by_jti[jti] = session
        return session

    async def get_session_by_jti(self, jti: uuid.UUID) -> UserSession | None:
        return self.sessions_by_jti.get(jti)

    async def revoke_sessions_except(
        self, *, user_id: uuid.UUID, except_jti: uuid.UUID | None
    ) -> None:
        for jti, session in self.sessions_by_jti.items():
            if session.user_id == user_id and jti != except_jti:
                session.revoked_at = datetime.now(UTC)

    async def commit(self) -> None:
        self.commit_called = True


class FakeVerificationTokenIssuer:
    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.issued_for: list[uuid.UUID] = []

    async def issue_pending_token(self, user_id: uuid.UUID) -> str:
        if self.raises:
            raise RuntimeError("token issuance failed")
        self.issued_for.append(user_id)
        return "raw-verification-token"


class FakeEmailSender:
    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.sent: list[dict[str, str]] = []

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.sent.append({"to": to, "raw_token": raw_token})

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None:
        pass

    async def send_email_change_notice(self, *, to: str) -> None:
        pass


def _make_service(
    repository: FakeUserRepository,
    issuer: FakeVerificationTokenIssuer | None = None,
    email_sender: FakeEmailSender | None = None,
) -> tuple[UserService, FakeVerificationTokenIssuer, FakeEmailSender]:
    issuer = issuer or FakeVerificationTokenIssuer()
    email_sender = email_sender or FakeEmailSender()
    return UserService(repository, issuer, email_sender), issuer, email_sender


async def test_register_user_valid_input_returns_pending_verification() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)
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
    service, _, _ = _make_service(repository)
    payload = UserCreate(email="user@example.com", password="Str0ng!Pass")

    # Act
    await service.register_user(payload)

    # Assert
    assert repository.created_with is not None
    assert repository.created_with["hashed_password"] != "Str0ng!Pass"


async def test_register_user_trims_and_lowercases_email() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)
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
    service, _, _ = _make_service(repository)
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
    service, _, _ = _make_service(repository)
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
    service, _, _ = _make_service(repository)
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
    service, _, _ = _make_service(repository)
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
    service, _, _ = _make_service(repository)
    payload = UserCreate(email="not-an-email", password="weak")

    # Act & Assert
    with pytest.raises(RegistrationValidationError) as exc_info:
        await service.register_user(payload)
    fields = {error.field for error in exc_info.value.errors}
    assert fields == {"email", "password"}


async def test_register_user_duplicate_email_raises_duplicate_email_error() -> None:
    # Arrange
    repository = FakeUserRepository(existing_emails={"user@example.com"})
    service, _, _ = _make_service(repository)
    payload = UserCreate(email="User@Example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(DuplicateEmailError):
        await service.register_user(payload)


async def test_register_user_issues_verification_token_and_sends_email() -> None:
    # Arrange
    repository = FakeUserRepository()
    issuer = FakeVerificationTokenIssuer()
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, issuer, email_sender)
    payload = UserCreate(email="new.user@example.com", password="Str0ng!Pass")

    # Act
    result = await service.register_user(payload)

    # Assert
    assert issuer.issued_for == [result.id]
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "new.user@example.com"
    assert email_sender.sent[0]["raw_token"] == "raw-verification-token"


async def test_register_user_swallows_token_issuance_failure() -> None:
    # Arrange
    repository = FakeUserRepository()
    issuer = FakeVerificationTokenIssuer(raises=True)
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, issuer, email_sender)
    payload = UserCreate(email="resilient@example.com", password="Str0ng!Pass")

    # Act
    result = await service.register_user(payload)

    # Assert: registration still succeeds even though issuance failed
    assert result.email == "resilient@example.com"
    assert repository.commit_called is True
    assert email_sender.sent == []


async def test_register_user_swallows_email_dispatch_failure() -> None:
    # Arrange
    repository = FakeUserRepository()
    issuer = FakeVerificationTokenIssuer()
    email_sender = FakeEmailSender(raises=True)
    service, _, _ = _make_service(repository, issuer, email_sender)
    payload = UserCreate(email="resilient2@example.com", password="Str0ng!Pass")

    # Act
    result = await service.register_user(payload)

    # Assert: registration still succeeds even though email dispatch failed
    assert result.email == "resilient2@example.com"
    assert repository.commit_called is True


async def _seed_user(
    repository: FakeUserRepository, *, email: str, password: str, email_verified: bool
) -> User:
    user = User(
        email=email, hashed_password=await hash_password(password), status="PENDING_VERIFICATION"
    )
    user.id = uuid.uuid4()
    user.email_verified = email_verified
    repository.users_by_email[email.lower()] = user
    return user


# --- VE-AC5: unverified account cannot log in ----------------------------------


async def test_authenticate_user_correct_password_unverified_raises_email_not_verified() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository, email="unverified@example.com", password="Str0ng!Pass", email_verified=False
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="unverified@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(EmailNotVerifiedError):
        await service.authenticate_user(payload)


# --- VE-AC6: verified account logs in normally ---------------------------------


async def test_authenticate_user_correct_password_verified_returns_access_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository, email="verified@example.com", password="Str0ng!Pass", email_verified=True
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="verified@example.com", password="Str0ng!Pass")

    # Act
    result = await service.authenticate_user(payload)

    # Assert
    assert result.token_type == "bearer"
    assert len(result.access_token) > 0
    claims = decode_access_token(result.access_token)
    assert claims.user_id == user.id
    assert repository.commit_called is True


async def test_authenticate_user_persists_a_session_row() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository, email="session@example.com", password="Str0ng!Pass", email_verified=True
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="session@example.com", password="Str0ng!Pass")

    # Act
    result = await service.authenticate_user(payload)

    # Assert
    claims = decode_access_token(result.access_token)
    assert claims.jti in repository.sessions_by_jti
    assert repository.sessions_by_jti[claims.jti].revoked_at is None


async def test_authenticate_user_wrong_password_raises_invalid_credentials() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository, email="verified@example.com", password="Str0ng!Pass", email_verified=True
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="verified@example.com", password="WrongPassword1!")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await service.authenticate_user(payload)


async def test_authenticate_user_unknown_email_raises_invalid_credentials() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="nobody@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await service.authenticate_user(payload)
