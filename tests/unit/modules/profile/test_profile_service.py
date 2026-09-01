import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from app.core.etag import compute_profile_etag
from app.core.security import hash_password
from app.modules.profile.exceptions import (
    DuplicateEmailError,
    ImmutableFieldError,
    PreconditionFailedError,
    PreconditionRequiredError,
    ReauthenticationRequiredError,
    TokenExpiredError,
    TokenInvalidError,
    ValidationFailedError,
)
from app.modules.profile.models import EmailChangeToken
from app.modules.profile.service import ProfileService
from app.modules.users.models import User

pytestmark = pytest.mark.unit

_ETAG_FIELDS = ("display_name", "locale", "timezone", "avatar_url", "email", "pending_email")
_FIXED_NOW = datetime(2026, 8, 29, 12, 0, 0, tzinfo=UTC)
_PASSWORD = "Str0ng!Pass1"  # pragma: allowlist secret
_WRONG_PASSWORD = "WrongPassword1!"  # pragma: allowlist secret


def _etag_for(user: User) -> str:
    return compute_profile_etag({field: getattr(user, field) for field in _ETAG_FIELDS})


async def _make_user(
    *,
    email: str = "user@example.com",
    password: str | None = None,
    display_name: str | None = None,
    locale: str | None = None,
    timezone: str | None = None,
    avatar_url: str | None = None,
    pending_email: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password=await hash_password(password or _PASSWORD),
        status="ACTIVE",
    )
    user.id = uuid.uuid4()
    user.created_at = _FIXED_NOW
    user.email_verified = True
    user.display_name = display_name
    user.locale = locale
    user.timezone = timezone
    user.avatar_url = avatar_url
    user.pending_email = pending_email
    return user


class FakeProfileRepository:
    def __init__(self) -> None:
        self.users_by_id: dict[uuid.UUID, User] = {}
        self.tokens_by_hash: dict[str, EmailChangeToken] = {}
        self.audit_entries: list[dict[str, object]] = []
        self.get_by_email_ci_calls: list[str] = []
        self.field_update_calls: list[dict[str, str]] = []
        self.commit_called = False
        self.apply_email_change_should_fail = False

    def seed(self, user: User) -> None:
        self.users_by_id[user.id] = user

    def seed_token(
        self,
        *,
        user_id: uuid.UUID,
        raw_token: str,
        expires_at: datetime,
        consumed_at: datetime | None = None,
    ) -> None:
        token = EmailChangeToken(
            user_id=user_id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=expires_at,
        )
        token.id = uuid.uuid4()
        token.consumed_at = consumed_at
        self.tokens_by_hash[token.token_hash] = token

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users_by_id.get(user_id)

    async def get_by_email_ci(self, email: str) -> User | None:
        self.get_by_email_ci_calls.append(email)
        for user in self.users_by_id.values():
            if user.email.lower() == email.lower():
                return user
        return None

    async def update_fields(self, user_id: uuid.UUID, fields: dict[str, str]) -> None:
        self.field_update_calls.append(fields)
        user = self.users_by_id[user_id]
        for key, value in fields.items():
            setattr(user, key, value)

    async def set_pending_email(self, user_id: uuid.UUID, pending_email: str) -> None:
        self.users_by_id[user_id].pending_email = pending_email

    async def apply_email_change(self, user_id: uuid.UUID, new_email: str) -> bool:
        if self.apply_email_change_should_fail:
            return False
        user = self.users_by_id[user_id]
        user.email = new_email
        user.pending_email = None
        return True

    async def create_email_change_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> EmailChangeToken:
        token = EmailChangeToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        token.id = uuid.uuid4()
        self.tokens_by_hash[token_hash] = token
        return token

    async def get_email_change_token_by_hash(self, token_hash: str) -> EmailChangeToken | None:
        return self.tokens_by_hash.get(token_hash)

    async def consume_email_change_token(self, token_id: uuid.UUID) -> bool:
        for token in self.tokens_by_hash.values():
            if token.id == token_id:
                if token.consumed_at is not None:
                    return False
                token.consumed_at = _FIXED_NOW
                return True
        return False

    async def create_audit_log_entry(
        self,
        *,
        actor_id: uuid.UUID,
        field: str,
        old_value: str | None,
        new_value: str | None,
        request_id: str,
    ) -> None:
        self.audit_entries.append(
            {
                "actor_id": actor_id,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "request_id": request_id,
            }
        )

    async def commit(self) -> None:
        self.commit_called = True


class FakeSessionRevoker:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, uuid.UUID | None]] = []

    async def revoke_other_sessions(
        self, *, user_id: uuid.UUID, except_jti: uuid.UUID | None
    ) -> None:
        self.calls.append((user_id, except_jti))


class RecordingEmailSender:
    def __init__(self) -> None:
        self.confirmations_sent: list[dict[str, str]] = []
        self.notices_sent: list[str] = []

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None:
        self.confirmations_sent.append({"to": to, "raw_token": raw_token})

    async def send_email_change_notice(self, *, to: str) -> None:
        self.notices_sent.append(to)

    async def send_refresh_reuse_alert(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_password_reset_email(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_password_reset_notice(self, *, to: str) -> None:
        raise NotImplementedError


def _make_service(
    repository: FakeProfileRepository,
    *,
    session_revoker: FakeSessionRevoker | None = None,
    email_sender: RecordingEmailSender | None = None,
    clock: Callable[[], datetime] = lambda: _FIXED_NOW,
) -> tuple[ProfileService, FakeSessionRevoker, RecordingEmailSender]:
    session_revoker = session_revoker or FakeSessionRevoker()
    email_sender = email_sender or RecordingEmailSender()
    service = ProfileService(repository, session_revoker, email_sender=email_sender, clock=clock)
    return service, session_revoker, email_sender


# --- UP-AC1: successful partial update ------------------------------------


async def test_apply_partial_update_single_field_returns_200_shape_and_new_etag() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)
    old_etag = _etag_for(user)

    # Act
    profile, new_etag, email_change_initiated = await service.apply_partial_update(
        user_id=user.id,
        raw_body={"display_name": "New Name"},
        if_match=old_etag,
        request_id="req-1",
    )

    # Assert
    assert email_change_initiated is False
    assert profile.display_name == "New Name"
    assert new_etag != old_etag
    assert repository.commit_called is True


async def test_apply_partial_update_multi_field_writes_one_audit_row_per_field() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act
    await service.apply_partial_update(
        user_id=user.id,
        raw_body={"display_name": "New Name", "locale": "en-GB"},
        if_match=_etag_for(user),
        request_id="req-2",
    )

    # Assert
    fields_logged = {entry["field"] for entry in repository.audit_entries}
    assert fields_logged == {"display_name", "locale"}
    for entry in repository.audit_entries:
        assert entry["request_id"] == "req-2"
        assert entry["actor_id"] == user.id


# --- UP-AC2/UP-AC3: concurrency ---------------------------------------------


async def test_apply_partial_update_missing_if_match_raises_precondition_required() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PreconditionRequiredError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"display_name": "New Name"},
            if_match=None,
            request_id="req-3",
        )
    assert repository.field_update_calls == []
    assert repository.commit_called is False


async def test_apply_partial_update_stale_if_match_raises_precondition_failed() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(PreconditionFailedError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"display_name": "New Name"},
            if_match='"stale-etag"',
            request_id="req-4",
        )
    assert repository.field_update_calls == []
    assert repository.commit_called is False


async def test_apply_partial_update_wildcard_if_match_always_matches() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act
    profile, _, _ = await service.apply_partial_update(
        user_id=user.id, raw_body={"display_name": "New Name"}, if_match="*", request_id="req-5"
    )

    # Assert
    assert profile.display_name == "New Name"


# --- UP-AC4/UP-AC5/UP-AC6: validation / schema strictness -------------------


async def test_apply_partial_update_invalid_locale_raises_validation_failed_naming_field() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(ValidationFailedError) as exc_info:
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"locale": "xx-XX"},
            if_match=_etag_for(user),
            request_id="req-6",
        )
    assert exc_info.value.errors is not None
    assert {error.field for error in exc_info.value.errors} == {"locale"}
    assert repository.field_update_calls == []


async def test_apply_partial_update_immutable_field_raises_immutable_field_error() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(ImmutableFieldError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"role": "admin"},
            if_match=_etag_for(user),
            request_id="req-7",
        )
    assert repository.field_update_calls == []
    assert repository.commit_called is False


async def test_apply_partial_update_unknown_field_raises_validation_failed() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"is_super_user": True},
            if_match=_etag_for(user),
            request_id="req-8",
        )
    assert repository.field_update_calls == []


async def test_apply_partial_update_current_password_without_email_raises_validation_failed() -> (
    None
):
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(ValidationFailedError) as exc_info:
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"current_password": _PASSWORD},  # pragma: allowlist secret
            if_match=_etag_for(user),
            request_id="req-9",
        )
    assert exc_info.value.errors is not None
    assert {error.field for error in exc_info.value.errors} == {"current_password"}


# --- UP-AC7: cross-user access has no reachable branch (invariant) ---------


async def test_apply_partial_update_id_in_body_is_rejected_not_used_to_retarget() -> None:
    # Arrange: a client tries to smuggle another user's id into the body —
    # the service must reject it outright rather than ever reading it as a
    # target selector (the only selector is the authenticated user_id param).
    repository = FakeProfileRepository()
    user = await _make_user()
    other_user_id = uuid.uuid4()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(ImmutableFieldError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"id": str(other_user_id), "display_name": "New Name"},
            if_match=_etag_for(user),
            request_id="req-10",
        )
    assert repository.field_update_calls == []


# --- UP-AC9: email change requires correct current_password -----------------


async def test_apply_partial_update_email_change_missing_password_raises_reauthentication() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user()
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(ReauthenticationRequiredError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"email": "new@example.com"},
            if_match=_etag_for(user),
            request_id="req-11",
        )
    assert user.pending_email is None
    assert repository.get_by_email_ci_calls == []
    assert repository.commit_called is False


async def test_apply_partial_update_email_change_wrong_password_raises_reauthentication() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user(password=_PASSWORD)  # pragma: allowlist secret
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(ReauthenticationRequiredError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={
                "email": "new@example.com",
                "current_password": _WRONG_PASSWORD,  # pragma: allowlist secret
            },
            if_match=_etag_for(user),
            request_id="req-12",
        )
    assert user.pending_email is None
    assert repository.get_by_email_ci_calls == []


# --- UP-AC10: email change initiated successfully ---------------------------


async def test_apply_partial_update_duplicate_email_raises_409_pending_email_untouched() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user(password=_PASSWORD)
    other_user = await _make_user(email="taken@example.com")
    repository.seed(user)
    repository.seed(other_user)
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(DuplicateEmailError):
        await service.apply_partial_update(
            user_id=user.id,
            raw_body={"email": "taken@example.com", "current_password": _PASSWORD},
            if_match=_etag_for(user),
            request_id="req-13",
        )
    assert user.pending_email is None


async def test_apply_partial_update_email_change_initiated_returns_true_and_issues_token() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user(password=_PASSWORD)
    repository.seed(user)
    service, _, email_sender = _make_service(repository)

    # Act
    profile, _, email_change_initiated = await service.apply_partial_update(
        user_id=user.id,
        raw_body={"email": "new@example.com", "current_password": _PASSWORD},
        if_match=_etag_for(user),
        request_id="req-14",
    )

    # Assert
    assert email_change_initiated is True
    assert profile.pending_email == "new@example.com"
    assert profile.email == "user@example.com"
    assert user.pending_email == "new@example.com"
    assert len(email_sender.confirmations_sent) == 1
    assert email_sender.confirmations_sent[0]["to"] == "new@example.com"
    assert email_sender.notices_sent == ["user@example.com"]


async def test_apply_partial_update_combined_field_and_email_change_commits_once() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user(password=_PASSWORD)
    repository.seed(user)
    service, _, _ = _make_service(repository)

    # Act
    profile, _, email_change_initiated = await service.apply_partial_update(
        user_id=user.id,
        raw_body={
            "display_name": "New Name",
            "email": "new@example.com",
            "current_password": _PASSWORD,
        },
        if_match=_etag_for(user),
        request_id="req-15",
    )

    # Assert
    assert email_change_initiated is True
    assert profile.display_name == "New Name"
    assert profile.pending_email == "new@example.com"
    assert repository.commit_called is True


# --- UP-AC11/UP-AC12: confirm-email-change ----------------------------------


async def test_confirm_email_change_valid_token_swaps_email_and_exempts_current_session() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user(pending_email="new@example.com")
    repository.seed(user)
    repository.seed_token(
        user_id=user.id, raw_token="raw-token", expires_at=_FIXED_NOW + timedelta(hours=1)
    )
    service, session_revoker, _ = _make_service(repository)

    # Act
    result = await service.confirm_email_change(
        raw_token="raw-token", authorization=None, request_id="req-16"
    )

    # Assert
    assert result.email == "new@example.com"
    assert user.email == "new@example.com"
    assert user.pending_email is None
    assert session_revoker.calls == [(user.id, None)]


async def test_confirm_email_change_unknown_token_raises_token_invalid() -> None:
    # Arrange
    repository = FakeProfileRepository()
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await service.confirm_email_change(
            raw_token="unknown", authorization=None, request_id="req-17"
        )


async def test_confirm_email_change_missing_token_raises_token_invalid() -> None:
    # Arrange
    repository = FakeProfileRepository()
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await service.confirm_email_change(raw_token=None, authorization=None, request_id="req-18")


async def test_confirm_email_change_expired_token_raises_token_expired() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user(pending_email="new@example.com")
    repository.seed(user)
    repository.seed_token(
        user_id=user.id, raw_token="raw-token", expires_at=_FIXED_NOW - timedelta(seconds=1)
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenExpiredError):
        await service.confirm_email_change(
            raw_token="raw-token", authorization=None, request_id="req-19"
        )
    assert user.email != "new@example.com"


async def test_confirm_email_change_already_consumed_token_raises_token_invalid() -> None:
    # Arrange
    repository = FakeProfileRepository()
    user = await _make_user(pending_email="new@example.com")
    repository.seed(user)
    repository.seed_token(
        user_id=user.id,
        raw_token="raw-token",
        expires_at=_FIXED_NOW + timedelta(hours=1),
        consumed_at=_FIXED_NOW,
    )
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(TokenInvalidError):
        await service.confirm_email_change(
            raw_token="raw-token", authorization=None, request_id="req-20"
        )


async def test_confirm_email_change_duplicate_email_race_raises_duplicate_email() -> None:
    # Arrange: simulates another account claiming the target address between
    # the email-change initiation and this confirmation.
    repository = FakeProfileRepository()
    user = await _make_user(pending_email="new@example.com")
    repository.seed(user)
    repository.seed_token(
        user_id=user.id, raw_token="raw-token", expires_at=_FIXED_NOW + timedelta(hours=1)
    )
    repository.apply_email_change_should_fail = True
    service, _, _ = _make_service(repository)

    # Act & Assert
    with pytest.raises(DuplicateEmailError):
        await service.confirm_email_change(
            raw_token="raw-token", authorization=None, request_id="req-21"
        )


async def test_confirm_email_change_with_valid_bearer_exempts_that_session() -> None:
    # Arrange
    from app.core.security import encode_access_token

    repository = FakeProfileRepository()
    user = await _make_user(pending_email="new@example.com")
    repository.seed(user)
    repository.seed_token(
        user_id=user.id, raw_token="raw-token", expires_at=_FIXED_NOW + timedelta(hours=1)
    )
    jti = uuid.uuid4()
    token = encode_access_token(user_id=user.id, jti=jti, scopes=[])
    service, session_revoker, _ = _make_service(repository)

    # Act
    await service.confirm_email_change(
        raw_token="raw-token", authorization=f"Bearer {token}", request_id="req-22"
    )

    # Assert
    assert session_revoker.calls == [(user.id, jti)]
