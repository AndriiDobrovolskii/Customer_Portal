import string
from typing import Protocol

from email_validator import EmailNotValidError, validate_email

from app.core.exceptions import DuplicateEmailError, FieldError, RegistrationValidationError
from app.core.security import hash_password
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserRead, UserStatus

_SPECIAL_CHARACTERS = set(string.punctuation)
_MIN_PASSWORD_LENGTH = 8


class UserRepositoryProtocol(Protocol):
    async def create(self, *, email: str, hashed_password: str, status: str) -> User | None: ...

    async def commit(self) -> None: ...


def _validate_email(email: str | None, errors: list[FieldError]) -> str | None:
    trimmed = (email or "").strip()
    if not trimmed:
        errors.append(FieldError(field="email", message="Email is required.", code="REQUIRED"))
        return None
    try:
        result = validate_email(trimmed, check_deliverability=False)
    except EmailNotValidError:
        errors.append(
            FieldError(
                field="email",
                message="Email address is not a valid RFC 5322 address.",
                code="INVALID_FORMAT",
            )
        )
        return None
    return result.normalized


def _validate_password(password: str | None, errors: list[FieldError]) -> str | None:
    if not password:
        errors.append(
            FieldError(field="password", message="Password is required.", code="REQUIRED")
        )
        return None

    missing: list[str] = []
    if len(password) < _MIN_PASSWORD_LENGTH:
        missing.append(f"at least {_MIN_PASSWORD_LENGTH} characters")
    if not any(char.isupper() for char in password):
        missing.append("an uppercase letter")
    if not any(char.islower() for char in password):
        missing.append("a lowercase letter")
    if not any(char.isdigit() for char in password):
        missing.append("a digit")
    if not any(char in _SPECIAL_CHARACTERS for char in password):
        missing.append("a special character")

    if missing:
        errors.append(
            FieldError(
                field="password",
                message=f"Password must contain {', '.join(missing)}.",
                code="POLICY_VIOLATION",
            )
        )
        return None
    return password


class UserService:
    def __init__(self, repository: UserRepositoryProtocol) -> None:
        self._repository = repository

    async def register_user(self, payload: UserCreate) -> UserRead:
        errors: list[FieldError] = []
        normalized_email = _validate_email(payload.email, errors)
        valid_password = _validate_password(payload.password, errors)

        if errors:
            raise RegistrationValidationError(errors=errors)

        assert normalized_email is not None
        assert valid_password is not None

        hashed_password = await hash_password(valid_password)

        user = await self._repository.create(
            email=normalized_email.lower(),
            hashed_password=hashed_password,
            status=UserStatus.PENDING_VERIFICATION.value,
        )
        if user is None:
            raise DuplicateEmailError()

        await self._repository.commit()

        return UserRead.model_validate(user)
