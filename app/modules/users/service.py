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
    hash_refresh_token,
    verify_password,
    verify_password_dummy,
)
from app.modules.users.exceptions import (
    AccountDeactivatedError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    RegistrationValidationError,
    TokenInvalidError,
    TooManyAttemptsError,
)
from app.modules.users.models import RefreshToken, User, UserSession
from app.modules.users.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    UserCreate,
    UserRead,
    UserStatus,
)

_REFRESH_IDLE_TIMEOUT = timedelta(days=14)
_REFRESH_CONCURRENT_GRACE_WINDOW = timedelta(seconds=10)
_REFRESH_RATE_LIMIT_MAX_REQUESTS = 60
_REFRESH_RATE_LIMIT_WINDOW_SECONDS = 3600

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

    async def commit(self) -> None: ...


class VerificationTokenIssuerProtocol(Protocol):
    async def issue_pending_token(self, user_id: uuid.UUID) -> str: ...


class RevocationCacheProtocol(Protocol):
    async def get_revoke_before(self, user_id: uuid.UUID) -> datetime | None: ...

    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None: ...


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
    ) -> None:
        self._repository = repository
        self._issuer = issuer
        self._email_sender = email_sender
        self._revocation_cache = revocation_cache
        self._throttle_cache = throttle_cache
        self._account_service = account_service
        self._refresh_rate_limit_cache = refresh_rate_limit_cache

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

        response = LoginResponse(
            access_token=encode_access_token(user_id=user.id, jti=jti),
            expires_in=settings.access_token_ttl_seconds,
        )
        return response, raw_refresh_token

    async def get_authenticated_user(
        self, token: str, *, allow_revoked: bool = False
    ) -> AuthenticatedUser | None:
        """`allow_revoked` (resolved OD-2, US-2.2) lets `POST /v1/auth/logout`
        alone resolve a caller whose session is already revoked, so a repeat
        logout call is idempotent (LO-AC4) rather than 401ing (LO-AC5).
        Every other caller — including every other route — leaves this at
        its default `False` and gets today's strict behavior unchanged. A
        jti with no session row at all is never resolved, regardless of this
        flag: "revoked" and "never existed" are different failure modes.
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

        return AuthenticatedUser(user_id=claims.user_id, jti=claims.jti)

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

        response = RefreshResponse(
            access_token=encode_access_token(user_id=consumed.user_id, jti=jti),
            expires_in=settings.access_token_ttl_seconds,
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
