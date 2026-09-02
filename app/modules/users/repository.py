import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import (
    AuthAuditLog,
    MfaRecoveryCode,
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
        target_family: uuid.UUID | None = None,
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
                target_family=target_family,
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

    async def update_mfa_pending_secret(
        self, *, user_id: uuid.UUID, secret_encrypted: bytes
    ) -> None:
        """FR-1/OD-11: always overwrites - re-enrolling while a PENDING
        secret already exists replaces it. `mfa_enabled` is untouched
        (stays false), so an unfinished enrolment can never lock a user
        out (MF-AC1).
        """
        await self._session.execute(
            update(User).where(User.id == user_id).values(mfa_secret_encrypted=secret_encrypted)
        )

    async def activate_mfa(self, *, user_id: uuid.UUID) -> None:
        """FR-2: also clears mfa_reenrollment_required unconditionally -
        the shared exit condition for both enrolment-scoped-token triggers
        (FR-6's privileged-role grant, FR-7's recovery-code use). Harmless
        to clear when it was already false.
        """
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(mfa_enabled=True, mfa_activated_at=func.now(), mfa_reenrollment_required=False)
        )

    async def set_mfa_reenrollment_required(self, *, user_id: uuid.UUID) -> None:
        """FR-7/OD-5: does not touch mfa_enabled or the existing secret/
        remaining recovery codes - a degraded state, not a disable.
        """
        await self._session.execute(
            update(User).where(User.id == user_id).values(mfa_reenrollment_required=True)
        )

    async def disable_mfa(self, *, user_id: uuid.UUID) -> None:
        """FR-8: full purge of enrolment state. Recovery codes themselves
        are deleted separately (delete_recovery_codes_for_user) since
        they're a different table.
        """
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                mfa_enabled=False,
                mfa_secret_encrypted=None,
                mfa_activated_at=None,
                mfa_reenrollment_required=False,
            )
        )

    async def create_recovery_codes(self, *, user_id: uuid.UUID, code_hashes: list[str]) -> None:
        """FR-2: issues all 10 in one call. Argon2id-hashed by the caller
        (service layer) - this method only persists already-hashed values.
        """
        self._session.add_all(
            [MfaRecoveryCode(user_id=user_id, code_hash=code_hash) for code_hash in code_hashes]
        )
        await self._session.flush()

    async def list_unconsumed_recovery_codes(self, *, user_id: uuid.UUID) -> list[MfaRecoveryCode]:
        """FR-7: each stored hash is independently salted, so a submitted
        recovery code can't be looked up by hash equality - the caller
        must verify it against every unconsumed row (per US-009-db-
        design.md's documented one-of-N pattern).
        """
        result = await self._session.execute(
            select(MfaRecoveryCode).where(
                MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.consumed_at.is_(None)
            )
        )
        return list(result.scalars().all())

    async def consume_recovery_code(self, *, code_id: uuid.UUID) -> MfaRecoveryCode | None:
        """Atomic check-and-consume, same pattern as consume_refresh_token/
        consume_password_reset_token: a conditional UPDATE guarded by
        `consumed_at IS NULL` so two concurrent verify calls presenting the
        same recovery code can never both succeed.
        """
        result = await self._session.execute(
            update(MfaRecoveryCode)
            .where(MfaRecoveryCode.id == code_id, MfaRecoveryCode.consumed_at.is_(None))
            .values(consumed_at=func.now())
            .returning(MfaRecoveryCode)
        )
        return result.scalar_one_or_none()

    async def delete_recovery_codes_for_user(self, *, user_id: uuid.UUID) -> None:
        """FR-8/OD-8: hard-delete, not mark-consumed - disable purges every
        recovery code, since a code is worthless without a secret and
        keeping it is pure liability. Deliberately diverges from
        PasswordResetToken's keep-but-mark-consumed precedent.
        """
        await self._session.execute(
            delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
        )

    async def get_any_refresh_token_for_family(
        self, *, family_id: uuid.UUID, user_id: uuid.UUID
    ) -> RefreshToken | None:
        """FR-3/FR-4 (US-2.6): confirms family ownership regardless of
        revoked/expired state, distinguishing "belongs to caller but
        inactive" (204, idempotent) from "never belonged to this user"
        (404) - `list_live_families_for_user` only returns live rows,
        which can't answer this question on its own. Found while building
        `service.py`'s `revoke_session` - same class of gap prior stories
        hit (e.g. `get_by_id`, US-2.3).
        """
        result = await self._session.execute(
            select(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.user_id == user_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def lock_live_refresh_tokens_for_user(self, *, user_id: uuid.UUID) -> None:
        """US-2.6 FR-7 (spec-review resolution): row-locks the acting
        user's own live rows ahead of the count-and-evict check in
        `service.py`'s login path, so two logins racing concurrently for
        the SAME user serialize rather than both observing a stale family
        count. Scoped to `user_id` only - never a table-wide lock, which
        would serialize unrelated users' logins and blow the login
        endpoint's own latency budget.
        """
        await self._session.execute(
            select(RefreshToken.id)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > func.now(),
            )
            .with_for_update()
        )

    async def list_live_families_for_user(self, *, user_id: uuid.UUID) -> list[RefreshToken]:
        """FR-1/FR-7: one row per live family - the row with the latest
        `issued_at` represents that family's current state (US-2.3's
        single-use-then-rotate invariant guarantees at most one un-revoked,
        un-expired row is "live" per family at a time). PostgreSQL's
        DISTINCT ON, not a Python-side reduction, keeps this a single
        indexed query against `ix_refresh_tokens_user_id_family_id_issued_at`
        (see docs/designs/database/US-010-db-design.md).
        """
        result = await self._session.execute(
            select(RefreshToken)
            .distinct(RefreshToken.family_id)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > func.now(),
            )
            .order_by(RefreshToken.family_id, RefreshToken.issued_at.desc())
        )
        return list(result.scalars().all())

    async def get_family_created_at_map_for_user(
        self, *, user_id: uuid.UUID
    ) -> dict[uuid.UUID, datetime]:
        """FR-1's `created_at` (per family) is `MIN(issued_at)` across that
        family's rotation chain, not the current row's own `issued_at` -
        see US-010-db-design.md. Also doubles as FR-7's oldest-family
        lookup: the caller picks the minimum value from the returned map
        rather than a second, near-duplicate query (at most 20 live
        families per user, so this is cheap in Python).
        """
        result = await self._session.execute(
            select(RefreshToken.family_id, func.min(RefreshToken.issued_at))
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > func.now(),
            )
            .group_by(RefreshToken.family_id)
        )
        # dict(result.all()) (ruff's C416 suggestion) fails mypy strict:
        # Row isn't a subtype of tuple[UUID, datetime] as far as dict()'s
        # overloads see it.
        return {family_id: created_at for family_id, created_at in result.all()}  # noqa: C416

    async def commit(self) -> None:
        await self._session.commit()
