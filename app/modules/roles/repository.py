import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.roles.models import AdminAuditLog, Role, UserRole
from app.modules.users.models import User


class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all_with_permissions(self) -> list[Role]:
        result = await self._session.execute(select(Role).options(selectinload(Role.permissions)))
        return list(result.scalars().all())

    async def get_by_names(self, names: list[str]) -> list[Role]:
        if not names:
            return []
        result = await self._session.execute(
            select(Role).where(Role.name.in_(names)).options(selectinload(Role.permissions))
        )
        return list(result.scalars().all())


class UserRoleRepository:
    """Owns the `user_roles` association.

    `count_active_admins_excluding` reads `users.status` directly — a
    deliberate, narrow exception to "cross-module calls go service ->
    service" (AGENTS.md SS3), justified by FR-7's explicit requirement
    that the last-admin check and the role-set update run in one
    transaction. See docs/impact-analysis/US-012-impact-analysis.md's
    2026-09-01 resolution. Do not copy this pattern elsewhere without the
    same justification.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_role_names_for_user(self, user_id: uuid.UUID) -> list[str]:
        result = await self._session.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    async def count_active_admins_excluding(
        self, *, admin_role_id: uuid.UUID, excluding_user_id: uuid.UUID
    ) -> int:
        """FR-7 (MR-AC7's `[gate]` concurrency test): `FOR UPDATE` locks
        every `user_roles` row holding `admin_role_id` for the duration of
        this transaction. Two concurrent requests targeting *different*
        admins both matching this WHERE clause would otherwise both read
        "at least one other active admin remains" before either commits,
        letting both succeed and leave zero admins — `FOR UPDATE` here
        serializes the second request behind the first's commit, so it
        re-reads the post-delete row set instead of a stale one. A plain
        aggregate `count()` cannot carry `FOR UPDATE` in PostgreSQL, so the
        matching rows are locked and counted in Python instead.
        """
        result = await self._session.execute(
            select(UserRole.user_id)
            .join(User, User.id == UserRole.user_id)
            .where(UserRole.role_id == admin_role_id, User.status == "active")
            .with_for_update(of=UserRole)
        )
        admin_user_ids = set(result.scalars().all())
        admin_user_ids.discard(excluding_user_id)
        return len(admin_user_ids)

    async def replace_for_user(self, *, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> None:
        await self._session.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for role_id in role_ids:
            self._session.add(UserRole(user_id=user_id, role_id=role_id))
        await self._session.flush()

    async def create_admin_audit_log_entry(
        self,
        *,
        event: str,
        actor_id: uuid.UUID,
        target_id: uuid.UUID | None,
        old_roles: list[str] | None,
        new_roles: list[str] | None,
        severity: str | None,
        request_id: str,
    ) -> None:
        self._session.add(
            AdminAuditLog(
                event=event,
                actor_id=actor_id,
                target_id=target_id,
                old_roles=old_roles,
                new_roles=new_roles,
                severity=severity,
                request_id=request_id,
            )
        )
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()
