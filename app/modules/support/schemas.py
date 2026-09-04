import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateTicketRequest(BaseModel):
    """`category` carries no enum/minLength beyond `max_length=50`: OD-3's
    valid value list is an unresolved stakeholder decision
    (`docs/decisions/US-4.1-open-decisions.md`), not something this schema
    may infer. `attachment_ids` defaults to an empty list, not `None`, per
    `US-4.1-openapi.yaml`.
    """

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=5000)
    category: str = Field(max_length=50)
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)


class TicketRead(BaseModel):
    """`US-4.1-openapi.yaml` `TicketRead` field list verbatim. No SLA-target
    field (FR-1) and no nested `attachments`/audit data (US-4.1-db-design.md
    "Relationships" — no `relationship()` declared on `Ticket`).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_number: str
    status: str
    requester_id: uuid.UUID
    subject: str
    body: str
    category: str
    created_at: datetime
    updated_at: datetime


class TicketListResponse(BaseModel):
    items: list[TicketRead]
    next_cursor: str | None = None
