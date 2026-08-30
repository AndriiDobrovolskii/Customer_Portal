import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountLifecycleAuditLog(Base):
    __tablename__ = "account_lifecycle_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Deliberately no FK: a future permanent-deletion job removes the users
    # row this entry describes, after writing the entry — the audit trail
    # must survive that deletion (mirrors email_verification's AuditLog).
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
