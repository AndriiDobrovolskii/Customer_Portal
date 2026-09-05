import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.support.models import TicketReply
from app.modules.support.schemas import (
    CreateReplyRequest,
    ReplyRead,
    ReplyThreadPage,
    TicketDetailRead,
)

pytestmark = pytest.mark.unit

_FIXED_NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


# --- TR-AC7/FR-7: CreateReplyRequest validation -----------------------------


def test_create_reply_request_rejects_unknown_field() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        CreateReplyRequest(body="Hello", extra_field="not allowed")  # type: ignore[call-arg]


def test_create_reply_request_rejects_empty_body() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        CreateReplyRequest(body="")


def test_create_reply_request_rejects_body_over_5000_chars() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        CreateReplyRequest(body="x" * 5001)


def test_create_reply_request_accepts_body_at_5000_char_boundary() -> None:
    # Arrange / Act
    request = CreateReplyRequest(body="x" * 5000)

    # Assert
    assert len(request.body) == 5000


def test_create_reply_request_visibility_omitted_defaults_to_none() -> None:
    # Arrange / Act: schema itself does not default to "public" — Resolution
    # OD-6's defaulting is a service-layer behavior (visibility is optional
    # here per US-4.2-openapi.yaml's CreateReplyRequest, which has no
    # `default` on the property).
    request = CreateReplyRequest(body="Hello")

    # Assert
    assert request.visibility is None


def test_create_reply_request_attachment_ids_defaults_to_empty_list() -> None:
    # Arrange / Act
    request = CreateReplyRequest(body="Hello")

    # Assert
    assert request.attachment_ids == []


@pytest.mark.parametrize("visibility", ["public", "internal"])
def test_create_reply_request_accepts_valid_visibility_values(visibility: str) -> None:
    # Arrange / Act
    request = CreateReplyRequest(body="Hello", visibility=visibility)

    # Assert
    assert request.visibility == visibility


def test_create_reply_request_rejects_invalid_visibility_value() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        CreateReplyRequest(body="Hello", visibility="secret")


# --- ReplyRead / ReplyThreadPage / TicketDetailRead -------------------------


def test_reply_read_from_attributes_reads_a_real_orm_instance() -> None:
    # Arrange: a real ORM model, not a lookalike dataclass — matches this
    # project's existing fake-repository convention (see test_support_service.py).
    reply = TicketReply(
        ticket_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        author_kind="agent",
        body="We're looking into it.",
        visibility="public",
    )
    reply.id = uuid.uuid4()
    reply.created_at = _FIXED_NOW

    # Act
    read = ReplyRead.model_validate(reply)

    # Assert
    assert read.id == reply.id
    assert read.author_kind == "agent"
    assert read.visibility == "public"
    assert read.body == "We're looking into it."
    assert read.created_at == _FIXED_NOW


def test_reply_thread_page_next_cursor_defaults_to_none() -> None:
    # Arrange / Act
    page = ReplyThreadPage(items=[])

    # Assert
    assert page.next_cursor is None


def test_ticket_detail_read_composes_reply_thread_page() -> None:
    # Arrange: `TicketDetailRead` is composed by the service from two direct
    # repository calls (no `relationship()` exists to `model_validate()` off
    # — US-4.2-entity-model.md "Relationships"), so it is constructed via
    # explicit keyword arguments here, not `model_validate(ticket_orm_obj)`.
    reply = TicketReply(
        ticket_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        author_kind="customer",
        body="Any update?",
        visibility="public",
    )
    reply.id = uuid.uuid4()
    reply.created_at = _FIXED_NOW

    # Act
    detail = TicketDetailRead(
        id=uuid.uuid4(),
        ticket_number="CP-2026-0000001",
        status="waiting_on_support",
        requester_id=uuid.uuid4(),
        subject="Cannot log in",
        body="My login keeps failing.",
        category="billing",
        first_response_at=None,
        created_at=_FIXED_NOW,
        updated_at=_FIXED_NOW,
        replies=ReplyThreadPage(items=[ReplyRead.model_validate(reply)], next_cursor=None),
    )

    # Assert: FR-2's "resolved_at is not cleared" language is vacuously true
    # for this schema — no `resolved_at` field exists at all (API_DESIGN OQ-3,
    # confirmed absent by US-4.2-db-design.md).
    assert not hasattr(detail, "resolved_at")
    assert detail.first_response_at is None
    assert len(detail.replies.items) == 1
    assert detail.replies.items[0].author_kind == "customer"


def test_ticket_detail_read_first_response_at_present_once_stamped() -> None:
    # Arrange / Act
    detail = TicketDetailRead(
        id=uuid.uuid4(),
        ticket_number="CP-2026-0000002",
        status="waiting_on_customer",
        requester_id=uuid.uuid4(),
        subject="Billing question",
        body="Why was I charged twice?",
        category="billing",
        first_response_at=_FIXED_NOW,
        created_at=_FIXED_NOW,
        updated_at=_FIXED_NOW,
        replies=ReplyThreadPage(items=[], next_cursor=None),
    )

    # Assert
    assert detail.first_response_at == _FIXED_NOW
