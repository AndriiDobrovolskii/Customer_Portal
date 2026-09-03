import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.models import User
from scripts.anonymize_erased_user import anonymize_erased_user

pytestmark = pytest.mark.integration


async def _seed_user(db_session: AsyncSession, *, email: str, display_name: str) -> User:
    user = User(email=email, hashed_password=await hash_password("Str0ng!Pass1"), status="active")
    user.email_verified = True
    user.display_name = display_name
    db_session.add(user)
    await db_session.flush()
    return user


async def test_anonymize_erased_user_anonymizes_users_row_and_redacts_auth_audit_ip(
    db_session: AsyncSession,
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="erased@example.com", display_name="Erase Me")
    await db_session.execute(
        text(
            "INSERT INTO auth_audit_log (id, event, actor_id, ip, request_id, occurred_at) "
            "VALUES (:id, 'login_success', :actor_id, '10.5.5.5', 'req-erase', now())"
        ),
        {"id": uuid.uuid4(), "actor_id": user.id},
    )

    # Act
    await anonymize_erased_user(db_session, user.id)

    # Assert
    result = await db_session.execute(
        text("SELECT email, display_name FROM users WHERE id = :id"), {"id": user.id}
    )
    row = result.mappings().one()
    assert row["email"] == f"deleted-{user.id}@anonymized.invalid"
    assert row["display_name"] is None

    ip_result = await db_session.execute(
        text("SELECT ip FROM auth_audit_log WHERE actor_id = :id"), {"id": user.id}
    )
    assert ip_result.scalar_one() == "redacted"


async def test_anonymize_erased_user_does_not_remove_audit_entries(
    db_session: AsyncSession,
) -> None:
    # Arrange: AU-AC8's third clause — entries remain queryable,
    # actor_id retained as an opaque UUID (never nulled).
    user = await _seed_user(db_session, email="stillqueryable@example.com", display_name="X")
    await db_session.execute(
        text(
            "INSERT INTO auth_audit_log (id, event, actor_id, ip, request_id, occurred_at) "
            "VALUES (:id, 'login_success', :actor_id, '10.5.5.6', 'req-erase2', now())"
        ),
        {"id": uuid.uuid4(), "actor_id": user.id},
    )

    # Act
    await anonymize_erased_user(db_session, user.id)

    # Assert
    result = await db_session.execute(
        text("SELECT actor_id FROM auth_audit_log WHERE request_id = 'req-erase2'")
    )
    assert result.scalar_one() == user.id


async def test_anonymize_erased_user_leaves_profile_audit_log_untouched(
    db_session: AsyncSession,
) -> None:
    # Arrange: OD-20 — profile_audit_log's append-only trigger makes
    # redaction there technically impossible; the script must not attempt
    # it. A row would raise if the script tried to UPDATE it.
    user = await _seed_user(db_session, email="profileuser@example.com", display_name="Y")
    await db_session.execute(
        text(
            "INSERT INTO profile_audit_log "
            '(id, actor_id, field, old_value, new_value, request_id, "timestamp") '
            "VALUES (:id, :actor_id, 'display_name', 'Old', 'Y', 'req-erase3', now())"
        ),
        {"id": uuid.uuid4(), "actor_id": user.id},
    )

    # Act
    await anonymize_erased_user(db_session, user.id)

    # Assert: no exception raised, and the row is untouched
    result = await db_session.execute(
        text("SELECT old_value, new_value FROM profile_audit_log WHERE request_id = 'req-erase3'")
    )
    row = result.mappings().one()
    assert row["old_value"] == "Old"
    assert row["new_value"] == "Y"
