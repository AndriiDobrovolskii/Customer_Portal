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
    generate_refresh_token,
    hash_password,
    verify_password,
    verify_password_dummy,
)
from app.modules.users.exceptions import (
    AccountDeactivatedError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    RegistrationValidationError,
    TooManyAttemptsError,
)
from app.modules.users.models import RefreshToken, User, UserSession
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

    async def update_last_login_at(self, *, user_id: uuid.UUID) -> None: ...

    async def create_auth_audit_log_entry(
        self,
        *,
        event: str,
        reason: str | None,
        actor_id: uuid.UUID | None,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> None: ...

    async def create_refresh_token(
        self,
        *,
        token_hash: str,
        family_id: uuid.UUID,
        user_id: uuid.UUID,
        expires_at: datetime,
    ) -> RefreshToken: ...

    async def commit(self) -> None: ...


class VerificationTokenIssuerProtocol(Protocol):
    async def issue_pending_token(self, user_id: uuid.UUID) -> str: ...


class RevocationCacheReaderProtocol(Protocol):
    async def get_revoke_before(self, user_id: uuid.UUID) -> datetime | None: ...


class LoginThrottleCacheProtocol(Protocol):
    async def record_account_failure(self, user_id: uuid.UUID, *, window_seconds: int) -> int: ...

    async def record_ip_failure(self, ip: str, *, window_seconds: int) -> int: ...

    async def get_account_failure_count(self, user_id: uuid.UUID) -> int: ...

    async def get_ip_failure_count(self, ip: str) -> int: ...

    async def get_account_retry_after_seconds(self, user_id: uuid.UUID) -> int: ...

    async def get_ip_retry_after_seconds(self, ip: str) -> int: ...

    async def reset_account_failures(self, user_id: uuid.UUID) -> None: ...


class AccountServiceProtocol(Protocol):
    """Cross-module collaborator (resolved OD-10): reactivation lives in the
    `account` module, called here via its service, never its router/
    repository, mirroring `revoke_other_sessions`'s existing cross-module
    pattern in the other direction (`profile` -> `users`).
    """

    async def reactivate_account(self, user_id: uuid.UUID) -> bool: ...


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
        throttle_cache: LoginThrottleCacheProtocol,
        account_service: AccountServiceProtocol,
    ) -> None:
        self._repository = repository
        self._issuer = issuer
        self._email_sender = email_sender
        self._revocation_cache = revocation_cache
        self._throttle_cache = throttle_cache
        self._account_service = account_service

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

    async def authenticate_user(
        self, payload: LoginRequest, *, ip: str, user_agent: str | None, request_id: str
    ) -> tuple[LoginResponse, str]:
        """Returns (response, raw_refresh_token) — the raw refresh token is
        never part of the LoginResponse body (FR-1: it's a Set-Cookie value,
        not a JSON field), so the router receives it separately to build the
        cookie, mirroring profile/service.py's own tuple-return pattern for
        a value the router needs beyond the response schema.
        """
        settings = get_settings()

        # Checked first, before any DB lookup: an IP already over its limit
        # is blocked regardless of which account it's trying (FR-5).
        ip_failure_count = await self._throttle_cache.get_ip_failure_count(ip)
        if ip_failure_count >= settings.login_failure_threshold_ip:
            retry_after = await self._throttle_cache.get_ip_retry_after_seconds(ip)
            raise TooManyAttemptsError(retry_after_seconds=retry_after)

        user = await self._repository.get_by_email(payload.email)

        if user is not None:
            account_failure_count = await self._throttle_cache.get_account_failure_count(user.id)
            if account_failure_count >= settings.login_failure_threshold_account:
                retry_after = await self._throttle_cache.get_account_retry_after_seconds(user.id)
                raise TooManyAttemptsError(retry_after_seconds=retry_after)

        if user is None:
            # Dummy Argon2id verification so response timing doesn't reveal
            # account existence (FR-3, NFR-002).
            await verify_password_dummy()
            await self._repository.create_auth_audit_log_entry(
                event="login_failed",
                reason="unknown_email",
                actor_id=None,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self._repository.commit()
            # Cache write after the commit (AGENTS.md §3).
            await self._throttle_cache.record_ip_failure(
                ip, window_seconds=settings.login_throttle_window_seconds
            )
            raise InvalidCredentialsError

        # Checked before the verification gate below: a wrong-password guess
        # against an unverified or deactivated account must not be
        # distinguishable from one against a normal account (FR-4).
        if not await verify_password(payload.password.get_secret_value(), user.hashed_password):
            await self._repository.create_auth_audit_log_entry(
                event="login_failed",
                reason="bad_password",
                actor_id=user.id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self._repository.commit()
            await self._throttle_cache.record_account_failure(
                user.id, window_seconds=settings.login_throttle_window_seconds
            )
            await self._throttle_cache.record_ip_failure(
                ip, window_seconds=settings.login_throttle_window_seconds
            )
            raise InvalidCredentialsError

        # Deactivation gate tests the actual persisted value ("deactivated"),
        # never "!= active" — nothing in this codebase ever writes "active"
        # to users.status, so that comparison would reject every real user.
        if user.status == UserStatus.DEACTIVATED.value:
            reactivated = await self._account_service.reactivate_account(user.id)
            if not reactivated:
                await self._repository.create_auth_audit_log_entry(
                    event="login_failed",
                    reason="account_deactivated",
                    actor_id=user.id,
                    ip=ip,
                    user_agent=user_agent,
                    request_id=request_id,
                )
                await self._repository.commit()
                raise AccountDeactivatedError
            # else: reactivated within its grace period (resolved OD-10,
            # DA-AC8) — fall through to the ordinary success path below.
        elif not user.email_verified:
            await self._repository.create_auth_audit_log_entry(
                event="login_failed",
                reason="email_not_verified",
                actor_id=user.id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            await self._repository.commit()
            raise EmailNotVerifiedError

        jti = uuid.uuid4()
        session_expires_at = datetime.now(UTC) + timedelta(
            seconds=settings.access_token_ttl_seconds
        )
        await self._repository.create_session(
            user_id=user.id, jti=jti, expires_at=session_expires_at
        )

        raw_refresh_token, token_hash = generate_refresh_token()
        refresh_expires_at = datetime.now(UTC) + timedelta(
            seconds=settings.refresh_token_ttl_seconds
        )
        await self._repository.create_refresh_token(
            token_hash=token_hash,
            family_id=uuid.uuid4(),
            user_id=user.id,
            expires_at=refresh_expires_at,
        )

        await self._repository.update_last_login_at(user_id=user.id)
        await self._repository.create_auth_audit_log_entry(
            event="login_succeeded",
            reason=None,
            actor_id=user.id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self._repository.commit()

        # Resolved OD-5: only the account counter resets on success; the
        # per-IP counter is deliberately left alone.
        await self._throttle_cache.reset_account_failures(user.id)

        response = LoginResponse(
            access_token=encode_access_token(user_id=user.id, jti=jti),
            expires_in=settings.access_token_ttl_seconds,
        )
        return response, raw_refresh_token

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
