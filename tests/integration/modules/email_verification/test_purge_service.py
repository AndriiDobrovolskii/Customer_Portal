from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_verification.models import AuditLog
from app.modules.email_verification.repository import EmailVerificationRepository
from app.modules.email_verification.service import EmailVerificationService
from app.modules.users.models import User

pytestmark = pytest.mark.integration

_FIXED_NOW = datetime(2026, 8, 29, 12, 0, 0, tzinfo=UTC)


async def _seed_user(
    db_session: AsyncSession, *, email: str, created_at: datetime, email_verified: bool
) -> User:
    user = User(email=email, hashed_password="argon2-hash", status="PENDING_VERIFICATION")
    user.created_at = created_at
    user.email_verified = email_verified
    db_session.add(user)
    await db_session.flush()
    return user


async def test_purge_removes_only_stale_unverified_accounts(db_session: AsyncSession) -> None:
    # Arrange
    stale_unverified = await _seed_user(
        db_session,
        email="stale.unverified@example.com",
        created_at=_FIXED_NOW - timedelta(days=8),
        email_verified=False,
    )
    fresh_unverified = await _seed_user(
        db_session,
        email="fresh.unverified@example.com",
        created_at=_FIXED_NOW - timedelta(days=1),
        email_verified=False,
    )
    stale_verified = await _seed_user(
        db_session,
        email="stale.verified@example.com",
        created_at=_FIXED_NOW - timedelta(days=10),
        email_verified=True,
    )
    service = EmailVerificationService(
        EmailVerificationRepository(db_session), clock=lambda: _FIXED_NOW
    )

    # Act
    purged_count = await service.purge_unverified_accounts()

    # Assert
    assert purged_count == 1

    result = await db_session.execute(select(User.id))
    remaining_ids = {row[0] for row in result.all()}
    assert stale_unverified.id not in remaining_ids
    assert fresh_unverified.id in remaining_ids
    assert stale_verified.id in remaining_ids

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.subject_user_id == stale_unverified.id)
    )
    audit_rows = audit_result.scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].event == "unverified_account_purged"
