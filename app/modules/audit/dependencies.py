from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_request_id
from app.db.dependencies import get_db_session
from app.modules.audit.repository import AuditRepository
from app.modules.audit.service import AuditLogService
from app.modules.roles.dependencies import RoleServiceDep, require_scope
from app.modules.roles.exceptions import InsufficientPermissionError
from app.modules.users.dependencies import CurrentUserDep


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)], role_service: RoleServiceDep
) -> AuditLogService:
    repository = AuditRepository(session)
    return AuditLogService(repository, role_service)


AuditLogServiceDep = Annotated[AuditLogService, Depends(get_audit_log_service)]


def _get_client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


async def require_audit_read(
    request: Request,
    current_user: CurrentUserDep,
    service: AuditLogServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
) -> None:
    """AU-AC3/FR-3: wraps `roles.dependencies.require_scope("audit:read")`
    so the denial itself is recorded in `audit_log` — `require_scope` on
    its own writes no audit entry for any of its other callers
    (`users:read`, `users:write`, `roles:write`, ...), and this project's
    implementation plan deliberately keeps that fix local to this endpoint
    rather than widening the shared dependency, which would silently start
    auditing every other scope-gated route in the app.
    """
    checker = require_scope("audit:read")
    try:
        await checker(current_user)
    except InsufficientPermissionError:
        await service.record_access_denied(
            actor_id=current_user.user_id,
            request_id=request_id,
            ip=_get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
        raise
