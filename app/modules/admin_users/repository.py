import base64
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.account.models import AccountLifecycleAuditLog
from app.modules.admin_users.models import InvitationToken
from app.modules.roles.models import AdminAuditLog, Role, UserRole
from app.modules.users.models import User

# Cross-module model imports (User, Role, UserRole, AdminAuditLog,
# AccountLifecycleAuditLog) mirror app/modules/roles/repository.py's own
# precedent of importing User directly: this is a repository-layer join/
# write need (efficient search+filter SQL, and — for create — writing a
# new user's initial roles in the same transaction it's created in), not
# a business-logic decision, which stays in RoleService (service ->
# service) per US-011-implementation-plan.md's Architectural Change #2.


class UserListPage(NamedTuple):
    items: list[tuple[User, list[str]]]
    next_cursor: str | None


def _encode_cursor(created_at: datetime, user_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{user_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_raw, user_id_raw = raw.split("|", 1)
        return datetime.fromisoformat(created_at_raw), uuid.UUID(user_id_raw)
    except (ValueError, UnicodeDecodeError):
        return None


class AdminUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _role_names_for_users(
        self, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[str]]:
        if not user_ids:
            return {}
        result = await self._session.execute(
            select(UserRole.user_id, Role.name)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
        )
        roles_by_user: dict[uuid.UUID, list[str]] = {user_id: [] for user_id in user_ids}
        for user_id, role_name in result.all():
            roles_by_user[user_id].append(role_name)
        return roles_by_user

    async def list_users(
        self,
        *,
        q: str | None,
        status: str | None,
        role: str | None,
        cursor: str | None,
        limit: int,
    ) -> UserListPage | None:
        """Returns None for a malformed cursor (FR-4) or an unknown `role`
        filter name — both resolve to 422 validation-failed at the service
        layer, not a silent empty page.
        """
        stmt = select(User)

        if status is not None:
            stmt = stmt.where(User.status == status)

        if q is not None:
            pattern = f"%{q}%"
            stmt = stmt.where(or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))

        if role is not None:
            role_row = await self._session.execute(select(Role.id).where(Role.name == role))
            role_id = role_row.scalar_one_or_none()
            if role_id is None:
                return None
            stmt = stmt.where(
                User.id.in_(select(UserRole.user_id).where(UserRole.role_id == role_id))
            )

        if cursor is not None:
            decoded = _decode_cursor(cursor)
            if decoded is None:
                return None
            cursor_created_at, cursor_user_id = decoded
            stmt = stmt.where(
                or_(
                    User.created_at < cursor_created_at,
                    (User.created_at == cursor_created_at) & (User.id < cursor_user_id),
                )
            )

        stmt = stmt.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)

        roles_by_user = await self._role_names_for_users([row.id for row in rows])
        items = [(row, roles_by_user.get(row.id, [])) for row in rows]
        return UserListPage(items=items, next_cursor=next_cursor)

    async def get_with_roles(self, user_id: uuid.UUID) -> tuple[User, list[str]] | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        roles_by_user = await self._role_names_for_users([user_id])
        return user, roles_by_user.get(user_id, [])

    async def create(
        self, *, email: str, display_name: str, role_ids: list[uuid.UUID]
    ) -> User | None:
        """`status="invited"`, no password (FR-5). Returns None on a
        duplicate email (BR-001: atomic data-layer enforcement via the
        existing unique constraint on `users.email`, on the
        already-lowercased value the service normalizes to).
        """
        user = User(
            email=email,
            hashed_password="",
            status="invited",
            email_verified=False,
            display_name=display_name,
        )
        self._session.add(user)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return None
        for role_id in role_ids:
            self._session.add(UserRole(user_id=user.id, role_id=role_id))
        await self._session.flush()
        return user

    async def update_fields(self, user_id: uuid.UUID, fields: dict[str, str | None]) -> User | None:
        if not fields:
            result = await self._session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()
        result = await self._session.execute(
            update(User).where(User.id == user_id).values(**fields).returning(User)
        )
        return result.scalar_one_or_none()

    async def deactivate_if_active(self, user_id: uuid.UUID) -> datetime | None:
        """Atomic conditional update, mirroring
        app/modules/account/repository.py's deactivate_if_not_already.
        Returns None if the target isn't currently `active` (the caller
        distinguishes 404/409 by first checking existence via
        get_with_roles).
        """
        result = await self._session.execute(
            update(User)
            .where(User.id == user_id, User.status == "active")
            .values(status="deactivated", deactivated_at=func.now())
            .returning(User.deactivated_at)
        )
        return result.scalar_one_or_none()

    async def create_admin_audit_log_event(
        self, *, event: str, actor_id: uuid.UUID, target_id: uuid.UUID | None, request_id: str
    ) -> None:
        """FR-5 (user_created), FR-18 (invitation_resent) — no per-field
        shape, unlike create_admin_audit_log_field_change below.
        """
        self._session.add(
            AdminAuditLog(
                event=event, actor_id=actor_id, target_id=target_id, request_id=request_id
            )
        )
        await self._session.flush()

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
    ) -> None:
        """FR-9/OD-1 — one row per changed field."""
        self._session.add(
            AdminAuditLog(
                event="user_field_updated",
                actor_id=actor_id,
                target_id=target_id,
                field=field,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                request_id=request_id,
            )
        )
        await self._session.flush()

    async def create_account_lifecycle_audit_log_entry(
        self, *, user_id: uuid.UUID, event: str, actor: str, reason: str | None
    ) -> None:
        """FR-13/OD-2 — `reason` is populated only by the admin path;
        self-service deactivation (US-1.4) continues to omit it.
        """
        self._session.add(
            AccountLifecycleAuditLog(user_id=user_id, event=event, actor=actor, reason=reason)
        )
        await self._session.flush()

    async def get_latest_unconsumed_invitation_token(
        self, user_id: uuid.UUID
    ) -> InvitationToken | None:
        result = await self._session.execute(
            select(InvitationToken)
            .where(InvitationToken.user_id == user_id, InvitationToken.consumed_at.is_(None))
            .order_by(InvitationToken.issued_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_invitation_token(self, user_id: uuid.UUID) -> InvitationToken | None:
        """FR-20's 60-second cooldown check — unlike
        get_latest_unconsumed_invitation_token, considers every token
        regardless of consumed status: the most recently issued row is
        what the cooldown is measured against, even if it was already
        invalidated by an earlier resend.
        """
        result = await self._session.execute(
            select(InvitationToken)
            .where(InvitationToken.user_id == user_id)
            .order_by(InvitationToken.issued_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_invitation_tokens_issued_since(
        self, user_id: uuid.UUID, since: datetime
    ) -> int:
        """FR-20's per-account 5/hour cap."""
        result = await self._session.execute(
            select(func.count())
            .select_from(InvitationToken)
            .where(InvitationToken.user_id == user_id, InvitationToken.issued_at >= since)
        )
        return result.scalar_one()

    async def invalidate_invitation_token(self, token_id: uuid.UUID) -> None:
        await self._session.execute(
            update(InvitationToken)
            .where(InvitationToken.id == token_id)
            .values(consumed_at=func.now())
        )

    async def create_invitation_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> InvitationToken:
        token = InvitationToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(token)
        await self._session.flush()
        return token

    async def commit(self) -> None:
        await self._session.commit()
