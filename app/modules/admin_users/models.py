import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvitationToken(Base):
    """Same shape as email_verification_tokens/password_reset_tokens
    (US-3.1-db-design.md). `consumed_at` is reused (not a separate
    `invalidated_at` column) both when the invitee completes setup and
    when an admin resends and the prior token is invalidated (FR-18) —
    both mean "not usable"; the distinguishing detail lives in
    admin_audit_log's event=invitation_resent row, not this table.
    """

    __tablename__ = "invitation_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
