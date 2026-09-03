import base64
import uuid
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog

# `audit_log_history` is a raw SQL UNION ALL view (US-013-db-design.md,
# US-013-entity-model.md), deliberately not an ORM-mapped entity — a view
# has no single underlying table for SQLAlchemy to reflect a PK/relationship
# against, and mapping it to `Base` would make Alembic autogenerate treat it
# as a missing table. Query it via Core `text()`, matching db-design.md's
# own framing of this view as the primary query surface for FR-1, not part
# of the ORM containment `audit_log` itself gets.
_LIST_COLUMNS = (
    "occurred_at, actor_id, actor_role, event, target_id, request_id, ip, user_agent, outcome"
)


class AuditLogRow(NamedTuple):
    occurred_at: datetime
    actor_id: uuid.UUID | None
    actor_role: str | None
    event: str
    target_id: uuid.UUID | None
    request_id: str | None
    ip: str | None
    user_agent: str | None
    outcome: str | None


class AuditLogPage(NamedTuple):
    items: list[AuditLogRow]
    next_cursor: str | None


def _encode_cursor(occurred_at: datetime, row_id: uuid.UUID) -> str:
    raw = f"{occurred_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        occurred_at_raw, row_id_raw = raw.split("|", 1)
        return datetime.fromisoformat(occurred_at_raw), uuid.UUID(row_id_raw)
    except (ValueError, UnicodeDecodeError):
        return None


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_audit_logs(
        self,
        *,
        actor_id: uuid.UUID | None,
        event: str | None,
        target_id: uuid.UUID | None,
        window_from: datetime,
        window_to: datetime,
        cursor: str | None,
        limit: int,
    ) -> AuditLogPage | None:
        """Returns None for a malformed cursor (AU-AC1/OD-5), resolved to
        422 validation-failed at the service layer, not a silent empty page.
        `audit_log_history` carries no `id` column in its projection (AU-
        AC1's own field list omits `id`) — the keyset cursor's tiebreaker
        uses `id` from the view's underlying rows regardless, selected here
        but not returned in `AuditLogRow`, matching AuditLogEntry's schema.
        """
        params: dict[str, Any] = {
            "window_from": window_from,
            "window_to": window_to,
            "limit": limit + 1,
        }
        where = ["occurred_at >= :window_from", "occurred_at <= :window_to"]

        if actor_id is not None:
            where.append("actor_id = :actor_id")
            params["actor_id"] = actor_id
        if event is not None:
            where.append("event = :event")
            params["event"] = event
        if target_id is not None:
            where.append("target_id = :target_id")
            params["target_id"] = target_id

        if cursor is not None:
            decoded = _decode_cursor(cursor)
            if decoded is None:
                return None
            cursor_occurred_at, cursor_id = decoded
            where.append(
                "(occurred_at < :cursor_occurred_at "
                "OR (occurred_at = :cursor_occurred_at AND id < :cursor_id))"
            )
            params["cursor_occurred_at"] = cursor_occurred_at
            params["cursor_id"] = cursor_id

        # S608: no injection surface — the table/column names and every
        # `where` fragment come from this function's own fixed literals
        # (never from `actor_id`/`event`/`target_id`/`cursor` values, which
        # are always bound via `params`), not from request input.
        stmt = text(
            f"SELECT id, {_LIST_COLUMNS} FROM audit_log_history "  # noqa: S608
            f"WHERE {' AND '.join(where)} "
            "ORDER BY occurred_at DESC, id DESC LIMIT :limit"
        )
        result = await self._session.execute(stmt, params)
        rows = result.mappings().all()

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last["occurred_at"], last["id"])

        items = [
            AuditLogRow(
                occurred_at=row["occurred_at"],
                actor_id=row["actor_id"],
                actor_role=row["actor_role"],
                event=row["event"],
                target_id=row["target_id"],
                request_id=row["request_id"],
                ip=row["ip"],
                user_agent=row["user_agent"],
                outcome=row["outcome"],
            )
            for row in rows
        ]
        return AuditLogPage(items=items, next_cursor=next_cursor)

    async def record_self_audit(
        self,
        *,
        actor_id: uuid.UUID,
        actor_role: str | None,
        request_id: str,
        ip: str | None,
        user_agent: str | None,
        payload: dict[str, Any],
    ) -> None:
        """AU-AC2/FR-2 — `event=audit_log_viewed`, records the actor and the
        exact filter parameters used (`payload`).
        """
        self._session.add(
            AuditLog(
                category="audit",
                actor_id=actor_id,
                actor_role=actor_role,
                event="audit_log_viewed",
                outcome="success",
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                payload=payload,
            )
        )
        await self._session.flush()

    async def record_access_denied(
        self,
        *,
        actor_id: uuid.UUID,
        actor_role: str | None,
        request_id: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        """AU-AC3/FR-3 — `audit:read`-denial event. `actor_id` is never
        `None` here: `require_audit_read` (audit/dependencies.py) only
        raises the underlying `InsufficientPermissionError` after
        `CurrentUserDep` has already resolved an authenticated caller — an
        unauthenticated request is rejected with `401` upstream, before
        this ever runs.
        """
        self._session.add(
            AuditLog(
                category="audit",
                actor_id=actor_id,
                actor_role=actor_role,
                event="audit_log_access_denied",
                outcome="denied",
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
            )
        )
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()
