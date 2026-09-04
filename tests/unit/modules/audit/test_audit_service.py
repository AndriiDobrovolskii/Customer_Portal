import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.modules.audit.exceptions import RangeTooWideError, ValidationFailedError
from app.modules.audit.repository import AuditLogPage, AuditLogRow
from app.modules.audit.service import AuditLogService
from app.modules.roles.service import RoleGrant

pytestmark = pytest.mark.unit

_FIXED_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _make_row(*, event: str = "login_failed") -> AuditLogRow:
    return AuditLogRow(
        occurred_at=_FIXED_NOW,
        actor_id=uuid.uuid4(),
        actor_role=None,
        event=event,
        target_id=None,
        request_id="req-x",
        ip="10.0.0.1",
        user_agent="pytest",
        outcome=None,
    )


class FakeAuditRepository:
    def __init__(
        self,
        *,
        page: AuditLogPage | None = None,
        list_returns_none: bool = False,
    ) -> None:
        self.page = page or AuditLogPage(items=[], next_cursor=None)
        self.list_returns_none = list_returns_none
        self.list_calls: list[dict[str, Any]] = []
        self.self_audit_calls: list[dict[str, Any]] = []
        self.denied_calls: list[dict[str, Any]] = []
        self.event_calls: list[dict[str, Any]] = []
        self.committed = False

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
        self.list_calls.append(
            {
                "actor_id": actor_id,
                "event": event,
                "target_id": target_id,
                "window_from": window_from,
                "window_to": window_to,
                "cursor": cursor,
                "limit": limit,
            }
        )
        if self.list_returns_none:
            return None
        return self.page

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
        self.self_audit_calls.append(
            {
                "actor_id": actor_id,
                "actor_role": actor_role,
                "request_id": request_id,
                "ip": ip,
                "user_agent": user_agent,
                "payload": payload,
            }
        )

    async def record_access_denied(
        self,
        *,
        actor_id: uuid.UUID,
        actor_role: str | None,
        request_id: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        self.denied_calls.append(
            {
                "actor_id": actor_id,
                "actor_role": actor_role,
                "request_id": request_id,
                "ip": ip,
                "user_agent": user_agent,
            }
        )

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
        payload: dict[str, Any] | None,
    ) -> None:
        self.event_calls.append(
            {
                "category": category,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "event": event,
                "target_id": target_id,
                "outcome": outcome,
                "request_id": request_id,
                "ip": ip,
                "user_agent": user_agent,
                "payload": payload,
            }
        )

    async def commit(self) -> None:
        self.committed = True


class FakeRoleService:
    def __init__(self, *, role_names: list[str] | None = None) -> None:
        self.role_names = role_names or []
        self.calls: list[uuid.UUID] = []

    async def get_role_grants_for_user(self, user_id: uuid.UUID) -> list[RoleGrant]:
        self.calls.append(user_id)
        return [RoleGrant(name=name, granted_at=_FIXED_NOW) for name in self.role_names]


def _make_service(
    repository: FakeAuditRepository | None = None, role_service: FakeRoleService | None = None
) -> tuple[AuditLogService, FakeAuditRepository, FakeRoleService]:
    repository = repository or FakeAuditRepository()
    role_service = role_service or FakeRoleService()
    return AuditLogService(repository, role_service), repository, role_service


def _valid_window() -> tuple[datetime, datetime]:
    return _FIXED_NOW - timedelta(days=1), _FIXED_NOW


# --- AU-AC1/FR-1: list_audit_logs filter/window/pagination -----------------


async def test_list_audit_logs_applies_filters_and_pagination() -> None:
    # Arrange
    row = _make_row()
    repository = FakeAuditRepository(page=AuditLogPage(items=[row], next_cursor="next-page"))
    service, repository, _ = _make_service(repository=repository)
    window_from, window_to = _valid_window()
    actor_filter = uuid.uuid4()
    target_filter = uuid.uuid4()

    # Act
    result = await service.list_audit_logs(
        actor_id=uuid.uuid4(),
        actor_id_filter=actor_filter,
        event="login_failed",
        target_id=target_filter,
        window_from=window_from,
        window_to=window_to,
        cursor="prev-cursor",
        limit=25,
        request_id="req-1",
        ip="10.0.0.1",
        user_agent="pytest",
    )

    # Assert
    assert len(result.items) == 1
    assert result.next_cursor == "next-page"
    call = repository.list_calls[0]
    assert call["actor_id"] == actor_filter
    assert call["event"] == "login_failed"
    assert call["target_id"] == target_filter
    assert call["window_from"] == window_from
    assert call["window_to"] == window_to
    assert call["cursor"] == "prev-cursor"
    assert call["limit"] == 25


async def test_list_audit_logs_limit_over_max_returns_422() -> None:
    # Arrange
    service, _, _ = _make_service()
    window_from, window_to = _valid_window()

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.list_audit_logs(
            actor_id=uuid.uuid4(),
            actor_id_filter=None,
            event=None,
            target_id=None,
            window_from=window_from,
            window_to=window_to,
            cursor=None,
            limit=101,
            request_id="req-2",
            ip=None,
            user_agent=None,
        )


async def test_list_audit_logs_invalid_cursor_returns_422() -> None:
    # Arrange
    repository = FakeAuditRepository(list_returns_none=True)
    service, _, _ = _make_service(repository=repository)
    window_from, window_to = _valid_window()

    # Act & Assert
    with pytest.raises(ValidationFailedError):
        await service.list_audit_logs(
            actor_id=uuid.uuid4(),
            actor_id_filter=None,
            event=None,
            target_id=None,
            window_from=window_from,
            window_to=window_to,
            cursor="garbage",
            limit=25,
            request_id="req-3",
            ip=None,
            user_agent=None,
        )


# --- AU-AC5/FR-5: window validation -----------------------------------------


async def test_validate_window_rejects_over_90_days_and_both_omitted() -> None:
    # Arrange
    service, _, _ = _make_service()

    # Act & Assert: over 90 days
    with pytest.raises(RangeTooWideError):
        await service.list_audit_logs(
            actor_id=uuid.uuid4(),
            actor_id_filter=None,
            event=None,
            target_id=None,
            window_from=_FIXED_NOW - timedelta(days=91),
            window_to=_FIXED_NOW,
            cursor=None,
            limit=25,
            request_id="req-4",
            ip=None,
            user_agent=None,
        )

    # Act & Assert: both omitted
    with pytest.raises(RangeTooWideError):
        await service.list_audit_logs(
            actor_id=uuid.uuid4(),
            actor_id_filter=None,
            event=None,
            target_id=None,
            window_from=None,
            window_to=None,
            cursor=None,
            limit=25,
            request_id="req-5",
            ip=None,
            user_agent=None,
        )


async def test_validate_window_rejects_single_missing_bound() -> None:
    # Arrange: OD-10's resolution — a single missing bound is rejected the
    # same as both missing, not defaulted.
    service, _, _ = _make_service()

    # Act & Assert: from only
    with pytest.raises(RangeTooWideError):
        await service.list_audit_logs(
            actor_id=uuid.uuid4(),
            actor_id_filter=None,
            event=None,
            target_id=None,
            window_from=_FIXED_NOW - timedelta(days=1),
            window_to=None,
            cursor=None,
            limit=25,
            request_id="req-6",
            ip=None,
            user_agent=None,
        )

    # Act & Assert: to only
    with pytest.raises(RangeTooWideError):
        await service.list_audit_logs(
            actor_id=uuid.uuid4(),
            actor_id_filter=None,
            event=None,
            target_id=None,
            window_from=None,
            window_to=_FIXED_NOW,
            cursor=None,
            limit=25,
            request_id="req-7",
            ip=None,
            user_agent=None,
        )


# --- AU-AC2/FR-2: self-audit write ------------------------------------------


async def test_record_self_audit_writes_actor_and_filters() -> None:
    # Arrange
    role_service = FakeRoleService(role_names=["auditor"])
    service, repository, role_service = _make_service(role_service=role_service)
    window_from, window_to = _valid_window()
    actor_id = uuid.uuid4()
    actor_filter = uuid.uuid4()

    # Act
    await service.list_audit_logs(
        actor_id=actor_id,
        actor_id_filter=actor_filter,
        event="login_failed",
        target_id=None,
        window_from=window_from,
        window_to=window_to,
        cursor=None,
        limit=50,
        request_id="req-8",
        ip="10.0.0.2",
        user_agent="pytest-agent",
    )

    # Assert
    assert len(repository.self_audit_calls) == 1
    call = repository.self_audit_calls[0]
    assert call["actor_id"] == actor_id
    assert call["actor_role"] == "auditor"
    assert call["request_id"] == "req-8"
    assert call["ip"] == "10.0.0.2"
    assert call["user_agent"] == "pytest-agent"
    assert call["payload"]["actor_id"] == str(actor_filter)
    assert call["payload"]["event"] == "login_failed"
    assert call["payload"]["limit"] == 50
    assert repository.committed is True


async def test_list_audit_logs_actor_role_joins_multiple_role_names() -> None:
    # Arrange: actor_role is a single column but a caller may hold >1 role
    # (no design decision named this explicitly — resolved inline, joined
    # sorted with a comma).
    role_service = FakeRoleService(role_names=["auditor", "admin"])
    service, repository, _ = _make_service(role_service=role_service)
    window_from, window_to = _valid_window()

    # Act
    await service.list_audit_logs(
        actor_id=uuid.uuid4(),
        actor_id_filter=None,
        event=None,
        target_id=None,
        window_from=window_from,
        window_to=window_to,
        cursor=None,
        limit=50,
        request_id="req-9",
        ip=None,
        user_agent=None,
    )

    # Assert
    assert repository.self_audit_calls[0]["actor_role"] == "admin,auditor"


async def test_list_audit_logs_actor_role_none_when_no_roles_held() -> None:
    # Arrange
    role_service = FakeRoleService(role_names=[])
    service, repository, _ = _make_service(role_service=role_service)
    window_from, window_to = _valid_window()

    # Act
    await service.list_audit_logs(
        actor_id=uuid.uuid4(),
        actor_id_filter=None,
        event=None,
        target_id=None,
        window_from=window_from,
        window_to=window_to,
        cursor=None,
        limit=50,
        request_id="req-10",
        ip=None,
        user_agent=None,
    )

    # Assert
    assert repository.self_audit_calls[0]["actor_role"] is None


# --- AU-AC3/FR-3: denial write ------------------------------------------


async def test_record_access_denied_writes_entry() -> None:
    # Arrange
    role_service = FakeRoleService(role_names=["customer"])
    service, repository, _ = _make_service(role_service=role_service)
    actor_id = uuid.uuid4()

    # Act
    await service.record_access_denied(
        actor_id=actor_id, request_id="req-11", ip="10.0.0.3", user_agent="pytest"
    )

    # Assert
    assert len(repository.denied_calls) == 1
    call = repository.denied_calls[0]
    assert call["actor_id"] == actor_id
    assert call["actor_role"] == "customer"
    assert call["request_id"] == "req-11"
    assert call["ip"] == "10.0.0.3"
    assert repository.committed is True


# --- record_event: cross-module write path (US-4.1's ticket_created) -------


async def test_record_event_writes_without_committing() -> None:
    # Arrange: US-4.1-implementation-plan.md's Architectural Change #2 — the
    # calling module's service owns the transaction boundary and must commit
    # this write together with its own; `record_event` must not self-commit,
    # unlike every other method on this service.
    role_service = FakeRoleService(role_names=["support_agent"])
    service, repository, _ = _make_service(role_service=role_service)
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()

    # Act
    await service.record_event(
        category="tickets",
        event="ticket_created",
        actor_id=actor_id,
        target_id=target_id,
        outcome="success",
        payload={"ticket_number": "CP-2026-0000001", "category": "billing"},
    )

    # Assert
    assert len(repository.event_calls) == 1
    call = repository.event_calls[0]
    assert call["category"] == "tickets"
    assert call["event"] == "ticket_created"
    assert call["actor_id"] == actor_id
    assert call["actor_role"] == "support_agent"
    assert call["target_id"] == target_id
    assert call["outcome"] == "success"
    assert call["payload"] == {"ticket_number": "CP-2026-0000001", "category": "billing"}
    assert repository.committed is False


async def test_record_event_actor_role_none_when_no_roles_held() -> None:
    # Arrange
    service, repository, _ = _make_service(role_service=FakeRoleService(role_names=[]))
    actor_id = uuid.uuid4()

    # Act
    await service.record_event(
        category="tickets",
        event="ticket_created",
        actor_id=actor_id,
        target_id=None,
        outcome="success",
        payload=None,
    )

    # Assert
    assert repository.event_calls[0]["actor_role"] is None
