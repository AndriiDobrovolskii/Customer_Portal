import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogEntry(BaseModel):
    """AU-AC1's field list verbatim (US-013-openapi.yaml `AuditLogEntry`).
    Outbound-only: no inbound `*Create`/`*Update` schema exists anywhere in
    this module, which structurally enforces AU-AC4's API-layer
    immutability. `id`/`category`/`payload` are real `audit_log` columns
    but are not part of this response shape — AU-AC1's own AC text omits
    them.
    """

    model_config = ConfigDict(from_attributes=True)

    occurred_at: datetime
    actor_id: uuid.UUID | None
    actor_role: str | None
    event: str
    target_id: uuid.UUID | None
    request_id: str | None
    ip: str | None
    user_agent: str | None
    outcome: str | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    next_cursor: str | None = None
