import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.account.models import AccountLifecycleAuditLog
from app.modules.users.models import User


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def deactivate_if_not_already(self, user_id: uuid.UUID) -> datetime | None:
        """Atomically transitions an account to deactivated. Returns the new
        deactivated_at, or None if the account was already deactivated (the
        losing side of a race, or a genuine repeat call — both render as
        the same 409 to the caller, per spec Clarification #2)."""
        result = await self._session.execute(
            update(User)
            .where(
                User.id == user_id,
                User.email_verified.is_(True),
                User.status != "deactivated",
            )
            .values(status="deactivated", deactivated_at=func.now())
            .returning(User.deactivated_at)
        )
        return result.scalar_one_or_none()

    async def create_audit_log_entry(self, *, user_id: uuid.UUID, event: str, actor: str) -> None:
        self._session.add(AccountLifecycleAuditLog(user_id=user_id, event=event, actor=actor))

    async def commit(self) -> None:
        await self._session.commit()
