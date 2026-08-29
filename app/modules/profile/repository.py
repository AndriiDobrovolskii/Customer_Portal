import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profile.models import EmailChangeToken, ProfileAuditLog
from app.modules.users.models import User


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email_ci(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def update_fields(self, user_id: uuid.UUID, fields: dict[str, str]) -> None:
        if not fields:
            return
        await self._session.execute(update(User).where(User.id == user_id).values(**fields))

    async def set_pending_email(self, user_id: uuid.UUID, pending_email: str) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(pending_email=pending_email)
        )

    async def apply_email_change(self, user_id: uuid.UUID, new_email: str) -> bool:
        """Swap the confirmed email. Returns False if `new_email` was claimed
        by another account between initiation and confirmation (users.email
        is unique)."""
        try:
            await self._session.execute(
                update(User).where(User.id == user_id).values(email=new_email, pending_email=None)
            )
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return False
        return True

    async def create_email_change_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> EmailChangeToken:
        token = EmailChangeToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_email_change_token_by_hash(self, token_hash: str) -> EmailChangeToken | None:
        result = await self._session.execute(
            select(EmailChangeToken).where(EmailChangeToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def consume_email_change_token(self, token_id: uuid.UUID) -> bool:
        """Atomically mark a token consumed. Returns False if it already was."""
        result = await self._session.execute(
            update(EmailChangeToken)
            .where(
                EmailChangeToken.id == token_id,
                EmailChangeToken.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
            .returning(EmailChangeToken.id)
        )
        return result.scalar_one_or_none() is not None

    async def create_audit_log_entry(
        self,
        *,
        actor_id: uuid.UUID,
        field: str,
        old_value: str | None,
        new_value: str | None,
        request_id: str,
    ) -> None:
        self._session.add(
            ProfileAuditLog(
                actor_id=actor_id,
                field=field,
                old_value=old_value,
                new_value=new_value,
                request_id=request_id,
            )
        )

    async def commit(self) -> None:
        await self._session.commit()
