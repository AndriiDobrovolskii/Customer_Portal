import uuid
from datetime import datetime
from typing import Literal

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


class CreateReplyRequest(BaseModel):
    """`US-4.2-openapi.yaml` `CreateReplyRequest`. `visibility` has no schema-
    level default (`None` when omitted) — Resolution OD-6's "defaults to
    public for both actor kinds" is a service-layer behavior, not something
    this schema defaults, per `US-4.2-api-design.md` Open Questions.
    """

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=5000)
    visibility: Literal["public", "internal"] | None = None
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)


class ReplyRead(BaseModel):
    """`US-4.2-openapi.yaml` `ReplyRead` field list verbatim. No attachment
    references exposed (API_DESIGN Open Questions #5 — matches US-4.1's own
    write-only `attachment_ids` precedent).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    author_id: uuid.UUID
    author_kind: Literal["customer", "agent"]
    visibility: Literal["public", "internal"]
    body: str
    created_at: datetime


class ReplyThreadPage(BaseModel):
    items: list[ReplyRead]
    next_cursor: str | None = None


class TicketDetailRead(BaseModel):
    """`US-4.2-openapi.yaml` `TicketDetailRead` field list verbatim. No
    `resolved_at` field — no such column exists anywhere in this module's
    models and this story does not add one (API_DESIGN Open Questions #3).
    Composed by the service from two direct repository calls rather than
    `model_validate()`d off a single ORM object — no `relationship()` exists
    between `Ticket` and `TicketReply` (`US-4.2-entity-model.md`
    "Relationships") — but still declares `from_attributes=True` for
    consistency with this module's other `*Read` schemas.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_number: str
    status: str
    requester_id: uuid.UUID
    subject: str
    body: str
    category: str
    first_response_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    replies: ReplyThreadPage


class ResolveTicketRequest(BaseModel):
    """`US-4.3-openapi.yaml` `ResolveTicketRequest`. `max_length=5000` matches
    `US-4.3-db-design.md`'s `resolution_note` column (`String(5000)`); FR-10's
    non-empty requirement is `min_length=1`.
    """

    model_config = ConfigDict(extra="forbid")

    resolution_note: str = Field(min_length=1, max_length=5000)


class CloseTicketRequest(BaseModel):
    """`US-4.3-openapi.yaml` `CloseTicketRequest`. `reason` is accepted but not
    persisted anywhere (`US-4.3-db-design.md` "not persisted" section) —
    unconstrained per API_DESIGN Open Questions #4.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class ReopenTicketRequest(BaseModel):
    """`US-4.3-openapi.yaml` `ReopenTicketRequest`. `reason` is accepted but
    not persisted anywhere, same as `CloseTicketRequest`.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class TicketStateRead(BaseModel):
    """`US-4.3-openapi.yaml` `TicketStateRead` field list verbatim —
    deliberately minimal: `closed_by`/`resolution_note` are not exposed
    (API_DESIGN Open Questions #5, data-minimization).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_number: str
    status: str
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime


class AssignTicketRequest(BaseModel):
    """`US-4.4-openapi.yaml` `AssignTicketRequest`. Single required field —
    the target agent's user id (may equal the caller's own id, self-assign).
    Target validation (holds `tickets:write`, is active per OD-4) is a
    service-layer concern (FR-8), not expressible here.
    """

    model_config = ConfigDict(extra="forbid")

    assignee_id: uuid.UUID


class AgentTicketRead(BaseModel):
    """`US-4.4-openapi.yaml` `AgentTicketRead` — OD-1's adopted, APPROVED
    resolution: every `TicketRead` field plus `assignee_id`, as a distinct
    schema rather than an extension of `TicketRead` in place, so the
    customer-facing `TicketRead`/`TicketListResponse` contract stays
    provably unaffected (FR-1, FR-2; Assumption #7/NFR — `assignee_id` MUST
    NOT appear on any customer-facing response shape).
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
    assignee_id: uuid.UUID | None


class AgentTicketListResponse(BaseModel):
    """`US-4.4-openapi.yaml` `AgentTicketListResponse` — the agent branch's
    response envelope (FR-1, FR-2), parallel to `TicketListResponse` but
    carrying `AgentTicketRead` items. `next_cursor` is opaque and encoded
    `(updated_at, id)` — not interchangeable with `TicketListResponse`'s
    `(created_at, id)`-encoded cursor.
    """

    items: list[AgentTicketRead]
    next_cursor: str | None = None


class AgentTicketStateRead(BaseModel):
    """`US-4.4-openapi.yaml` `AgentTicketStateRead` — OD-1's adopted,
    APPROVED resolution: every `TicketStateRead` field plus `assignee_id`, as
    a distinct schema so `/resolve`, `/close`, and `/reopen` (all
    customer-reachable) stay provably unaffected (FR-3, FR-4, FR-9).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_number: str
    status: str
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime
    assignee_id: uuid.UUID | None
