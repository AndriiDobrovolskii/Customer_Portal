import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import (
    decode_access_token,
    encode_access_token,
    hash_password,
    hash_refresh_token,
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
from app.modules.users.schemas import LoginRequest, LoginResponse, UserCreate, UserStatus
from app.modules.users.service import UserService

pytestmark = pytest.mark.unit

_IP = "203.0.113.10"
_REQUEST_ID = "test-request-id"


class FakeUserRepository:
    def __init__(
        self, *, existing_emails: set[str] | None = None, simulate_race_on_consume: bool = False
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
        # RT-AC6: simulates a concurrent winner consuming this token between
        # this fake's own initial read and its atomic-consume call — the
        # first consume_refresh_token call sets consumed_at (as if another
        # request just won) and returns None (this request lost the race).
        self.simulate_race_on_consume = simulate_race_on_consume

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
    def __init__(self, *, raises: bool = False, raises_reuse_alert: bool = False) -> None:
        self.raises = raises
        self.raises_reuse_alert = raises_reuse_alert
        self.sent: list[dict[str, str]] = []
        self.reuse_alerts_sent: list[str] = []

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


def _make_service(
    repository: FakeUserRepository,
    issuer: FakeVerificationTokenIssuer | None = None,
    email_sender: FakeEmailSender | None = None,
    revocation_cache: FakeRevocationCache | None = None,
    throttle_cache: FakeLoginThrottleCache | None = None,
    account_service: FakeAccountService | None = None,
    refresh_rate_limit_cache: FakeRefreshRateLimitCache | None = None,
) -> tuple[UserService, FakeVerificationTokenIssuer, FakeEmailSender]:
    issuer = issuer or FakeVerificationTokenIssuer()
    email_sender = email_sender or FakeEmailSender()
    revocation_cache = revocation_cache or FakeRevocationCache()
    throttle_cache = throttle_cache or FakeLoginThrottleCache()
    account_service = account_service or FakeAccountService()
    refresh_rate_limit_cache = refresh_rate_limit_cache or FakeRefreshRateLimitCache()
    service = UserService(
        repository,
        issuer,
        email_sender,
        revocation_cache,
        throttle_cache,
        account_service,
        refresh_rate_limit_cache,
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
) -> User:
    user = User(email=email, hashed_password=await hash_password(password), status=status)
    user.id = uuid.uuid4()
    user.email_verified = email_verified
    user.deactivated_at = deactivated_at
    repository.users_by_email[email.lower()] = user
    return user


async def _login(service: UserService, payload: LoginRequest) -> tuple[LoginResponse, str]:
    return await service.authenticate_user(
        payload, ip=_IP, user_agent="pytest-agent", request_id=_REQUEST_ID
    )


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
    return encode_access_token(user_id=user_id, jti=jti)


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
    token = encode_access_token(user_id=uuid.uuid4(), jti=uuid.uuid4())
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
