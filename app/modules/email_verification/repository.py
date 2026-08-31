import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_verification.models import AuditLog, EmailVerificationToken
from app.modules.users.models import User


class EmailVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_latest_token_for_user(self, user_id: uuid.UUID) -> EmailVerificationToken | None:
        result = await self._session.execute(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id)
            .order_by(EmailVerificationToken.issued_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_token_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        result = await self._session.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def create_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> EmailVerificationToken:
        token = EmailVerificationToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def consume_token(self, token_id: uuid.UUID) -> bool:
        """Atomically mark a token consumed. Returns False if it already was."""
        result = await self._session.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.id == token_id,
                EmailVerificationToken.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
            .returning(EmailVerificationToken.id)
        )
        return result.scalar_one_or_none() is not None

    async def mark_user_verified(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(email_verified=True)
        )

    async def find_purge_candidates(self, cutoff: datetime) -> list[User]:
        result = await self._session.execute(
            select(User).where(User.email_verified.is_(False), User.created_at < cutoff)
        )
        return list(result.scalars().all())

    async def delete_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(delete(User).where(User.id == user_id))

    async def create_audit_log(
        self, *, event: str, subject_user_id: uuid.UUID, detail: str
    ) -> None:
        self._session.add(AuditLog(event=event, subject_user_id=subject_user_id, detail=detail))

    async def commit(self) -> None:
        await self._session.commit()
