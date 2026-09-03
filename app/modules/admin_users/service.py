import hashlib
import logging
import secrets
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pydantic import JsonValue, ValidationError

from app.core.config import get_settings
from app.core.email import EmailSender, LoggingEmailSender
from app.core.etag import compute_profile_etag
from app.core.exceptions import FieldError
from app.modules.admin_users.exceptions import (
    AlreadyDeactivatedError,
    CannotTargetSelfError,
    EmailAlreadyRegisteredError,
    ImmutableFieldError,
    InvalidStateTransitionError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    TooManyAttemptsError,
    ValidationFailedError,
)
from app.modules.admin_users.models import InvitationToken
from app.modules.admin_users.repository import UserListPage
from app.modules.admin_users.schemas import (
    ADMIN_USER_EDITABLE_FIELD_NAMES,
    ADMIN_USER_IMMUTABLE_FIELD_NAMES,
    CreateUserRequest,
    ResendInviteResponse,
    UpdateUserRequest,
    UserListResponse,
    UserRead,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

_TOKEN_BYTES = 32
_HOURLY_CAP_RETRY_AFTER_SECONDS = 3600

# The columns UserRead.roles-adjacent ETag is computed over — every field
# UpdateUserRequest can write. Mirrors app/modules/profile/service.py's
# _ETAG_FIELDS/compute_profile_etag pattern exactly (FR-9/FR-10).
_ETAG_FIELDS = ("display_name", "locale", "timezone", "avatar_url")


class AdminUserRepositoryProtocol(Protocol):
    async def list_users(
        self, *, q: str | None, status: str | None, role: str | None, cursor: str | None, limit: int
    ) -> UserListPage | None: ...

    async def get_with_roles(self, user_id: uuid.UUID) -> tuple[User, list[str]] | None: ...

    async def create(
        self, *, email: str, display_name: str, role_ids: list[uuid.UUID]
    ) -> User | None: ...

    async def update_fields(
        self, user_id: uuid.UUID, fields: dict[str, str | None]
    ) -> User | None: ...

    async def deactivate_if_active(self, user_id: uuid.UUID) -> datetime | None: ...

    async def create_admin_audit_log_event(
        self, *, event: str, actor_id: uuid.UUID, target_id: uuid.UUID | None, request_id: str
    ) -> None: ...

    async def create_admin_audit_log_field_change(
        self,
        *,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
        field: str,
        old_value: str | None,
        new_value: str | None,
        reason: str,
        request_id: str,
    ) -> None: ...

    async def create_account_lifecycle_audit_log_entry(
        self, *, user_id: uuid.UUID, event: str, actor: str, reason: str | None
    ) -> None: ...

    async def get_latest_unconsumed_invitation_token(
        self, user_id: uuid.UUID
    ) -> InvitationToken | None: ...

    async def get_latest_invitation_token(self, user_id: uuid.UUID) -> InvitationToken | None: ...

    async def count_invitation_tokens_issued_since(
        self, user_id: uuid.UUID, since: datetime
    ) -> int: ...

    async def invalidate_invitation_token(self, token_id: uuid.UUID) -> None: ...

    async def create_invitation_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> InvitationToken: ...

    async def commit(self) -> None: ...


class RoleServiceProtocol(Protocol):
    """Cross-module collaborator (US-3.2/spec US-3.2's roles.service),
    mirroring users/service.py's own RoleServiceProtocol pattern — the
    sanctioned "depend on the other module's service, never its
    repository/router" shape (AGENTS.md §3).
    """

    async def resolve_role_ids_for_grant(
        self,
        *,
        actor_id: uuid.UUID,
        actor_scopes: set[str],
        role_names: list[str],
        request_id: str,
    ) -> list[uuid.UUID]: ...

    async def raise_if_last_admin(self, target_user_id: uuid.UUID) -> None: ...


class RevocationCacheProtocol(Protocol):
    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None: ...


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


def _to_user_read(user: User, roles: list[str]) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        roles=sorted(roles),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


class AdminUserService:
    def __init__(
        self,
        repository: AdminUserRepositoryProtocol,
        role_service: RoleServiceProtocol,
        revocation_cache: RevocationCacheProtocol,
        email_sender: EmailSender | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._role_service = role_service
        self._revocation_cache = revocation_cache
        self._email_sender = email_sender or LoggingEmailSender()
        self._clock = clock

    async def list_users(
        self,
        *,
        q: str | None,
        status: str | None,
        role: str | None,
        cursor: str | None,
        limit: int,
    ) -> UserListResponse:
        """FR-1/FR-4."""
        if limit > 100:
            raise ValidationFailedError(
                errors=[FieldError(field="limit", message="limit must be at most 100.", code="max")]
            )
        if status is not None and status not in ("invited", "active", "deactivated"):
            raise ValidationFailedError(
                errors=[
                    FieldError(
                        field="status", message="Unknown status value.", code="unknown_status"
                    )
                ]
            )

        page = await self._repository.list_users(
            q=q, status=status, role=role, cursor=cursor, limit=limit
        )
        if page is None:
            field = "cursor" if cursor is not None else "role"
            raise ValidationFailedError(
                errors=[FieldError(field=field, message=f"Invalid {field}.", code="invalid")]
            )

        items = [_to_user_read(user, roles) for user, roles in page.items]
        return UserListResponse(items=items, next_cursor=page.next_cursor)

    async def get_user(self, user_id: uuid.UUID) -> tuple[UserRead, str]:
        """FR-22/FR-23."""
        result = await self._repository.get_with_roles(user_id)
        if result is None:
            raise NotFoundError()
        user, roles = result
        return _to_user_read(user, roles), compute_profile_etag(_etag_fields(user))

    async def create_user(
        self,
        *,
        actor_id: uuid.UUID,
        actor_scopes: set[str],
        payload: CreateUserRequest,
        request_id: str,
    ) -> tuple[UserRead, str]:
        """FR-5/FR-6/FR-7/FR-8. `password` is never accepted here — the
        request schema simply doesn't declare it, so `extra="forbid"`
        rejects one as an unknown field before this method runs.
        """
        role_ids = await self._role_service.resolve_role_ids_for_grant(
            actor_id=actor_id,
            actor_scopes=actor_scopes,
            role_names=payload.roles,
            request_id=request_id,
        )

        normalized_email = payload.email.strip().lower()
        user = await self._repository.create(
            email=normalized_email, display_name=payload.display_name, role_ids=role_ids
        )
        if user is None:
            raise EmailAlreadyRegisteredError()

        await self._repository.create_admin_audit_log_event(
            event="user_created", actor_id=actor_id, target_id=user.id, request_id=request_id
        )
        await self._repository.commit()

        # Best-effort, mirroring UserService.register_user: the account is
        # already committed and creation must succeed regardless of
        # whether the invitation email goes out.
        try:
            await self._issue_invitation(user)
        except Exception:
            logger.exception("failed to issue invitation token after admin user creation")

        result = await self._repository.get_with_roles(user.id)
        if result is None:
            msg = "user row vanished immediately after its own creation"
            raise RuntimeError(msg)
        created_user, roles = result
        return _to_user_read(created_user, roles), compute_profile_etag(_etag_fields(created_user))

    async def update_user(
        self,
        *,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
        raw_body: Mapping[str, JsonValue],
        if_match: str | None,
        request_id: str,
    ) -> tuple[UserRead, str]:
        """FR-9/FR-10/FR-11/FR-12."""
        result = await self._repository.get_with_roles(target_id)
        if result is None:
            raise NotFoundError()
        user, roles = result

        if if_match is None:
            raise PreconditionRequiredError()
        current_etag = compute_profile_etag(_etag_fields(user))
        if if_match not in ("*", current_etag):
            raise PreconditionFailedError()

        if set(raw_body) & ADMIN_USER_IMMUTABLE_FIELD_NAMES:
            raise ImmutableFieldError()

        try:
            payload = UpdateUserRequest.model_validate(raw_body)
        except ValidationError as exc:
            raise ValidationFailedError(errors=_convert_validation_error(exc)) from exc

        changes = {
            field: value
            for field, value in payload.model_dump(exclude_unset=True).items()
            if field in ADMIN_USER_EDITABLE_FIELD_NAMES
        }

        if changes:
            old_values = {field: getattr(user, field) for field in changes}
            updated_user = await self._repository.update_fields(target_id, changes)
            if updated_user is None:
                raise NotFoundError()
            for field, new_value in changes.items():
                await self._repository.create_admin_audit_log_field_change(
                    actor_id=actor_id,
                    target_id=target_id,
                    field=field,
                    old_value=old_values[field],
                    new_value=new_value,
                    reason=payload.reason,
                    request_id=request_id,
                )
            await self._repository.commit()
            user = updated_user

        return _to_user_read(user, roles), compute_profile_etag(_etag_fields(user))

    async def deactivate_user(
        self, *, actor_id: uuid.UUID, target_id: uuid.UUID, reason: str, request_id: str
    ) -> UserRead:
        """FR-13/FR-14/FR-15/FR-16/FR-17b."""
        if target_id == actor_id:
            raise CannotTargetSelfError()

        result = await self._repository.get_with_roles(target_id)
        if result is None:
            raise NotFoundError()
        user, roles = result

        await self._role_service.raise_if_last_admin(target_id)

        deactivated_at = await self._repository.deactivate_if_active(target_id)
        if deactivated_at is None:
            raise AlreadyDeactivatedError()

        await self._repository.create_account_lifecycle_audit_log_entry(
            user_id=target_id, event="deactivated", actor=f"admin:{actor_id}", reason=reason
        )
        await self._repository.commit()

        settings = get_settings()
        # Same TTL rationale as AccountService.deactivate_account: must
        # outlive the longest-lived credential (refresh token) this key
        # gates, per DA-AC10's "identical side effects" invariant.
        await self._revocation_cache.set_revoke_before(
            target_id, ttl_seconds=settings.refresh_token_ttl_seconds
        )

        user.status = "deactivated"
        user.deactivated_at = deactivated_at
        return _to_user_read(user, roles)

    async def resend_invite(
        self, *, actor_id: uuid.UUID, target_id: uuid.UUID, request_id: str
    ) -> ResendInviteResponse:
        """FR-18/FR-19/FR-20/FR-21."""
        result = await self._repository.get_with_roles(target_id)
        if result is None:
            raise NotFoundError()
        user, _roles = result

        if user.status != "invited":
            raise InvalidStateTransitionError()

        settings = get_settings()
        latest = await self._repository.get_latest_invitation_token(target_id)
        if latest is not None:
            elapsed = (self._clock() - latest.issued_at).total_seconds()
            if elapsed < settings.resend_cooldown_seconds:
                retry_after = int(settings.resend_cooldown_seconds - elapsed)
                raise TooManyAttemptsError(retry_after_seconds=retry_after)

        since = self._clock() - timedelta(hours=1)
        recent_count = await self._repository.count_invitation_tokens_issued_since(target_id, since)
        if recent_count >= settings.invitation_resend_hourly_limit:
            raise TooManyAttemptsError(retry_after_seconds=_HOURLY_CAP_RETRY_AFTER_SECONDS)

        prior_unconsumed = await self._repository.get_latest_unconsumed_invitation_token(target_id)
        if prior_unconsumed is not None:
            await self._repository.invalidate_invitation_token(prior_unconsumed.id)

        await self._issue_invitation(user)
        await self._repository.create_admin_audit_log_event(
            event="invitation_resent", actor_id=actor_id, target_id=target_id, request_id=request_id
        )
        await self._repository.commit()

        return ResendInviteResponse()

    async def _issue_invitation(self, user: User) -> None:
        settings = get_settings()
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        expires_at = self._clock() + timedelta(hours=settings.invitation_token_ttl_hours)
        await self._repository.create_invitation_token(
            user_id=user.id, token_hash=_hash_token(raw_token), expires_at=expires_at
        )
        await self._repository.commit()
        await self._email_sender.send_invitation_email(to=user.email, raw_token=raw_token)
