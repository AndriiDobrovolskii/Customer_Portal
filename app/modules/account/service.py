import uuid
from datetime import datetime
from typing import Protocol

from app.core.config import get_settings
from app.core.security import verify_password
from app.modules.account.exceptions import AlreadyDeactivatedError, InvalidPasswordError
from app.modules.account.schemas import DeactivateAccountRequest, DeactivateAccountResponse
from app.modules.account.schemas import DeactivationStatus as DeactivationStatusSchema
from app.modules.users.models import User


class AccountRepositoryProtocol(Protocol):
    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def deactivate_if_not_already(self, user_id: uuid.UUID) -> datetime | None: ...

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
        await self._cache.set_revoke_before(user_id, ttl_seconds=settings.access_token_ttl_seconds)

        return DeactivateAccountResponse(
            status=DeactivationStatusSchema.DEACTIVATED, deactivated_at=deactivated_at
        )
