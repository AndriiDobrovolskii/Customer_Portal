import uuid
from datetime import datetime, timedelta
from typing import Protocol

from app.core.exceptions import FieldError
from app.modules.audit.exceptions import RangeTooWideError, ValidationFailedError
from app.modules.audit.repository import AuditLogPage
from app.modules.audit.schemas import AuditLogEntry, AuditLogListResponse
from app.modules.roles.service import RoleGrant

_MAX_WINDOW_DAYS = 90
_MAX_LIMIT = 100


class AuditRepositoryProtocol(Protocol):
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
    ) -> AuditLogPage | None: ...

    async def record_self_audit(
        self,
        *,
        actor_id: uuid.UUID,
        actor_role: str | None,
        request_id: str,
        ip: str | None,
        user_agent: str | None,
        payload: dict[str, object],
    ) -> None: ...

    async def record_access_denied(
        self,
        *,
        actor_id: uuid.UUID,
        actor_role: str | None,
        request_id: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None: ...

    async def record_event(
        self,
        *,
        category: str,
        actor_id: uuid.UUID | None,
        actor_role: str | None,
        event: str,
        target_id: uuid.UUID | None,
        outcome: str | None,
        request_id: str | None,
        ip: str | None,
        user_agent: str | None,
        payload: dict[str, object] | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class RoleServiceProtocol(Protocol):
    """Cross-module collaborator (roles.service), mirroring
    admin_users/service.py's own RoleServiceProtocol pattern — service ->
    service, never a direct repository import (AGENTS.md §3).
    `get_role_grants_for_user` (not `list_role_names_for_user`, which is a
    repository-protocol-only method `RoleService` doesn't itself expose)
    is this project's public, service-layer way to read a user's role
    names, already used cross-module by `users.service` (US-2.5 FR-6).
    """

    async def get_role_grants_for_user(self, user_id: uuid.UUID) -> list[RoleGrant]: ...


async def _resolve_actor_role(role_service: RoleServiceProtocol, actor_id: uuid.UUID) -> str | None:
    """`actor_role` (US-3.3-entity-model.md) is a single, nullable
    `String(32)` column, but a user may hold more than one role. Not
    decided by any design/planning artifact for this story (a genuinely
    minor, purely-informational modeling detail — this field is never used
    for an authorization decision, only returned/recorded; the access-token
    scopes that actually gate this endpoint don't carry role names at
    all). Resolved here: join sorted role names with a comma when there's
    more than one, `None` when the caller holds none.
    """
    grants = await role_service.get_role_grants_for_user(actor_id)
    if not grants:
        return None
    return ",".join(sorted(grant.name for grant in grants))


class AuditLogService:
    def __init__(
        self, repository: AuditRepositoryProtocol, role_service: RoleServiceProtocol
    ) -> None:
        self._repository = repository
        self._role_service = role_service

    async def list_audit_logs(
        self,
        *,
        actor_id: uuid.UUID,
        actor_id_filter: uuid.UUID | None,
        event: str | None,
        target_id: uuid.UUID | None,
        window_from: datetime | None,
        window_to: datetime | None,
        cursor: str | None,
        limit: int,
        request_id: str,
        ip: str | None,
        user_agent: str | None,
    ) -> AuditLogListResponse:
        """AU-AC1/FR-1, AU-AC5/FR-5, AU-AC2/FR-2. `actor_id` is the caller
        (for the self-audit write); `actor_id_filter` is AU-AC1's optional
        `actor_id` query parameter (a different, unrelated actor to filter
        by) — kept as two separate parameters so they can never be
        conflated.
        """
        if (
            window_from is None
            or window_to is None
            or window_to - window_from > timedelta(days=_MAX_WINDOW_DAYS)
        ):
            raise RangeTooWideError

        if limit > _MAX_LIMIT:
            raise ValidationFailedError(
                errors=[FieldError(field="limit", message="limit must be at most 100.", code="max")]
            )

        page = await self._repository.list_audit_logs(
            actor_id=actor_id_filter,
            event=event,
            target_id=target_id,
            window_from=window_from,
            window_to=window_to,
            cursor=cursor,
            limit=limit,
        )
        if page is None:
            raise ValidationFailedError(
                errors=[FieldError(field="cursor", message="Invalid cursor.", code="invalid")]
            )

        actor_role = await _resolve_actor_role(self._role_service, actor_id)
        await self._repository.record_self_audit(
            actor_id=actor_id,
            actor_role=actor_role,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            payload={
                "actor_id": str(actor_id_filter) if actor_id_filter else None,
                "event": event,
                "target_id": str(target_id) if target_id else None,
                "from": window_from.isoformat(),
                "to": window_to.isoformat(),
                "cursor": cursor,
                "limit": limit,
            },
        )
        await self._repository.commit()

        items = [AuditLogEntry.model_validate(row) for row in page.items]
        return AuditLogListResponse(items=items, next_cursor=page.next_cursor)

    async def record_access_denied(
        self, *, actor_id: uuid.UUID, request_id: str, ip: str | None, user_agent: str | None
    ) -> None:
        """AU-AC3/FR-3 — called by `require_audit_read`
        (audit/dependencies.py) when the caller lacks `audit:read`."""
        actor_role = await _resolve_actor_role(self._role_service, actor_id)
        await self._repository.record_access_denied(
            actor_id=actor_id,
            actor_role=actor_role,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
        await self._repository.commit()

    async def record_event(
        self,
        *,
        category: str,
        event: str,
        actor_id: uuid.UUID,
        target_id: uuid.UUID | None,
        outcome: str | None,
        payload: dict[str, object] | None,
    ) -> None:
        """Generic write path for an event type owned by a module other
        than `audit` itself (US-4.1's `ticket_created` is the first
        caller) - service -> service, per `AGENTS.md` §3. Deliberately does
        **not** call `self._repository.commit()`, unlike every other method
        on this class: the calling module's service owns the transaction
        boundary and must commit this write together with its own, in the
        same request-scoped `AsyncSession` (US-4.1-implementation-plan.md
        Architectural Change #2). A caller that assumes this method commits
        (copying `list_audit_logs`/`record_access_denied`'s pattern) would
        silently lose this write.
        """
        actor_role = await _resolve_actor_role(self._role_service, actor_id)
        await self._repository.record_event(
            category=category,
            actor_id=actor_id,
            actor_role=actor_role,
            event=event,
            target_id=target_id,
            outcome=outcome,
            request_id=None,
            ip=None,
            user_agent=None,
            payload=payload,
        )
