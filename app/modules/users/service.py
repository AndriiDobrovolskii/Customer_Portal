import logging
import string
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from email_validator import EmailNotValidError, validate_email
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.email import EmailSender
from app.core.exceptions import FieldError
from app.core.security import (
    InvalidTokenError,
    decode_access_token,
    encode_access_token,
    hash_password,
    verify_password,
)
from app.modules.users.exceptions import (
    DuplicateEmailError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    RegistrationValidationError,
)
from app.modules.users.models import User, UserSession
from app.modules.users.schemas import LoginRequest, LoginResponse, UserCreate, UserRead, UserStatus

logger = logging.getLogger(__name__)

_SPECIAL_CHARACTERS = set(string.punctuation)
_MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """The identity resolved from a valid access token. Never the ORM User."""

    user_id: uuid.UUID
    jti: uuid.UUID


class UserRepositoryProtocol(Protocol):
    async def create(self, *, email: str, hashed_password: str, status: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def create_session(
        self, *, user_id: uuid.UUID, jti: uuid.UUID, expires_at: datetime
    ) -> UserSession: ...

    async def get_session_by_jti(self, jti: uuid.UUID) -> UserSession | None: ...

    async def revoke_sessions_except(
        self, *, user_id: uuid.UUID, except_jti: uuid.UUID | None
    ) -> None: ...

    async def commit(self) -> None: ...


class VerificationTokenIssuerProtocol(Protocol):
    async def issue_pending_token(self, user_id: uuid.UUID) -> str: ...


class RevocationCacheReaderProtocol(Protocol):
    async def get_revoke_before(self, user_id: uuid.UUID) -> datetime | None: ...


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


def _validate_password(secret: SecretStr | None, errors: list[FieldError]) -> str | None:
    password = secret.get_secret_value() if secret is not None else ""
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
    def __init__(
        self,
        repository: UserRepositoryProtocol,
        issuer: VerificationTokenIssuerProtocol,
        email_sender: EmailSender,
        revocation_cache: RevocationCacheReaderProtocol,
    ) -> None:
        self._repository = repository
        self._issuer = issuer
        self._email_sender = email_sender
        self._revocation_cache = revocation_cache

    async def register_user(self, payload: UserCreate) -> UserRead:
        errors: list[FieldError] = []
        normalized_email = _validate_email(payload.email, errors)
        valid_password = _validate_password(payload.password, errors)

        if errors or normalized_email is None or valid_password is None:
            raise RegistrationValidationError(errors=errors)

        hashed_password = await hash_password(valid_password)

        user = await self._repository.create(
            email=normalized_email.lower(),
            hashed_password=hashed_password,
            status=UserStatus.PENDING_VERIFICATION.value,
        )
        if user is None:
            raise DuplicateEmailError()

        await self._repository.commit()

        # Best-effort: the user account is already committed and registration
        # must succeed regardless of whether the verification email goes out.
        # A failure here just means the customer falls back to /resend later.
        try:
            raw_token = await self._issuer.issue_pending_token(user.id)
            await self._email_sender.send_verification_email(to=user.email, raw_token=raw_token)
        except Exception:
            logger.exception("failed to issue verification token after registration")

        return UserRead.model_validate(user)

    async def authenticate_user(self, payload: LoginRequest) -> LoginResponse:
        user = await self._repository.get_by_email(payload.email)
        if user is None:
            raise InvalidCredentialsError

        # Checked before the verification gate below: a wrong-password guess
        # against an unverified account must not be distinguishable from one
        # against a verified account.
        if not await verify_password(payload.password.get_secret_value(), user.hashed_password):
            raise InvalidCredentialsError

        if not user.email_verified:
            raise EmailNotVerifiedError

        settings = get_settings()
        jti = uuid.uuid4()
        expires_at = datetime.now(UTC) + timedelta(seconds=settings.access_token_ttl_seconds)
        await self._repository.create_session(user_id=user.id, jti=jti, expires_at=expires_at)
        await self._repository.commit()
        return LoginResponse(access_token=encode_access_token(user_id=user.id, jti=jti))

    async def get_authenticated_user(self, token: str) -> AuthenticatedUser | None:
        try:
            claims = decode_access_token(token)
        except InvalidTokenError:
            return None

        session = await self._repository.get_session_by_jti(claims.jti)
        if session is None or session.revoked_at is not None:
            return None
        if session.user_id != claims.user_id:
            return None

        try:
            revoke_before = await self._revocation_cache.get_revoke_before(claims.user_id)
        except Exception:
            # Fail closed: revoke_before is a token denylist, and AGENTS.md §3
            # carves the denylist out of the general "degrade to the DB on
            # cache outage" rule — an unreachable cache must reject the
            # token, not silently accept it. Deliberately broad: any failure
            # reading the denylist must reject, regardless of its cause.
            logger.exception("revoke_before check failed; rejecting token")
            return None
        if revoke_before is not None and session.issued_at <= revoke_before:
            return None

        return AuthenticatedUser(user_id=claims.user_id, jti=claims.jti)

    async def revoke_other_sessions(
        self, *, user_id: uuid.UUID, except_jti: uuid.UUID | None
    ) -> None:
        """Cross-module collaborator for the profile module's confirmed-email-
        change flow (UP-AC11) — injected as a Protocol-typed service→service
        dependency, per AGENTS.md's cross-module discipline. Owns its own
        commit, matching the existing multi-commit-per-request precedent in
        register_user's token-issuance composition.
        """
        await self._repository.revoke_sessions_except(user_id=user_id, except_jti=except_jti)
        await self._repository.commit()
