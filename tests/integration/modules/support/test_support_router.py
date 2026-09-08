import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import event, func, literal, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import get_settings
from app.core.security import encode_access_token, hash_password
from app.modules.audit.models import AuditLog
from app.modules.roles.models import Role, UserRole
from app.modules.support.models import Attachment, Ticket, TicketReply
from app.modules.support.repository import TicketRepository
from app.modules.users.models import User, UserSession

pytestmark = pytest.mark.integration

_TICKETS_PATH = "/api/v1/support/tickets"


def _replies_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}/replies"


def _ticket_detail_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}"


def _resolve_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}/resolve"


def _close_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}/close"


def _reopen_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}/reopen"


def _assign_path(ticket_id: uuid.UUID) -> str:
    return f"{_TICKETS_PATH}/{ticket_id}/assign"


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
    db_session: AsyncSession,
    *,
    requester_id: uuid.UUID,
    status: str = "open",
    category: str = "billing",
    resolved_at: datetime | None = None,
    resolution_note: str | None = None,
    closed_at: datetime | None = None,
    closed_by: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    updated_at: datetime | None = None,
) -> Ticket:
    """`assignee_id` (US-4.4, nullable FK, no default — omitting it leaves
    the row unassigned) and `updated_at` are both new, optional kwargs. Every
    US-4.4 test that asserts ordering by `updated_at` (AQ-AC1) or that
    `updated_at` is *unchanged* by assign/unassign (DR-3) MUST pass an
    explicit, distinct value here — `updated_at` carries
    `server_default=func.now()`, frozen for the lifetime of one transaction
    (AGENTS.md §5), so several tickets seeded within one test's `db_session`
    would otherwise share a byte-identical timestamp and any assertion about
    it would silently degrade to primary-key tiebreak order instead.
    """
    ticket = Ticket(
        ticket_number=f"CP-2026-{uuid.uuid4().hex[:10]}",
        requester_id=requester_id,
        subject="Cannot log in",
        body="My login keeps failing after the last update.",
        category=category,
        status=status,
    )
    if assignee_id is not None:
        ticket.assignee_id = assignee_id
    if updated_at is not None:
        ticket.updated_at = updated_at
    # US-4.3 db-design.md v3's CHECK constraints require both resolution
    # fields together whenever status="resolved" (ck_tickets_resolved_
    # requires_resolution_fields) and both closure fields together whenever
    # status="closed" (ck_tickets_closed_requires_closed_fields, a full
    # biconditional — a "closed" row with either field NULL violates it on
    # INSERT once T3's migration lands). Callers that only care about status
    # (most of this module's pre-existing US-4.1/US-4.2 seeds) get sane
    # defaults here rather than each needing to know about these constraints;
    # an explicit kwarg always wins.
    if status == "resolved":
        resolved_at = resolved_at or datetime.now(UTC)
        resolution_note = resolution_note or "Seeded resolution."
    if status == "closed":
        closed_at = closed_at or datetime.now(UTC)
        closed_by = closed_by or requester_id
    if resolved_at is not None:
        ticket.resolved_at = resolved_at
    if resolution_note is not None:
        ticket.resolution_note = resolution_note
    if closed_at is not None:
        ticket.closed_at = closed_at
    if closed_by is not None:
        ticket.closed_by = closed_by
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


# --- US-4.4: `reject_agent_queue_access` retired — agent branch now live ---
# NFR ("Removing reject_agent_queue_access MUST update, not delete, the
# US-4.1 tests that assert its 403 — the replacement assertion is the new
# agent branch") / implementation_plan.md Risk 7 / task_breakdown.md T9's
# explicit instruction to confirm this diff. This is the same test function
# US-4.1/US-4.2 named (`test_list_own_tickets_agent_scope_caller_returns_403`),
# updated in place — not deleted and not replaced by a differently-named test
# — to assert the new AQ-AC1 agent-branch `200` instead of the retired `403`.


async def test_list_own_tickets_agent_scope_caller_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    agent = await _seed_user(db_session, email="agent@example.com")
    await _assign_role(db_session, user_id=agent.id, role_name="support_agent")
    token = await _seed_session_and_token(db_session, user_id=agent.id, scopes=["tickets:read"])

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))

    # Assert: AQ-AC1 — a tickets:read caller now reaches the live agent
    # branch (`AgentTicketListResponse`), never the retired `403
    # agent-queue-not-available`.
    assert response.status_code == 200
    assert "items" in response.json()


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


# =============================================================================
# US-4.3 (Ticket Resolution)
# =============================================================================

_RESOLUTION_NOTE = "Restarted the affected service; confirmed the customer's report is fixed."
_RESOLUTION_WINDOW_DAYS = 7  # implementation_plan.md Decision 7's shared constant


def _resolve_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"resolution_note": _RESOLUTION_NOTE}
    payload.update(overrides)
    return payload


# --- FR-1: agent resolves a ticket ------------------------------------------


@pytest.mark.parametrize("status_before", ["open", "waiting_on_support", "waiting_on_customer"])
async def test_resolve_ticket_agent_from_eligible_status_returns_200_and_persists(
    client: AsyncClient, db_session: AsyncSession, status_before: str
) -> None:
    # Arrange: OD-5's resolve-eligible source-status set.
    requester = await _seed_user(db_session, email=f"resolve.{uuid.uuid4().hex}@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status=status_before)
    _, token = await _seed_agent(db_session, email=f"agent.{uuid.uuid4().hex}@example.com")

    # Act
    response = await client.post(
        _resolve_path(ticket.id), json=_resolve_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None
    assert "resolution_note" not in body
    assert "closed_by" not in body
    await db_session.refresh(ticket)
    assert ticket.status == "resolved"
    assert ticket.resolution_note == _RESOLUTION_NOTE
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_resolved")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.outcome == "success"


# --- FR-10: missing/empty resolution_note -----------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"resolution_note": ""}, id="empty_note"),
        pytest.param({}, id="missing_note"),
    ],
)
async def test_resolve_ticket_invalid_resolution_note_returns_422_and_leaves_ticket_unchanged(
    client: AsyncClient, db_session: AsyncSession, overrides: dict[str, object]
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email=f"resolve422.{uuid.uuid4().hex}@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    _, token = await _seed_agent(db_session, email=f"agent422.{uuid.uuid4().hex}@example.com")

    # Act
    response = await client.post(
        _resolve_path(ticket.id), json=overrides, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")
    await db_session.refresh(ticket)
    assert ticket.status == "open"


# --- FR-7: customer attempts to resolve, and check-order vs. FR-6 ----------


async def test_resolve_ticket_customer_on_open_ticket_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="resolve403@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _resolve_path(ticket.id), json=_resolve_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("insufficient-permission")


async def test_resolve_ticket_customer_on_closed_ticket_returns_409_not_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: the spec's own NFR — state checked before actor.
    requester = await _seed_user(db_session, email="resolve409actor@example.com")
    ticket = await _seed_ticket(
        db_session, requester_id=requester.id, status="closed", closed_at=datetime.now(UTC)
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _resolve_path(ticket.id), json=_resolve_payload(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 409
    body = response.json()
    assert body["type"].endswith("invalid-state-transition")
    assert body["allowed_events"] == []


# --- FR-6: illegal transition rejected --------------------------------------


@pytest.mark.parametrize(
    "path_factory,status_before,expected_allowed",
    [
        pytest.param(_resolve_path, "closed", [], id="resolve_from_closed"),
        pytest.param(_reopen_path, "open", ["resolve", "close"], id="reopen_from_open"),
        pytest.param(_reopen_path, "closed", [], id="reopen_from_closed"),
        pytest.param(_close_path, "closed", [], id="close_from_closed"),
    ],
)
async def test_transition_endpoints_ineligible_status_returns_409_with_allowed_events(
    client: AsyncClient,
    db_session: AsyncSession,
    path_factory: object,
    status_before: str,
    expected_allowed: list[str],
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email=f"transition409.{uuid.uuid4().hex}@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status=status_before,
        closed_at=datetime.now(UTC) if status_before == "closed" else None,
    )
    _, token = await _seed_agent(db_session, email=f"agent409.{uuid.uuid4().hex}@example.com")

    # Act
    response = await client.post(
        path_factory(ticket.id),  # type: ignore[operator]
        json=_resolve_payload() if path_factory is _resolve_path else {},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 409
    body = response.json()
    assert body["type"].endswith("invalid-state-transition")
    assert body["allowed_events"] == expected_allowed


# --- FR-9: concurrent resolution (conditional UPDATE, second caller loses) --


async def test_resolve_ticket_second_concurrent_caller_returns_409_first_note_intact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: two agents "simultaneously" resolving the same ticket —
    # exercised sequentially against the real conditional UPDATE (the
    # second call's WHERE no longer matches once the first has committed),
    # which is what actually proves FR-9's "exactly one succeeds."
    requester = await _seed_user(db_session, email="concurrent409@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    _, first_token = await _seed_agent(db_session, email="agent-first@example.com")
    _, second_token = await _seed_agent(db_session, email="agent-second@example.com")

    # Act
    first = await client.post(
        _resolve_path(ticket.id),
        json=_resolve_payload(resolution_note="First agent's note."),
        headers=_auth_headers(first_token),
    )
    second = await client.post(
        _resolve_path(ticket.id),
        json=_resolve_payload(resolution_note="Second agent's note — must not win."),
        headers=_auth_headers(second_token),
    )

    # Assert
    assert first.status_code == 200
    assert second.status_code == 409
    await db_session.refresh(ticket)
    assert ticket.resolution_note == "First agent's note."


# --- FR-8: acting on someone else's ticket ----------------------------------


@pytest.mark.parametrize(
    "path_factory,status_before",
    [
        pytest.param(_resolve_path, "open", id="resolve"),
        pytest.param(_close_path, "open", id="close"),
        pytest.param(_reopen_path, "resolved", id="reopen"),
    ],
)
async def test_transition_endpoints_different_customer_returns_404(
    client: AsyncClient, db_session: AsyncSession, path_factory: object, status_before: str
) -> None:
    # Arrange
    owner = await _seed_user(db_session, email=f"txowner.{uuid.uuid4().hex}@example.com")
    other = await _seed_user(db_session, email=f"txother.{uuid.uuid4().hex}@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=owner.id,
        status=status_before,
        resolved_at=datetime.now(UTC) if status_before == "resolved" else None,
    )
    other_token = await _seed_session_and_token(db_session, user_id=other.id)

    # Act
    response = await client.post(
        path_factory(ticket.id),  # type: ignore[operator]
        json=_resolve_payload() if path_factory is _resolve_path else {},
        headers=_auth_headers(other_token),
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["type"].endswith("not-found")


# --- FR-2: ticket closed by requester or agent ------------------------------


async def test_close_ticket_requester_returns_200_and_persists_closed_by(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="closebyself@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(_close_path(ticket.id), json={}, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["closed_at"] is not None
    await db_session.refresh(ticket)
    assert ticket.closed_by == requester.id
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_closed")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == requester.id


async def test_close_ticket_agent_returns_200_and_persists_closed_by_agent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="closebyagent@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="waiting_on_support")
    agent, token = await _seed_agent(db_session, email="closingagent@example.com")

    # Act
    response = await client.post(
        _close_path(ticket.id), json={"reason": "Duplicate."}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 200
    await db_session.refresh(ticket)
    assert ticket.closed_by == agent.id
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_closed")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == agent.id


async def test_close_ticket_from_resolved_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: FR-2's "any non-closed status" scope includes "resolved".
    requester = await _seed_user(db_session, email="closefromresolved@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="resolved",
        resolved_at=datetime.now(UTC),
        resolution_note="Already resolved.",
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(_close_path(ticket.id), json={}, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


# --- FR-5: direct reopen of a resolved ticket -------------------------------


async def test_reopen_ticket_requester_within_window_returns_200_and_clears_resolved_at(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="reopenself@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="resolved",
        resolved_at=datetime.now(UTC) - timedelta(days=1),
        resolution_note="Thought it was fixed.",
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(_reopen_path(ticket.id), json={}, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "waiting_on_support"
    assert body["resolved_at"] is None
    await db_session.refresh(ticket)
    assert ticket.status == "waiting_on_support"
    assert ticket.resolved_at is None
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_reopened")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == requester.id


async def test_reopen_ticket_agent_within_window_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="reopenagentowner@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="resolved",
        resolved_at=datetime.now(UTC) - timedelta(hours=1),
        resolution_note="Fixed.",
    )
    agent, token = await _seed_agent(db_session, email="reopeningagent@example.com")

    # Act
    response = await client.post(_reopen_path(ticket.id), json={}, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_reopened")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == agent.id


async def test_reopen_ticket_outside_window_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: OD-4 — the reopen guard is inclusive at exactly 7 days. A
    # 5-minute margin past the boundary (not the 1-second margin the OD-4
    # boundary test itself uses) — the guard is evaluated by Postgres against
    # its own transaction-start now() (frozen for the whole transaction,
    # per _seed_reply's own docstring), which is always earlier than this
    # Arrange block's `datetime.now(UTC)` call by however long fixture setup
    # (including this test's own password hashing) took. A 1-second margin
    # would make this assertion flaky against that setup gap; 5 minutes is
    # unambiguously outside the window under any realistic setup latency.
    requester = await _seed_user(db_session, email="reopenoutside@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="resolved",
        resolved_at=datetime.now(UTC) - timedelta(days=_RESOLUTION_WINDOW_DAYS, minutes=5),
        resolution_note="Old fix.",
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(_reopen_path(ticket.id), json={}, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("invalid-state-transition")
    await db_session.refresh(ticket)
    assert ticket.status == "resolved"


async def _seed_ticket_resolved_at_exact_window_boundary(
    db_session: AsyncSession, *, requester_id: uuid.UUID
) -> Ticket:
    """Seeds a "resolved" ticket whose `resolved_at` is exactly
    `_RESOLUTION_WINDOW_DAYS` ago as computed by Postgres itself, not Python's
    wall clock. The reopen guard's own `now() - make_interval(...)` predicate
    reads the same transaction-frozen `now()` this UPDATE does (`db_session`
    runs the whole test in one transaction), so this seed and that predicate
    can never disagree on which side of the boundary they're on - unlike a
    Python-computed `datetime.now(UTC) - timedelta(...)`, whose comparison
    against Postgres's `now()` depends on real elapsed wall-clock time between
    Arrange and Act.
    """
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester_id,
        status="resolved",
        resolution_note="Right at the edge.",
    )
    await db_session.execute(
        update(Ticket)
        .where(Ticket.id == ticket.id)
        .values(
            resolved_at=func.now() - func.make_interval(0, 0, 0, literal(_RESOLUTION_WINDOW_DAYS))
        )
    )
    await db_session.flush()
    await db_session.refresh(ticket)
    return ticket


async def test_reopen_ticket_at_exactly_7_days_boundary_succeeds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: OD-4 — the reply/reopen guard is inclusive
    # (`now - resolved_at <= 7 days`); exactly 7 days ago must still succeed.
    # This is the one pairing no existing test in this codebase exercises
    # (implementation_plan.md Testing Strategy's own called-out gap).
    # resolved_at is seeded server-side (see helper docstring) so the boundary
    # comparison is deterministic regardless of wall-clock timing.
    requester = await _seed_user(db_session, email="reopenboundary@example.com")
    ticket = await _seed_ticket_resolved_at_exact_window_boundary(
        db_session, requester_id=requester.id
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(_reopen_path(ticket.id), json={}, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "waiting_on_support"


# --- Authentication matrix (AGENTS.md §5) -----------------------------------


@pytest.mark.parametrize(
    "path_factory,status_before",
    [
        pytest.param(_resolve_path, "open", id="resolve"),
        pytest.param(_close_path, "open", id="close"),
        pytest.param(_reopen_path, "resolved", id="reopen"),
    ],
)
@pytest.mark.parametrize(
    "token_factory_name",
    ["no_token", "malformed", "expired", "revoked"],
)
async def test_transition_endpoints_auth_matrix_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
    path_factory: object,
    status_before: str,
    token_factory_name: str,
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email=f"authmatrix.{uuid.uuid4().hex}@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status=status_before,
        resolved_at=datetime.now(UTC) if status_before == "resolved" else None,
    )
    headers: dict[str, str] = {}
    if token_factory_name == "malformed":
        headers = _auth_headers("not-a-real-jwt")
    elif token_factory_name == "expired":
        headers = _auth_headers(await _expired_token(db_session, user_id=requester.id))
    elif token_factory_name == "revoked":
        headers = _auth_headers(await _revoked_session_token(db_session, user_id=requester.id))
    # "no_token": headers stays {}

    # Act
    response = await client.post(
        path_factory(ticket.id),  # type: ignore[operator]
        json=_resolve_payload() if path_factory is _resolve_path else {},
        headers=headers,
    )

    # Assert
    assert response.status_code == 401


# --- FR-4 (modified): reply reopens a resolved ticket, now audited (DR-4) --


async def test_create_reply_customer_on_resolved_within_window_writes_reopened_audit_entry(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: DESIGN_REVIEW v2 DR-4 — this reopening path (via the existing
    # US-4.2 replies endpoint) must now also write `audit_log`
    # (`event=ticket_reopened`), matching FR-5's direct `/reopen` audit.
    requester = await _seed_user(db_session, email="fr4audit@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="resolved",
        resolved_at=datetime.now(UTC) - timedelta(hours=1),
        resolution_note="Thought it was fixed.",
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="It broke again."),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    await db_session.refresh(ticket)
    assert ticket.status == "waiting_on_support"
    assert ticket.resolved_at is None
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_reopened")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == requester.id


async def test_create_reply_customer_on_resolved_outside_window_makes_no_status_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: implementation_plan.md Decision 2 — the reply-driven reopen
    # shares the same window-guarded conditional UPDATE as /reopen; a reply
    # is still accepted (FR-6 does not gate replies) but the ticket does not
    # transition once outside the window. A 5-minute margin past the
    # boundary, not 1 second — see test_reopen_ticket_outside_window_returns_409's
    # own comment on why (Postgres's frozen-per-transaction now() vs. this
    # Arrange block's datetime.now(UTC) call).
    requester = await _seed_user(db_session, email="fr4outsidewindow@example.com")
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="resolved",
        resolved_at=datetime.now(UTC) - timedelta(days=_RESOLUTION_WINDOW_DAYS, minutes=5),
        resolution_note="Old fix.",
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.post(
        _replies_path(ticket.id),
        json=_reply_payload(body="Still broken?"),
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 201
    await db_session.refresh(ticket)
    assert ticket.status == "resolved"
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_reopened")
    )
    assert audit_result.first() is None


# =============================================================================
# US-4.4 (Agent Ticket Queue & Assignment)
# =============================================================================

_CUSTOMER_TICKET_READ_FIELDS = {
    "id",
    "ticket_number",
    "status",
    "requester_id",
    "subject",
    "body",
    "category",
    "created_at",
    "updated_at",
}
_AGENT_TICKET_READ_FIELDS = _CUSTOMER_TICKET_READ_FIELDS | {"assignee_id"}


async def _seed_agent_only(db_session: AsyncSession, *, email: str, status: str = "active") -> User:
    """A `support_agent`-holding user seeded for use as an assign *target*
    only — no session/token needed, since the target is referenced by id in
    the request body, never authenticated itself in these tests.
    """
    agent = await _seed_user(db_session, email=email, status=status)
    await _assign_role(db_session, user_id=agent.id, role_name="support_agent")
    return agent


# --- AQ-AC1/FR-1: agent sees the queue --------------------------------------


async def test_list_own_tickets_agent_branch_orders_oldest_updated_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: explicit, distinct `updated_at` values (AGENTS.md §5) — the
    # frozen-per-transaction `now()` would otherwise tie-break on (random)
    # primary key, not the ordering under test.
    requester = await _seed_user(db_session, email="queue.order@example.com")
    now = datetime.now(UTC)
    oldest = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", updated_at=now - timedelta(hours=2)
    )
    middle = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="waiting_on_support",
        updated_at=now - timedelta(hours=1),
    )
    newest = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", updated_at=now
    )
    _, token = await _seed_agent(db_session, email="queue.agent@example.com")

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))

    # Assert: AQ-AC1 — "every non-closed ticket regardless of requester,
    # ordered oldest-updated first"; every item carries `assignee_id`; no
    # total count field anywhere in the envelope.
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert ids.index(str(oldest.id)) < ids.index(str(middle.id)) < ids.index(str(newest.id))
    for item in body["items"]:
        assert set(item.keys()) == _AGENT_TICKET_READ_FIELDS
    assert "total" not in body
    assert "count" not in body


async def test_list_own_tickets_agent_branch_excludes_closed_by_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="queue.excludeclosed@example.com")
    open_ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    closed_ticket = await _seed_ticket(db_session, requester_id=requester.id, status="closed")
    _, token = await _seed_agent(db_session, email="queue.agent2@example.com")

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))

    # Assert
    ids = [item["id"] for item in response.json()["items"]]
    assert str(open_ticket.id) in ids
    assert str(closed_ticket.id) not in ids


async def test_list_own_tickets_agent_branch_status_closed_is_the_only_way_closed_appears(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: AQ-AC2 — "status=closed is the only way a closed ticket appears".
    requester = await _seed_user(db_session, email="queue.explicitclosed@example.com")
    closed_ticket = await _seed_ticket(db_session, requester_id=requester.id, status="closed")
    _, token = await _seed_agent(db_session, email="queue.agent3@example.com")

    # Act
    response = await client.get(
        _TICKETS_PATH, params={"status": "closed"}, headers=_auth_headers(token)
    )

    # Assert
    ids = [item["id"] for item in response.json()["items"]]
    assert str(closed_ticket.id) in ids


# --- AQ-AC2/FR-2: queue filters ----------------------------------------------


async def test_list_own_tickets_agent_branch_filters_by_category(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="queue.category@example.com")
    billing = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", category="billing"
    )
    technical = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", category="technical"
    )
    _, token = await _seed_agent(db_session, email="queue.agent4@example.com")

    # Act
    response = await client.get(
        _TICKETS_PATH, params={"category": "billing"}, headers=_auth_headers(token)
    )

    # Assert
    ids = [item["id"] for item in response.json()["items"]]
    assert str(billing.id) in ids
    assert str(technical.id) not in ids


async def test_list_own_tickets_agent_branch_assignee_id_me_returns_only_own(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="queue.assignedme@example.com")
    agent, token = await _seed_agent(db_session, email="queue.agent5@example.com")
    other_agent = await _seed_agent_only(db_session, email="queue.otheragent@example.com")
    mine = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=agent.id
    )
    not_mine = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=other_agent.id
    )

    # Act
    response = await client.get(
        _TICKETS_PATH, params={"assignee_id": "me"}, headers=_auth_headers(token)
    )

    # Assert: AQ-AC2 — "assignee_id=me resolves to the calling agent's own id".
    ids = [item["id"] for item in response.json()["items"]]
    assert str(mine.id) in ids
    assert str(not_mine.id) not in ids


async def test_list_own_tickets_agent_branch_assignee_id_none_returns_only_unassigned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="queue.unassigned@example.com")
    agent, token = await _seed_agent(db_session, email="queue.agent6@example.com")
    unassigned = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    assigned = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=agent.id
    )

    # Act
    response = await client.get(
        _TICKETS_PATH, params={"assignee_id": "none"}, headers=_auth_headers(token)
    )

    # Assert: AQ-AC2 — "assignee_id=none returns only unassigned tickets".
    ids = [item["id"] for item in response.json()["items"]]
    assert str(unassigned.id) in ids
    assert str(assigned.id) not in ids


async def test_list_own_tickets_agent_branch_assignee_id_specific_uuid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="queue.specific@example.com")
    _, token = await _seed_agent(db_session, email="queue.agent7@example.com")
    target_agent = await _seed_agent_only(db_session, email="queue.targetagent@example.com")
    theirs = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=target_agent.id
    )
    unrelated = await _seed_ticket(db_session, requester_id=requester.id, status="open")

    # Act
    response = await client.get(
        _TICKETS_PATH, params={"assignee_id": str(target_agent.id)}, headers=_auth_headers(token)
    )

    # Assert
    ids = [item["id"] for item in response.json()["items"]]
    assert str(theirs.id) in ids
    assert str(unrelated.id) not in ids


async def test_list_own_tickets_agent_branch_malformed_assignee_id_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    _, token = await _seed_agent(db_session, email="queue.malformed@example.com")

    # Act
    response = await client.get(
        _TICKETS_PATH, params={"assignee_id": "not-a-uuid"}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")


async def test_list_own_tickets_agent_branch_paginates_by_cursor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: three tickets, page size 2 — the agent branch's own
    # `(updated_at, id)` cursor encoding (not `list_for_requester`'s).
    requester = await _seed_user(db_session, email="queue.paginate@example.com")
    now = datetime.now(UTC)
    for i in range(3):
        await _seed_ticket(
            db_session,
            requester_id=requester.id,
            status="open",
            updated_at=now - timedelta(hours=3 - i),
        )
    _, token = await _seed_agent(db_session, email="queue.agent8@example.com")

    # Act
    first_page = await client.get(_TICKETS_PATH, params={"limit": 2}, headers=_auth_headers(token))
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None
    second_page = await client.get(
        _TICKETS_PATH,
        params={"limit": 2, "cursor": first_body["next_cursor"]},
        headers=_auth_headers(token),
    )

    # Assert
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body["items"]) == 1
    assert {item["id"] for item in first_body["items"]}.isdisjoint(
        {item["id"] for item in second_body["items"]}
    )


# --- AQ-AC5/AQ-AC6/FR-5/FR-6: customer branch is unaffected -----------------


async def test_list_own_tickets_customer_branch_response_has_no_assignee_id_field(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: AQ-AC5 — byte-identical to the pre-existing US-4.1 contract,
    # not merely "no assignee_id key present alongside others"
    # (implementation_plan.md Risk 1).
    requester = await _seed_user(db_session, email="customer.shape@example.com")
    await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert set(body["items"][0].keys()) == _CUSTOMER_TICKET_READ_FIELDS


async def test_list_own_tickets_customer_branch_ignores_agent_only_query_params(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: AQ-AC6 — a customer's own-tickets result is unaffected by
    # agent-only query params, and no 422 is returned for them either (the
    # ownership filter, not parameter validation, protects the data).
    requester = await _seed_user(db_session, email="customer.ignoreparams@example.com")
    mine = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    other = await _seed_user(db_session, email="customer.other@example.com")
    await _seed_ticket(db_session, requester_id=other.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    plain_response = await client.get(_TICKETS_PATH, headers=_auth_headers(token))
    with_agent_params_response = await client.get(
        _TICKETS_PATH,
        params={"assignee_id": "not-a-real-uuid-or-me-or-none", "category": "anything"},
        headers=_auth_headers(token),
    )

    # Assert: identical result set either way — never another customer's
    # ticket, never a 422 for the malformed agent-only `assignee_id`.
    assert with_agent_params_response.status_code == 200
    plain_ids = {item["id"] for item in plain_response.json()["items"]}
    with_params_ids = {item["id"] for item in with_agent_params_response.json()["items"]}
    assert plain_ids == with_params_ids == {str(mine.id)}


# --- AQ-AC3/FR-3: assign ----------------------------------------------------


async def test_assign_ticket_returns_200_and_persists_assignee_with_audit_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="assign.happy.customer@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    caller, token = await _seed_agent(db_session, email="assign.happy.caller@example.com")
    target = await _seed_agent_only(db_session, email="assign.happy.target@example.com")

    # Act
    response = await client.post(
        _assign_path(ticket.id),
        json={"assignee_id": str(target.id)},
        headers=_auth_headers(token),
    )

    # Assert: AQ-AC3 — 200 with assignee_id set, audit entry written in the
    # same transaction as the write.
    assert response.status_code == 200
    body = response.json()
    assert body["assignee_id"] == str(target.id)
    await db_session.refresh(ticket)
    assert ticket.assignee_id == target.id
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_assigned")
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == caller.id


async def test_assign_ticket_reassign_replaces_assignee_and_audits_the_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: AQ-AC3 — "re-assigning an already-assigned ticket replaces
    # the assignee and audits the change".
    requester = await _seed_user(db_session, email="assign.reassign.customer@example.com")
    first_target = await _seed_agent_only(db_session, email="assign.reassign.first@example.com")
    ticket = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=first_target.id
    )
    _, token = await _seed_agent(db_session, email="assign.reassign.caller@example.com")
    second_target = await _seed_agent_only(db_session, email="assign.reassign.second@example.com")

    # Act
    response = await client.post(
        _assign_path(ticket.id),
        json={"assignee_id": str(second_target.id)},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["assignee_id"] == str(second_target.id)
    await db_session.refresh(ticket)
    assert ticket.assignee_id == second_target.id
    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == ticket.id, AuditLog.event == "ticket_assigned")
    )
    # The ticket is seeded directly with `assignee_id=first_target.id` (no
    # prior service call, so no prior audit row) and exactly one
    # `POST /assign` call is made above — `TicketService.assign_ticket`
    # writes exactly one `ticket_assigned` audit row per call
    # (service.py's `assign_ticket`, ~lines 561-568), so only 1 row exists.
    assert len(audit_result.scalars().all()) == 1


async def test_assign_ticket_self_assign_succeeds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: Assumption #5 — the caller may name their own id.
    requester = await _seed_user(db_session, email="assign.self.customer@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    caller, token = await _seed_agent(db_session, email="assign.self.caller@example.com")

    # Act
    response = await client.post(
        _assign_path(ticket.id), json={"assignee_id": str(caller.id)}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["assignee_id"] == str(caller.id)


# --- AQ-AC7/FR-7: assignment requires the scope -----------------------------


async def test_assign_ticket_customer_returns_404_indistinguishable_from_unknown_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: AQ-AC7 — a customer (no tickets:* scope) gets 404, and the
    # body is identical whether the ticket exists or not (never confirming
    # the ticket id exists).
    requester = await _seed_user(db_session, email="assign.customer404@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    token = await _seed_session_and_token(db_session, user_id=requester.id)
    target = await _seed_agent_only(db_session, email="assign.customer404.target@example.com")

    # Act
    existing_ticket_response = await client.post(
        _assign_path(ticket.id), json={"assignee_id": str(target.id)}, headers=_auth_headers(token)
    )
    unknown_ticket_response = await client.post(
        _assign_path(uuid.uuid4()),
        json={"assignee_id": str(target.id)},
        headers=_auth_headers(token),
    )

    # Assert: identical on every field that could leak whether the ticket
    # id exists. `instance` is deliberately excluded from this comparison —
    # `app/main.py`'s ProblemBase handler sets it to `request.url.path`,
    # which legitimately differs between the two request paths themselves
    # (a different ticket id in the URL) without that difference revealing
    # anything about the ticket's existence.
    assert existing_ticket_response.status_code == 404
    assert unknown_ticket_response.status_code == 404
    existing_body = existing_ticket_response.json()
    unknown_body = unknown_ticket_response.json()
    existing_body.pop("instance", None)
    unknown_body.pop("instance", None)
    assert existing_body == unknown_body


async def test_assign_ticket_read_only_agent_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="assign.readonly.customer@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    reader = await _seed_user(db_session, email="assign.readonly.agent@example.com")
    await _assign_role(db_session, user_id=reader.id, role_name="support_agent")
    token = await _seed_session_and_token(db_session, user_id=reader.id, scopes=["tickets:read"])
    target = await _seed_agent_only(db_session, email="assign.readonly.target@example.com")

    # Act
    response = await client.post(
        _assign_path(ticket.id), json={"assignee_id": str(target.id)}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("insufficient-permission")


# --- AQ-AC8/FR-8 (and OD-4): assignee must be an agent ----------------------


async def test_assign_ticket_target_lacking_tickets_write_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="assign.badtarget.customer@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    _, token = await _seed_agent(db_session, email="assign.badtarget.caller@example.com")
    non_agent_target = await _seed_user(db_session, email="assign.badtarget.target@example.com")

    # Act
    response = await client.post(
        _assign_path(ticket.id),
        json={"assignee_id": str(non_agent_target.id)},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")
    await db_session.refresh(ticket)
    assert ticket.assignee_id is None


async def test_assign_ticket_deactivated_target_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: OD-4's adopted default — a target holding tickets:write but
    # a deactivated account is rejected the same way. Not yet
    # human-confirmed (docs/decisions/US-4.4-open-decisions.md OD-4) — see
    # docs/tests/US-4.4-test-strategy.md for the reversal blast radius.
    requester = await _seed_user(db_session, email="assign.deactivated.customer@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    _, token = await _seed_agent(db_session, email="assign.deactivated.caller@example.com")
    deactivated_target = await _seed_agent_only(
        db_session, email="assign.deactivated.target@example.com", status="deactivated"
    )

    # Act
    response = await client.post(
        _assign_path(ticket.id),
        json={"assignee_id": str(deactivated_target.id)},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("validation-failed")


# --- AQ-AC9/FR-9: assigning a closed ticket ---------------------------------


async def test_assign_ticket_closed_ticket_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="assign.closed.customer@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="closed")
    _, token = await _seed_agent(db_session, email="assign.closed.caller@example.com")
    target = await _seed_agent_only(db_session, email="assign.closed.target@example.com")

    # Act
    response = await client.post(
        _assign_path(ticket.id), json={"assignee_id": str(target.id)}, headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("invalid-state-transition")
    await db_session.refresh(ticket)
    assert ticket.assignee_id is None


# --- AQ-AC10/FR-10: concurrent assignment -----------------------------------


async def test_assign_ticket_repository_conditional_update_rejects_stale_expected_value(
    db_session: AsyncSession,
) -> None:
    # Arrange: FR-10/AQ-AC10's actual mechanism is the repository's
    # conditional `UPDATE ... WHERE assignee_id IS NOT DISTINCT FROM
    # :expected` (implementation_plan.md Architectural Change #6). Driving
    # two genuinely simultaneous HTTP requests through this project's
    # `real_client`+`db_session` combined-fixture pattern does NOT prove
    # this for `assign`: unlike the pattern's existing precedents
    # (`test_refresh_concurrent_requests_exactly_one_succeeds`,
    # `test_password_reset_confirm_concurrent_same_token_exactly_one_succeeds`
    # in tests/integration/modules/users/test_users_router.py, both guarded
    # by a *consumed-state* check where a second reader already sees
    # "consumed"), `db_session`'s override means both requests share one
    # session, so they execute serially, not concurrently — the second
    # request's own `get_by_id` read would see the *first* request's
    # already-committed `assignee_id`, take that as its own `expected`
    # value, and its conditional UPDATE would then also match and succeed
    # (the API design deliberately generalized this guard to cover
    # re-assignment too, "Concurrency Design" in
    # US-4.4-api-design.md) — yielding `[200, 200]`, not `[200, 409]`,
    # against a perfectly correct implementation. This test instead drives
    # the repository directly with a deliberately **stale** `expected_
    # assignee_id` for the second call — the exact condition FR-10
    # describes (two agents who both read the ticket as unassigned before
    # either wrote) — which is real, deterministic, and requires no second
    # DB connection. The `None` → `AssignmentConflictError` mapping itself
    # is proven at the unit layer
    # (test_assign_ticket_concurrency_loss_raises_409_assignment_conflict);
    # together the two form complete AQ-AC10 coverage.
    requester = await _seed_user(db_session, email="assign.race.repo@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    target_one = await _seed_agent_only(db_session, email="assign.race.repo.target1@example.com")
    target_two = await _seed_agent_only(db_session, email="assign.race.repo.target2@example.com")
    repository = TicketRepository(db_session)

    # Act: both calls read the ticket as unassigned (`expected_assignee_id
    # =None`) before either wrote — the first's conditional UPDATE matches
    # and wins; the second's still carries the now-stale `None` and must
    # find zero matching rows.
    first = await repository.assign_ticket(
        ticket.id, new_assignee_id=target_one.id, expected_assignee_id=None
    )
    second = await repository.assign_ticket(
        ticket.id, new_assignee_id=target_two.id, expected_assignee_id=None
    )

    # Assert
    assert first is not None
    assert first.assignee_id == target_one.id
    assert second is None
    await db_session.refresh(ticket)
    assert ticket.assignee_id == target_one.id


# --- AQ-AC4/FR-4: unassign ---------------------------------------------------


async def test_unassign_ticket_returns_200_and_clears_assignee_with_audit_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="unassign.happy.customer@example.com")
    previous = await _seed_agent_only(db_session, email="unassign.happy.previous@example.com")
    ticket = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=previous.id
    )
    caller, token = await _seed_agent(db_session, email="unassign.happy.caller@example.com")

    # Act
    response = await client.delete(_assign_path(ticket.id), headers=_auth_headers(token))

    # Assert: AQ-AC4 — 200 with assignee_id null, audit entry written.
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None
    await db_session.refresh(ticket)
    assert ticket.assignee_id is None
    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.target_id == ticket.id, AuditLog.event == "ticket_unassigned"
        )
    )
    audit_row = audit_result.scalar_one()
    assert audit_row.actor_id == caller.id


async def test_unassign_ticket_already_unassigned_is_idempotent_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="unassign.idempotent.customer@example.com")
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    _, token = await _seed_agent(db_session, email="unassign.idempotent.caller@example.com")

    # Act
    response = await client.delete(_assign_path(ticket.id), headers=_auth_headers(token))

    # Assert: idempotent — not a 404/409 for a ticket that was already unassigned.
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


# --- AQ-AC7/FR-7 (unassign) --------------------------------------------------


async def test_unassign_ticket_customer_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="unassign.customer404@example.com")
    agent = await _seed_agent_only(db_session, email="unassign.customer404.agent@example.com")
    ticket = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=agent.id
    )
    token = await _seed_session_and_token(db_session, user_id=requester.id)

    # Act
    response = await client.delete(_assign_path(ticket.id), headers=_auth_headers(token))

    # Assert
    assert response.status_code == 404


async def test_unassign_ticket_read_only_agent_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    requester = await _seed_user(db_session, email="unassign.readonly.customer@example.com")
    agent = await _seed_agent_only(db_session, email="unassign.readonly.assignee@example.com")
    ticket = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", assignee_id=agent.id
    )
    reader = await _seed_user(db_session, email="unassign.readonly.caller@example.com")
    await _assign_role(db_session, user_id=reader.id, role_name="support_agent")
    token = await _seed_session_and_token(db_session, user_id=reader.id, scopes=["tickets:read"])

    # Act
    response = await client.delete(_assign_path(ticket.id), headers=_auth_headers(token))

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("insufficient-permission")


# --- FR-4/OD-3: unassign on a closed ticket ---------------------------------


async def test_unassign_ticket_closed_ticket_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: OD-3's adopted default (not yet human-confirmed — see
    # docs/decisions/US-4.4-open-decisions.md OD-3 and
    # docs/tests/US-4.4-test-strategy.md for the reversal blast radius).
    requester = await _seed_user(db_session, email="unassign.closed.customer@example.com")
    agent = await _seed_agent_only(db_session, email="unassign.closed.assignee@example.com")
    ticket = await _seed_ticket(
        db_session, requester_id=requester.id, status="closed", assignee_id=agent.id
    )
    _, token = await _seed_agent(db_session, email="unassign.closed.caller@example.com")

    # Act
    response = await client.delete(_assign_path(ticket.id), headers=_auth_headers(token))

    # Assert
    assert response.status_code == 409
    assert response.json()["type"].endswith("invalid-state-transition")
    await db_session.refresh(ticket)
    assert ticket.assignee_id == agent.id


# --- DR-3: assign/unassign must not bump updated_at -------------------------


async def test_assign_ticket_does_not_change_updated_at(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: implementation_plan.md Architectural Change #9 (DR-3) — an
    # explicit, distinct *past* `updated_at`, per AGENTS.md §5's frozen-
    # `func.now()`-per-transaction rule: seeding via `server_default=func.now()`
    # and asserting in the same transaction would pass identically whether
    # or not the fix is present, proving nothing.
    requester = await _seed_user(db_session, email="assign.updatedat.customer@example.com")
    past = datetime.now(UTC) - timedelta(days=3)
    ticket = await _seed_ticket(
        db_session, requester_id=requester.id, status="open", updated_at=past
    )
    _, token = await _seed_agent(db_session, email="assign.updatedat.caller@example.com")
    target = await _seed_agent_only(db_session, email="assign.updatedat.target@example.com")

    # Act
    response = await client.post(
        _assign_path(ticket.id), json={"assignee_id": str(target.id)}, headers=_auth_headers(token)
    )

    # Assert: the queue's "longest-waiting-first" ordering must survive an
    # assign cycle with zero actual work performed on the ticket.
    assert response.status_code == 200
    await db_session.refresh(ticket)
    assert ticket.updated_at == past


async def test_unassign_ticket_does_not_change_updated_at(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: same DR-3 proof, for `unassign_ticket`'s independent
    # `.values()` clause — implementation_plan.md Risk 5's "half-applied fix"
    # concern (assign preserves it but unassign doesn't, or vice versa).
    requester = await _seed_user(db_session, email="unassign.updatedat.customer@example.com")
    agent = await _seed_agent_only(db_session, email="unassign.updatedat.assignee@example.com")
    past = datetime.now(UTC) - timedelta(days=3)
    ticket = await _seed_ticket(
        db_session,
        requester_id=requester.id,
        status="open",
        assignee_id=agent.id,
        updated_at=past,
    )
    _, token = await _seed_agent(db_session, email="unassign.updatedat.caller@example.com")

    # Act
    response = await client.delete(_assign_path(ticket.id), headers=_auth_headers(token))

    # Assert
    assert response.status_code == 200
    await db_session.refresh(ticket)
    assert ticket.updated_at == past


# --- Authentication matrix (AGENTS.md §5) -----------------------------------


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("token_factory_name", ["no_token", "malformed", "expired", "revoked"])
async def test_assign_and_unassign_auth_matrix_returns_401(
    client: AsyncClient, db_session: AsyncSession, method: str, token_factory_name: str
) -> None:
    # Arrange
    requester = await _seed_user(
        db_session, email=f"authmatrix.assign.{uuid.uuid4().hex}@example.com"
    )
    ticket = await _seed_ticket(db_session, requester_id=requester.id, status="open")
    target = await _seed_agent_only(
        db_session, email=f"authmatrix.assign.target.{uuid.uuid4().hex}@example.com"
    )
    headers: dict[str, str] = {}
    if token_factory_name == "malformed":
        headers = _auth_headers("not-a-real-jwt")
    elif token_factory_name == "expired":
        headers = _auth_headers(await _expired_token(db_session, user_id=requester.id))
    elif token_factory_name == "revoked":
        headers = _auth_headers(await _revoked_session_token(db_session, user_id=requester.id))
    # "no_token": headers stays {}

    # Act
    if method == "POST":
        response = await client.post(
            _assign_path(ticket.id), json={"assignee_id": str(target.id)}, headers=headers
        )
    else:
        response = await client.delete(_assign_path(ticket.id), headers=headers)

    # Assert
    assert response.status_code == 401


# --- Index coverage: DR-1's literal `status != 'closed'` predicate ---------


async def test_agent_queue_default_query_uses_partial_index(db_session: AsyncSession) -> None:
    # Arrange/Act: Enforcement Matrix `[gate]` — DR-1's actual claim is that
    # the partial index is *usable* (survives PostgreSQL's predicate-
    # implication check) for the literal `status != 'closed'` filter, not
    # that it is the planner's cheapest choice on whatever data happens to
    # be in the table when this test runs — on a near-empty `tickets`
    # table (this test seeds none) a sequential scan is cheaper regardless
    # of how correct the index and predicate are, so asserting "no Seq Scan"
    # directly would fail against a perfectly correct implementation.
    # `SET LOCAL enable_seqscan = off` removes that cost-model confound: if
    # the index were NOT usable for this predicate (e.g. the repository
    # wrote `status.in_([...])` instead of the literal `!= 'closed'` —
    # implementation_plan.md Architectural Change #10 / Risk 4), PostgreSQL
    # would fall back to a Seq Scan anyway (disabling one plan never makes
    # the planner error), so the index's *name* actually appearing in the
    # plan is the real, discriminating proof — not a plain "no Seq Scan"
    # assertion, which the empty-table cost model would fail on its own.
    await db_session.execute(text("SET LOCAL enable_seqscan = off"))
    result = await db_session.execute(
        text(
            "EXPLAIN SELECT * FROM tickets WHERE status != 'closed' "
            "ORDER BY updated_at, id LIMIT 100"
        )
    )
    plan = "\n".join(row[0] for row in result.all())

    # Assert
    assert "ix_tickets_queue_default_updated_at_id" in plan
