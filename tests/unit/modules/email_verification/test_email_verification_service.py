import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.email_verification.exceptions import (
    InvalidRequestError,
    TokenExpiredError,
    TokenInvalidError,
    TooManyAttemptsError,
)
from app.modules.email_verification.models import EmailVerificationToken
from app.modules.email_verification.service import EmailVerificationService
from app.modules.users.models import User

pytestmark = pytest.mark.unit

_FIXED_NOW = datetime(2026, 8, 29, 12, 0, 0, tzinfo=UTC)
_RAW_TOKEN = "raw"
_RAW_TOKEN_HASH = hashlib.sha256(_RAW_TOKEN.encode()).hexdigest()


def _make_user(*, email: str = "user@example.com", email_verified: bool = False) -> User:
    user = User(email=email, hashed_password="hash", status="PENDING_VERIFICATION")
    user.id = uuid.uuid4()
    user.email_verified = email_verified
    user.created_at = _FIXED_NOW - timedelta(days=1)
    return user


def _make_token(
    *,
    user_id: uuid.UUID,
    token_hash: str | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    consumed_at: datetime | None = None,
) -> EmailVerificationToken:
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash or hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        expires_at=expires_at or (_FIXED_NOW + timedelta(hours=24)),
    )
    token.id = uuid.uuid4()
    token.issued_at = issued_at or _FIXED_NOW
    token.consumed_at = consumed_at
    return token


class FakeEmailVerificationRepository:
    def __init__(self) -> None:
        self.users_by_email: dict[str, User] = {}
        self.tokens_by_hash: dict[str, EmailVerificationToken] = {}
        self.tokens_by_user: dict[uuid.UUID, list[EmailVerificationToken]] = {}
        self.consume_result: bool = True
        self.consumed_token_ids: list[uuid.UUID] = []
        self.verified_user_ids: list[uuid.UUID] = []
        self.created_tokens: list[dict[str, object]] = []
        self.audit_logs: list[dict[str, object]] = []
        self.deleted_user_ids: list[uuid.UUID] = []
        self.purge_candidates: list[User] = []
        self.commit_called = False

    async def get_user_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email.lower())

    async def get_latest_token_for_user(self, user_id: uuid.UUID) -> EmailVerificationToken | None:
        tokens = self.tokens_by_user.get(user_id, [])
        if not tokens:
            return None
        return max(tokens, key=lambda t: t.issued_at)

    async def get_token_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        return self.tokens_by_hash.get(token_hash)

    async def create_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> EmailVerificationToken:
        self.created_tokens.append(
            {"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at}
        )
        token = _make_token(
            user_id=user_id, token_hash=token_hash, issued_at=_FIXED_NOW, expires_at=expires_at
        )
        self.tokens_by_hash[token_hash] = token
        self.tokens_by_user.setdefault(user_id, []).append(token)
        return token

    async def consume_token(self, token_id: uuid.UUID) -> bool:
        self.consumed_token_ids.append(token_id)
        return self.consume_result

    async def mark_user_verified(self, user_id: uuid.UUID) -> None:
        self.verified_user_ids.append(user_id)

    async def find_purge_candidates(self, cutoff: datetime) -> list[User]:
        return self.purge_candidates

    async def delete_user(self, user_id: uuid.UUID) -> None:
        self.deleted_user_ids.append(user_id)

    async def create_audit_log(
        self, *, event: str, subject_user_id: uuid.UUID, detail: str
    ) -> None:
        self.audit_logs.append(
            {"event": event, "subject_user_id": subject_user_id, "detail": detail}
        )

    async def commit(self) -> None:
        self.commit_called = True


class RecordingEmailSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        self.sent.append({"to": to, "raw_token": raw_token})

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None:
        pass

    async def send_email_change_notice(self, *, to: str) -> None:
        pass

    async def send_refresh_reuse_alert(self, *, to: str) -> None:
        pass

    async def send_password_reset_email(self, *, to: str, raw_token: str) -> None:
        pass

    async def send_password_reset_notice(self, *, to: str) -> None:
        pass

    async def send_mfa_recovery_used_notice(self, *, to: str) -> None:
        pass

    async def send_invitation_email(self, *, to: str, raw_token: str) -> None:
        pass


def _make_service(
    repository: FakeEmailVerificationRepository, email_sender: RecordingEmailSender | None = None
) -> EmailVerificationService:
    return EmailVerificationService(
        repository, email_sender=email_sender or RecordingEmailSender(), clock=lambda: _FIXED_NOW
    )


# --- VE-AC1: successful verification -----------------------------------------


async def test_verify_email_valid_token_marks_user_verified() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user()
    token = _make_token(user_id=user.id)
    repository.tokens_by_hash[hashlib.sha256(b"test").hexdigest()] = token
    service = _make_service(repository)

    # Act
    result = await service.verify_email("test")

    # Assert
    assert result.email_verified is True
    assert repository.verified_user_ids == [user.id]
    assert repository.consumed_token_ids == [token.id]
    assert repository.commit_called is True


# --- VE-AC1 (race): consume_token loses the race -----------------------------


async def test_verify_email_lost_race_raises_token_invalid() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user()
    token = _make_token(user_id=user.id)
    repository.tokens_by_hash[_RAW_TOKEN_HASH] = token
    repository.consume_result = False
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await service.verify_email(_RAW_TOKEN)
    assert repository.verified_user_ids == []


# --- VE-AC2: expired token ----------------------------------------------------


async def test_verify_email_expired_token_raises_token_expired() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user()
    token = _make_token(user_id=user.id, expires_at=_FIXED_NOW - timedelta(seconds=1))
    repository.tokens_by_hash[_RAW_TOKEN_HASH] = token
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenExpiredError):
        await service.verify_email(_RAW_TOKEN)


async def test_verify_email_token_expiring_exactly_now_raises_token_expired() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user()
    token = _make_token(user_id=user.id, expires_at=_FIXED_NOW)
    repository.tokens_by_hash[_RAW_TOKEN_HASH] = token
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenExpiredError):
        await service.verify_email(_RAW_TOKEN)


# --- VE-AC3: already-consumed token ------------------------------------------


async def test_verify_email_consumed_token_raises_token_invalid() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user()
    token = _make_token(user_id=user.id, consumed_at=_FIXED_NOW - timedelta(minutes=1))
    repository.tokens_by_hash[_RAW_TOKEN_HASH] = token
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await service.verify_email(_RAW_TOKEN)


# --- VE-AC4: unknown/malformed token ------------------------------------------


async def test_verify_email_unknown_token_raises_token_invalid() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await service.verify_email("unknown-token")


@pytest.mark.parametrize("raw_token", [None, ""])
async def test_verify_email_missing_token_raises_token_invalid(raw_token: str | None) -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await service.verify_email(raw_token)


# --- VE-AC7: resend cooldown ---------------------------------------------------


async def test_resend_within_cooldown_raises_too_many_attempts() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user(email="cooldown@example.com")
    repository.users_by_email["cooldown@example.com"] = user
    repository.tokens_by_user[user.id] = [
        _make_token(user_id=user.id, issued_at=_FIXED_NOW - timedelta(seconds=30))
    ]
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(TooManyAttemptsError) as exc_info:
        await service.resend_verification("cooldown@example.com")
    assert exc_info.value.headers is not None
    assert int(exc_info.value.headers["Retry-After"]) == 30


async def test_resend_at_cooldown_boundary_is_allowed() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user(email="boundary@example.com")
    repository.users_by_email["boundary@example.com"] = user
    repository.tokens_by_user[user.id] = [
        _make_token(user_id=user.id, issued_at=_FIXED_NOW - timedelta(seconds=60))
    ]
    service = _make_service(repository)

    # Act
    result = await service.resend_verification("boundary@example.com")

    # Assert
    assert result.message == (
        "If this email is registered and unverified, a verification email has been sent."
    )


# --- VE-AC8: unregistered email ------------------------------------------------


async def test_resend_unregistered_email_returns_generic_response_no_side_effects() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    service = _make_service(repository)

    # Act
    result = await service.resend_verification("unknown@example.com")

    # Assert
    assert result.message == (
        "If this email is registered and unverified, a verification email has been sent."
    )
    assert repository.created_tokens == []


@pytest.mark.parametrize("email", [None, "", "not-an-email"])
async def test_resend_malformed_email_raises_invalid_request_before_lookup(
    email: str | None,
) -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    service = _make_service(repository)

    # Act & Assert
    with pytest.raises(InvalidRequestError):
        await service.resend_verification(email)
    assert repository.created_tokens == []


# --- VE-AC9: already-verified account ------------------------------------------


async def test_resend_already_verified_account_returns_generic_response_no_new_token() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user(email="verified@example.com", email_verified=True)
    repository.users_by_email["verified@example.com"] = user
    service = _make_service(repository)

    # Act
    result = await service.resend_verification("verified@example.com")

    # Assert
    assert result.message == (
        "If this email is registered and unverified, a verification email has been sent."
    )
    assert repository.created_tokens == []


# --- resend happy path ---------------------------------------------------------


async def test_resend_happy_path_issues_token_and_sends_email() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user(email="fresh@example.com")
    repository.users_by_email["fresh@example.com"] = user
    email_sender = RecordingEmailSender()
    service = _make_service(repository, email_sender=email_sender)

    # Act
    result = await service.resend_verification("fresh@example.com")

    # Assert
    assert result.message == (
        "If this email is registered and unverified, a verification email has been sent."
    )
    assert len(repository.created_tokens) == 1
    assert repository.commit_called is True
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "fresh@example.com"


# --- issue_pending_token --------------------------------------------------------


async def test_issue_pending_token_creates_token_matching_returned_raw_value() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    user = _make_user()
    service = _make_service(repository)

    # Act
    raw_token = await service.issue_pending_token(user.id)

    # Assert
    assert len(repository.created_tokens) == 1
    assert repository.created_tokens[0]["user_id"] == user.id
    import hashlib

    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert repository.created_tokens[0]["token_hash"] == expected_hash
    assert repository.commit_called is True


# --- VE-AC10: purge -------------------------------------------------------------


async def test_purge_unverified_accounts_deletes_candidates_and_writes_audit_log() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    stale_user = _make_user(email="stale@example.com")
    repository.purge_candidates = [stale_user]
    service = _make_service(repository)

    # Act
    count = await service.purge_unverified_accounts()

    # Assert
    assert count == 1
    assert repository.deleted_user_ids == [stale_user.id]
    assert len(repository.audit_logs) == 1
    assert repository.audit_logs[0]["event"] == "unverified_account_purged"
    assert repository.audit_logs[0]["subject_user_id"] == stale_user.id
    assert repository.commit_called is True


async def test_purge_unverified_accounts_no_candidates_is_noop() -> None:
    # Arrange
    repository = FakeEmailVerificationRepository()
    service = _make_service(repository)

    # Act
    count = await service.purge_unverified_accounts()

    # Assert
    assert count == 0
    assert repository.deleted_user_ids == []
    assert repository.audit_logs == []
