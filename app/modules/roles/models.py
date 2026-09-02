import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    # Collection relationship: eager-loaded via selectinload(Role.permissions)
    # in the repository (FR-3 catalogue read, FR-6 privilege-escalation
    # check) — never accessed lazily under AsyncSession.
    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions", lazy="raise_on_sql", viewonly=True
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # US-2.5 spec-review resolution (not part of the original US-012
    # design): the 14-day MFA-enrolment grace period (US-009 FR-6) needs a
    # data source for "since the role was granted". Set explicitly by
    # `replace_for_user` on every written row, not left to rely solely on
    # the server default.
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AdminAuditLog(Base):
    """Not in the original US-012 DB design — added during T4 (service)
    because MR-AC1/MR-AC6 explicitly require an `admin_audit_log` entry,
    and `docs/product/business-glossary.md`'s "Audit Log" entry already
    documents `admin_audit_log` as one of this system's five domain audit
    tables (the other four: US-3.1, not yet built). Shape mirrors
    `app.modules.users.models.AuthAuditLog` (this codebase's only existing
    audit table) as closely as the column set allows. Deliberately no FK
    on `actor_id`/`target_id`, matching `AuthAuditLog`'s own precedent —
    the row must survive account deletion/anonymization (BR-007).
    """

    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    old_roles: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    new_roles: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    severity: Mapped[str | None] = mapped_column(String(16))
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # US-3.1 OD-1: this table's second write path (per-field profile
    # updates, app/modules/admin_users/repository.py) populates these four
    # and leaves old_roles/new_roles/severity null; the role-replacement
    # path above does the reverse. Nullable, no default — either write
    # path's unused columns simply stay null on its own rows.
    field: Mapped[str | None] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text())
    new_value: Mapped[str | None] = mapped_column(Text())
    reason: Mapped[str | None] = mapped_column(Text())
