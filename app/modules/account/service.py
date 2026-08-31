import uuid
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

from app.core.config import get_settings
from app.core.security import verify_password
from app.modules.account.exceptions import AlreadyDeactivatedError, InvalidPasswordError
from app.modules.account.schemas import DeactivateAccountRequest, DeactivateAccountResponse
from app.modules.account.schemas import DeactivationStatus as DeactivationStatusSchema
from app.modules.users.models import User

# Resolved OD-10: matches BR-007 / DA-AC8's 30-day reactivation grace period.
_REACTIVATION_GRACE_PERIOD_DAYS: Final = 30


class AccountRepositoryProtocol(Protocol):
    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def deactivate_if_not_already(self, user_id: uuid.UUID) -> datetime | None: ...

    async def reactivate_if_within_grace(
        self, user_id: uuid.UUID, *, grace_period_cutoff: datetime
    ) -> bool: ...

    async def create_audit_log_entry(
        self, *, user_id: uuid.UUID, event: str, actor: str
    ) -> None: ...

    async def commit(self) -> None: ...


class RevocationCacheProtocol(Protocol):
    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None: ...


class AccountService:
    def __init__(
        self, repository: AccountRepositoryProtocol, cache: RevocationCacheProtocol
    ) -> None:
        self._repository = repository
        self._cache = cache

    async def deactivate_account(
        self, *, user_id: uuid.UUID, payload: DeactivateAccountRequest
    ) -> DeactivateAccountResponse:
        user = await self._repository.get_user_by_id(user_id)
        password = payload.current_password.get_secret_value() if payload.current_password else ""

        # Password verified before the state check below, so a caller who
        # doesn't know the password can't learn whether the account is
        # already deactivated (mirrors users/service.py's login ordering).
        if user is None or not await verify_password(password, user.hashed_password):
            raise InvalidPasswordError

        deactivated_at = await self._repository.deactivate_if_not_already(user_id)
        if deactivated_at is None:
            raise AlreadyDeactivatedError

        await self._repository.create_audit_log_entry(
            user_id=user_id, event="deactivated", actor="self"
        )
        await self._repository.commit()

        settings = get_settings()
        # Must outlive the longest-lived credential this key is meant to
        # gate. get_authenticated_user only checks access tokens today, but
        # the revoke_before key is shared with US-2.3's future /refresh
        # endpoint (see US-2.2's logout_all, which already uses this TTL) —
        # a shorter TTL here would let a deactivated account's refresh
        # token silently become valid again once the key expires (found via
        # independent review, 2026-09-01).
        await self._cache.set_revoke_before(user_id, ttl_seconds=settings.refresh_token_ttl_seconds)

        return DeactivateAccountResponse(
            status=DeactivationStatusSchema.DEACTIVATED, deactivated_at=deactivated_at
        )

    async def reactivate_account(self, user_id: uuid.UUID) -> bool:
        """Cross-module collaborator for the login flow (resolved OD-10,
        DA-AC8): reactivates a deactivated account if it's still within its
        30-day grace period. Returns True if this call actually reactivated
        the account, False if it was a no-op (already active, or past the
        grace period) — either way, the caller (users/service.py) proceeds
        with an ordinary login. Injected as a Protocol-typed service->service
        collaborator, per AGENTS.md's cross-module discipline, mirroring
        users/service.py's own revoke_other_sessions collaborator pattern.
        """
        grace_period_cutoff = datetime.now(UTC) - timedelta(days=_REACTIVATION_GRACE_PERIOD_DAYS)
        reactivated = await self._repository.reactivate_if_within_grace(
            user_id, grace_period_cutoff=grace_period_cutoff
        )
        if reactivated:
            await self._repository.create_audit_log_entry(
                user_id=user_id, event="reactivated", actor="self"
            )
            await self._repository.commit()
        return reactivated
