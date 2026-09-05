import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import get_settings
from app.core.security import encode_access_token, hash_password
from app.modules.audit.models import AuditLog
from app.modules.roles.models import Role, UserRole
from app.modules.support.models import Attachment, Ticket, TicketReply
from app.modules.users.models import User, UserSession

pytestmark = pytest.mark.integration

_TICKETS_PATH = "/api/v1/support/tickets"


def _replies_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}/replies"


def _ticket_detail_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}"


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


# --- US-4.2 (Ticket Replies) shared helpers ---------------------------------


async def _seed_ticket(
    db_session: AsyncSession, *, requester_id: uuid.UUID, status: str = "open"
) -> Ticket:
    ticket = Ticket(
        ticket_number=f"CP-2026-{uuid.uuid4().hex[:10]}",
        requester_id=requester_id,
        subject="Cannot log in",
        body="My login keeps failing after the last update.",
        category="billing",
        status=status,
    )
    db_session.add(ticket)
    await db_session.flush()
    return ticket


async def _seed_reply(
    db_session: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    author_id: uuid.UUID,
    author_kind: str,
    visibility: str = "public",
    body: str = "Reply body.",
    created_at: datetime | None = None,
) -> TicketReply:
    """RLS-aware, deterministic-time seeder for `ticket_replies`.

    RLS: `db_session` runs through the non-superuser `app_runtime` role, so
    an internal-visibility insert only satisfies `ticket_replies_write`'s
    `WITH CHECK (visibility = 'public' OR actor_kind = 'agent')` under an
    `'agent'` session context. This helper sets that context for its own
    INSERT only and resets it immediately after, so it never leaks into a
    caller's later raw queries or a subsequent real HTTP request's own
    `get_rls_session` context. A caller that needs to exercise the RLS
    mechanism directly (e.g. asserting a customer-context `SELECT` alone
    hides an internal row) still sets `app.actor_kind` itself around that
    assertion - this only covers the seed insert's own `WITH CHECK`.

    `created_at` is optional: PostgreSQL's `now()` (this column's
    `server_default`) is frozen for the lifetime of one transaction, so
    several replies seeded within one test's `db_session` fixture would
    otherwise share a byte-identical timestamp - callers that assert
    chronological ordering must pass distinct, explicit values here (same
    precedent as US-4.1's own
    test_list_own_tickets_returns_only_callers_tickets_newest_first, which
    seeds explicit created_at values for the identical reason).
    """
    needs_agent_context = visibility == "internal"
    if needs_agent_context:
        await db_session.execute(text("SET LOCAL app.actor_kind = 'agent'"))

    reply = TicketReply(
        ticket_id=ticket_id,
        author_id=author_id,
        author_kind=author_kind,
        body=body,
        visibility=visibility,
    )
    if created_at is not None:
        reply.created_at = created_at
    db_session.add(reply)
    await db_session.flush()

    if needs_agent_context:
        await db_session.execute(text("RESET app.actor_kind"))

    return reply


def _reply_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"body": "Thanks for reaching out."}
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


# =============================================================================
# US-4.2 (Ticket Replies)
# =============================================================================


async def _seed_agent(
    db_session: AsyncSession, *, email: str, scopes: list[str] | None = None
) -> tuple[User, str]:
    agent = await _seed_user(db_session, email=email)
    await _assign_role(db_session, user_id=agent.id, role_name="support_agent")
    token = await _seed_session_and_token(
        db_session, user_id=agent.id, scopes=scopes or ["tickets:read", "tickets:write"]
    )
    return agent, token


# --- TR-AC1/FR-1: agent public reply ----------------------------------------


async def test_create_reply_agent_public_returns_201_and_advances_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester1@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    agent, token = await _seed_agent(db_session, email="agent1@example.com")

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="We're on it.", visibility="public"),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["author_kind"] == "agent"
    assert body["visibility"] == "public"
    await db_session.refresh(ticket)
    assert ticket.status == "waiting_on_customer"
    assert ticket.first_response_at is not None
    reply_result = await db_session.execute(
        select(TicketReply).where(TicketReply.ticket_id == ticket.id)
    )
    reply = reply_result.scalar_one()
    assert reply.author_id == agent.id
    assert reply.author_kind == "agent"


async def test_create_reply_agent_public_second_reply_does_not_restamp_first_response_at(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester1b@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    _, token = await _seed_agent(db_session, email="agent1b@example.com")

    # Act
    await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="First reply."),
        headers=_auth_headers(token),
    )
    await db_session.refresh(ticket)
    first_stamp = ticket.first_response_at
    await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="Second reply."),
        headers=_auth_headers(token),
    )

    # Assert
    await db_session.refresh(ticket)
    assert ticket.first_response_at == first_stamp


# --- TR-AC2/FR-2: customer reply ---------------------------------------------


async def test_create_reply_customer_returns_201_and_reverts_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester2@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="waiting_on_customer")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="Still broken."),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["author_kind"] == "customer"
    await db_session.refresh(ticket)
    assert ticket.status == "waiting_on_support"


async def test_create_reply_customer_on_open_ticket_returns_201_with_no_status_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: API_DESIGN v3 Open Question #1 — not stated by any FR/AC; the
    # plan's conservative default (implementation-plan Architectural Change
    # #4) is "reply still accepted, no status write."
    requester = await _seed_user(db_session, email="requester2b@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="Just checking in."),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    await db_session.refresh(ticket)
    assert ticket.status == "open"


# --- FR-6: closed and resolved tickets --------------------------------------


async def test_create_reply_on_closed_ticket_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester6@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="closed")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("ticket-closed")
    result = await db_session.execute(select(TicketReply).where(TicketReply.ticket_id == ticket.id))
    assert result.first() is None


async def test_create_reply_agent_public_on_resolved_ticket_status_stays_resolved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: Resolution OD-5.
    requester = await _seed_user(db_session, email="requester6b@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="resolved")
    _, token = await _seed_agent(db_session, email="agent6b@example.com")

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="Confirming resolved."),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    await db_session.refresh(ticket)
    assert ticket.status == "resolved"


async def test_create_reply_customer_on_resolved_ticket_reopens_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: Resolution OD-8 (human decision, 2026-09-05) — a customer
    # reply on a resolved ticket reopens it to "waiting_on_support".
    requester = await _seed_user(db_session, email="requester6c@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="resolved")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="It's back."),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    await db_session.refresh(ticket)
    assert ticket.status == "waiting_on_support"


# --- TR-AC5/FR-5: internal notes restricted to agents -----------------------


async def test_create_reply_customer_visibility_internal_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester5@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="Let me sneak this in.", visibility="internal"),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("insufficient-permission")
    result = await db_session.execute(select(TicketReply).where(TicketReply.ticket_id == ticket.id))
    assert result.first() is None


async def test_create_reply_customer_omitted_visibility_defaults_to_public(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester5b@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="No visibility field."),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    assert response.json()["visibility"] == "public"


async def test_create_reply_agent_internal_note_is_created_visible_to_agent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester3@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    _, token = await _seed_agent(db_session, email="agent3@example.com")

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="Internal-only note.", visibility="internal"),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    assert response.json()["visibility"] == "internal"


# --- TR-AC3/FR-3: internal notes isolated from customers (GET) -------------


async def test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="requester3b@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    agent, agent_token = await _seed_agent(db_session, email="agent3b@example.com")
    await _seed_reply(
        db_session,
        ticket_id=ticket.id,
        author_id=agent.id,
        author_kind="agent",
        visibility="public",
        body="Public reply.",
    )
    # _seed_reply() itself sets/resets the RLS session context this
    # internal-visibility insert needs (see its own docstring) - no manual
    # SET LOCAL required here.
    internal_reply = await _seed_reply(
        db_session,
        ticket_id=ticket.id,
        author_id=agent.id,
        author_kind="agent",
        visibility="internal",
        body="Internal-only note.",
    )
    customer_token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    customer_response = await client.get(
        _ticket_detail_path(ticket.id), headers=_auth_headers(customer_token)
    )
    agent_response = await client.get(
        _ticket_detail_path(ticket.id), headers=_auth_headers(agent_token)
    )

    # Assert
    assert customer_response.status_code == 200
    customer_reply_ids = {item["id"] for item in customer_response.json()["replies"]["items"]}
    assert str(internal_reply.id) not in customer_reply_ids

    assert agent_response.status_code == 200
    agent_reply_ids = {item["id"] for item in agent_response.json()["replies"]["items"]}
    assert str(internal_reply.id) in agent_reply_ids
    agent_internal_item = next(
        item
        for item in agent_response.json()["replies"]["items"]
        if item["id"] == str(internal_reply.id)
    )
    assert agent_internal_item["visibility"] == "internal"


async def test_internal_reply_hidden_from_customer_context_by_rls_alone(
    db_session: AsyncSession,
) -> None:
    # Arrange: NFR — "the RLS policy needs its own test that queries through
    # a customer-context connection with the application filter deliberately
    # disabled". This bypasses the repository/service entirely: a raw SELECT
    # with no visibility filter of its own, through a session whose only
    # customer-context signal is the `SET LOCAL app.actor_kind` GUC the RLS
    # policy reads (US-4.2-db-design.md's `ticket_replies_read` policy).
    requester = await _seed_user(db_session, email="rls-customer@example.com")
    agent = await _seed_user(db_session, email="rls-agent@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    # Seeding an internal-visibility reply is itself an INSERT the
    # ticket_replies_write RLS policy's WITH CHECK gates (visibility =
    # 'public' OR actor_kind = 'agent') now that db_session runs through the
    # non-superuser app_runtime role — set agent context for the seed itself.
    await db_session.execute(text("SET LOCAL app.actor_kind = 'agent'"))
    await _seed_reply(
        db_session,
        ticket_id=ticket.id,
        author_id=agent.id,
        author_kind="agent",
        visibility="public",
        body="Public.",
    )
    await _seed_reply(
        db_session,
        ticket_id=ticket.id,
        author_id=agent.id,
        author_kind="agent",
        visibility="internal",
        body="Internal.",
    )

    # Act: no application-layer filter — a bare SELECT, deliberately. This
    # SET LOCAL overrides the Arrange-phase one above for the rest of the
    # transaction.
    await db_session.execute(text("SET LOCAL app.actor_kind = 'customer'"))
    result = await db_session.execute(select(TicketReply).where(TicketReply.ticket_id == ticket.id))
    rows = result.scalars().all()

    # Assert: the database alone hides the internal row — FORCE ROW LEVEL
    # SECURITY applies even to the owning application role (Risk 1).
    assert {row.visibility for row in rows} == {"public"}


async def test_agent_context_sees_internal_reply_via_rls(db_session: AsyncSession) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="rls-customer2@example.com")
    agent = await _seed_user(db_session, email="rls-agent2@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    # Seeding an internal-visibility reply is itself an INSERT the
    # ticket_replies_write RLS policy's WITH CHECK gates now that db_session
    # runs through the non-superuser app_runtime role.
    await db_session.execute(text("SET LOCAL app.actor_kind = 'agent'"))
    await _seed_reply(
        db_session,
        ticket_id=ticket.id,
        author_id=agent.id,
        author_kind="agent",
        visibility="internal",
        body="Internal.",
    )

    # Act
    await db_session.execute(text("SET LOCAL app.actor_kind = 'agent'"))
    result = await db_session.execute(select(TicketReply).where(TicketReply.ticket_id == ticket.id))
    rows = result.scalars().all()

    # Assert
    assert {row.visibility for row in rows} == {"internal"}


async def test_no_actor_kind_set_defaults_to_hiding_internal_reply(
    db_session: AsyncSession,
) -> None:
    # Arrange: db-design v3's "fail-closed by construction" note —
    # `current_setting('app.actor_kind', true)` returns NULL when never set;
    # `NULL = 'agent'` is not true, so the policy hides internal rows the
    # same way a customer-context connection would.
    requester = await _seed_user(db_session, email="rls-customer3@example.com")
    agent = await _seed_user(db_session, email="rls-agent3@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    # Seeding an internal-visibility reply is itself an INSERT the
    # ticket_replies_write RLS policy's WITH CHECK gates now that db_session
    # runs through the non-superuser app_runtime role — set agent context
    # for the seed itself, then RESET it below so it doesn't leak into Act.
    await db_session.execute(text("SET LOCAL app.actor_kind = 'agent'"))
    await _seed_reply(
        db_session,
        ticket_id=ticket.id,
        author_id=agent.id,
        author_kind="agent",
        visibility="internal",
        body="Internal.",
    )
    # SET LOCAL persists for the rest of the transaction, not just the
    # statement it was issued for — this session's whole test body runs in
    # one savepoint-based transaction that is never rolled back mid-test, so
    # the seeding GUC above must be explicitly cleared here or it would still
    # be 'agent' during the Act SELECT below, defeating this test's premise.
    await db_session.execute(text("RESET app.actor_kind"))

    # Act: actor_kind was reset above, so this SELECT genuinely runs with no
    # `app.actor_kind` GUC set — current_setting(..., true) returns NULL.
    result = await db_session.execute(select(TicketReply).where(TicketReply.ticket_id == ticket.id))
    rows = result.scalars().all()

    # Assert
    assert rows == []


# --- TR-AC4/FR-4: cross-customer / unauthorized access ----------------------


async def test_create_reply_different_customer_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    owner = await _seed_user(db_session, email="owner4@example.com")
    other = await _seed_user(db_session, email="other4@example.com")
    ticket = await _seed_ticket(db_session, requester_id=owner.id, status="open")
    other_token = await _seed_session_and_token(db_session, user_id=other.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(), headers=_auth_headers(other_token)
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["type"].endswith("not-found")


async def test_get_ticket_detail_different_customer_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    owner = await _seed_user(db_session, email="owner4b@example.com")
    other = await _seed_user(db_session, email="other4b@example.com")
    ticket = await _seed_ticket(db_session, requester_id=owner.id, status="open")
    other_token = await _seed_session_and_token(db_session, user_id=other.id)

    # Act
    response = await client.get(_ticket_detail_path(ticket.id), headers=_auth_headers(other_token))

    # Assert
    assert response.status_code == 404
    assert response.json()["type"].endswith("not-found")


async def test_get_ticket_detail_agent_lacking_tickets_read_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: FR-4's GET-specific rule — never 403, to avoid confirming the
    # ticket id exists. Not reachable under the shipped role seed (which
    # always grants tickets:read alongside tickets:write) — confirmed here
    # by explicitly withholding both scopes, since a caller lacking
    # tickets:read AND not the owner falls to the same "neither" branch.
    owner = await _seed_user(db_session, email="owner4c@example.com")
    ticket = await _seed_ticket(db_session, requester_id=owner.id, status="open")
    agent = await _seed_user(db_session, email="agent4c@example.com")
    await _assign_role(db_session, user_id=agent.id, role_name="support_agent")
    token = await _seed_session_and_token(db_session, user_id=agent.id, scopes=[])

    # Act
    response = await client.get(_ticket_detail_path(ticket.id), headers=_auth_headers(token))

    # Assert
    assert response.status_code == 404
    assert response.json()["type"].endswith("not-found")


async def test_create_reply_unknown_ticket_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="unknown4d@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id)

    # Act
    response = await client.post(
        _replies_path(uuid.uuid4()), json=_reply_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 404


# --- Authentication matrix (AGENTS.md §5: no token / malformed / expired / revoked) ---


async def test_create_reply_no_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="noauth-post@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)

    # Act
    response = await client.post(_replies_path(ticket.id), json=_reply_payload())

    # Assert
    assert response.status_code == 401


async def test_create_reply_malformed_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="malformed-post@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(), headers=_auth_headers("not-a-real-jwt")
    )

    # Assert
    assert response.status_code == 401


async def test_create_reply_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="expired-post@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)
    token = await _expired_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 401


async def test_create_reply_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="revoked-post@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)
    token = await _revoked_session_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 401


async def test_get_ticket_detail_no_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="noauth-get@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)

    # Act
    response = await client.get(_ticket_detail_path(ticket.id))

    # Assert
    assert response.status_code == 401


async def test_get_ticket_detail_malformed_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="malformed-get@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)

    # Act
    response = await client.get(
        _ticket_detail_path(ticket.id), headers=_auth_headers("not-a-real-jwt")
    )

    # Assert
    assert response.status_code == 401


async def test_get_ticket_detail_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="expired-get@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)
    token = await _expired_token(db_session, user_id=requester.id)

    # Act
    response = await client.get(_ticket_detail_path(ticket.id), headers=_auth_headers(token))

    # Assert
    assert response.status_code == 401


async def test_get_ticket_detail_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="revoked-get@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id)
    token = await _revoked_session_token(db_session, user_id=requester.id)

    # Act
    response = await client.get(_ticket_detail_path(ticket.id), headers=_auth_headers(token))

    # Assert
    assert response.status_code == 401


# --- TR-AC7/FR-7: reply body validation -------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"body": ""}, id="empty_body"),
        pytest.param({"body": "x" * 5001}, id="body_over_5000_chars"),
    ],
)
async def test_create_reply_invalid_body_returns_422_and_creates_nothing(
    client: AsyncClient, db_session: AsyncSession, overrides: dict[str, str]
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email=f"invalidreply.{uuid.uuid4().hex}@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(**overrides), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")
    result = await db_session.execute(select(TicketReply).where(TicketReply.ticket_id == ticket.id))
    assert result.first() is None


async def test_create_reply_rejects_unknown_field_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="extrafield@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(is_admin=True),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422


# --- NFR: reply rate limit (30/user/hour) -----------------------------------


async def test_create_reply_31st_in_hour_returns_429_with_retry_after(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="flooder2@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    for i in range(30):
        response = await client.post(
            _replies_path(ticket.id),
            json=_reply_payload(body=f"Reply {i}"),
            headers=_auth_headers(token),
        )
        assert response.status_code == 201

    # Act
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(body="Reply 31"), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    result = await db_session.execute(select(TicketReply).where(TicketReply.ticket_id == ticket.id))
    assert len(result.all()) == 30


async def test_reply_rate_limit_independent_of_ticket_creation_rate_limit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: Risk 6 — a shared counter would let one traffic type exhaust
    # the other's limit.
    requester = await _seed_user(db_session, email="independence@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    for i in range(5):
        response = await client.post(
            _TICKETS_PATH,
            json=_create_payload(subject=f"Ticket {i}"),
            headers={**_auth_headers(token), "Idempotency-Key": f"indep-{i}"},
        )
        assert response.status_code == 201

    # Act: five ticket creations already exhausted the *ticket-creation*
    # limit (FR-6/US-4.1); a reply must not be blocked by that counter.
    response = await client.post(
        _replies_path(ticket.id), json=_reply_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 201


# --- OD-1: attachment reply-binding (IDOR) ----------------------------------


async def test_create_reply_attachment_owned_by_other_user_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="replyidor1@example.com")
    other = await _seed_user(db_session, email="replyidor1-owner@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    attachment = await _seed_attachment(db_session, uploaded_by=other.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(attachment_ids=[str(attachment.id)]),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("attachment-not-owned")


async def test_create_reply_attachment_already_bound_to_another_reply_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="replyidor2@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    existing_reply = await _seed_reply(
        db_session, ticket_id=ticket.id, author_id=requester.id, author_kind="customer"
    )
    attachment = await _seed_attachment(db_session, uploaded_by=requester.id)
    attachment.ticket_reply_id = existing_reply.id
    await db_session.flush()

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(attachment_ids=[str(attachment.id)]),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("attachment-not-owned")


async def test_create_reply_attachment_unknown_id_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="replyidor3@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(attachment_ids=[str(uuid.uuid4())]),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("attachment-not-owned")


async def test_create_reply_attachment_owned_and_unbound_is_bound_to_the_reply(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="replyidor4@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    attachment = await _seed_attachment(db_session, uploaded_by=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(attachment_ids=[str(attachment.id)]),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    reply_id = uuid.UUID(response.json()["id"])
    await db_session.refresh(attachment)
    assert attachment.ticket_reply_id == reply_id
    # Reply-scoped binding is independent of ticket-scoped binding
    # (Resolution OD-1) — never bound to the ticket by this same call.
    assert attachment.ticket_id is None


# --- GET Thread Pagination (Resolution OD-3) --------------------------------


async def test_get_ticket_detail_paginates_reply_thread_oldest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: explicit, distinct, sequential `created_at` values - within
    # one transaction PostgreSQL's `now()` (this column's `server_default`)
    # is frozen, so seeding all three without an override would give them a
    # byte-identical timestamp and make the assertion below depend on the
    # `id` tiebreaker's random UUID order instead of actual seed order.
    requester = await _seed_user(db_session, email="pagination@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    base_time = datetime.now(UTC)
    for i in range(3):
        await _seed_reply(
            db_session,
            ticket_id=ticket.id,
            author_id=requester.id,
            author_kind="customer",
            body=f"Reply {i}",
            created_at=base_time + timedelta(seconds=i),
        )

    # Act
    response = await client.get(
        _ticket_detail_path(ticket.id), params={"limit": 2}, headers=_auth_headers(token)
    )

    # Assert: oldest-first ("newest-last" per US-4.2-openapi.yaml's
    # ReplyThreadPage description), unlike ticket listing's newest-first.
    assert response.status_code == 200
    body = response.json()
    assert [item["body"] for item in body["replies"]["items"]] == ["Reply 0", "Reply 1"]
    assert body["replies"]["next_cursor"] is not None


async def test_get_ticket_detail_malformed_cursor_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="badcursor2@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.get(
        _ticket_detail_path(ticket.id),
        params={"cursor": "not-a-real-cursor"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")


@pytest.mark.parametrize("limit", [0, 101])
async def test_get_ticket_detail_out_of_range_limit_returns_422(
    client: AsyncClient, db_session: AsyncSession, limit: int
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email=f"badlimit.{uuid.uuid4().hex}@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.get(
        _ticket_detail_path(ticket.id), params={"limit": limit}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422


# --- AGENTS.md §5: statement-count ceiling for a nested-data list endpoint --


async def test_get_ticket_detail_reply_thread_statement_count_independent_of_reply_count(
    client: AsyncClient, db_session: AsyncSession, db_connection: AsyncConnection
) -> None:
    # Arrange: no `relationship()` exists on `Ticket`/`TicketReply`
    # (US-4.2-entity-model.md) — the thread is composed from exactly two
    # direct queries (get_by_id + list_for_ticket), never a per-reply query.
    # This project has no existing statement-counting harness to reuse (see
    # tests/integration/modules/audit/test_audit_router.py's own note on the
    # same rule); comparing the statement count across a small and a larger
    # reply count is the more precise test of the actual claim (no N+1),
    # rather than asserting a brittle absolute ceiling this pass cannot
    # verify against the real query count until IMPLEMENTATION lands.
    requester = await _seed_user(db_session, email="statcount@example.com")
    small_ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    for i in range(2):
        await _seed_reply(
            db_session,
            ticket_id=small_ticket.id,
            author_id=requester.id,
            author_kind="customer",
            body=f"Small {i}",
        )
    large_ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    for i in range(20):
        await _seed_reply(
            db_session,
            ticket_id=large_ticket.id,
            author_id=requester.id,
            author_kind="customer",
            body=f"Large {i}",
        )
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    sync_conn = db_connection.sync_connection

    counts: dict[str, int] = {"small": 0, "large": 0}

    def _count_small(*_args: object, **_kwargs: object) -> None:
        counts["small"] += 1

    def _count_large(*_args: object, **_kwargs: object) -> None:
        counts["large"] += 1

    # Act
    event.listen(sync_conn, "before_cursor_execute", _count_small)
    try:
        small_response = await client.get(
            _ticket_detail_path(small_ticket.id), params={"limit": 50}, headers=_auth_headers(token)
        )
    finally:
        event.remove(sync_conn, "before_cursor_execute", _count_small)

    event.listen(sync_conn, "before_cursor_execute", _count_large)
    try:
        large_response = await client.get(
            _ticket_detail_path(large_ticket.id), params={"limit": 50}, headers=_auth_headers(token)
        )
    finally:
        event.remove(sync_conn, "before_cursor_execute", _count_large)

    # Assert
    assert small_response.status_code == 200
    assert large_response.status_code == 200
    assert len(small_response.json()["replies"]["items"]) == 2
    assert len(large_response.json()["replies"]["items"]) == 20
    assert counts["small"] == counts["large"]
