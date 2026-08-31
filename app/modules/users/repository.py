import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import AuthAuditLog, RefreshToken, User, UserSession


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def create(self, *, email: str, hashed_password: str, status: str) -> User | None:
        user = User(email=email, hashed_password=hashed_password, status=status)
        self._session.add(user)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return None
        return user

    async def create_session(
        self, *, user_id: uuid.UUID, jti: uuid.UUID, expires_at: datetime
    ) -> UserSession:
        session = UserSession(jti=jti, user_id=user_id, expires_at=expires_at)
        self._session.add(session)
        await self._session.flush()
        return session

    async def get_session_by_jti(self, jti: uuid.UUID) -> UserSession | None:
        result = await self._session.execute(select(UserSession).where(UserSession.jti == jti))
        return result.scalar_one_or_none()

    async def revoke_sessions_except(
        self, *, user_id: uuid.UUID, except_jti: uuid.UUID | None
    ) -> None:
        stmt = update(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
        )
        if except_jti is not None:
            stmt = stmt.where(UserSession.jti != except_jti)
        await self._session.execute(stmt.values(revoked_at=func.now()))

    async def update_last_login_at(self, *, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(last_login_at=func.now())
        )

    async def create_auth_audit_log_entry(
        self,
        *,
        event: str,
        reason: str | None,
        actor_id: uuid.UUID | None,
        ip: str,
        user_agent: str | None,
        request_id: str,
    ) -> None:
        self._session.add(
            AuthAuditLog(
                event=event,
                reason=reason,
                actor_id=actor_id,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
        )

    async def create_refresh_token(
        self,
        *,
        token_hash: str,
        family_id: uuid.UUID,
        user_id: uuid.UUID,
        expires_at: datetime,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            token_hash=token_hash, family_id=family_id, user_id=user_id, expires_at=expires_at
        )
        self._session.add(refresh_token)
        await self._session.flush()
        return refresh_token

    async def commit(self) -> None:
        await self._session.commit()
