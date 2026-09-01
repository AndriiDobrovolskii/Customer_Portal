import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import (
    AuthAuditLog,
    PasswordResetToken,
    RefreshToken,
    User,
    UserSession,
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
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

    async def revoke_session(self, *, jti: uuid.UUID) -> None:
        await self._session.execute(
            update(UserSession).where(UserSession.jti == jti).values(revoked_at=func.now())
        )

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token_family(self, *, family_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .values(revoked_at=func.now())
        )

    async def consume_refresh_token(self, *, token_hash: str) -> RefreshToken | None:
        """Atomic check-and-consume (RT-AC7): a conditional UPDATE guarded by
        `consumed_at IS NULL`, so two concurrent callers presenting the same
        token can never both succeed — a read-then-write pair here would be
        a TOCTOU bug (both would observe `consumed_at IS NULL` and rotate).
        Returns `None` when the token was already consumed (by a prior
        rotation, or by a losing concurrent request).
        """
        result = await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash, RefreshToken.consumed_at.is_(None))
            .values(consumed_at=func.now())
            .returning(RefreshToken)
        )
        return result.scalar_one_or_none()

    async def update_last_login_at(self, *, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(last_login_at=func.now())
        )

    async def update_password_hash(self, *, user_id: uuid.UUID, hashed_password: str) -> None:
        """FR-2: no existing write path actually covers this — registration
        `create`s a new row and login never writes `hashed_password` — so
        this is a genuinely new method, found while building the service
        (impact-analysis's "existing write path" note undersold it; same
        class of gap US-2.3 hit with `get_by_id`).
        """
        await self._session.execute(
            update(User).where(User.id == user_id).values(hashed_password=hashed_password)
        )

    async def create_auth_audit_log_entry(
        self,
        *,
        event: str,
        reason: str | None,
        scope: str | None,
        actor_id: uuid.UUID | None,
        ip: str,
        user_agent: str | None,
        request_id: str,
        severity: str | None = None,
    ) -> None:
        self._session.add(
            AuthAuditLog(
                event=event,
                reason=reason,
                scope=scope,
                severity=severity,
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
        ip: str | None = None,
        user_agent: str | None = None,
        last_used_at: datetime | None = None,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            token_hash=token_hash,
            family_id=family_id,
            user_id=user_id,
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
            last_used_at=last_used_at,
        )
        self._session.add(refresh_token)
        await self._session.flush()
        return refresh_token

    async def invalidate_password_reset_tokens_for_user(self, *, user_id: uuid.UUID) -> None:
        """FR-1: any previously issued, unconsumed reset token for the
        account is invalidated when a new one issues. Reuses `consumed_at`
        itself as the invalidation marker (per db-design.md) — a row
        invalidated this way is indistinguishable at the DB level from one
        consumed by actual use, which is correct: both must reject
        identically at `confirm` (FR-4).
        """
        await self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.consumed_at.is_(None))
            .values(consumed_at=func.now())
        )

    async def create_password_reset_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        reset_token = PasswordResetToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self._session.add(reset_token)
        await self._session.flush()
        return reset_token

    async def get_password_reset_token_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self._session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def consume_password_reset_token(self, *, token_hash: str) -> PasswordResetToken | None:
        """Atomic check-and-consume, same pattern as `consume_refresh_token`
        (RT-AC7) and required by the US-008 spec review's accepted Missing
        Edge Cases finding: a conditional UPDATE guarded by `consumed_at IS
        NULL` so two concurrent `confirm` calls against the same token can
        never both succeed. Returns `None` when the token was already
        consumed (by prior use, by FR-1's invalidation, or by a losing
        concurrent request).
        """
        result = await self._session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
            .returning(PasswordResetToken)
        )
        return result.scalar_one_or_none()

    async def commit(self) -> None:
        await self._session.commit()
