import hashlib
import logging
import secrets
import string
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from email_validator import EmailNotValidError, validate_email
from pydantic import SecretStr

from app.core.breached_passwords import is_breached_password
from app.core.config import get_settings
from app.core.crypto import decrypt_mfa_secret, encrypt_mfa_secret
from app.core.device import resolve_device_label
from app.core.email import EmailSender
from app.core.exceptions import FieldError
from app.core.geoip import GeoLocation, resolve_location
from app.core.security import (
    InvalidTokenError,
    build_otpauth_uri,
    decode_access_token,
    encode_access_token,
    encode_totp_secret,
    generate_mfa_token,
    generate_refresh_token,
    generate_totp_secret,
    hash_mfa_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_password_dummy,
    verify_totp_code,
)
from app.modules.users.exceptions import (
    AccountDeactivatedError,
    CurrentSessionError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    MfaEnrollmentRequiredError,
    MfaInvalidCodeError,
    MfaRequiredForRoleError,
    PasswordPolicyError,
    PasswordResetTokenExpiredError,
    PasswordResetTokenInvalidError,
    RegistrationValidationError,
    SessionNotFoundError,
    TokenInvalidError,
    TokenStaleError,
    TooManyAttemptsError,
)
from app.modules.users.models import (
    MfaRecoveryCode,
    PasswordResetToken,
    RefreshToken,
    User,
    UserSession,
)
from app.modules.users.schemas import (
    LoginRequest,
    LoginResponse,
    MfaActivateRequest,
    MfaActivateResponse,
    MfaDisableRequest,
    MfaEnrollRequest,
    MfaEnrollResponse,
    MfaRequiredResponse,
    MfaVerifyRequest,
    MfaVerifyResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    PasswordResetRequestResponse,
    RefreshResponse,
    SessionEntry,
    SessionListResponse,
    SessionLocation,
    UserCreate,
    UserRead,
    UserStatus,
)

_REFRESH_IDLE_TIMEOUT = timedelta(days=14)
_REFRESH_CONCURRENT_GRACE_WINDOW = timedelta(seconds=10)
_REFRESH_RATE_LIMIT_MAX_REQUESTS = 60
_REFRESH_RATE_LIMIT_WINDOW_SECONDS = 3600
_PASSWORD_RESET_TOKEN_BYTES = 32
_PASSWORD_RESET_HOURLY_WINDOW_SECONDS = 3600
_MIN_RESET_PASSWORD_LENGTH = 12
# US-2.5 FR-6/FR-8: the fixed role catalogue names (US-3.2) MFA is
# mandatory for. Duplicated here rather than imported from roles.models
# (a models-layer import a service must never make cross-module, per
# AGENTS.md §3) - these three names are also the spec's own literal text.
_PRIVILEGED_ROLE_NAMES = {"admin", "auditor", "support_agent"}
_RECOVERY_CODE_COUNT = 10
_RECOVERY_CODE_BYTES = 5

logger = logging.getLogger(__name__)

_SPECIAL_CHARACTERS = set(string.punctuation)
_MIN_PASSWORD_LENGTH = 8


def _to_session_location(geo: GeoLocation | None) -> SessionLocation | None:
    if geo is None:
        return None
    return SessionLocation(city=geo.city, country=geo.country)


def _hash_password_reset_token(raw_token: str) -> str:
    """Module-local, same pattern as `email_verification.service._hash_token`
    — password_reset_tokens is explicitly modeled on email_verification_tokens
    (source story's Data Model Notes), so it gets its own local hash helper
    the same way, rather than reusing `hash_refresh_token` (a different
    token type/table, US-2.3's own naming).
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """The identity resolved from a valid access token. Never the ORM User."""

    user_id: uuid.UUID
    jti: uuid.UUID
    scopes: list[str]
    mfa_enrollment_required: bool = False


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

    async def revoke_session(self, *, jti: uuid.UUID) -> None: ...

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def revoke_refresh_token_family(self, *, family_id: uuid.UUID) -> None: ...

    async def consume_refresh_token(self, *, token_hash: str) -> RefreshToken | None: ...

    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def update_last_login_at(self, *, user_id: uuid.UUID) -> None: ...

    async def create_auth_audit_log_entry(
        self,
        *,
        event: str,
        reason: str | None,
        scope: str | None,
        actor_id: uuid.UUID | None,
        ip: str,
        user_agent: str | None,
        request_id: str,
        severity: str | None = None,
        target_family: uuid.UUID | None = None,
    ) -> None: ...

    async def create_refresh_token(
        self,
        *,
        token_hash: str,
        family_id: uuid.UUID,
        user_id: uuid.UUID,
        expires_at: datetime,
        ip: str | None = None,
        user_agent: str | None = None,
        last_used_at: datetime | None = None,
    ) -> RefreshToken: ...

    async def update_password_hash(self, *, user_id: uuid.UUID, hashed_password: str) -> None: ...

    async def invalidate_password_reset_tokens_for_user(self, *, user_id: uuid.UUID) -> None: ...

    async def create_password_reset_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken: ...

    async def get_password_reset_token_by_hash(
        self, token_hash: str
    ) -> PasswordResetToken | None: ...

    async def consume_password_reset_token(
        self, *, token_hash: str
    ) -> PasswordResetToken | None: ...

    async def update_mfa_pending_secret(
        self, *, user_id: uuid.UUID, secret_encrypted: bytes
    ) -> None: ...

    async def activate_mfa(self, *, user_id: uuid.UUID) -> None: ...

    async def set_mfa_reenrollment_required(self, *, user_id: uuid.UUID) -> None: ...

    async def disable_mfa(self, *, user_id: uuid.UUID) -> None: ...

    async def create_recovery_codes(
        self, *, user_id: uuid.UUID, code_hashes: list[str]
    ) -> None: ...

    async def list_unconsumed_recovery_codes(
        self, *, user_id: uuid.UUID
    ) -> list[MfaRecoveryCode]: ...

    async def consume_recovery_code(self, *, code_id: uuid.UUID) -> MfaRecoveryCode | None: ...

    async def delete_recovery_codes_for_user(self, *, user_id: uuid.UUID) -> None: ...

    async def get_any_refresh_token_for_family(
        self, *, family_id: uuid.UUID, user_id: uuid.UUID
    ) -> RefreshToken | None: ...

    async def lock_live_refresh_tokens_for_user(self, *, user_id: uuid.UUID) -> None: ...

    async def list_live_families_for_user(self, *, user_id: uuid.UUID) -> list[RefreshToken]: ...

    async def get_family_created_at_map_for_user(
        self, *, user_id: uuid.UUID
    ) -> dict[uuid.UUID, datetime]: ...

    async def commit(self) -> None: ...


class VerificationTokenIssuerProtocol(Protocol):
    async def issue_pending_token(self, user_id: uuid.UUID) -> str: ...


class RevocationCacheProtocol(Protocol):
    async def get_revoke_before(self, user_id: uuid.UUID) -> datetime | None: ...

    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None: ...


class PermissionEpochCacheProtocol(Protocol):
    async def get_perm_epoch(self, user_id: uuid.UUID) -> datetime | None: ...

    async def set_perm_epoch(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None: ...


class RoleServiceProtocol(Protocol):
    """Cross-module collaborator (US-3.2/spec US-3.2): resolves the
    permission scopes a JWT `scopes` claim carries at token issuance,
    called here via `roles.service`, never its router/repository —
    mirrors `AccountServiceProtocol`'s existing cross-module pattern.
    """

    async def resolve_scopes_for_user(self, user_id: uuid.UUID) -> list[str]: ...

    async def get_role_grants_for_user(
        self, user_id: uuid.UUID
    ) -> Sequence[tuple[str, datetime]]: ...


class LoginThrottleCacheProtocol(Protocol):
    async def record_account_failure(self, user_id: uuid.UUID, *, window_seconds: int) -> int: ...

    async def record_ip_failure(self, ip: str, *, window_seconds: int) -> int: ...

    async def get_account_failure_count(self, user_id: uuid.UUID) -> int: ...

    async def get_ip_failure_count(self, ip: str) -> int: ...

    async def get_account_retry_after_seconds(self, user_id: uuid.UUID) -> int: ...

    async def get_ip_retry_after_seconds(self, ip: str) -> int: ...

    async def reset_account_failures(self, user_id: uuid.UUID) -> None: ...


class RefreshRateLimitCacheProtocol(Protocol):
    async def record_request(self, family_id: uuid.UUID, *, window_seconds: int) -> int: ...

    async def get_retry_after_seconds(self, family_id: uuid.UUID) -> int: ...


class PasswordResetRateLimitCacheProtocol(Protocol):
    async def record_cooldown_attempt(self, email_hash: str, *, window_seconds: int) -> int: ...

    async def get_cooldown_retry_after_seconds(self, email_hash: str) -> int: ...

    async def record_account_attempt(self, email_hash: str, *, window_seconds: int) -> int: ...

    async def get_account_retry_after_seconds(self, email_hash: str) -> int: ...

    async def record_ip_attempt(self, ip: str, *, window_seconds: int) -> int: ...

    async def get_ip_retry_after_seconds(self, ip: str) -> int: ...


class MfaTokenCacheProtocol(Protocol):
    async def issue(self, token_hash: str, *, user_id: uuid.UUID, ttl_seconds: int) -> None: ...

    async def get_user_id(self, token_hash: str) -> uuid.UUID | None: ...

    async def consume(self, token_hash: str) -> uuid.UUID | None: ...

    async def record_failed_attempt(self, token_hash: str, *, window_seconds: int) -> int: ...

    async def invalidate(self, token_hash: str) -> None: ...


class MfaReplayCacheProtocol(Protocol):
    async def mark_step_used(self, user_id: uuid.UUID, *, step: int, ttl_seconds: int) -> bool: ...


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
        revocation_cache: RevocationCacheProtocol,
        throttle_cache: LoginThrottleCacheProtocol,
        account_service: AccountServiceProtocol,
        refresh_rate_limit_cache: RefreshRateLimitCacheProtocol,
        password_reset_rate_limit_cache: PasswordResetRateLimitCacheProtocol,
        permission_epoch_cache: PermissionEpochCacheProtocol,
        role_service: RoleServiceProtocol,
        mfa_token_cache: MfaTokenCacheProtocol,
        mfa_replay_cache: MfaReplayCacheProtocol,
    ) -> None:
        self._repository = repository
        self._issuer = issuer
        self._email_sender = email_sender
        self._revocation_cache = revocation_cache
        self._throttle_cache = throttle_cache
        self._account_service = account_service
        self._refresh_rate_limit_cache = refresh_rate_limit_cache
        self._password_reset_rate_limit_cache = password_reset_rate_limit_cache
        self._permission_epoch_cache = permission_epoch_cache
        self._role_service = role_service
        self._mfa_token_cache = mfa_token_cache
        self._mfa_replay_cache = mfa_replay_cache

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

    async def _resolve_enrollment_scoping(self, user: User) -> tuple[bool, datetime | None]:
        """US-2.5 FR-6/FR-7: whether the next-issued access token should be
        enrolment-scoped, and (only for the FR-6 grace-period case) the
        deadline to surface in the login response (OD-4).

        Two independent triggers, checked in this order:
        1. `mfa_reenrollment_required` (FR-7/OD-5, recovery-code use) -
           scopes immediately, no grace period, regardless of `mfa_enabled`
           (which OD-5 deliberately leaves `true`).
        2. A privileged role (`admin`/`auditor`/`support_agent`) held while
           `mfa_enabled` is still `false` (FR-6) - scoped once the 14-day
           grace period (from the earliest such role's `granted_at`) has
           passed; within it, returns the deadline instead.
        """
        if user.mfa_reenrollment_required:
            return True, None

        if user.mfa_enabled:
            return False, None

        grants = await self._role_service.get_role_grants_for_user(user.id)
        privileged_grants = [g for g in grants if g[0] in _PRIVILEGED_ROLE_NAMES]
        if not privileged_grants:
            return False, None

        settings = get_settings()
        grace_period = timedelta(days=settings.mfa_grace_period_days)
        deadlines = [granted_at + grace_period for _, granted_at in privileged_grants]
        earliest_deadline = min(deadlines)
        if datetime.now(UTC) >= earliest_deadline:
            return True, None
        return False, earliest_deadline

    async def _evict_oldest_family_if_at_cap(
        self, user_id: uuid.UUID, *, ip: str, user_agent: str | None, request_id: str
    ) -> None:
        """US-2.6 FR-7 (spec-review resolution): called from both family-
        creation sites (`authenticate_user`'s ordinary login, and
        `_complete_mfa_login`'s post-MFA login completion - the same
        duplication precedent this file already applies to session/
        refresh-token minting). Locks the acting user's own live rows
        before counting, so two logins racing concurrently for the SAME
        user serialize on this lock rather than both observing a stale
        count - scoped to `user_id` only, never a table-wide lock. Must be
        called, and its effects committed, in the same transaction as the
        new family's own row for the lock to be meaningful.
        """
        settings = get_settings()
        await self._repository.lock_live_refresh_tokens_for_user(user_id=user_id)
        family_created_at = await self._repository.get_family_created_at_map_for_user(
            user_id=user_id
        )
        if len(family_created_at) >= settings.max_live_sessions_per_user:
            oldest_family_id = min(family_created_at, key=lambda fid: family_created_at[fid])
            await self._repository.revoke_refresh_token_family(family_id=oldest_family_id)
            await self._repository.create_auth_audit_log_entry(
                event="session_evicted",
                reason=None,
                scope=None,
                actor_id=user_id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
                severity=None,
                target_family=oldest_family_id,
            )

    async def _encode_access_token_for_user(
        self, user: User, *, jti: uuid.UUID
    ) -> tuple[str, datetime | None]:
        scopes = await self._role_service.resolve_scopes_for_user(user.id)
        scoped, deadline = await self._resolve_enrollment_scoping(user)
        access_token = encode_access_token(
            user_id=user.id, jti=jti, scopes=scopes, mfa_enrollment_required=scoped
        )
        return access_token, deadline

    async def authenticate_user(
        self, payload: LoginRequest, *, ip: str, user_agent: str | None, request_id: str
    ) -> tuple[LoginResponse | MfaRequiredResponse, str | None]:
        """Returns (response, raw_refresh_token) — the raw refresh token is
        never part of the LoginResponse body (FR-1: it's a Set-Cookie value,
        not a JSON field), so the router receives it separately to build the
        cookie, mirroring profile/service.py's own tuple-return pattern for
        a value the router needs beyond the response schema. When
        `mfa_enabled` is true (US-2.5 MF-AC3), returns an MfaRequiredResponse
        and `None` instead — no session/refresh token is issued at this
        point, so there is nothing for the router to set a cookie with.
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
                scope=None,
                actor_id=None,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
                severity=None,
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
                scope=None,
                actor_id=user.id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
                severity=None,
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
                    scope=None,
                    actor_id=user.id,
                    ip=ip,
                    user_agent=user_agent,
                    request_id=request_id,
                    severity=None,
                )
                await self._repository.commit()
                raise AccountDeactivatedError
            # else: reactivated within its grace period (resolved OD-10,
            # DA-AC8) — fall through to the ordinary success path below.
        elif not user.email_verified:
            await self._repository.create_auth_audit_log_entry(
                event="login_failed",
                reason="email_not_verified",
                scope=None,
                actor_id=user.id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
                severity=None,
            )
            await self._repository.commit()
            raise EmailNotVerifiedError

        if user.mfa_enabled:
            # MF-AC3: no access/refresh token issued at this point. The
            # mfa_token is single-use (Valkey GETDEL on consumption) and
            # scoped only to MFA verification.
            raw_mfa_token, token_hash = generate_mfa_token()
            await self._mfa_token_cache.issue(
                token_hash, user_id=user.id, ttl_seconds=settings.mfa_token_ttl_seconds
            )
            return MfaRequiredResponse(mfa_token=raw_mfa_token), None

        jti = uuid.uuid4()
        session_expires_at = datetime.now(UTC) + timedelta(
            seconds=settings.access_token_ttl_seconds
        )
        await self._repository.create_session(
            user_id=user.id, jti=jti, expires_at=session_expires_at
        )

        await self._evict_oldest_family_if_at_cap(
            user.id, ip=ip, user_agent=user_agent, request_id=request_id
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
            ip=ip,
            user_agent=user_agent,
        )

        await self._repository.update_last_login_at(user_id=user.id)
        await self._repository.create_auth_audit_log_entry(
            event="login_succeeded",
            reason=None,
            scope=None,
            actor_id=user.id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

        # Resolved OD-5: only the account counter resets on success; the
        # per-IP counter is deliberately left alone.
        await self._throttle_cache.reset_account_failures(user.id)

        access_token, deadline = await self._encode_access_token_for_user(user, jti=jti)
        response = LoginResponse(
            access_token=access_token,
            expires_in=settings.access_token_ttl_seconds,
            mfa_enrollment_deadline=deadline,
        )
        return response, raw_refresh_token

    async def get_authenticated_user(
        self,
        token: str,
        *,
        allow_revoked: bool = False,
        allow_enrollment_scoped: bool = False,
    ) -> AuthenticatedUser | None:
        """`allow_revoked` (resolved OD-2, US-2.2) lets `POST /v1/auth/logout`
        alone resolve a caller whose session is already revoked, so a repeat
        logout call is idempotent (LO-AC4) rather than 401ing (LO-AC5).
        Every other caller — including every other route — leaves this at
        its default `False` and gets today's strict behavior unchanged. A
        jti with no session row at all is never resolved, regardless of this
        flag: "revoked" and "never existed" are different failure modes.

        `allow_enrollment_scoped` (US-2.5 FR-6/FR-7) is the single
        default-deny choke point for the enrolment-scoped-token mechanism:
        every route rejects such a token with `403 mfa-enrollment-required`
        by default, and only `POST /v1/auth/mfa/enroll`/`activate` pass
        `True` (via `get_current_user_allow_enrollment_scoped`, mirroring
        `allow_revoked`'s exact same narrow-opt-in shape) — see
        docs/plans/US-2.5-implementation-plan.md Architectural Change #2.
        """
        try:
            claims = decode_access_token(token)
        except InvalidTokenError:
            return None

        session = await self._repository.get_session_by_jti(claims.jti)
        if session is None:
            return None
        if session.revoked_at is not None and not allow_revoked:
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

        try:
            perm_epoch = await self._permission_epoch_cache.get_perm_epoch(claims.user_id)
        except Exception:
            # Same fail-closed rationale as the revoke_before check above.
            logger.exception("perm_epoch check failed; rejecting token")
            return None
        if perm_epoch is not None and session.issued_at <= perm_epoch:
            # Deliberately raised, not returned as None (MR-AC2, US-3.2):
            # every other failure in this method is intentionally
            # indistinguishable (a generic 401), but a stale-permission
            # token needs its own `token-stale` type slug so the client
            # knows to call /auth/refresh rather than re-authenticate.
            raise TokenStaleError

        if claims.mfa_enrollment_required and not allow_enrollment_scoped:
            raise MfaEnrollmentRequiredError

        return AuthenticatedUser(
            user_id=claims.user_id,
            jti=claims.jti,
            scopes=claims.scopes,
            mfa_enrollment_required=claims.mfa_enrollment_required,
        )

    async def logout(
        self,
        *,
        jti: uuid.UUID,
        user_id: uuid.UUID,
        refresh_token: str | None,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> None:
        """FR-1/FR-4 (LO-AC1, LO-AC4): revokes the caller's own session by
        jti (resolved OD-1 — `user_sessions.revoked_at`, not a Valkey
        denylist), and — if a refresh cookie was presented — revokes its
        whole rotation family (resolved OD-3). Idempotent by construction:
        re-revoking an already-revoked session/family is a harmless
        overwrite, and the caller reaching this method at all already
        required `get_authenticated_user(allow_revoked=True)` to resolve
        the (possibly already-revoked) jti — see LO-AC4's leniency there.
        """
        await self._repository.revoke_session(jti=jti)

        if refresh_token is not None:
            token_hash = hash_refresh_token(refresh_token)
            existing = await self._repository.get_refresh_token_by_hash(token_hash)
            if existing is not None and existing.user_id == user_id:
                # Lookup-miss (spec-review finding, resolved 2026-08-31): a
                # stale/tampered/deleted cookie value silently skips this
                # step — every other effect (jti revocation, audit entry)
                # still occurs identically, so no response-level signal
                # distinguishes a matched from an unmatched cookie. A
                # cookie matching a *different* user's token (advisor
                # finding, 2026-09-01: IDOR — a stolen refresh token must
                # not let its holder revoke the victim's session family)
                # is treated identically to a lookup-miss for the same
                # anti-enumeration reason: silent skip, still 204.
                await self._repository.revoke_refresh_token_family(family_id=existing.family_id)

        await self._repository.create_auth_audit_log_entry(
            event="logout",
            reason=None,
            scope="session",
            actor_id=user_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

    async def logout_all(
        self, *, user_id: uuid.UUID, ip: str, user_agent: str | None, request_id: str
    ) -> None:
        """FR-2 (LO-AC2): reuses the existing `revoke_before` mechanism
        (US-1.4/US-2.1) — every access and refresh token issued before this
        moment is rejected on its next use via the same shared check
        `get_authenticated_user` already performs.
        """
        settings = get_settings()
        await self._revocation_cache.set_revoke_before(
            user_id, ttl_seconds=settings.refresh_token_ttl_seconds
        )
        await self._repository.create_auth_audit_log_entry(
            event="logout",
            reason=None,
            scope="all_sessions",
            actor_id=user_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

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

    async def _resolve_current_family_id(
        self, *, user_id: uuid.UUID, refresh_cookie: str | None
    ) -> uuid.UUID | None:
        """US-2.6 spec-review resolution: the caller's "current" family is
        identified by hashing the optional `refresh_token` cookie and
        matching it to a live token - the same lookup `logout` already
        performs (US-2.2). Returns `None` (never raises) when the cookie
        is absent, or matches no token, or matches a *different* user's
        token (same IDOR-safe treatment `logout` applies) - callers then
        treat "no current family known" as the safe default rather than
        erroring.
        """
        if refresh_cookie is None:
            return None
        token_hash = hash_refresh_token(refresh_cookie)
        existing = await self._repository.get_refresh_token_by_hash(token_hash)
        if existing is None or existing.user_id != user_id:
            return None
        return existing.family_id

    async def list_sessions(
        self, *, user_id: uuid.UUID, refresh_cookie: str | None
    ) -> SessionListResponse:
        """FR-1: one entry per live refresh-token family."""
        current_family_id = await self._resolve_current_family_id(
            user_id=user_id, refresh_cookie=refresh_cookie
        )
        live_rows = await self._repository.list_live_families_for_user(user_id=user_id)
        family_created_at = await self._repository.get_family_created_at_map_for_user(
            user_id=user_id
        )
        entries = [
            SessionEntry(
                family_id=row.family_id,
                created_at=family_created_at[row.family_id],
                last_used_at=row.last_used_at,
                location=_to_session_location(resolve_location(row.ip)) if row.ip else None,
                device_label=resolve_device_label(row.user_agent),
                is_current=row.family_id == current_family_id,
            )
            for row in live_rows
        ]
        return SessionListResponse(sessions=entries)

    async def revoke_session(
        self,
        *,
        user_id: uuid.UUID,
        family_id: uuid.UUID,
        refresh_cookie: str | None,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> None:
        """FR-2/FR-3/FR-4/FR-6."""
        current_family_id = await self._resolve_current_family_id(
            user_id=user_id, refresh_cookie=refresh_cookie
        )
        if current_family_id is not None and current_family_id == family_id:
            raise CurrentSessionError

        owned = await self._repository.get_any_refresh_token_for_family(
            family_id=family_id, user_id=user_id
        )
        if owned is None:
            raise SessionNotFoundError

        # FR-2 writes the audit entry only when a live token was actually
        # revoked; FR-4's already-revoked/expired path is a silent no-op
        # (per US-2.6-api-design.md) - `revoke_refresh_token_family` itself
        # is unconditionally idempotent either way.
        was_live = owned.revoked_at is None and owned.expires_at > datetime.now(UTC)
        await self._repository.revoke_refresh_token_family(family_id=family_id)
        if was_live:
            await self._repository.create_auth_audit_log_entry(
                event="session_revoked",
                reason=None,
                scope=None,
                actor_id=user_id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
                severity=None,
                target_family=family_id,
            )
        await self._repository.commit()

    async def rotate_refresh_token(
        self, raw_token: str | None, *, ip: str, user_agent: str | None, request_id: str
    ) -> tuple[RefreshResponse, str]:
        """FR-1-FR-7 (RT-AC1-RT-AC6): single-use rotation, reuse detection,
        idle/absolute lifetime enforcement, account eligibility, a per-family
        rate limit (resolved OD-1), and an atomic check-and-consume.

        Check order (resolved OD-5; rate-limit position and the expired-vs-
        reused precedence resolved in the 2026-09-01 spec review addendum):
        unknown -> rate limit -> expired/absolute-cap -> revoked-by-logout ->
        already-consumed/reuse -> account eligibility -> idle timeout ->
        atomic consume-and-rotate. Every rejection raises the identical
        `TokenInvalidError` (FR-3's indistinguishability, resolved OD-3).

        Returns (response, raw_refresh_token) — mirrors `authenticate_user`'s
        tuple-return pattern for a value the router needs beyond the schema.
        """
        if raw_token is None:
            raise TokenInvalidError

        settings = get_settings()
        token_hash = hash_refresh_token(raw_token)
        existing = await self._repository.get_refresh_token_by_hash(token_hash)
        if existing is None:
            raise TokenInvalidError

        # Resolved OD-1: keyed by family_id, checked as soon as a family is
        # known — a client hammering a real family is throttled regardless
        # of whether this specific call would otherwise succeed or 401.
        request_count = await self._refresh_rate_limit_cache.record_request(
            existing.family_id, window_seconds=_REFRESH_RATE_LIMIT_WINDOW_SECONDS
        )
        if request_count > _REFRESH_RATE_LIMIT_MAX_REQUESTS:
            retry_after = await self._refresh_rate_limit_cache.get_retry_after_seconds(
                existing.family_id
            )
            raise TooManyAttemptsError(retry_after_seconds=retry_after)

        now = datetime.now(UTC)

        # FR-5 (absolute cap): `expires_at` is fixed at family creation and
        # copied forward unchanged by every rotation (FR-1 below), so this
        # single check also covers FR-3's "expired" case — no separate
        # family-creation timestamp is needed.
        if existing.expires_at <= now:
            raise TokenInvalidError

        # FR-3's "revoked by logout" case, checked before reuse per resolved
        # OD-5 / the spec's own FR-3 note ("first check... before reuse").
        if existing.revoked_at is not None:
            raise TokenInvalidError

        if existing.consumed_at is not None:
            await self._handle_reuse_or_race(
                existing, now=now, ip=ip, user_agent=user_agent, request_id=request_id
            )
            raise TokenInvalidError

        user = await self._repository.get_by_id(existing.user_id)
        if user is None or user.status == UserStatus.DEACTIVATED.value:
            raise TokenInvalidError
        revoke_before = await self._revocation_cache.get_revoke_before(existing.user_id)
        if revoke_before is not None and existing.issued_at <= revoke_before:
            raise TokenInvalidError

        last_used_reference = existing.last_used_at or existing.issued_at
        if now - last_used_reference > _REFRESH_IDLE_TIMEOUT:
            raise TokenInvalidError

        consumed = await self._repository.consume_refresh_token(token_hash=token_hash)
        if consumed is None:
            # Lost a concurrent race (RT-AC6): another request consumed this
            # token between the read above and this atomic attempt. Re-fetch
            # to apply the same grace-window-vs-reuse logic as above.
            raced = await self._repository.get_refresh_token_by_hash(token_hash)
            if raced is not None:
                await self._handle_reuse_or_race(
                    raced,
                    now=datetime.now(UTC),
                    ip=ip,
                    user_agent=user_agent,
                    request_id=request_id,
                )
            raise TokenInvalidError

        new_raw_token, new_token_hash = generate_refresh_token()
        await self._repository.create_refresh_token(
            token_hash=new_token_hash,
            family_id=consumed.family_id,
            user_id=consumed.user_id,
            expires_at=consumed.expires_at,
            ip=ip,
            user_agent=user_agent,
            last_used_at=now,
        )

        jti = uuid.uuid4()
        session_expires_at = now + timedelta(seconds=settings.access_token_ttl_seconds)
        await self._repository.create_session(
            user_id=consumed.user_id, jti=jti, expires_at=session_expires_at
        )
        await self._repository.commit()

        # Re-evaluates the enrolment-scoping condition on every refresh, not
        # only at login (spec-review resolution, US-2.5 FR-6): an
        # enrolment-scoped account stays scoped across a refresh, and an
        # account that has since completed enrolment gets an unscoped token
        # back without needing to log in again.
        access_token, deadline = await self._encode_access_token_for_user(user, jti=jti)
        response = RefreshResponse(
            access_token=access_token,
            expires_in=settings.access_token_ttl_seconds,
            mfa_enrollment_deadline=deadline,
        )
        return response, new_raw_token

    async def _handle_reuse_or_race(
        self,
        token: RefreshToken,
        *,
        now: datetime,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> None:
        """RT-AC2 vs. RT-AC6: a token already marked `consumed_at` is either
        a losing concurrent request inside the 10-second grace window (a
        race, not an attack — no revocation) or genuine reuse of an
        already-completed rotation (the whole family is destroyed and the
        owner is alerted). Runs regardless of account eligibility (resolved
        OD-5) — reuse of a consumed token is evidence of compromise
        independent of the account's current status.
        """
        consumed_at = token.consumed_at
        if consumed_at is not None and now - consumed_at <= _REFRESH_CONCURRENT_GRACE_WINDOW:
            return

        await self._repository.revoke_refresh_token_family(family_id=token.family_id)
        await self._repository.create_auth_audit_log_entry(
            event="refresh_reuse_detected",
            reason=None,
            scope=None,
            actor_id=token.user_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity="high",
        )
        await self._repository.commit()

        # Fire-and-forget (resolved 2026-09-01 spec review): the revocation/
        # audit outcome above does not wait on or depend on this succeeding.
        user = await self._repository.get_by_id(token.user_id)
        if user is not None:
            try:
                await self._email_sender.send_refresh_reuse_alert(to=user.email)
            except Exception:
                logger.exception("failed to send refresh reuse alert email")

    async def request_password_reset(
        self,
        payload: PasswordResetRequestRequest,
        *,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> PasswordResetRequestResponse:
        """FR-1/FR-3 (PR-AC1/PR-AC3): the response is identical regardless of
        whether the email resolves to an eligible account (NFR-002 anti-
        enumeration). Rate limiting (FR-6, resolved OD-2) is checked first,
        in cooldown -> per-account/hour -> per-IP/hour order; the account-
        scoped limits are keyed by a hash of the normalized email, not
        `user_id`, since an unknown email has none (plan.md's Architectural
        Change #2).

        "Eligible" mirrors login's own notion (status != deactivated AND
        email_verified) rather than only PR-AC3's literal "not registered or
        deactivated" — an unverified account can't log in yet either, so
        resetting its password wouldn't unblock anything; not itself an
        Open Decision since it changes no external behavior (still 202,
        still generic body, still no email observably distinguishable).
        """
        settings = get_settings()
        normalized_email = payload.email.strip().lower()
        email_hash = hashlib.sha256(normalized_email.encode()).hexdigest()

        cooldown_count = await self._password_reset_rate_limit_cache.record_cooldown_attempt(
            email_hash, window_seconds=settings.password_reset_cooldown_seconds
        )
        if cooldown_count > 1:
            retry_after = (
                await self._password_reset_rate_limit_cache.get_cooldown_retry_after_seconds(
                    email_hash
                )
            )
            raise TooManyAttemptsError(retry_after_seconds=retry_after)

        account_count = await self._password_reset_rate_limit_cache.record_account_attempt(
            email_hash, window_seconds=_PASSWORD_RESET_HOURLY_WINDOW_SECONDS
        )
        if account_count > settings.password_reset_account_hourly_limit:
            retry_after = (
                await self._password_reset_rate_limit_cache.get_account_retry_after_seconds(
                    email_hash
                )
            )
            raise TooManyAttemptsError(retry_after_seconds=retry_after)

        ip_count = await self._password_reset_rate_limit_cache.record_ip_attempt(
            ip, window_seconds=_PASSWORD_RESET_HOURLY_WINDOW_SECONDS
        )
        if ip_count > settings.password_reset_ip_hourly_limit:
            retry_after = await self._password_reset_rate_limit_cache.get_ip_retry_after_seconds(ip)
            raise TooManyAttemptsError(retry_after_seconds=retry_after)

        user = await self._repository.get_by_email(normalized_email)
        eligible = (
            user is not None and user.status != UserStatus.DEACTIVATED.value and user.email_verified
        )

        raw_token: str | None = None
        if eligible and user is not None:
            await self._repository.invalidate_password_reset_tokens_for_user(user_id=user.id)
            raw_token = secrets.token_urlsafe(_PASSWORD_RESET_TOKEN_BYTES)
            token_hash = _hash_password_reset_token(raw_token)
            expires_at = datetime.now(UTC) + timedelta(
                minutes=settings.password_reset_token_ttl_minutes
            )
            await self._repository.create_password_reset_token(
                user_id=user.id, token_hash=token_hash, expires_at=expires_at
            )

        # OD-3: written for every attempt, including an unknown/deactivated/
        # unverified email — server-side only, doesn't affect the response.
        await self._repository.create_auth_audit_log_entry(
            event="password_reset_requested",
            reason=None,
            scope=None,
            actor_id=user.id if user is not None else None,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

        if eligible and user is not None and raw_token is not None:
            # Best-effort, after commit (AGENTS.md §3): a failed dispatch
            # must not undo the already-committed token issuance/audit
            # entry — mirrors register_user's verification-email pattern.
            try:
                await self._email_sender.send_password_reset_email(
                    to=user.email, raw_token=raw_token
                )
            except Exception:
                logger.exception("failed to send password reset email")

        return PasswordResetRequestResponse()

    async def confirm_password_reset(
        self,
        payload: PasswordResetConfirmRequest,
        *,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> None:
        """FR-2/FR-4/FR-5 (PR-AC2/PR-AC4/PR-AC5). Token-state mapping
        resolved by precedent (`email_verification`): unknown hash and
        already-consumed both -> `PasswordResetTokenInvalidError` (400),
        expired -> `PasswordResetTokenExpiredError` (400). A password-policy
        failure (422) does NOT consume the token (FR-5) — checked before the
        atomic consume. Consumption is atomic (spec-review resolution,
        accepted 2026-09-01) via the same check-and-consume pattern as
        `consume_refresh_token`; losing the race is treated identically to
        any other invalid-token case.
        """
        token_hash = _hash_password_reset_token(payload.token)
        token = await self._repository.get_password_reset_token_by_hash(token_hash)
        if token is None:
            raise PasswordResetTokenInvalidError
        if token.consumed_at is not None:
            raise PasswordResetTokenInvalidError
        if token.expires_at <= datetime.now(UTC):
            raise PasswordResetTokenExpiredError

        user = await self._repository.get_by_id(token.user_id)
        if user is None:
            raise PasswordResetTokenInvalidError

        new_password = payload.new_password.get_secret_value()
        rules: list[str] = []
        if len(new_password) < _MIN_RESET_PASSWORD_LENGTH:
            rules.append("min_length")
        if is_breached_password(new_password):
            rules.append("breached")
        if await verify_password(new_password, user.hashed_password):
            rules.append("reused")
        if rules:
            raise PasswordPolicyError(rules=rules)

        consumed = await self._repository.consume_password_reset_token(token_hash=token_hash)
        if consumed is None:
            # Lost a concurrent race (spec-review resolution): another
            # request consumed this token between the read above and this
            # atomic attempt.
            raise PasswordResetTokenInvalidError

        hashed_password = await hash_password(new_password)
        await self._repository.update_password_hash(
            user_id=user.id, hashed_password=hashed_password
        )

        # revoke_before set before the commit below, matching logout_all's
        # existing ordering for this exact cache (not the module's own
        # cache.py — RevocationCache is shared core infra with its own
        # established precedent here).
        settings = get_settings()
        await self._revocation_cache.set_revoke_before(
            user.id, ttl_seconds=settings.refresh_token_ttl_seconds
        )
        await self._repository.create_auth_audit_log_entry(
            event="password_reset_completed",
            reason=None,
            scope=None,
            actor_id=user.id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

        # Best-effort, after commit (AGENTS.md §3).
        try:
            await self._email_sender.send_password_reset_notice(to=user.email)
        except Exception:
            logger.exception("failed to send password reset notice email")

    async def enroll_mfa(self, user_id: uuid.UUID, payload: MfaEnrollRequest) -> MfaEnrollResponse:
        """FR-1. Re-enrolling while a PENDING enrolment already exists
        overwrites the secret (OD-11) - mfa_enabled/mfa_activated_at are
        untouched either way, so an unfinished enrolment can never lock
        the user out.
        """
        user = await self._repository.get_by_id(user_id)
        if user is None or not await verify_password(
            payload.current_password.get_secret_value(), user.hashed_password
        ):
            raise InvalidCredentialsError

        secret = generate_totp_secret()
        await self._repository.update_mfa_pending_secret(
            user_id=user_id, secret_encrypted=encrypt_mfa_secret(secret)
        )
        await self._repository.commit()

        return MfaEnrollResponse(
            secret=encode_totp_secret(secret),
            otpauth_uri=build_otpauth_uri(secret=secret, account_email=user.email),
        )

    async def activate_mfa(
        self,
        user_id: uuid.UUID,
        payload: MfaActivateRequest,
        *,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> MfaActivateResponse:
        """FR-2. Also the shared exit condition for both enrolment-scoped-
        token triggers (FR-6/FR-7): if the account was scoped, this clears
        it via perm_epoch, matching US-3.2's existing token-stale mechanism.
        """
        user = await self._repository.get_by_id(user_id)
        if user is None or user.mfa_secret_encrypted is None:
            # No PENDING enrolment to activate - folded into the same
            # generic MfaInvalidCodeError as a wrong code (API design Open
            # Question #1, not resolved by the spec).
            raise MfaInvalidCodeError

        secret = decrypt_mfa_secret(user.mfa_secret_encrypted)
        if verify_totp_code(secret, payload.code) is None:
            raise MfaInvalidCodeError

        was_scoped, _ = await self._resolve_enrollment_scoping(user)

        raw_codes = [secrets.token_hex(_RECOVERY_CODE_BYTES) for _ in range(_RECOVERY_CODE_COUNT)]
        hashed_codes = [await hash_password(code) for code in raw_codes]
        await self._repository.create_recovery_codes(user_id=user_id, code_hashes=hashed_codes)
        await self._repository.activate_mfa(user_id=user_id)
        await self._repository.create_auth_audit_log_entry(
            event="mfa_enabled",
            reason=None,
            scope=None,
            actor_id=user_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

        if was_scoped:
            settings = get_settings()
            await self._permission_epoch_cache.set_perm_epoch(
                user_id, ttl_seconds=settings.perm_epoch_ttl_seconds
            )

        return MfaActivateResponse(recovery_codes=raw_codes)

    async def _try_consume_recovery_code(self, user_id: uuid.UUID, code: str) -> bool:
        """FR-7: each stored hash is independently salted (Argon2id), so a
        submitted code can't be looked up by hash equality - verify against
        every unconsumed row, then atomically consume the matching one.
        """
        candidates = await self._repository.list_unconsumed_recovery_codes(user_id=user_id)
        for candidate in candidates:
            if await verify_password(code, candidate.code_hash):
                consumed = await self._repository.consume_recovery_code(code_id=candidate.id)
                return consumed is not None
        return False

    async def _complete_mfa_login(
        self, user: User, *, ip: str, user_agent: str | None, request_id: str
    ) -> tuple[MfaVerifyResponse, str]:
        """Mints a session + refresh token the same way authenticate_user's
        own success path does (no shared helper between the two - this
        codebase already keeps that block independently duplicated between
        login and refresh, so this follows the same precedent rather than
        introducing a new abstraction).
        """
        settings = get_settings()
        jti = uuid.uuid4()
        session_expires_at = datetime.now(UTC) + timedelta(
            seconds=settings.access_token_ttl_seconds
        )
        await self._repository.create_session(
            user_id=user.id, jti=jti, expires_at=session_expires_at
        )

        await self._evict_oldest_family_if_at_cap(
            user.id, ip=ip, user_agent=user_agent, request_id=request_id
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
            ip=ip,
            user_agent=user_agent,
        )

        await self._repository.update_last_login_at(user_id=user.id)
        await self._repository.create_auth_audit_log_entry(
            event="login_succeeded",
            reason=None,
            scope="mfa",
            actor_id=user.id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

        access_token, _ = await self._encode_access_token_for_user(user, jti=jti)
        response = MfaVerifyResponse(
            access_token=access_token, expires_in=settings.access_token_ttl_seconds
        )
        return response, raw_refresh_token

    async def verify_mfa(
        self, payload: MfaVerifyRequest, *, ip: str, user_agent: str | None, request_id: str
    ) -> tuple[MfaVerifyResponse, str]:
        """FR-3/FR-4/FR-5/FR-7. Accepts either a TOTP code or a recovery
        code in the same `code` field - a recovery-code match is tried
        first since it's a direct per-user lookup, cheaper than decrypting
        the TOTP secret first only to fail and fall back.
        """
        settings = get_settings()
        token_hash = hash_mfa_token(payload.mfa_token)

        user_id = await self._mfa_token_cache.get_user_id(token_hash)
        if user_id is None:
            raise MfaInvalidCodeError

        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise MfaInvalidCodeError

        if await self._try_consume_recovery_code(user_id, payload.code):
            await self._mfa_token_cache.consume(token_hash)
            await self._repository.set_mfa_reenrollment_required(user_id=user_id)
            await self._repository.create_auth_audit_log_entry(
                event="mfa_recovery_used",
                reason=None,
                scope=None,
                actor_id=user_id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
                severity=None,
            )
            await self._repository.commit()
            try:
                await self._email_sender.send_mfa_recovery_used_notice(to=user.email)
            except Exception:
                logger.exception("failed to send mfa recovery-used notice email")
            return await self._complete_mfa_login(
                user, ip=ip, user_agent=user_agent, request_id=request_id
            )

        totp_matched = False
        if user.mfa_secret_encrypted is not None:
            secret = decrypt_mfa_secret(user.mfa_secret_encrypted)
            step = verify_totp_code(secret, payload.code)
            if step is not None:
                # MF-AC4 replay protection: a step already marked used
                # (by this or an earlier request) counts as a failure,
                # even though the code itself was correct.
                totp_matched = await self._mfa_replay_cache.mark_step_used(
                    user_id, step=step, ttl_seconds=settings.mfa_token_ttl_seconds
                )

        if not totp_matched:
            attempt_count = await self._mfa_token_cache.record_failed_attempt(
                token_hash, window_seconds=settings.mfa_token_ttl_seconds
            )
            await self._repository.create_auth_audit_log_entry(
                event="mfa_verify_failed",
                reason=None,
                scope=None,
                actor_id=user_id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
                severity=None,
            )
            await self._repository.commit()
            if attempt_count >= settings.mfa_verify_lockout_threshold:
                # FR-5: the mfa_token is invalidated - full re-authentication
                # is required, so no Retry-After is meaningful here (unlike
                # login's own lockout, there is nothing to retry).
                await self._mfa_token_cache.invalidate(token_hash)
                raise TooManyAttemptsError(retry_after_seconds=0)
            raise MfaInvalidCodeError

        await self._mfa_token_cache.consume(token_hash)
        return await self._complete_mfa_login(
            user, ip=ip, user_agent=user_agent, request_id=request_id
        )

    async def disable_mfa(
        self,
        user_id: uuid.UUID,
        payload: MfaDisableRequest,
        *,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> None:
        """FR-6 (privileged block, 409) / FR-8 (non-privileged success -
        OD-6/OD-8, not covered by any source AC).

        Check order (undecided by the spec/API design - API design Open
        Question #3, resolved here as a documented, conservative default):
        password and code are evaluated jointly and raise the same
        `InvalidCredentialsError` on either failure - a caller who has the
        password but not the code (or vice versa) cannot distinguish which
        factor was wrong from the response. This matters specifically for
        this endpoint's threat model (a hijacked bearer session must not be
        able to strip the second factor by brute-forcing one factor at a
        time): a distinct "wrong code" response would already confirm the
        password was correct, halving the attacker's search space. Both
        checks run unconditionally (never short-circuited) so the response
        also carries no timing signal. Only after both succeed does the
        privileged-role check run, so a wrong password/code never reveals
        whether the account is privileged (409) either.
        """
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError

        password_ok = await verify_password(
            payload.current_password.get_secret_value(), user.hashed_password
        )
        code_ok = user.mfa_secret_encrypted is not None and (
            verify_totp_code(decrypt_mfa_secret(user.mfa_secret_encrypted), payload.code)
            is not None
        )
        if not (password_ok and code_ok):
            raise InvalidCredentialsError

        grants = await self._role_service.get_role_grants_for_user(user_id)
        if any(name in _PRIVILEGED_ROLE_NAMES for name, _ in grants):
            raise MfaRequiredForRoleError

        await self._repository.disable_mfa(user_id=user_id)
        await self._repository.delete_recovery_codes_for_user(user_id=user_id)
        await self._repository.create_auth_audit_log_entry(
            event="mfa_disabled",
            reason=None,
            scope=None,
            actor_id=user_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            severity=None,
        )
        await self._repository.commit()

        # revoke_before set after the commit above (OD-6/OD-8): every other
        # active session ends, matching the precedent password reset and
        # deactivation already establish for this exact cache.
        settings = get_settings()
        await self._revocation_cache.set_revoke_before(
            user_id, ttl_seconds=settings.refresh_token_ttl_seconds
        )
