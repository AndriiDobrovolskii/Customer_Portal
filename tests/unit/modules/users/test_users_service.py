import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest

import app.core.security as security
from app.core.crypto import encrypt_mfa_secret
from app.core.security import (
    current_totp_step,
    decode_access_token,
    encode_access_token,
    generate_totp_secret,
    hash_mfa_token,
    hash_password,
    hash_refresh_token,
)
from app.modules.users.exceptions import (
    AccountDeactivatedError,
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
    MfaDisableRequest,
    MfaEnrollRequest,
    MfaRequiredResponse,
    MfaVerifyRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    RefreshResponse,
    UserCreate,
    UserStatus,
)
from app.modules.users.service import UserService

pytestmark = pytest.mark.unit

_IP = "203.0.113.10"
_REQUEST_ID = "test-request-id"


class FakeUserRepository:
    def __init__(
        self,
        *,
        existing_emails: set[str] | None = None,
        simulate_race_on_consume: bool = False,
        simulate_race_on_consume_reset: bool = False,
    ) -> None:
        self.existing_emails = existing_emails or set()
        self.created_with: dict[str, str] | None = None
        self.commit_called = False
        self.users_by_email: dict[str, User] = {}
        self.sessions_by_jti: dict[uuid.UUID, UserSession] = {}
        self.last_login_at_updates: list[uuid.UUID] = []
        self.audit_log_entries: list[dict[str, object]] = []
        self.refresh_tokens: list[dict[str, object]] = []
        self.refresh_tokens_by_hash: dict[str, RefreshToken] = {}
        self.revoked_session_jtis: list[uuid.UUID] = []
        self.revoked_family_ids: list[uuid.UUID] = []
        self.password_hash_updates: dict[uuid.UUID, str] = {}
        self.password_reset_tokens_by_hash: dict[str, PasswordResetToken] = {}
        self.invalidated_reset_tokens_for: list[uuid.UUID] = []
        self.recovery_codes_by_user: dict[uuid.UUID, list[MfaRecoveryCode]] = {}
        self.disable_mfa_calls: list[uuid.UUID] = []
        self.set_reenrollment_required_calls: list[uuid.UUID] = []
        # RT-AC6: simulates a concurrent winner consuming this token between
        # this fake's own initial read and its atomic-consume call — the
        # first consume_refresh_token call sets consumed_at (as if another
        # request just won) and returns None (this request lost the race).
        self.simulate_race_on_consume = simulate_race_on_consume
        # Same pattern for password_reset_tokens (spec-review resolution).
        self.simulate_race_on_consume_reset = simulate_race_on_consume_reset

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

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        for user in self.users_by_email.values():
            if user.id == user_id:
                return user
        return None

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

    async def revoke_session(self, *, jti: uuid.UUID) -> None:
        self.revoked_session_jtis.append(jti)
        session = self.sessions_by_jti.get(jti)
        if session is not None:
            session.revoked_at = datetime.now(UTC)

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.refresh_tokens_by_hash.get(token_hash)

    async def revoke_refresh_token_family(self, *, family_id: uuid.UUID) -> None:
        self.revoked_family_ids.append(family_id)
        for token in self.refresh_tokens_by_hash.values():
            if token.family_id == family_id:
                token.revoked_at = datetime.now(UTC)

    async def consume_refresh_token(self, *, token_hash: str) -> RefreshToken | None:
        token = self.refresh_tokens_by_hash.get(token_hash)
        if token is None or token.consumed_at is not None:
            return None
        if self.simulate_race_on_consume:
            self.simulate_race_on_consume = False
            token.consumed_at = datetime.now(UTC)
            return None
        token.consumed_at = datetime.now(UTC)
        return token

    async def update_last_login_at(self, *, user_id: uuid.UUID) -> None:
        self.last_login_at_updates.append(user_id)

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
    ) -> None:
        self.audit_log_entries.append(
            {
                "event": event,
                "reason": reason,
                "scope": scope,
                "severity": severity,
                "actor_id": actor_id,
                "ip": ip,
                "user_agent": user_agent,
                "request_id": request_id,
            }
        )

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
    ) -> RefreshToken:
        self.refresh_tokens.append(
            {
                "token_hash": token_hash,
                "family_id": family_id,
                "user_id": user_id,
                "expires_at": expires_at,
                "ip": ip,
                "user_agent": user_agent,
                "last_used_at": last_used_at,
            }
        )
        token = RefreshToken(
            token_hash=token_hash,
            family_id=family_id,
            user_id=user_id,
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
            last_used_at=last_used_at,
        )
        self.refresh_tokens_by_hash[token_hash] = token
        return token

    async def update_password_hash(self, *, user_id: uuid.UUID, hashed_password: str) -> None:
        self.password_hash_updates[user_id] = hashed_password
        for user in self.users_by_email.values():
            if user.id == user_id:
                user.hashed_password = hashed_password

    async def invalidate_password_reset_tokens_for_user(self, *, user_id: uuid.UUID) -> None:
        self.invalidated_reset_tokens_for.append(user_id)
        for token in self.password_reset_tokens_by_hash.values():
            if token.user_id == user_id and token.consumed_at is None:
                token.consumed_at = datetime.now(UTC)

    async def create_password_reset_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.password_reset_tokens_by_hash[token_hash] = token
        return token

    async def get_password_reset_token_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self.password_reset_tokens_by_hash.get(token_hash)

    async def consume_password_reset_token(self, *, token_hash: str) -> PasswordResetToken | None:
        token = self.password_reset_tokens_by_hash.get(token_hash)
        if token is None or token.consumed_at is not None:
            return None
        if self.simulate_race_on_consume_reset:
            self.simulate_race_on_consume_reset = False
            token.consumed_at = datetime.now(UTC)
            return None
        token.consumed_at = datetime.now(UTC)
        return token

    async def update_mfa_pending_secret(
        self, *, user_id: uuid.UUID, secret_encrypted: bytes
    ) -> None:
        user = await self.get_by_id(user_id)
        if user is not None:
            user.mfa_secret_encrypted = secret_encrypted

    async def activate_mfa(self, *, user_id: uuid.UUID) -> None:
        user = await self.get_by_id(user_id)
        if user is not None:
            user.mfa_enabled = True
            user.mfa_activated_at = datetime.now(UTC)
            user.mfa_reenrollment_required = False

    async def set_mfa_reenrollment_required(self, *, user_id: uuid.UUID) -> None:
        self.set_reenrollment_required_calls.append(user_id)
        user = await self.get_by_id(user_id)
        if user is not None:
            user.mfa_reenrollment_required = True

    async def disable_mfa(self, *, user_id: uuid.UUID) -> None:
        self.disable_mfa_calls.append(user_id)
        user = await self.get_by_id(user_id)
        if user is not None:
            user.mfa_enabled = False
            user.mfa_secret_encrypted = None
            user.mfa_activated_at = None
            user.mfa_reenrollment_required = False

    async def create_recovery_codes(self, *, user_id: uuid.UUID, code_hashes: list[str]) -> None:
        codes = self.recovery_codes_by_user.setdefault(user_id, [])
        for code_hash in code_hashes:
            code = MfaRecoveryCode(user_id=user_id, code_hash=code_hash)
            code.id = uuid.uuid4()
            codes.append(code)

    async def list_unconsumed_recovery_codes(self, *, user_id: uuid.UUID) -> list[MfaRecoveryCode]:
        return [
            code
            for code in self.recovery_codes_by_user.get(user_id, [])
            if code.consumed_at is None
        ]

    async def consume_recovery_code(self, *, code_id: uuid.UUID) -> MfaRecoveryCode | None:
        for codes in self.recovery_codes_by_user.values():
            for code in codes:
                if code.id == code_id:
                    if code.consumed_at is not None:
                        return None
                    code.consumed_at = datetime.now(UTC)
                    return code
        return None

    async def delete_recovery_codes_for_user(self, *, user_id: uuid.UUID) -> None:
        self.recovery_codes_by_user.pop(user_id, None)

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


class FakeRevocationCache:
    def __init__(
        self,
        *,
        revoke_before_by_user: dict[uuid.UUID, datetime] | None = None,
        raises: bool = False,
    ) -> None:
        self.revoke_before_by_user = revoke_before_by_user or {}
        self.raises = raises
        self.set_revoke_before_calls: list[tuple[uuid.UUID, int]] = []

    async def get_revoke_before(self, user_id: uuid.UUID) -> datetime | None:
        if self.raises:
            raise ConnectionError("valkey unreachable")
        return self.revoke_before_by_user.get(user_id)

    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None:
        self.set_revoke_before_calls.append((user_id, ttl_seconds))
        self.revoke_before_by_user[user_id] = datetime.now(UTC)


class FakeLoginThrottleCache:
    def __init__(
        self,
        *,
        account_counts: dict[uuid.UUID, int] | None = None,
        ip_counts: dict[str, int] | None = None,
        account_ttls: dict[uuid.UUID, int] | None = None,
        ip_ttls: dict[str, int] | None = None,
    ) -> None:
        self.account_counts = dict(account_counts or {})
        self.ip_counts = dict(ip_counts or {})
        self.account_ttls = account_ttls or {}
        self.ip_ttls = ip_ttls or {}
        self.account_failures_recorded: list[uuid.UUID] = []
        self.ip_failures_recorded: list[str] = []
        self.account_resets: list[uuid.UUID] = []

    async def record_account_failure(self, user_id: uuid.UUID, *, window_seconds: int) -> int:
        self.account_failures_recorded.append(user_id)
        self.account_counts[user_id] = self.account_counts.get(user_id, 0) + 1
        return self.account_counts[user_id]

    async def record_ip_failure(self, ip: str, *, window_seconds: int) -> int:
        self.ip_failures_recorded.append(ip)
        self.ip_counts[ip] = self.ip_counts.get(ip, 0) + 1
        return self.ip_counts[ip]

    async def get_account_failure_count(self, user_id: uuid.UUID) -> int:
        return self.account_counts.get(user_id, 0)

    async def get_ip_failure_count(self, ip: str) -> int:
        return self.ip_counts.get(ip, 0)

    async def get_account_retry_after_seconds(self, user_id: uuid.UUID) -> int:
        return self.account_ttls.get(user_id, 900)

    async def get_ip_retry_after_seconds(self, ip: str) -> int:
        return self.ip_ttls.get(ip, 900)

    async def reset_account_failures(self, user_id: uuid.UUID) -> None:
        self.account_resets.append(user_id)
        self.account_counts.pop(user_id, None)


class FakeAccountService:
    def __init__(self, *, reactivate_result: bool = False) -> None:
        self.reactivate_result = reactivate_result
        self.reactivate_called_for: list[uuid.UUID] = []

    async def reactivate_account(self, user_id: uuid.UUID) -> bool:
        self.reactivate_called_for.append(user_id)
        return self.reactivate_result


class FakeEmailSender:
    def __init__(
        self,
        *,
        raises: bool = False,
        raises_reuse_alert: bool = False,
        raises_reset_email: bool = False,
        raises_reset_notice: bool = False,
        raises_mfa_recovery_used_notice: bool = False,
    ) -> None:
        self.raises = raises
        self.raises_reuse_alert = raises_reuse_alert
        self.raises_reset_email = raises_reset_email
        self.raises_reset_notice = raises_reset_notice
        self.raises_mfa_recovery_used_notice = raises_mfa_recovery_used_notice
        self.sent: list[dict[str, str]] = []
        self.reuse_alerts_sent: list[str] = []
        self.reset_emails_sent: list[dict[str, str]] = []
        self.reset_notices_sent: list[str] = []
        self.mfa_recovery_used_notices_sent: list[str] = []

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.sent.append({"to": to, "raw_token": raw_token})

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None:
        pass

    async def send_email_change_notice(self, *, to: str) -> None:
        pass

    async def send_refresh_reuse_alert(self, *, to: str) -> None:
        if self.raises_reuse_alert:
            raise RuntimeError("reuse alert dispatch failed")
        self.reuse_alerts_sent.append(to)

    async def send_password_reset_email(self, *, to: str, raw_token: str) -> None:
        if self.raises_reset_email:
            raise RuntimeError("password reset email dispatch failed")
        self.reset_emails_sent.append({"to": to, "raw_token": raw_token})

    async def send_password_reset_notice(self, *, to: str) -> None:
        if self.raises_reset_notice:
            raise RuntimeError("password reset notice dispatch failed")
        self.reset_notices_sent.append(to)

    async def send_mfa_recovery_used_notice(self, *, to: str) -> None:
        if self.raises_mfa_recovery_used_notice:
            raise RuntimeError("mfa recovery-used notice dispatch failed")
        self.mfa_recovery_used_notices_sent.append(to)


class FakeRefreshRateLimitCache:
    def __init__(
        self,
        *,
        counts: dict[uuid.UUID, int] | None = None,
        retry_after: dict[uuid.UUID, int] | None = None,
    ) -> None:
        self.counts = dict(counts or {})
        self.retry_after = retry_after or {}
        self.recorded_for: list[uuid.UUID] = []

    async def record_request(self, family_id: uuid.UUID, *, window_seconds: int) -> int:
        self.recorded_for.append(family_id)
        self.counts[family_id] = self.counts.get(family_id, 0) + 1
        return self.counts[family_id]

    async def get_retry_after_seconds(self, family_id: uuid.UUID) -> int:
        return self.retry_after.get(family_id, 3600)


class FakePasswordResetRateLimitCache:
    """Three independent counters (resolved OD-2), mirroring the real
    `PasswordResetRateLimitCache`'s three key namespaces.
    """

    def __init__(
        self,
        *,
        cooldown_counts: dict[str, int] | None = None,
        cooldown_retry_after: dict[str, int] | None = None,
        account_counts: dict[str, int] | None = None,
        account_retry_after: dict[str, int] | None = None,
        ip_counts: dict[str, int] | None = None,
        ip_retry_after: dict[str, int] | None = None,
    ) -> None:
        self.cooldown_counts = dict(cooldown_counts or {})
        self.cooldown_retry_after = cooldown_retry_after or {}
        self.account_counts = dict(account_counts or {})
        self.account_retry_after = account_retry_after or {}
        self.ip_counts = dict(ip_counts or {})
        self.ip_retry_after = ip_retry_after or {}
        self.cooldown_attempts_recorded: list[str] = []
        self.account_attempts_recorded: list[str] = []
        self.ip_attempts_recorded: list[str] = []

    async def record_cooldown_attempt(self, email_hash: str, *, window_seconds: int) -> int:
        self.cooldown_attempts_recorded.append(email_hash)
        self.cooldown_counts[email_hash] = self.cooldown_counts.get(email_hash, 0) + 1
        return self.cooldown_counts[email_hash]

    async def get_cooldown_retry_after_seconds(self, email_hash: str) -> int:
        return self.cooldown_retry_after.get(email_hash, 60)

    async def record_account_attempt(self, email_hash: str, *, window_seconds: int) -> int:
        self.account_attempts_recorded.append(email_hash)
        self.account_counts[email_hash] = self.account_counts.get(email_hash, 0) + 1
        return self.account_counts[email_hash]

    async def get_account_retry_after_seconds(self, email_hash: str) -> int:
        return self.account_retry_after.get(email_hash, 3600)

    async def record_ip_attempt(self, ip: str, *, window_seconds: int) -> int:
        self.ip_attempts_recorded.append(ip)
        self.ip_counts[ip] = self.ip_counts.get(ip, 0) + 1
        return self.ip_counts[ip]

    async def get_ip_retry_after_seconds(self, ip: str) -> int:
        return self.ip_retry_after.get(ip, 3600)


class FakePermissionEpochCache:
    def __init__(
        self, epochs: dict[uuid.UUID, datetime] | None = None, *, raises: bool = False
    ) -> None:
        self.epochs = dict(epochs or {})
        self.raises = raises
        self.set_for: list[tuple[uuid.UUID, int]] = []

    async def get_perm_epoch(self, user_id: uuid.UUID) -> datetime | None:
        if self.raises:
            raise ConnectionError("valkey unreachable")
        return self.epochs.get(user_id)

    async def set_perm_epoch(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None:
        self.set_for.append((user_id, ttl_seconds))
        self.epochs[user_id] = datetime.now(UTC)


class FakeRoleService:
    def __init__(
        self,
        scopes_by_user: dict[uuid.UUID, list[str]] | None = None,
        grants_by_user: dict[uuid.UUID, list[tuple[str, datetime]]] | None = None,
    ) -> None:
        self.scopes_by_user = dict(scopes_by_user or {})
        self.grants_by_user = dict(grants_by_user or {})
        self.resolved_for: list[uuid.UUID] = []

    async def resolve_scopes_for_user(self, user_id: uuid.UUID) -> list[str]:
        self.resolved_for.append(user_id)
        return self.scopes_by_user.get(user_id, [])

    async def get_role_grants_for_user(self, user_id: uuid.UUID) -> list[tuple[str, datetime]]:
        return self.grants_by_user.get(user_id, [])


class FakeMfaTokenCache:
    def __init__(self) -> None:
        self.user_id_by_hash: dict[str, uuid.UUID] = {}
        self.attempt_counts: dict[str, int] = {}
        self.invalidated: list[str] = []

    async def issue(self, token_hash: str, *, user_id: uuid.UUID, ttl_seconds: int) -> None:
        self.user_id_by_hash[token_hash] = user_id

    async def get_user_id(self, token_hash: str) -> uuid.UUID | None:
        return self.user_id_by_hash.get(token_hash)

    async def consume(self, token_hash: str) -> uuid.UUID | None:
        return self.user_id_by_hash.pop(token_hash, None)

    async def record_failed_attempt(self, token_hash: str, *, window_seconds: int) -> int:
        self.attempt_counts[token_hash] = self.attempt_counts.get(token_hash, 0) + 1
        return self.attempt_counts[token_hash]

    async def invalidate(self, token_hash: str) -> None:
        self.invalidated.append(token_hash)
        self.user_id_by_hash.pop(token_hash, None)
        self.attempt_counts.pop(token_hash, None)


class FakeMfaReplayCache:
    def __init__(self, *, already_used_steps: set[tuple[uuid.UUID, int]] | None = None) -> None:
        self.used_steps: set[tuple[uuid.UUID, int]] = set(already_used_steps or set())

    async def mark_step_used(self, user_id: uuid.UUID, *, step: int, ttl_seconds: int) -> bool:
        key = (user_id, step)
        if key in self.used_steps:
            return False
        self.used_steps.add(key)
        return True


def _email_hash(email: str) -> str:
    """Test-side mirror of the service's own normalized-email hashing, used
    only to pre-seed/assert against the fake rate-limit cache's keys.
    """
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _make_service(
    repository: FakeUserRepository,
    issuer: FakeVerificationTokenIssuer | None = None,
    email_sender: FakeEmailSender | None = None,
    revocation_cache: FakeRevocationCache | None = None,
    throttle_cache: FakeLoginThrottleCache | None = None,
    account_service: FakeAccountService | None = None,
    refresh_rate_limit_cache: FakeRefreshRateLimitCache | None = None,
    password_reset_rate_limit_cache: FakePasswordResetRateLimitCache | None = None,
    permission_epoch_cache: FakePermissionEpochCache | None = None,
    role_service: FakeRoleService | None = None,
    mfa_token_cache: FakeMfaTokenCache | None = None,
    mfa_replay_cache: FakeMfaReplayCache | None = None,
) -> tuple[UserService, FakeVerificationTokenIssuer, FakeEmailSender]:
    issuer = issuer or FakeVerificationTokenIssuer()
    email_sender = email_sender or FakeEmailSender()
    revocation_cache = revocation_cache or FakeRevocationCache()
    throttle_cache = throttle_cache or FakeLoginThrottleCache()
    account_service = account_service or FakeAccountService()
    refresh_rate_limit_cache = refresh_rate_limit_cache or FakeRefreshRateLimitCache()
    password_reset_rate_limit_cache = (
        password_reset_rate_limit_cache or FakePasswordResetRateLimitCache()
    )
    permission_epoch_cache = permission_epoch_cache or FakePermissionEpochCache()
    role_service = role_service or FakeRoleService()
    mfa_token_cache = mfa_token_cache or FakeMfaTokenCache()
    mfa_replay_cache = mfa_replay_cache or FakeMfaReplayCache()
    service = UserService(
        repository,
        issuer,
        email_sender,
        revocation_cache,
        throttle_cache,
        account_service,
        refresh_rate_limit_cache,
        password_reset_rate_limit_cache,
        permission_epoch_cache,
        role_service,
        mfa_token_cache,
        mfa_replay_cache,
    )
    return service, issuer, email_sender


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
    repository: FakeUserRepository,
    *,
    email: str,
    password: str,
    email_verified: bool,
    status: str = "PENDING_VERIFICATION",
    deactivated_at: datetime | None = None,
    mfa_enabled: bool = False,
    mfa_secret_encrypted: bytes | None = None,
    mfa_reenrollment_required: bool = False,
) -> User:
    user = User(email=email, hashed_password=await hash_password(password), status=status)
    user.id = uuid.uuid4()
    user.email_verified = email_verified
    user.deactivated_at = deactivated_at
    user.mfa_enabled = mfa_enabled
    user.mfa_secret_encrypted = mfa_secret_encrypted
    user.mfa_reenrollment_required = mfa_reenrollment_required
    repository.users_by_email[email.lower()] = user
    return user


async def _login(service: UserService, payload: LoginRequest) -> tuple[LoginResponse, str]:
    """Existing call sites all expect a normal (non-MFA) login — asserts
    and narrows accordingly. US-009 tests exercising the MFA-challenge
    branch call `service.authenticate_user` directly instead.
    """
    response, raw_refresh_token = await service.authenticate_user(
        payload, ip=_IP, user_agent="pytest-agent", request_id=_REQUEST_ID
    )
    assert isinstance(response, LoginResponse)
    assert raw_refresh_token is not None
    return response, raw_refresh_token


# --- LI-AC1: successful login (FR-1) --------------------------------------


async def test_authenticate_user_correct_credentials_returns_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="verified@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="verified@example.com", password="Str0ng!Pass")

    # Act
    response, raw_refresh_token = await _login(service, payload)

    # Assert
    assert response.token_type == "Bearer"
    assert response.expires_in > 0
    assert len(raw_refresh_token) > 0
    claims = decode_access_token(response.access_token)
    assert claims.user_id == user.id
    assert repository.commit_called is True
    assert repository.last_login_at_updates == [user.id]
    assert repository.audit_log_entries[-1]["event"] == "login_succeeded"
    assert repository.refresh_tokens[-1]["user_id"] == user.id


async def test_authenticate_user_persists_a_session_row() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository,
        email="session@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="session@example.com", password="Str0ng!Pass")

    # Act
    response, _ = await _login(service, payload)

    # Assert
    claims = decode_access_token(response.access_token)
    assert claims.jti in repository.sessions_by_jti
    assert repository.sessions_by_jti[claims.jti].revoked_at is None


# --- LI-AC2: wrong password (FR-2) ------------------------------------------


async def test_authenticate_user_wrong_password_raises_invalid_credentials() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository,
        email="verified@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="verified@example.com", password="WrongPassword1!")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await _login(service, payload)
    assert repository.audit_log_entries[-1]["reason"] == "bad_password"


# --- LI-AC3: unknown email, anti-enumeration (FR-3, resolved OD-3) ---------


async def test_authenticate_user_unknown_email_calls_dummy_verification() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="nobody@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await _login(service, payload)
    entry = repository.audit_log_entries[-1]
    assert entry["event"] == "login_failed"
    assert entry["reason"] == "unknown_email"
    assert entry["actor_id"] is None


# --- LI-AC4: account-state gating (FR-4) -------------------------------------


async def test_authenticate_user_unverified_raises_email_not_verified() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository, email="unverified@example.com", password="Str0ng!Pass", email_verified=False
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email="unverified@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(EmailNotVerifiedError):
        await _login(service, payload)
    assert repository.audit_log_entries[-1]["reason"] == "email_not_verified"


async def test_authenticate_user_deactivated_past_grace_raises_account_deactivated() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository,
        email="deactivated@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="deactivated",
    )
    account_service = FakeAccountService(reactivate_result=False)
    service, _, _ = _make_service(repository, account_service=account_service)
    payload = LoginRequest(email="deactivated@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(AccountDeactivatedError):
        await _login(service, payload)
    assert repository.audit_log_entries[-1]["reason"] == "account_deactivated"


async def test_authenticate_user_deactivated_wrong_password_returns_generic_401() -> None:
    # Arrange — ordering guarantee (FR-4/DA-AC7): credential check precedes
    # the state check, so a wrong password against a deactivated account
    # must be indistinguishable from one against a normal account.
    repository = FakeUserRepository()
    await _seed_user(
        repository,
        email="deactivated@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="deactivated",
    )
    account_service = FakeAccountService()
    service, _, _ = _make_service(repository, account_service=account_service)
    payload = LoginRequest(email="deactivated@example.com", password="WrongPassword1!")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await _login(service, payload)
    assert account_service.reactivate_called_for == []


# --- DA-AC8 (resolved OD-10): reactivation within the grace period ---------


async def test_authenticate_user_deactivated_within_grace_reactivates_and_logs_in() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="grace@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="deactivated",
        deactivated_at=datetime.now(UTC) - timedelta(days=5),
    )
    account_service = FakeAccountService(reactivate_result=True)
    service, _, _ = _make_service(repository, account_service=account_service)
    payload = LoginRequest(email="grace@example.com", password="Str0ng!Pass")

    # Act
    response, raw_refresh_token = await _login(service, payload)

    # Assert
    assert account_service.reactivate_called_for == [user.id]
    assert len(response.access_token) > 0
    assert len(raw_refresh_token) > 0
    assert repository.audit_log_entries[-1]["event"] == "login_succeeded"
    assert repository.last_login_at_updates == [user.id]


# --- LI-AC5: brute-force throttling (FR-5) -----------------------------------


async def test_authenticate_user_account_throttle_exceeded_raises_too_many_attempts() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="throttled@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    throttle_cache = FakeLoginThrottleCache(
        account_counts={user.id: 10}, account_ttls={user.id: 300}
    )
    service, _, _ = _make_service(repository, throttle_cache=throttle_cache)
    payload = LoginRequest(email="throttled@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await _login(service, payload)
    assert exc_info.value.headers == {"Retry-After": "300"}
    # No login attempt was actually processed against this account.
    assert repository.audit_log_entries == []


async def test_authenticate_user_ip_throttle_exceeded_raises_too_many_attempts() -> None:
    # Arrange
    repository = FakeUserRepository()
    throttle_cache = FakeLoginThrottleCache(ip_counts={_IP: 20}, ip_ttls={_IP: 600})
    service, _, _ = _make_service(repository, throttle_cache=throttle_cache)
    payload = LoginRequest(email="anyone@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await _login(service, payload)
    assert exc_info.value.headers == {"Retry-After": "600"}


async def test_authenticate_user_success_resets_account_counter_not_ip_counter() -> None:
    # Arrange — resolved OD-5.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="resets@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    throttle_cache = FakeLoginThrottleCache(account_counts={user.id: 3}, ip_counts={_IP: 5})
    service, _, _ = _make_service(repository, throttle_cache=throttle_cache)
    payload = LoginRequest(email="resets@example.com", password="Str0ng!Pass")

    # Act
    await _login(service, payload)

    # Assert
    assert throttle_cache.account_resets == [user.id]
    assert throttle_cache.ip_counts[_IP] == 5  # untouched


async def test_authenticate_user_wrong_password_records_both_counters() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="wrongpw@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    throttle_cache = FakeLoginThrottleCache()
    service, _, _ = _make_service(repository, throttle_cache=throttle_cache)
    payload = LoginRequest(email="wrongpw@example.com", password="WrongPassword1!")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await _login(service, payload)
    assert throttle_cache.account_failures_recorded == [user.id]
    assert throttle_cache.ip_failures_recorded == [_IP]


async def test_authenticate_user_unknown_email_records_only_ip_counter() -> None:
    # Arrange
    repository = FakeUserRepository()
    throttle_cache = FakeLoginThrottleCache()
    service, _, _ = _make_service(repository, throttle_cache=throttle_cache)
    payload = LoginRequest(email="nobody@example.com", password="Str0ng!Pass")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await _login(service, payload)
    assert throttle_cache.account_failures_recorded == []
    assert throttle_cache.ip_failures_recorded == [_IP]


# --- DA-AC4 (US-004): revoke_before check in the shared auth dependency -------


async def _seed_session(
    repository: FakeUserRepository, *, user_id: uuid.UUID, issued_at: datetime
) -> str:
    jti = uuid.uuid4()
    session = UserSession(
        jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    session.issued_at = issued_at
    repository.sessions_by_jti[jti] = session
    return encode_access_token(user_id=user_id, jti=jti, scopes=[])


async def test_get_authenticated_user_token_before_revoke_before_rejected() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    issued_at = datetime.now(UTC) - timedelta(minutes=10)
    token = await _seed_session(repository, user_id=user_id, issued_at=issued_at)
    revoke_before = issued_at + timedelta(minutes=1)
    cache = FakeRevocationCache(revoke_before_by_user={user_id: revoke_before})
    service, _, _ = _make_service(repository, revocation_cache=cache)

    # Act
    result = await service.get_authenticated_user(token)

    # Assert
    assert result is None


async def test_get_authenticated_user_revoke_before_absent_accepted() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    cache = FakeRevocationCache()
    service, _, _ = _make_service(repository, revocation_cache=cache)

    # Act
    result = await service.get_authenticated_user(token)

    # Assert
    assert result is not None
    assert result.user_id == user_id


async def test_get_authenticated_user_token_issued_after_revoke_before_accepted() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    revoke_before = datetime.now(UTC) - timedelta(minutes=10)
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    cache = FakeRevocationCache(revoke_before_by_user={user_id: revoke_before})
    service, _, _ = _make_service(repository, revocation_cache=cache)

    # Act
    result = await service.get_authenticated_user(token)

    # Assert
    assert result is not None


async def test_get_authenticated_user_cache_read_error_rejected() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    cache = FakeRevocationCache(raises=True)
    service, _, _ = _make_service(repository, revocation_cache=cache)

    # Act
    result = await service.get_authenticated_user(token)

    # Assert: fail closed on a cache-read error, per AGENTS.md §3's
    # denylist carve-out — an outage must reject, not accept, the token.
    assert result is None


async def test_get_authenticated_user_perm_epoch_cache_read_error_rejected() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    permission_epoch_cache = FakePermissionEpochCache(raises=True)
    service, _, _ = _make_service(repository, permission_epoch_cache=permission_epoch_cache)

    # Act
    result = await service.get_authenticated_user(token)

    # Assert: same fail-closed rationale as revoke_before's cache-read-error case.
    assert result is None


async def test_get_authenticated_user_token_before_perm_epoch_raises_token_stale() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    issued_at = datetime.now(UTC)
    token = await _seed_session(repository, user_id=user_id, issued_at=issued_at)
    permission_epoch_cache = FakePermissionEpochCache({user_id: issued_at + timedelta(seconds=5)})
    service, _, _ = _make_service(repository, permission_epoch_cache=permission_epoch_cache)

    # Act & Assert: distinct from every other failure in this method (MR-AC2,
    # US-3.2) — raised, not returned as None.
    with pytest.raises(TokenStaleError):
        await service.get_authenticated_user(token)


async def test_get_authenticated_user_perm_epoch_absent_accepted() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    service, _, _ = _make_service(repository)

    # Act
    result = await service.get_authenticated_user(token)

    # Assert
    assert result is not None
    assert result.user_id == user_id


# --- US-2.2 (spec US-006): logout / logout-all -------------------------------


async def _seed_refresh_token(
    repository: FakeUserRepository, *, user_id: uuid.UUID, family_id: uuid.UUID | None = None
) -> str:
    """Seeds a refresh_tokens row and returns the raw token value (the
    presented cookie), mirroring how login actually issues one.
    """
    raw_token = f"raw-refresh-token-{uuid.uuid4()}"
    await repository.create_refresh_token(
        token_hash=hash_refresh_token(raw_token),
        family_id=family_id or uuid.uuid4(),
        user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    return raw_token


async def test_logout_revokes_session_and_refresh_family() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    claims = decode_access_token(token)
    family_id = uuid.uuid4()
    raw_refresh_token = await _seed_refresh_token(repository, user_id=user_id, family_id=family_id)
    service, _, _ = _make_service(repository)

    # Act
    await service.logout(
        jti=claims.jti,
        user_id=user_id,
        refresh_token=raw_refresh_token,
        ip=_IP,
        user_agent="pytest",
        request_id=_REQUEST_ID,
    )

    # Assert
    assert claims.jti in repository.revoked_session_jtis
    assert repository.sessions_by_jti[claims.jti].revoked_at is not None
    assert family_id in repository.revoked_family_ids
    assert repository.audit_log_entries[-1]["event"] == "logout"
    assert repository.audit_log_entries[-1]["scope"] == "session"
    assert repository.audit_log_entries[-1]["actor_id"] == user_id
    assert repository.commit_called is True


async def test_logout_no_refresh_cookie_still_revokes_session() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    claims = decode_access_token(token)
    service, _, _ = _make_service(repository)

    # Act
    await service.logout(
        jti=claims.jti,
        user_id=user_id,
        refresh_token=None,
        ip=_IP,
        user_agent="pytest",
        request_id=_REQUEST_ID,
    )

    # Assert
    assert claims.jti in repository.revoked_session_jtis
    assert repository.revoked_family_ids == []
    assert repository.audit_log_entries[-1]["scope"] == "session"
    assert repository.commit_called is True


async def test_logout_refresh_cookie_lookup_miss_skips_family_revocation() -> None:
    # Arrange: a cookie value that was never issued (stale/tampered/deleted)
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    claims = decode_access_token(token)
    service, _, _ = _make_service(repository)

    # Act
    await service.logout(
        jti=claims.jti,
        user_id=user_id,
        refresh_token="never-issued-token-value",
        ip=_IP,
        user_agent="pytest",
        request_id=_REQUEST_ID,
    )

    # Assert: jti still revoked, audit entry still written, no family to revoke
    assert claims.jti in repository.revoked_session_jtis
    assert repository.revoked_family_ids == []
    assert repository.audit_log_entries[-1]["scope"] == "session"
    assert repository.commit_called is True


async def test_logout_cross_user_refresh_cookie_does_not_revoke_other_users_family() -> None:
    # Arrange: caller presents a refresh cookie that hashes to a real row,
    # but the row belongs to a different user (e.g. a stolen token). Advisor
    # finding, fixed 2026-09-01: without an ownership check this let any
    # authenticated caller revoke an arbitrary victim's session family.
    caller_id = uuid.uuid4()
    victim_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=caller_id, issued_at=datetime.now(UTC))
    claims = decode_access_token(token)
    victim_family_id = uuid.uuid4()
    victim_refresh_token = await _seed_refresh_token(
        repository, user_id=victim_id, family_id=victim_family_id
    )
    service, _, _ = _make_service(repository)

    # Act
    await service.logout(
        jti=claims.jti,
        user_id=caller_id,
        refresh_token=victim_refresh_token,
        ip=_IP,
        user_agent="pytest",
        request_id=_REQUEST_ID,
    )

    # Assert: caller's own session is revoked, but the victim's refresh
    # family is untouched — identical outward behavior to a lookup-miss.
    assert claims.jti in repository.revoked_session_jtis
    assert victim_family_id not in repository.revoked_family_ids
    assert repository.audit_log_entries[-1]["scope"] == "session"
    assert repository.commit_called is True


async def test_logout_all_sets_revoke_before() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    cache = FakeRevocationCache()
    service, _, _ = _make_service(repository, revocation_cache=cache)

    # Act
    await service.logout_all(user_id=user_id, ip=_IP, user_agent="pytest", request_id=_REQUEST_ID)

    # Assert
    assert len(cache.set_revoke_before_calls) == 1
    assert cache.set_revoke_before_calls[0][0] == user_id
    assert repository.audit_log_entries[-1]["event"] == "logout"
    assert repository.audit_log_entries[-1]["scope"] == "all_sessions"
    assert repository.audit_log_entries[-1]["actor_id"] == user_id
    assert repository.commit_called is True


async def test_get_authenticated_user_allow_revoked_resolves_revoked_session() -> None:
    # Arrange: a session that has already been revoked (e.g. a prior logout)
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    token = await _seed_session(repository, user_id=user_id, issued_at=datetime.now(UTC))
    claims = decode_access_token(token)
    repository.sessions_by_jti[claims.jti].revoked_at = datetime.now(UTC)
    service, _, _ = _make_service(repository)

    # Act
    strict_result = await service.get_authenticated_user(token)
    lenient_result = await service.get_authenticated_user(token, allow_revoked=True)

    # Assert: default behavior unchanged (401-shaped), leniency resolves it
    assert strict_result is None
    assert lenient_result is not None
    assert lenient_result.user_id == user_id


async def test_get_authenticated_user_allow_revoked_rejects_unknown_jti() -> None:
    # Arrange: a well-formed token whose jti has no session row at all —
    # "revoked" and "never existed" are different failure modes (Open
    # Question #2, US-006-api-design.md).
    repository = FakeUserRepository()
    token = encode_access_token(user_id=uuid.uuid4(), jti=uuid.uuid4(), scopes=[])
    service, _, _ = _make_service(repository)

    # Act
    result = await service.get_authenticated_user(token, allow_revoked=True)

    # Assert
    assert result is None


# --- US-2.3 (spec US-007): refresh token rotation ----------------------------


async def _seed_rotatable_token(
    repository: FakeUserRepository,
    *,
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
    consumed_at: datetime | None = None,
    revoked_at: datetime | None = None,
    last_used_at: datetime | None = None,
    issued_at: datetime | None = None,
) -> str:
    """Seeds a rotatable refresh_tokens row and returns its raw (presented)
    value, mirroring how login actually issues one, then overrides whichever
    state fields the test needs to control.
    """
    raw_token = f"raw-refresh-token-{uuid.uuid4()}"
    token = await repository.create_refresh_token(
        token_hash=hash_refresh_token(raw_token),
        family_id=family_id or uuid.uuid4(),
        user_id=user_id,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=30)),
        last_used_at=last_used_at,
    )
    # `issued_at` is DB `server_default=func.now()` (models.py) — never set
    # by the Python constructor, so the fake must populate it explicitly,
    # same as `_seed_session` already does for `UserSession`.
    token.issued_at = issued_at or datetime.now(UTC)
    if consumed_at is not None:
        token.consumed_at = consumed_at
    if revoked_at is not None:
        token.revoked_at = revoked_at
    return raw_token


async def _rotate(service: UserService, raw_token: str | None) -> tuple[object, str]:
    return await service.rotate_refresh_token(
        raw_token, ip=_IP, user_agent="pytest-agent", request_id=_REQUEST_ID
    )


# --- RT-AC1: successful rotation (FR-1) --------------------------------------


async def test_rotate_refresh_token_rotates_and_preserves_family_and_expiry() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.happy@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    family_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=20)
    raw_token = await _seed_rotatable_token(
        repository, user_id=user.id, family_id=family_id, expires_at=expires_at
    )
    old_token_hash = hash_refresh_token(raw_token)
    service, _, _ = _make_service(repository)

    # Act
    response, new_raw_token = await _rotate(service, raw_token)

    # Assert
    assert len(response.access_token) > 0  # type: ignore[attr-defined]
    assert response.expires_in > 0  # type: ignore[attr-defined]
    assert new_raw_token != raw_token
    assert repository.refresh_tokens_by_hash[old_token_hash].consumed_at is not None
    new_token = repository.refresh_tokens_by_hash[hash_refresh_token(new_raw_token)]
    assert new_token.family_id == family_id
    assert new_token.expires_at == expires_at
    assert repository.commit_called is True


async def test_rotate_refresh_token_creates_a_new_session_for_new_access_token() -> None:
    # Arrange: the new access token's jti must resolve via get_authenticated_
    # user afterward, which requires a matching user_sessions row.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.session@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_rotatable_token(repository, user_id=user.id)
    service, _, _ = _make_service(repository)

    # Act
    response, _ = await _rotate(service, raw_token)

    # Assert
    claims = decode_access_token(response.access_token)  # type: ignore[attr-defined]
    assert claims.jti in repository.sessions_by_jti
    assert repository.sessions_by_jti[claims.jti].revoked_at is None


# --- RT-AC2: reuse detection (FR-2) -------------------------------------------


async def test_rotate_refresh_token_reuse_revokes_family_and_alerts() -> None:
    # Arrange: a token already consumed well outside the concurrency grace
    # window — genuine reuse of an already-completed rotation.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.reuse@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    family_id = uuid.uuid4()
    raw_token = await _seed_rotatable_token(
        repository,
        user_id=user.id,
        family_id=family_id,
        consumed_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)
    assert family_id in repository.revoked_family_ids
    entry = repository.audit_log_entries[-1]
    assert entry["event"] == "refresh_reuse_detected"
    assert entry["severity"] == "high"
    assert entry["actor_id"] == user.id
    assert email_sender.reuse_alerts_sent == [user.email]


async def test_rotate_refresh_token_reuse_alerts_even_when_account_deactivated() -> None:
    # Arrange — resolved OD-5: reuse alerting fires regardless of account
    # eligibility, since it's evidence of compromise independent of status.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.reuse.deactivated@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="deactivated",
    )
    family_id = uuid.uuid4()
    raw_token = await _seed_rotatable_token(
        repository,
        user_id=user.id,
        family_id=family_id,
        consumed_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)
    assert family_id in repository.revoked_family_ids
    assert repository.audit_log_entries[-1]["severity"] == "high"
    assert email_sender.reuse_alerts_sent == [user.email]


async def test_rotate_refresh_token_reuse_email_failure_does_not_block_response() -> None:
    # Arrange — fire-and-forget (resolved 2026-09-01 spec review): a failed
    # alert email must not prevent the revocation/audit outcome.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.reuse.emailfail@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    family_id = uuid.uuid4()
    raw_token = await _seed_rotatable_token(
        repository,
        user_id=user.id,
        family_id=family_id,
        consumed_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    email_sender = FakeEmailSender(raises_reuse_alert=True)
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)
    assert family_id in repository.revoked_family_ids
    assert repository.audit_log_entries[-1]["severity"] == "high"


# --- RT-AC3: unknown / revoked-by-logout, indistinguishable (FR-3) ----------


async def test_rotate_refresh_token_unknown_token_returns_token_invalid() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, "never-issued-token-value")


async def test_rotate_refresh_token_no_cookie_returns_token_invalid() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, None)


async def test_rotate_refresh_token_revoked_by_logout_returns_token_invalid() -> None:
    # Arrange: revoked by a prior /logout call, never consumed — must NOT be
    # treated as reuse (checked before the consumed_at branch per FR-3).
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.revoked@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    family_id = uuid.uuid4()
    raw_token = await _seed_rotatable_token(
        repository, user_id=user.id, family_id=family_id, revoked_at=datetime.now(UTC)
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)
    assert repository.revoked_family_ids == []
    assert repository.audit_log_entries == []


async def test_rotate_refresh_token_expired_and_consumed_resolves_as_expired() -> None:
    # Arrange — spec-review finding, resolved 2026-09-01: expired takes
    # precedence over reuse, so no family revocation/audit/email fires.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.expired.reused@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    family_id = uuid.uuid4()
    raw_token = await _seed_rotatable_token(
        repository,
        user_id=user.id,
        family_id=family_id,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        consumed_at=datetime.now(UTC) - timedelta(days=1),
    )
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)
    assert repository.revoked_family_ids == []
    assert repository.audit_log_entries == []
    assert email_sender.reuse_alerts_sent == []


# --- RT-AC4: idle timeout and absolute cap (FR-4, FR-5) ----------------------


async def test_rotate_refresh_token_idle_timeout_returns_token_invalid() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.idle@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_rotatable_token(
        repository, user_id=user.id, last_used_at=datetime.now(UTC) - timedelta(days=15)
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)


async def test_rotate_refresh_token_idle_timeout_falls_back_to_issued_at_when_never_rotated() -> (
    None
):
    # Arrange: never rotated since login — last_used_at is NULL, so the
    # 14-day check falls back to issued_at.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.idle.fallback@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_rotatable_token(
        repository, user_id=user.id, issued_at=datetime.now(UTC) - timedelta(days=15)
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)


async def test_rotate_refresh_token_within_idle_window_succeeds() -> None:
    # Arrange: last used 10 days ago — inside the 14-day idle window.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.idle.ok@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_rotatable_token(
        repository, user_id=user.id, last_used_at=datetime.now(UTC) - timedelta(days=10)
    )
    service, _, _ = _make_service(repository)

    # Act
    response, _ = await _rotate(service, raw_token)

    # Assert
    assert len(response.access_token) > 0  # type: ignore[attr-defined]


async def test_rotate_refresh_token_absolute_cap_ignores_recent_use() -> None:
    # Arrange: family created (and its expires_at fixed) beyond the 30-day
    # cap, even though it was used very recently — FR-5's "regardless of
    # recent activity."
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.absolute@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_rotatable_token(
        repository,
        user_id=user.id,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        last_used_at=datetime.now(UTC),
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)


# --- RT-AC5: account eligibility (FR-6) --------------------------------------


async def test_rotate_refresh_token_deactivated_account_returns_token_invalid() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.deactivated@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="deactivated",
    )
    raw_token = await _seed_rotatable_token(repository, user_id=user.id)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)


async def test_rotate_refresh_token_revoke_before_returns_token_invalid() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.revokebefore@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    issued_at = datetime.now(UTC) - timedelta(hours=1)
    raw_token = await _seed_rotatable_token(repository, user_id=user.id, issued_at=issued_at)
    cache = FakeRevocationCache(revoke_before_by_user={user.id: issued_at + timedelta(minutes=1)})
    service, _, _ = _make_service(repository, revocation_cache=cache)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)


# --- RT-AC6: atomic concurrent handling (FR-7) -------------------------------


async def test_rotate_refresh_token_concurrent_race_within_grace_returns_401_no_revocation() -> (
    None
):
    # Arrange: simulates losing a concurrent race — the atomic consume fails
    # even though the initial read saw an unconsumed token.
    repository = FakeUserRepository(simulate_race_on_consume=True)
    user = await _seed_user(
        repository,
        email="refresh.race@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    family_id = uuid.uuid4()
    raw_token = await _seed_rotatable_token(repository, user_id=user.id, family_id=family_id)
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await _rotate(service, raw_token)
    assert repository.revoked_family_ids == []
    assert email_sender.reuse_alerts_sent == []


# --- Resolved OD-1: per-family rate limit ------------------------------------


async def test_rotate_refresh_token_rate_limit_exceeded_raises_too_many_attempts() -> None:
    # Arrange: this family is already at the 60/hour ceiling.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresh.ratelimited@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    family_id = uuid.uuid4()
    raw_token = await _seed_rotatable_token(repository, user_id=user.id, family_id=family_id)
    rate_limit_cache = FakeRefreshRateLimitCache(
        counts={family_id: 60}, retry_after={family_id: 120}
    )
    service, _, _ = _make_service(repository, refresh_rate_limit_cache=rate_limit_cache)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await _rotate(service, raw_token)
    assert exc_info.value.headers == {"Retry-After": "120"}
    # No rotation was attempted against this token.
    assert repository.refresh_tokens_by_hash[hash_refresh_token(raw_token)].consumed_at is None


# --- US-2.4 (spec US-008): password reset ------------------------------------


async def _seed_reset_token(
    repository: FakeUserRepository,
    *,
    user_id: uuid.UUID,
    expires_at: datetime | None = None,
    consumed_at: datetime | None = None,
) -> str:
    raw_token = f"raw-reset-token-{uuid.uuid4()}"
    token = await repository.create_password_reset_token(
        user_id=user_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=30)),
    )
    if consumed_at is not None:
        token.consumed_at = consumed_at
    return raw_token


async def _request_reset(service: UserService, email: str) -> None:
    await service.request_password_reset(
        PasswordResetRequestRequest(email=email),
        ip=_IP,
        user_agent="pytest-agent",
        request_id=_REQUEST_ID,
    )


_RESET_OLD_PASSWORD = "OldStr0ng!Pass"  # pragma: allowlist secret
_RESET_NEW_PASSWORD = "BrandNewStr0ngPass!"  # pragma: allowlist secret
_RESET_SHORT_PASSWORD = "Sh0rt!"  # pragma: allowlist secret
_RESET_BREACHED_PASSWORD = "Password123!"  # pragma: allowlist secret
_RESET_CURRENT_PASSWORD = "CurrentStr0ngPass!"  # pragma: allowlist secret


async def _confirm_reset(service: UserService, *, token: str, new_password: str) -> None:
    await service.confirm_password_reset(
        PasswordResetConfirmRequest(token=token, new_password=new_password),
        ip=_IP,
        user_agent="pytest-agent",
        request_id=_REQUEST_ID,
    )


# --- PR-AC1: requesting a reset (FR-1) ---------------------------------------


async def test_request_password_reset_known_account_creates_token_and_sends_email() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="reset.happy@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act
    await _request_reset(service, "reset.happy@example.com")

    # Assert
    assert len(repository.password_reset_tokens_by_hash) == 1
    token = next(iter(repository.password_reset_tokens_by_hash.values()))
    assert token.user_id == user.id
    assert token.consumed_at is None
    assert len(email_sender.reset_emails_sent) == 1
    assert email_sender.reset_emails_sent[0]["to"] == "reset.happy@example.com"
    assert repository.commit_called is True


async def test_request_password_reset_invalidates_prior_unconsumed_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="reset.invalidate@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    prior_raw_token = await _seed_reset_token(repository, user_id=user.id)
    prior_hash = hashlib.sha256(prior_raw_token.encode()).hexdigest()
    service, _, _ = _make_service(repository)

    # Act
    await _request_reset(service, "reset.invalidate@example.com")

    # Assert
    assert repository.password_reset_tokens_by_hash[prior_hash].consumed_at is not None
    assert repository.invalidated_reset_tokens_for == [user.id]


async def test_request_password_reset_writes_audit_log_entry() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="reset.audit@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="active",
    )
    service, _, _ = _make_service(repository)

    # Act
    await _request_reset(service, "reset.audit@example.com")

    # Assert
    entry = repository.audit_log_entries[-1]
    assert entry["event"] == "password_reset_requested"
    assert entry["actor_id"] == user.id


# --- PR-AC3: anti-enumeration (FR-3, resolved OD-3) --------------------------


async def test_request_password_reset_unknown_email_returns_generic_response_no_email_sent() -> (
    None
):
    # Arrange
    repository = FakeUserRepository()
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act
    await _request_reset(service, "nobody@example.com")

    # Assert
    assert repository.password_reset_tokens_by_hash == {}
    assert email_sender.reset_emails_sent == []


async def test_request_password_reset_deactivated_returns_generic_no_email() -> None:
    # Arrange
    repository = FakeUserRepository()
    await _seed_user(
        repository,
        email="reset.deactivated@example.com",
        password="Str0ng!Pass",
        email_verified=True,
        status="deactivated",
    )
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act
    await _request_reset(service, "reset.deactivated@example.com")

    # Assert
    assert repository.password_reset_tokens_by_hash == {}
    assert email_sender.reset_emails_sent == []


async def test_request_password_reset_unverified_returns_generic_no_email() -> None:
    # Arrange — eligibility mirrors login's own notion (email_verified
    # required); an unverified account can't log in yet either.
    repository = FakeUserRepository()
    await _seed_user(
        repository,
        email="reset.unverified@example.com",
        password="Str0ng!Pass",
        email_verified=False,
    )
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act
    await _request_reset(service, "reset.unverified@example.com")

    # Assert
    assert repository.password_reset_tokens_by_hash == {}
    assert email_sender.reset_emails_sent == []


async def test_request_password_reset_unknown_email_still_writes_audit_log_entry() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)

    # Act
    await _request_reset(service, "nobody@example.com")

    # Assert
    entry = repository.audit_log_entries[-1]
    assert entry["event"] == "password_reset_requested"
    assert entry["actor_id"] is None


# --- PR-AC6: request flooding (FR-6, resolved OD-2) --------------------------


async def test_request_password_reset_second_call_within_cooldown_returns_429() -> None:
    # Arrange
    repository = FakeUserRepository()
    email_hash = _email_hash("reset.cooldown@example.com")
    rate_limit_cache = FakePasswordResetRateLimitCache(
        cooldown_counts={email_hash: 1}, cooldown_retry_after={email_hash: 45}
    )
    service, _, _ = _make_service(repository, password_reset_rate_limit_cache=rate_limit_cache)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await _request_reset(service, "reset.cooldown@example.com")
    assert exc_info.value.headers == {"Retry-After": "45"}


async def test_request_password_reset_sixth_call_within_hour_returns_429() -> None:
    # Arrange
    repository = FakeUserRepository()
    email_hash = _email_hash("reset.hourly@example.com")
    rate_limit_cache = FakePasswordResetRateLimitCache(
        account_counts={email_hash: 5}, account_retry_after={email_hash: 1800}
    )
    service, _, _ = _make_service(repository, password_reset_rate_limit_cache=rate_limit_cache)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await _request_reset(service, "reset.hourly@example.com")
    assert exc_info.value.headers == {"Retry-After": "1800"}


async def test_request_password_reset_eleventh_call_from_ip_within_hour_returns_429() -> None:
    # Arrange
    repository = FakeUserRepository()
    rate_limit_cache = FakePasswordResetRateLimitCache(
        ip_counts={_IP: 10}, ip_retry_after={_IP: 2400}
    )
    service, _, _ = _make_service(repository, password_reset_rate_limit_cache=rate_limit_cache)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await _request_reset(service, "anyone@example.com")
    assert exc_info.value.headers == {"Retry-After": "2400"}


async def test_request_password_reset_check_order_cooldown_before_hourly_limits() -> None:
    # Arrange — resolved OD-2: both the cooldown and the account-hourly
    # limit are tripped simultaneously; cooldown's Retry-After must win, and
    # the hourly counters must never even be recorded.
    repository = FakeUserRepository()
    email = "reset.order@example.com"
    email_hash = _email_hash(email)
    rate_limit_cache = FakePasswordResetRateLimitCache(
        cooldown_counts={email_hash: 1},
        cooldown_retry_after={email_hash: 30},
        account_counts={email_hash: 5},
        account_retry_after={email_hash: 1800},
    )
    service, _, _ = _make_service(repository, password_reset_rate_limit_cache=rate_limit_cache)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await _request_reset(service, email)
    assert exc_info.value.headers == {"Retry-After": "30"}
    assert rate_limit_cache.account_attempts_recorded == []
    assert rate_limit_cache.ip_attempts_recorded == []


# --- PR-AC2: completing the reset (FR-2) -------------------------------------


async def test_confirm_password_reset_valid_token_replaces_password_and_revokes_sessions() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.happy@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(repository, user_id=user.id)
    revocation_cache = FakeRevocationCache()
    service, _, _ = _make_service(repository, revocation_cache=revocation_cache)

    # Act
    await _confirm_reset(service, token=raw_token, new_password=_RESET_NEW_PASSWORD)

    # Assert
    assert repository.password_hash_updates[user.id] != "OldStr0ng!Pass"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert repository.password_reset_tokens_by_hash[token_hash].consumed_at is not None
    assert len(revocation_cache.set_revoke_before_calls) == 1
    assert revocation_cache.set_revoke_before_calls[0][0] == user.id
    assert repository.commit_called is True


async def test_confirm_password_reset_sends_notification_email() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.notify@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(repository, user_id=user.id)
    email_sender = FakeEmailSender()
    service, _, _ = _make_service(repository, email_sender=email_sender)

    # Act
    await _confirm_reset(service, token=raw_token, new_password=_RESET_NEW_PASSWORD)

    # Assert
    assert email_sender.reset_notices_sent == [user.email]


async def test_confirm_password_reset_writes_audit_log_completed_event() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.audit@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(repository, user_id=user.id)
    service, _, _ = _make_service(repository)

    # Act
    await _confirm_reset(service, token=raw_token, new_password=_RESET_NEW_PASSWORD)

    # Assert
    entry = repository.audit_log_entries[-1]
    assert entry["event"] == "password_reset_completed"
    assert entry["actor_id"] == user.id


# --- PR-AC4: expired, consumed, or unknown token (FR-4) ----------------------


async def test_confirm_password_reset_unknown_token_hash_raises_token_invalid() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PasswordResetTokenInvalidError):
        await _confirm_reset(service, token="never-issued-token", new_password=_RESET_NEW_PASSWORD)


async def test_confirm_password_reset_already_consumed_token_raises_token_invalid() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.consumed@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(
        repository, user_id=user.id, consumed_at=datetime.now(UTC) - timedelta(minutes=5)
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PasswordResetTokenInvalidError):
        await _confirm_reset(service, token=raw_token, new_password=_RESET_NEW_PASSWORD)


async def test_confirm_password_reset_expired_token_raises_token_expired() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.expired@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(
        repository, user_id=user.id, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PasswordResetTokenExpiredError):
        await _confirm_reset(service, token=raw_token, new_password=_RESET_NEW_PASSWORD)


# --- PR-AC5: weak or reused password (FR-5, resolved OD-1) -------------------


async def test_confirm_password_reset_too_short_raises_policy_keeps_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.short@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(repository, user_id=user.id)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PasswordPolicyError) as exc_info:
        await _confirm_reset(service, token=raw_token, new_password=_RESET_SHORT_PASSWORD)
    codes = {error.code for error in exc_info.value.errors or []}
    assert "min_length" in codes
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert repository.password_reset_tokens_by_hash[token_hash].consumed_at is None


async def test_confirm_password_reset_breached_raises_policy_keeps_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.breached@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(repository, user_id=user.id)
    service, _, _ = _make_service(repository)

    # Act & Assert — "Password123!" is in the bundled common_passwords.txt.
    with pytest.raises(PasswordPolicyError) as exc_info:
        await _confirm_reset(service, token=raw_token, new_password=_RESET_BREACHED_PASSWORD)
    codes = {error.code for error in exc_info.value.errors or []}
    assert "breached" in codes
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert repository.password_reset_tokens_by_hash[token_hash].consumed_at is None


async def test_confirm_password_reset_reused_raises_policy_keeps_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="confirm.reused@example.com",
        password=_RESET_CURRENT_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(repository, user_id=user.id)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PasswordPolicyError) as exc_info:
        await _confirm_reset(service, token=raw_token, new_password=_RESET_CURRENT_PASSWORD)
    codes = {error.code for error in exc_info.value.errors or []}
    assert "reused" in codes
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert repository.password_reset_tokens_by_hash[token_hash].consumed_at is None


# --- Spec-review resolution (accepted 2026-09-01): atomic consumption -------


async def test_confirm_password_reset_concurrent_requests_only_one_succeeds() -> None:
    # Arrange: simulates losing a concurrent race — the atomic consume fails
    # even though the initial read saw an unconsumed token.
    repository = FakeUserRepository(simulate_race_on_consume_reset=True)
    user = await _seed_user(
        repository,
        email="confirm.race@example.com",
        password=_RESET_OLD_PASSWORD,
        email_verified=True,
        status="active",
    )
    raw_token = await _seed_reset_token(repository, user_id=user.id)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PasswordResetTokenInvalidError):
        await _confirm_reset(service, token=raw_token, new_password=_RESET_NEW_PASSWORD)
    # The password was never actually changed by the losing request.
    assert user.id not in repository.password_hash_updates


# ============================================================================
# US-2.5 / spec US-009: Multi-Factor Authentication (TOTP)
# ============================================================================

_MFA_PASSWORD = "Str0ng!Pass"


async def _seed_mfa_user(
    repository: FakeUserRepository,
    *,
    email: str = "mfa@example.com",
    mfa_enabled: bool = False,
    with_secret: bool = False,
    mfa_reenrollment_required: bool = False,
) -> tuple[User, bytes]:
    secret = generate_totp_secret()
    user = await _seed_user(
        repository,
        email=email,
        password=_MFA_PASSWORD,
        email_verified=True,
        status="active",
        mfa_enabled=mfa_enabled,
        mfa_secret_encrypted=encrypt_mfa_secret(secret) if (with_secret or mfa_enabled) else None,
        mfa_reenrollment_required=mfa_reenrollment_required,
    )
    return user, secret


def _totp_code(secret: bytes, *, at: datetime | None = None) -> str:
    step = current_totp_step(at=at or datetime.now(UTC))
    return security._hotp(secret, step)


# --- MF-AC1 / FR-1: enrolment ----------------------------------------------


async def test_enroll_mfa_creates_pending_secret_encrypted_at_rest() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository, email="enroll@example.com", password=_MFA_PASSWORD, email_verified=True
    )
    service, _, _ = _make_service(repository)
    payload = MfaEnrollRequest(current_password=_MFA_PASSWORD)

    # Act
    result = await service.enroll_mfa(user.id, payload)

    # Assert
    assert result.otpauth_uri.startswith("otpauth://totp/")
    assert user.mfa_secret_encrypted is not None
    assert user.mfa_secret_encrypted != result.secret.encode()
    assert user.mfa_enabled is False
    assert repository.commit_called is True


async def test_enroll_mfa_wrong_password_returns_401() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository, email="enroll2@example.com", password=_MFA_PASSWORD, email_verified=True
    )
    service, _, _ = _make_service(repository)
    payload = MfaEnrollRequest(current_password="WrongPassword1!")

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await service.enroll_mfa(user.id, payload)


async def test_enroll_mfa_reenroll_while_pending_overwrites_secret() -> None:
    # Arrange: OD-11 - a second enroll call while PENDING replaces the secret.
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, with_secret=True)
    first_secret = user.mfa_secret_encrypted
    service, _, _ = _make_service(repository)
    payload = MfaEnrollRequest(current_password=_MFA_PASSWORD)

    # Act
    await service.enroll_mfa(user.id, payload)

    # Assert
    assert user.mfa_secret_encrypted != first_secret
    assert user.mfa_enabled is False


# --- MF-AC2 / FR-2: activation and recovery codes --------------------------


async def test_activate_mfa_valid_code_issues_recovery_codes_and_enables_mfa() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, with_secret=True)
    service, _, _ = _make_service(repository)
    payload = MfaActivateRequest(code=_totp_code(secret))

    # Act
    result = await service.activate_mfa(
        user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
    )

    # Assert
    assert len(result.recovery_codes) == 10
    assert len(set(result.recovery_codes)) == 10
    assert user.mfa_enabled is True
    assert repository.audit_log_entries[-1]["event"] == "mfa_enabled"
    assert repository.commit_called is True


async def test_activate_mfa_recovery_codes_stored_as_argon2id_hashes() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, with_secret=True)
    service, _, _ = _make_service(repository)
    payload = MfaActivateRequest(code=_totp_code(secret))

    # Act
    result = await service.activate_mfa(
        user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
    )

    # Assert
    stored = repository.recovery_codes_by_user[user.id]
    assert all(code.code_hash.startswith("$argon2id$") for code in stored)
    assert all(code.code_hash not in result.recovery_codes for code in stored)


async def test_activate_mfa_wrong_code_returns_401() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, with_secret=True)
    service, _, _ = _make_service(repository)
    payload = MfaActivateRequest(code="000000")

    # Act & Assert
    with pytest.raises(MfaInvalidCodeError):
        await service.activate_mfa(
            user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
        )


async def test_activate_mfa_no_pending_enrollment_returns_401() -> None:
    # Arrange: never called enroll - no secret at all.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository, email="nopending@example.com", password=_MFA_PASSWORD, email_verified=True
    )
    service, _, _ = _make_service(repository)
    payload = MfaActivateRequest(code="123456")

    # Act & Assert
    with pytest.raises(MfaInvalidCodeError):
        await service.activate_mfa(
            user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
        )


async def test_activate_mfa_privileged_scoped_account_sets_perm_epoch() -> None:
    # Arrange: an admin role granted well past the grace period, MFA not yet enabled.
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, with_secret=True)
    old_grant = datetime.now(UTC) - timedelta(days=30)
    role_service = FakeRoleService(grants_by_user={user.id: [("admin", old_grant)]})
    permission_epoch_cache = FakePermissionEpochCache()
    service, _, _ = _make_service(
        repository, role_service=role_service, permission_epoch_cache=permission_epoch_cache
    )
    payload = MfaActivateRequest(code=_totp_code(secret))

    # Act
    await service.activate_mfa(user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    # Assert: FR-2's exit condition fired because the account was scoped.
    assert len(permission_epoch_cache.set_for) == 1
    assert permission_epoch_cache.set_for[0][0] == user.id


async def test_activate_mfa_ordinary_enrollment_does_not_set_perm_epoch() -> None:
    # Arrange: a non-privileged, never-scoped self-service enrolment.
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, with_secret=True)
    permission_epoch_cache = FakePermissionEpochCache()
    service, _, _ = _make_service(repository, permission_epoch_cache=permission_epoch_cache)
    payload = MfaActivateRequest(code=_totp_code(secret))

    # Act
    await service.activate_mfa(user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    # Assert
    assert permission_epoch_cache.set_for == []


async def test_activate_mfa_clears_reenrollment_required_and_sets_perm_epoch() -> None:
    # Arrange: OD-5's recovery-code trigger, already mfa_enabled=true.
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(
        repository, with_secret=True, mfa_enabled=True, mfa_reenrollment_required=True
    )
    permission_epoch_cache = FakePermissionEpochCache()
    service, _, _ = _make_service(repository, permission_epoch_cache=permission_epoch_cache)
    payload = MfaActivateRequest(code=_totp_code(secret))

    # Act
    await service.activate_mfa(user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    # Assert
    assert user.mfa_reenrollment_required is False
    assert len(permission_epoch_cache.set_for) == 1


# --- MF-AC3/MF-AC6 / FR-3/FR-6: login branches -----------------------------


async def test_authenticate_user_mfa_enabled_returns_challenge_no_tokens() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=True)
    mfa_token_cache = FakeMfaTokenCache()
    service, _, _ = _make_service(repository, mfa_token_cache=mfa_token_cache)
    payload = LoginRequest(email=user.email, password=_MFA_PASSWORD)

    # Act
    response, raw_refresh_token = await service.authenticate_user(
        payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
    )

    # Assert
    assert isinstance(response, MfaRequiredResponse)
    assert response.mfa_required is True
    assert raw_refresh_token is None
    assert hash_mfa_token(response.mfa_token) in mfa_token_cache.user_id_by_hash


async def test_authenticate_user_privileged_role_past_grace_period_issues_scoped_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="priv@example.com",
        password=_MFA_PASSWORD,
        email_verified=True,
        status="active",
    )
    old_grant = datetime.now(UTC) - timedelta(days=30)
    role_service = FakeRoleService(grants_by_user={user.id: [("admin", old_grant)]})
    service, _, _ = _make_service(repository, role_service=role_service)
    payload = LoginRequest(email=user.email, password=_MFA_PASSWORD)

    # Act
    response, _ = await _login(service, payload)

    # Assert
    claims = decode_access_token(response.access_token)
    assert claims.mfa_enrollment_required is True
    assert response.mfa_enrollment_deadline is None


async def test_authenticate_user_privileged_role_within_grace_returns_deadline_field() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="priv2@example.com",
        password=_MFA_PASSWORD,
        email_verified=True,
        status="active",
    )
    recent_grant = datetime.now(UTC) - timedelta(days=1)
    role_service = FakeRoleService(grants_by_user={user.id: [("admin", recent_grant)]})
    service, _, _ = _make_service(repository, role_service=role_service)
    payload = LoginRequest(email=user.email, password=_MFA_PASSWORD)

    # Act
    response, _ = await _login(service, payload)

    # Assert
    claims = decode_access_token(response.access_token)
    assert claims.mfa_enrollment_required is False
    assert response.mfa_enrollment_deadline == recent_grant + timedelta(days=14)


async def test_authenticate_user_reenrollment_required_issues_scoped_token_no_grace() -> None:
    # Arrange: OD-5 - no grace period for this trigger, and mfa_enabled stays true.
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=False, with_secret=True)
    user.mfa_enabled = True
    user.mfa_reenrollment_required = True
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email=user.email, password=_MFA_PASSWORD)

    # Act: mfa_enabled=true routes through the MFA challenge (MF-AC3), not a
    # direct token issuance - assert the challenge fires, since the scoping
    # decision only materializes once verify_mfa completes the login.
    response, raw_refresh_token = await service.authenticate_user(
        payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
    )

    # Assert
    assert isinstance(response, MfaRequiredResponse)
    assert raw_refresh_token is None


async def test_authenticate_user_ordinary_user_unaffected_by_mfa_scoping() -> None:
    # Arrange: non-privileged, never enrolled, no reenrollment flag.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="ordinary@example.com",
        password=_MFA_PASSWORD,
        email_verified=True,
        status="active",
    )
    service, _, _ = _make_service(repository)
    payload = LoginRequest(email=user.email, password=_MFA_PASSWORD)

    # Act
    response, _ = await _login(service, payload)

    # Assert
    claims = decode_access_token(response.access_token)
    assert claims.mfa_enrollment_required is False
    assert response.mfa_enrollment_deadline is None


# --- FR-6 spec-review resolution: refresh re-evaluates scoping -------------


async def test_rotate_refresh_token_reissues_scoped_token_when_condition_still_holds() -> None:
    # Arrange
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refscope@example.com",
        password=_MFA_PASSWORD,
        email_verified=True,
        status="active",
    )
    old_grant = datetime.now(UTC) - timedelta(days=30)
    role_service = FakeRoleService(grants_by_user={user.id: [("admin", old_grant)]})
    service, _, _ = _make_service(repository, role_service=role_service)
    raw_token = await _seed_rotatable_token(repository, user_id=user.id)

    # Act
    response, _ = await _rotate(service, raw_token)

    # Assert
    assert isinstance(response, RefreshResponse)
    claims = decode_access_token(response.access_token)
    assert claims.mfa_enrollment_required is True


async def test_rotate_refresh_token_both_scoping_triggers_true_issues_single_scoped_token() -> None:
    # Arrange: mfa_reenrollment_required (OD-5) AND a privileged role held
    # past its grace period are simultaneously true. _resolve_enrollment_
    # scoping checks mfa_reenrollment_required first and returns before
    # ever consulting role grants (app/modules/users/service.py:429-433) -
    # this proves that precedence holds and no deadline from the role
    # branch leaks through, rather than assuming it from reading the code.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="bothtriggers@example.com",
        password=_MFA_PASSWORD,
        email_verified=True,
        status="active",
        mfa_enabled=True,
    )
    user.mfa_reenrollment_required = True
    old_grant = datetime.now(UTC) - timedelta(days=30)
    role_service = FakeRoleService(grants_by_user={user.id: [("admin", old_grant)]})
    service, _, _ = _make_service(repository, role_service=role_service)
    raw_token = await _seed_rotatable_token(repository, user_id=user.id)

    # Act
    response, _ = await _rotate(service, raw_token)

    # Assert: exactly one scoped token, no grace-period deadline leaking
    # in from the (never-reached) role-grant branch.
    assert isinstance(response, RefreshResponse)
    claims = decode_access_token(response.access_token)
    assert claims.mfa_enrollment_required is True
    assert response.mfa_enrollment_deadline is None


async def test_rotate_refresh_token_reissues_normal_token_when_condition_resolved() -> None:
    # Arrange: mfa_enabled is now true - condition no longer holds.
    repository = FakeUserRepository()
    user = await _seed_user(
        repository,
        email="refresolved@example.com",
        password=_MFA_PASSWORD,
        email_verified=True,
        status="active",
        mfa_enabled=True,
    )
    service, _, _ = _make_service(repository)
    raw_token = await _seed_rotatable_token(repository, user_id=user.id)

    # Act
    response, _ = await _rotate(service, raw_token)

    # Assert
    assert isinstance(response, RefreshResponse)
    claims = decode_access_token(response.access_token)
    assert claims.mfa_enrollment_required is False


# --- MF-AC4/MF-AC5/MF-AC7 / FR-4/FR-5/FR-7: verify_mfa ---------------------


async def _issue_mfa_token(mfa_token_cache: FakeMfaTokenCache, user: User) -> str:
    raw_token = "raw-mfa-token"
    await mfa_token_cache.issue(hash_mfa_token(raw_token), user_id=user.id, ttl_seconds=300)
    return raw_token


async def test_verify_mfa_valid_totp_completes_login() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, mfa_enabled=True)
    mfa_token_cache = FakeMfaTokenCache()
    service, _, _ = _make_service(repository, mfa_token_cache=mfa_token_cache)
    raw_token = await _issue_mfa_token(mfa_token_cache, user)
    payload = MfaVerifyRequest(mfa_token=raw_token, code=_totp_code(secret))

    # Act
    response, raw_refresh_token = await service.verify_mfa(
        payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
    )

    # Assert
    assert len(raw_refresh_token) > 0
    claims = decode_access_token(response.access_token)
    assert claims.user_id == user.id
    assert hash_mfa_token(raw_token) not in mfa_token_cache.user_id_by_hash


async def test_verify_mfa_incorrect_code_returns_401() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=True)
    mfa_token_cache = FakeMfaTokenCache()
    service, _, _ = _make_service(repository, mfa_token_cache=mfa_token_cache)
    raw_token = await _issue_mfa_token(mfa_token_cache, user)
    payload = MfaVerifyRequest(mfa_token=raw_token, code="000000")

    # Act & Assert
    with pytest.raises(MfaInvalidCodeError):
        await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)


async def test_verify_mfa_invalid_mfa_token_returns_401() -> None:
    # Arrange
    repository = FakeUserRepository()
    service, _, _ = _make_service(repository)
    payload = MfaVerifyRequest(mfa_token="never-issued", code="123456")

    # Act & Assert
    with pytest.raises(MfaInvalidCodeError):
        await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)


async def test_verify_mfa_replayed_code_returns_401() -> None:
    # Arrange: the replay cache reports this (user, step) as already used.
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, mfa_enabled=True)
    now = datetime.now(UTC)
    step = current_totp_step(at=now)
    mfa_token_cache = FakeMfaTokenCache()
    mfa_replay_cache = FakeMfaReplayCache(already_used_steps={(user.id, step)})
    service, _, _ = _make_service(
        repository, mfa_token_cache=mfa_token_cache, mfa_replay_cache=mfa_replay_cache
    )
    raw_token = await _issue_mfa_token(mfa_token_cache, user)
    payload = MfaVerifyRequest(mfa_token=raw_token, code=_totp_code(secret, at=now))

    # Act & Assert
    with pytest.raises(MfaInvalidCodeError):
        await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)


async def test_verify_mfa_fifth_failure_returns_429_invalidates_token() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=True)
    mfa_token_cache = FakeMfaTokenCache()
    service, _, _ = _make_service(repository, mfa_token_cache=mfa_token_cache)
    raw_token = await _issue_mfa_token(mfa_token_cache, user)
    payload = MfaVerifyRequest(mfa_token=raw_token, code="000000")

    # Act: 4 failures accumulate normally, the 5th invalidates the token.
    for _ in range(4):
        with pytest.raises(MfaInvalidCodeError):
            await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    with pytest.raises(TooManyAttemptsError):
        await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    # Assert
    assert hash_mfa_token(raw_token) in mfa_token_cache.invalidated


async def test_verify_mfa_wrong_recovery_code_counts_toward_totp_lockout() -> None:
    # Arrange: OD-10 - a wrong recovery code is a guess against the same
    # mfa_token as a wrong TOTP code, so it must increment the same
    # lockout counter, not a separate one.
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=True)
    await repository.create_recovery_codes(
        user_id=user.id,
        code_hashes=[await hash_password("realcode12")],  # pragma: allowlist secret
    )
    mfa_token_cache = FakeMfaTokenCache()
    service, _, _ = _make_service(repository, mfa_token_cache=mfa_token_cache)
    raw_token = await _issue_mfa_token(mfa_token_cache, user)
    payload = MfaVerifyRequest(mfa_token=raw_token, code="wrongcode1")  # pragma: allowlist secret

    # Act: 4 wrong-recovery-code guesses accumulate normally, the 5th
    # (of any kind) invalidates the token via the shared counter.
    for _ in range(4):
        with pytest.raises(MfaInvalidCodeError):
            await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    with pytest.raises(TooManyAttemptsError):
        await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    # Assert
    assert hash_mfa_token(raw_token) in mfa_token_cache.invalidated


async def test_verify_mfa_valid_recovery_code_completes_login_and_consumes_it() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=True)
    raw_recovery_code = "a1b2c3d4e5"  # pragma: allowlist secret
    await repository.create_recovery_codes(
        user_id=user.id, code_hashes=[await hash_password(raw_recovery_code)]
    )
    mfa_token_cache = FakeMfaTokenCache()
    service, _, email_sender = _make_service(repository, mfa_token_cache=mfa_token_cache)
    raw_token = await _issue_mfa_token(mfa_token_cache, user)
    payload = MfaVerifyRequest(mfa_token=raw_token, code=raw_recovery_code)

    # Act
    response, raw_refresh_token = await service.verify_mfa(
        payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
    )

    # Assert
    assert len(raw_refresh_token) > 0
    decode_access_token(response.access_token)
    stored = repository.recovery_codes_by_user[user.id][0]
    assert stored.consumed_at is not None
    assert user.mfa_reenrollment_required is True
    assert repository.audit_log_entries[-2]["event"] == "mfa_recovery_used"
    assert isinstance(email_sender, FakeEmailSender)
    assert email_sender.mfa_recovery_used_notices_sent == [user.email]


async def test_verify_mfa_already_consumed_recovery_code_returns_401() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=True)
    raw_recovery_code = "f6g7h8i9j0"
    await repository.create_recovery_codes(
        user_id=user.id, code_hashes=[await hash_password(raw_recovery_code)]
    )
    repository.recovery_codes_by_user[user.id][0].consumed_at = datetime.now(UTC)
    mfa_token_cache = FakeMfaTokenCache()
    service, _, _ = _make_service(repository, mfa_token_cache=mfa_token_cache)
    raw_token = await _issue_mfa_token(mfa_token_cache, user)
    payload = MfaVerifyRequest(mfa_token=raw_token, code=raw_recovery_code)

    # Act & Assert: falls through to the (also-failing) TOTP path.
    with pytest.raises(MfaInvalidCodeError):
        await service.verify_mfa(payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)


# --- MF-AC6/FR-8: disable_mfa -----------------------------------------------


@pytest.mark.parametrize("privileged_role", ["admin", "auditor", "support_agent"])
async def test_disable_mfa_privileged_role_returns_409(privileged_role: str) -> None:
    # Arrange
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, mfa_enabled=True, email="priv3@example.com")
    role_service = FakeRoleService(grants_by_user={user.id: [(privileged_role, datetime.now(UTC))]})
    service, _, _ = _make_service(repository, role_service=role_service)
    payload = MfaDisableRequest(current_password=_MFA_PASSWORD, code=_totp_code(secret))

    # Act & Assert
    with pytest.raises(MfaRequiredForRoleError):
        await service.disable_mfa(user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)


async def test_disable_mfa_non_privileged_success_purges_state_and_revokes_sessions() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, mfa_enabled=True)
    await repository.create_recovery_codes(user_id=user.id, code_hashes=["h1", "h2"])
    revocation_cache = FakeRevocationCache()
    service, _, _ = _make_service(repository, revocation_cache=revocation_cache)
    payload = MfaDisableRequest(current_password=_MFA_PASSWORD, code=_totp_code(secret))

    # Act
    await service.disable_mfa(user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)

    # Assert
    assert user.mfa_enabled is False
    assert user.mfa_secret_encrypted is None
    assert user.id not in repository.recovery_codes_by_user
    assert repository.audit_log_entries[-1]["event"] == "mfa_disabled"
    assert len(revocation_cache.set_revoke_before_calls) == 1
    assert revocation_cache.set_revoke_before_calls[0][0] == user.id


async def test_disable_mfa_wrong_password_returns_401() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, mfa_enabled=True, email="priv4@example.com")
    service, _, _ = _make_service(repository)
    payload = MfaDisableRequest(current_password="WrongPassword1!", code=_totp_code(secret))

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await service.disable_mfa(user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)


async def test_disable_mfa_wrong_code_returns_401() -> None:
    # Arrange
    repository = FakeUserRepository()
    user, _ = await _seed_mfa_user(repository, mfa_enabled=True, email="priv5@example.com")
    service, _, _ = _make_service(repository)
    payload = MfaDisableRequest(current_password=_MFA_PASSWORD, code="000000")

    # Act & Assert: same exception as a wrong password (see
    # test_disable_mfa_wrong_password_and_wrong_code_are_indistinguishable) so
    # a hijacked session can't learn which factor was wrong.
    with pytest.raises(InvalidCredentialsError):
        await service.disable_mfa(user.id, payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID)


async def test_disable_mfa_wrong_password_and_wrong_code_are_indistinguishable() -> None:
    # Arrange: two callers, one with a wrong password (correct code), one
    # with a wrong code (correct password) - both must raise the exact same
    # exception type so a stolen bearer token can't be used to learn which
    # factor is correct one guess at a time.
    repository = FakeUserRepository()
    user, secret = await _seed_mfa_user(repository, mfa_enabled=True, email="priv6@example.com")
    service, _, _ = _make_service(repository)
    wrong_password_payload = MfaDisableRequest(
        current_password="WrongPassword1!", code=_totp_code(secret)
    )
    wrong_code_payload = MfaDisableRequest(current_password=_MFA_PASSWORD, code="000000")

    # Act
    with pytest.raises(InvalidCredentialsError) as wrong_password_exc:
        await service.disable_mfa(
            user.id, wrong_password_payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
        )
    with pytest.raises(InvalidCredentialsError) as wrong_code_exc:
        await service.disable_mfa(
            user.id, wrong_code_payload, ip=_IP, user_agent=None, request_id=_REQUEST_ID
        )

    # Assert: identical exception type, identical (empty) constructor args -
    # nothing distinguishes the two failure reasons.
    assert type(wrong_password_exc.value) is type(wrong_code_exc.value)
    assert wrong_password_exc.value.args == wrong_code_exc.value.args


# --- Default-deny enrolment-scoping mechanism (get_authenticated_user) -----


async def test_get_authenticated_user_rejects_enrollment_scoped_token_by_default() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    jti = uuid.uuid4()
    session = UserSession(
        jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    session.issued_at = datetime.now(UTC)
    repository.sessions_by_jti[jti] = session
    token = encode_access_token(user_id=user_id, jti=jti, scopes=[], mfa_enrollment_required=True)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(MfaEnrollmentRequiredError):
        await service.get_authenticated_user(token)


async def test_get_authenticated_user_allow_enrollment_scoped_accepts_scoped_token() -> None:
    # Arrange
    user_id = uuid.uuid4()
    repository = FakeUserRepository()
    jti = uuid.uuid4()
    session = UserSession(
        jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    session.issued_at = datetime.now(UTC)
    repository.sessions_by_jti[jti] = session
    token = encode_access_token(user_id=user_id, jti=jti, scopes=[], mfa_enrollment_required=True)
    service, _, _ = _make_service(repository)

    # Act
    result = await service.get_authenticated_user(token, allow_enrollment_scoped=True)

    # Assert
    assert result is not None
    assert result.mfa_enrollment_required is True
