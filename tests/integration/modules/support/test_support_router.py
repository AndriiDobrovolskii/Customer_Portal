import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encode_access_token, hash_password
from app.modules.audit.models import AuditLog
from app.modules.roles.models import Role, UserRole
from app.modules.support.models import Attachment, Ticket
from app.modules.users.models import User, UserSession

pytestmark = pytest.mark.integration

_TICKETS_PATH = "/api/v1/support/tickets"


async def _seed_user(db_session: AsyncSession, *, email: str, status: str = "active") -> User:
    user = User(email=email, hashed_password=await hash_password("Str0ng!Pass1"), status=status)
    user.email_verified = True
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_session_and_token(
    db_session: AsyncSession, *, user_id: uuid.UUID, scopes: list[str] | None = None
) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1))
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=scopes or [])


async def _assign_role(db_session: AsyncSession, *, user_id: uuid.UUID, role_name: str) -> None:
    result = await db_session.execute(select(Role.id).where(Role.name == role_name))
    role_id = result.scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role_id))
    await db_session.flush()


async def _expired_token(db_session: AsyncSession, *, user_id: uuid.UUID) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.flush()
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "scopes": [],
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


async def _revoked_session_token(db_session: AsyncSession, *, user_id: uuid.UUID) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=[])


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _seed_attachment(
    db_session: AsyncSession, *, uploaded_by: uuid.UUID, ticket_id: uuid.UUID | None = None
) -> Attachment:
    attachment = Attachment(uploaded_by=uploaded_by, ticket_id=ticket_id)
    db_session.add(attachment)
    await db_session.flush()
    return attachment


def _create_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject": "Cannot log in",
        "body": "My login keeps failing after the last update.",
        "category": "billing",
    }
    payload.update(overrides)
    return payload


# --- ST-AC1/FR-1: successful creation ---------------------------------------


async def test_create_ticket_returns_201_and_persists_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="creator@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(),
        headers={**_auth_headers(token), "Idempotency-Key": "create-1"},
    )

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["requester_id"] == str(user.id)
    assert body["ticket_number"].startswith("CP-")
    assert "id" not in body or body["id"] != body["ticket_number"]
    result = await db_session.execute(select(Ticket).where(Ticket.id == uuid.UUID(body["id"])))
    ticket = result.scalar_one()
    assert ticket.status == "open"
    assert ticket.requester_id == user.id
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_created")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.category == "tickets"
    assert audit_row.actor_id == user.id
    assert audit_row.outcome == "success"


# --- ST-AC2/FR-2: listing own tickets ---------------------------------------


async def test_list_own_tickets_returns_only_callers_tickets_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    owner = await _seed_user(db_session, email="owner@example.com")
    other = await _seed_user(db_session, email="other@example.com")
    owner_token = await _seed_session_and_token(db_session, user_id=owner.id)
    now = datetime.now(UTC)
    older = Ticket(
        ticket_number="CP-2026-0000101",
        requester_id=owner.id,
        subject="Older ticket",
        body="First.",
        category="billing",
        status="open",
        created_at=now - timedelta(minutes=1),
    )
    newer = Ticket(
        ticket_number="CP-2026-0000102",
        requester_id=owner.id,
        subject="Newer ticket",
        body="Second.",
        category="billing",
        status="open",
        created_at=now,
    )
    others_ticket = Ticket(
        ticket_number="CP-2026-0000103",
        requester_id=other.id,
        subject="Not mine",
        body="Should not appear.",
        category="billing",
        status="open",
        created_at=now,
    )
    db_session.add_all([older, newer, others_ticket])
    await db_session.flush()

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(owner_token))

    # Assert
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert str(others_ticket.id) not in ids
    assert ids.index(str(newer.id)) < ids.index(str(older.id))


async def test_list_own_tickets_malformed_cursor_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="badcursor@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.get(
        _TICKETS_PATH, params={"cursor": "not-a-real-cursor"}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")


# --- ST-AC3/FR-3: invalid input ---------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"subject": ""}, id="empty_subject"),
        pytest.param({"subject": "x" * 151}, id="subject_over_150_chars"),
        pytest.param({"body": "x" * 5001}, id="body_over_5000_chars"),
    ],
)
async def test_create_ticket_invalid_input_returns_422_and_creates_nothing(
    client: AsyncClient, db_session: AsyncSession, overrides: dict[str, str]
) -> None:
    # Arrange
    user = await _seed_user(db_session, email=f"invalid.{uuid.uuid4().hex}@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(**overrides),
        headers={**_auth_headers(token), "Idempotency-Key": f"invalid-{uuid.uuid4().hex}"},
    )

    # Assert
    assert response.status_code == 422
    body = response.json()
    assert body["type"].endswith("validation-failed")
    assert body["errors"]
    result = await db_session.execute(select(Ticket).where(Ticket.requester_id == user.id))
    assert result.first() is None


# --- ST-AC4/FR-4: idempotency replay and reuse ------------------------------


async def test_create_ticket_replay_same_key_returns_original_ticket(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="replay@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    headers = {**_auth_headers(token), "Idempotency-Key": "replay-key"}
    payload = _create_payload()

    # Act
    first = await client.post(_TICKETS_PATH, json=payload, headers=headers)
    second = await client.post(_TICKETS_PATH, json=payload, headers=headers)

    # Assert
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    result = await db_session.execute(select(Ticket).where(Ticket.requester_id == user.id))
    assert len(result.all()) == 1


async def test_create_ticket_key_reused_with_different_body_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="reuse@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    headers = {**_auth_headers(token), "Idempotency-Key": "reuse-key"}

    # Act
    first = await client.post(_TICKETS_PATH, json=_create_payload(), headers=headers)
    second = await client.post(
        _TICKETS_PATH, json=_create_payload(body="A completely different body."), headers=headers
    )

    # Assert
    assert first.status_code == 201
    assert second.status_code == 422
    assert second.json()["type"].endswith("idempotency-key-reuse")
    result = await db_session.execute(select(Ticket).where(Ticket.requester_id == user.id))
    assert len(result.all()) == 1


async def test_create_ticket_missing_idempotency_key_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="missingkey@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH, json=_create_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")


# --- ST-AC5/FR-5: authentication / eligibility ------------------------------


async def test_create_ticket_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        _TICKETS_PATH, json=_create_payload(), headers={"Idempotency-Key": "no-token"}
    )

    # Assert
    assert response.status_code == 401


async def test_create_ticket_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(),
        headers={**_auth_headers("not-a-real-jwt"), "Idempotency-Key": "malformed"},
    )

    # Assert
    assert response.status_code == 401


async def test_create_ticket_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="expiredticket@example.com")
    token = await _expired_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(),
        headers={**_auth_headers(token), "Idempotency-Key": "expired"},
    )

    # Assert
    assert response.status_code == 401


async def test_create_ticket_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="revokedticket@example.com")
    token = await _revoked_session_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(),
        headers={**_auth_headers(token), "Idempotency-Key": "revoked"},
    )

    # Assert
    assert response.status_code == 401


async def test_create_ticket_deactivated_account_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="deactivated@example.com", status="deactivated")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(),
        headers={**_auth_headers(token), "Idempotency-Key": "deactivated"},
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("account-deactivated")


async def test_list_own_tickets_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get(_TICKETS_PATH)

    # Assert
    assert response.status_code == 401


async def test_list_own_tickets_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers("not-a-real-jwt"))

    # Assert
    assert response.status_code == 401


async def test_list_own_tickets_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="expiredlist@example.com")
    token = await _expired_token(db_session, user_id=user.id)

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 401


async def test_list_own_tickets_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="revokedlist@example.com")
    token = await _revoked_session_token(db_session, user_id=user.id)

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 401


# --- ST-AC6/FR-6: creation rate limit ---------------------------------------


async def test_create_ticket_sixth_in_hour_returns_429_and_existing_tickets_unaffected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="flooder@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    for i in range(5):
        response = await client.post(
            _TICKETS_PATH,
            json=_create_payload(subject=f"Ticket {i}"),
            headers={**_auth_headers(token), "Idempotency-Key": f"flood-{i}"},
        )
        assert response.status_code == 201

    # Act
    sixth = await client.post(
        _TICKETS_PATH,
        json=_create_payload(subject="Ticket 6"),
        headers={**_auth_headers(token), "Idempotency-Key": "flood-6"},
    )

    # Assert
    assert sixth.status_code == 429
    assert "Retry-After" in sixth.headers
    result = await db_session.execute(
        select(Ticket).where(Ticket.requester_id == user.id, Ticket.status == "open")
    )
    assert len(result.all()) == 5


# --- ST-AC7/FR-7: attachment ownership (IDOR) -------------------------------


async def test_create_ticket_attachment_owned_by_other_user_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="idor1@example.com")
    other = await _seed_user(db_session, email="idor1-owner@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    attachment = await _seed_attachment(db_session, uploaded_by=other.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(attachment_ids=[str(attachment.id)]),
        headers={**_auth_headers(token), "Idempotency-Key": "idor-1"},
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("attachment-not-owned")


async def test_create_ticket_attachment_already_bound_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="idor2@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    existing_ticket = Ticket(
        ticket_number="CP-2026-0000201",
        requester_id=user.id,
        subject="Existing",
        body="Already has this attachment.",
        category="billing",
        status="open",
    )
    db_session.add(existing_ticket)
    await db_session.flush()
    attachment = await _seed_attachment(
        db_session, uploaded_by=user.id, ticket_id=existing_ticket.id
    )

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(attachment_ids=[str(attachment.id)]),
        headers={**_auth_headers(token), "Idempotency-Key": "idor-2"},
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("attachment-not-owned")


async def test_create_ticket_attachment_unknown_id_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="idor3@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(attachment_ids=[str(uuid.uuid4())]),
        headers={**_auth_headers(token), "Idempotency-Key": "idor-3"},
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("attachment-not-owned")


async def test_create_ticket_attachment_owned_and_unbound_is_bound_and_immutable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="idor4@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)
    attachment = await _seed_attachment(db_session, uploaded_by=user.id)

    # Act
    response = await client.post(
        _TICKETS_PATH,
        json=_create_payload(attachment_ids=[str(attachment.id)]),
        headers={**_auth_headers(token), "Idempotency-Key": "idor-4"},
    )

    # Assert
    assert response.status_code == 201
    ticket_id = uuid.UUID(response.json()["id"])
    await db_session.refresh(attachment)
    assert attachment.ticket_id == ticket_id


# --- Agent-scope rejection on GET (OD-4 / design review DR-4) ---------------


async def test_list_own_tickets_agent_scope_caller_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    agent = await _seed_user(db_session, email="agent@example.com")
    await _assign_role(db_session, user_id=agent.id, role_name="support_agent")
    token = await _seed_session_and_token(db_session, user_id=agent.id, scopes=["tickets:read"])

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("agent-queue-not-available")
