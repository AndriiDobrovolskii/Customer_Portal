import hashlib
import logging
import secrets
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.email import EmailSender, LoggingEmailSender
from app.core.etag import compute_profile_etag
from app.core.exceptions import FieldError
from app.core.security import InvalidTokenError, decode_access_token, verify_password
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
from app.modules.profile.schemas import ConfirmEmailChangeResponse, ProfileRead, ProfileUpdate
from app.modules.users.models import User

logger = logging.getLogger(__name__)

_TOKEN_BYTES = 32

# Columns tracked by the ETag — every field the profile module can change,
# whether directly (the editable whitelist) or indirectly (pending_email via
# the email-change flow, email via confirmation).
_ETAG_FIELDS = ("display_name", "locale", "timezone", "avatar_url", "email", "pending_email")

# The story's immutable set (id, created_at, role, email_verified) plus
# pending_email, which is system-derived and never legitimately
# client-writable even though the story doesn't name it explicitly.
_IMMUTABLE_FIELD_NAMES = frozenset({"id", "created_at", "role", "email_verified", "pending_email"})
_EDITABLE_FIELD_NAMES = frozenset({"display_name", "locale", "timezone", "avatar_url"})


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _etag_fields(user: User) -> dict[str, str | None]:
    return {field: getattr(user, field) for field in _ETAG_FIELDS}


def _convert_validation_error(exc: ValidationError) -> list[FieldError]:
    return [
        FieldError(
            field=str(error["loc"][-1]) if error["loc"] else "body",
            message=error["msg"],
            code=error["type"],
        )
        for error in exc.errors()
    ]


def _resolve_exempt_jti(authorization: str | None) -> uuid.UUID | None:
    """Best-effort: an absent or invalid header simply exempts no session —
    it must never fail the (Auth: None) confirm-email-change endpoint."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return decode_access_token(token).jti
    except InvalidTokenError:
        return None


class ProfileRepositoryProtocol(Protocol):
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email_ci(self, email: str) -> User | None: ...

    async def update_fields(self, user_id: uuid.UUID, fields: dict[str, str]) -> None: ...

    async def set_pending_email(self, user_id: uuid.UUID, pending_email: str) -> None: ...

    async def apply_email_change(self, user_id: uuid.UUID, new_email: str) -> bool: ...

    async def create_email_change_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> EmailChangeToken: ...

    async def get_email_change_token_by_hash(self, token_hash: str) -> EmailChangeToken | None: ...

    async def consume_email_change_token(self, token_id: uuid.UUID) -> bool: ...

    async def create_audit_log_entry(
        self,
        *,
        actor_id: uuid.UUID,
        field: str,
        old_value: str | None,
        new_value: str | None,
        request_id: str,
    ) -> None: ...

    async def commit(self) -> None: ...


class SessionRevokerProtocol(Protocol):
    async def revoke_other_sessions(
        self, *, user_id: uuid.UUID, except_jti: uuid.UUID | None
    ) -> None: ...


class ProfileService:
    def __init__(
        self,
        repository: ProfileRepositoryProtocol,
        session_revoker: SessionRevokerProtocol,
        email_sender: EmailSender | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._session_revoker = session_revoker
        self._email_sender = email_sender or LoggingEmailSender()
        self._clock = clock

    async def apply_partial_update(
        self,
        *,
        user_id: uuid.UUID,
        raw_body: Mapping[str, object],
        if_match: str | None,
        request_id: str,
    ) -> tuple[ProfileRead, str, bool]:
        """Returns (profile, etag, email_change_initiated)."""
        # UP-AC7: the target user is derived solely from `user_id` (the
        # authenticated session) — no path/body parameter can redirect this
        # to another user's row, so cross-user access has no reachable branch
        # to test beyond this invariant. See the accompanying unit test.
        user = await self._repository.get_by_id(user_id)
        if user is None:
            # Unreachable in practice: user_sessions has ON DELETE CASCADE on
            # users.id, so a session that authenticated this request cannot
            # outlive its user. A 500 here would mean that invariant broke.
            msg = "authenticated session references a user that no longer exists"
            raise RuntimeError(msg)

        if if_match is None:
            raise PreconditionRequiredError

        current_etag = compute_profile_etag(_etag_fields(user))
        if if_match not in ("*", current_etag):
            raise PreconditionFailedError

        if set(raw_body) & _IMMUTABLE_FIELD_NAMES:
            raise ImmutableFieldError

        try:
            payload = ProfileUpdate.model_validate(raw_body)
        except ValidationError as exc:
            raise ValidationFailedError(errors=_convert_validation_error(exc)) from exc

        if payload.current_password is not None and payload.email is None:
            raise ValidationFailedError(
                errors=[
                    FieldError(
                        field="current_password",
                        message="current_password may only be submitted together with email.",
                        code="unknown_field",
                    )
                ]
            )

        changes = payload.model_dump(exclude_unset=True, exclude={"current_password", "email"})
        field_updates: dict[str, str] = {
            key: str(value)
            for key, value in changes.items()
            if key in _EDITABLE_FIELD_NAMES and value is not None
        }

        email_change_initiated = False
        new_email: str | None = None
        raw_token: str | None = None

        if payload.email is not None:
            password = (
                payload.current_password.get_secret_value() if payload.current_password else ""
            )
            if not await verify_password(password, user.hashed_password):
                raise ReauthenticationRequiredError

            existing = await self._repository.get_by_email_ci(payload.email)
            if existing is not None and existing.id != user.id:
                raise DuplicateEmailError

            new_email = payload.email
            email_change_initiated = True

        old_values = {key: getattr(user, key) for key in field_updates}

        if field_updates:
            await self._repository.update_fields(user_id, field_updates)

        if email_change_initiated and new_email is not None:
            await self._repository.set_pending_email(user_id, new_email)
            raw_token = await self._issue_email_change_token(user_id, new_email)

        for field, new_value in field_updates.items():
            await self._repository.create_audit_log_entry(
                actor_id=user_id,
                field=field,
                old_value=old_values[field],
                new_value=new_value,
                request_id=request_id,
            )
        if email_change_initiated:
            await self._repository.create_audit_log_entry(
                actor_id=user_id,
                field="pending_email",
                old_value=user.pending_email,
                new_value=new_email,
                request_id=request_id,
            )

        await self._repository.commit()

        final_fields = _etag_fields(user)
        final_fields.update(field_updates)
        if email_change_initiated:
            final_fields["pending_email"] = new_email
        new_etag = compute_profile_etag(final_fields)

        profile = ProfileRead(
            id=user.id,
            email=user.email,
            pending_email=new_email if email_change_initiated else user.pending_email,
            display_name=field_updates.get("display_name", user.display_name),
            locale=field_updates.get("locale", user.locale),
            timezone=field_updates.get("timezone", user.timezone),
            avatar_url=field_updates.get("avatar_url", user.avatar_url),
            email_verified=user.email_verified,
            created_at=user.created_at,
        )

        if email_change_initiated and new_email is not None and raw_token is not None:
            # Best-effort, mirrors UserService.register_user: the change is
            # already committed and must not be rolled back by a mail failure.
            try:
                await self._email_sender.send_email_change_confirmation(
                    to=new_email, raw_token=raw_token
                )
                await self._email_sender.send_email_change_notice(to=user.email)
            except Exception:
                logger.exception("failed to dispatch email-change notifications")

        return profile, new_etag, email_change_initiated

    async def _issue_email_change_token(self, user_id: uuid.UUID, new_email: str) -> str:
        settings = get_settings()
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        expires_at = self._clock() + timedelta(hours=settings.email_change_token_ttl_hours)
        await self._repository.create_email_change_token(
            user_id=user_id, token_hash=_hash_token(raw_token), expires_at=expires_at
        )
        return raw_token

    async def confirm_email_change(
        self, *, raw_token: str | None, authorization: str | None, request_id: str
    ) -> ConfirmEmailChangeResponse:
        if not raw_token:
            raise TokenInvalidError

        token_hash = _hash_token(raw_token)
        token = await self._repository.get_email_change_token_by_hash(token_hash)
        if token is None or token.consumed_at is not None:
            raise TokenInvalidError
        if token.expires_at <= self._clock():
            raise TokenExpiredError

        won_race = await self._repository.consume_email_change_token(token.id)
        if not won_race:
            raise TokenInvalidError

        user = await self._repository.get_by_id(token.user_id)
        if user is None or user.pending_email is None:
            raise TokenInvalidError

        new_email = user.pending_email
        old_email = user.email
        applied = await self._repository.apply_email_change(token.user_id, new_email)
        if not applied:
            raise DuplicateEmailError

        await self._repository.create_audit_log_entry(
            actor_id=token.user_id,
            field="email",
            old_value=old_email,
            new_value=new_email,
            request_id=request_id,
        )
        await self._repository.commit()

        except_jti = _resolve_exempt_jti(authorization)
        await self._session_revoker.revoke_other_sessions(
            user_id=token.user_id, except_jti=except_jti
        )

        return ConfirmEmailChangeResponse(email=new_email)
