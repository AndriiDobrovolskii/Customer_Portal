import logging
import uuid
from datetime import datetime
from typing import NamedTuple, Protocol

from app.core.config import get_settings
from app.core.exceptions import FieldError
from app.modules.roles.exceptions import (
    CannotTargetSelfError,
    LastAdminError,
    PrivilegeEscalationError,
    ValidationFailedError,
)
from app.modules.roles.models import Role
from app.modules.roles.schemas import (
    ReplaceUserRolesResponse,
    RoleCatalogueResponse,
    RoleSummary,
)

_ADMIN_ROLE_NAME = "admin"

logger = logging.getLogger(__name__)


class RoleRepositoryProtocol(Protocol):
    async def list_all_with_permissions(self) -> list[Role]: ...

    async def get_by_names(self, names: list[str]) -> list[Role]: ...


class RoleGrant(NamedTuple):
    """US-009 FR-6: a role name plus the moment it was granted, used to
    compute the 14-day MFA-enrolment grace period. A superset of what
    `resolve_scopes_for_user` needs (names only), so it's a separate
    method/return type rather than changing that one's signature.
    """

    name: str
    granted_at: datetime


class UserRoleRepositoryProtocol(Protocol):
    async def list_role_names_for_user(self, user_id: uuid.UUID) -> list[str]: ...

    async def list_role_grants_for_user(self, user_id: uuid.UUID) -> list[tuple[str, datetime]]: ...

    async def count_active_admins_excluding(
        self, *, admin_role_id: uuid.UUID, excluding_user_id: uuid.UUID
    ) -> int: ...

    async def replace_for_user(self, *, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> None: ...

    async def create_admin_audit_log_entry(
        self,
        *,
        event: str,
        actor_id: uuid.UUID,
        target_id: uuid.UUID | None,
        old_roles: list[str] | None,
        new_roles: list[str] | None,
        severity: str | None,
        request_id: str,
    ) -> None: ...

    async def commit(self) -> None: ...


class PermissionEpochCacheProtocol(Protocol):
    async def set_perm_epoch(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None: ...


class RoleService:
    def __init__(
        self,
        role_repository: RoleRepositoryProtocol,
        user_role_repository: UserRoleRepositoryProtocol,
        permission_epoch_cache: PermissionEpochCacheProtocol,
    ) -> None:
        self._role_repository = role_repository
        self._user_role_repository = user_role_repository
        self._permission_epoch_cache = permission_epoch_cache

    async def list_catalogue(self) -> RoleCatalogueResponse:
        """FR-3."""
        roles = await self._role_repository.list_all_with_permissions()
        return RoleCatalogueResponse(
            roles=[
                RoleSummary(name=role.name, permissions=sorted(p.scope for p in role.permissions))
                for role in roles
            ]
        )

    async def resolve_scopes_for_user(self, user_id: uuid.UUID) -> list[str]:
        """The cross-module read `users.service` calls at token issuance
        (login, refresh) to populate the JWT `scopes` claim (T6). Not part
        of the original US-012 DB/API design — added here because that
        integration point needs a single method returning the flattened,
        deduplicated permission set for a user's current roles.
        """
        role_names = await self._user_role_repository.list_role_names_for_user(user_id)
        if not role_names:
            return []
        roles = await self._role_repository.get_by_names(role_names)
        return sorted({permission.scope for role in roles for permission in role.permissions})

    async def get_role_grants_for_user(self, user_id: uuid.UUID) -> list[RoleGrant]:
        """US-009 FR-6: the cross-module read `users.service` calls at
        login/refresh to check privileged-role membership and the 14-day
        grace-period clock. Same `users` -> `roles` direction
        `resolve_scopes_for_user` already established.
        """
        grants = await self._user_role_repository.list_role_grants_for_user(user_id)
        return [RoleGrant(name=name, granted_at=granted_at) for name, granted_at in grants]

    async def replace_user_roles(
        self,
        *,
        actor_id: uuid.UUID,
        actor_scopes: set[str],
        target_id: uuid.UUID,
        requested_role_names: list[str],
        request_id: str,
    ) -> ReplaceUserRolesResponse:
        """FR-1, guarded by FR-4-FR-7.

        Check order (plan-review finding, not stated by the spec — see
        docs/plans/US-012-task-breakdown.md's Notes): self-target (FR-5,
        cheapest, no query needed) -> structural validation of the
        requested set (empty/duplicate/unknown role names, FR-4 plus the
        plan-review-resolved empty/duplicate default) -> privilege
        escalation (FR-6) -> last-admin invariant (FR-7) -> the write.
        """
        if target_id == actor_id:
            raise CannotTargetSelfError()

        if not requested_role_names or len(requested_role_names) != len(set(requested_role_names)):
            raise ValidationFailedError(
                errors=[
                    FieldError(
                        field="roles",
                        message="roles must be a non-empty list with no duplicate names.",
                        code="invalid_roles",
                    )
                ]
            )

        matched_roles = await self._role_repository.get_by_names(requested_role_names)
        matched_names = {role.name for role in matched_roles}
        unknown_names = set(requested_role_names) - matched_names
        if unknown_names:
            raise ValidationFailedError(
                errors=[
                    FieldError(
                        field="roles",
                        message=f"Unknown role(s): {', '.join(sorted(unknown_names))}.",
                        code="unknown_role",
                    )
                ]
            )

        requested_permissions = {
            permission.scope for role in matched_roles for permission in role.permissions
        }
        if not requested_permissions.issubset(actor_scopes):
            await self._user_role_repository.create_admin_audit_log_entry(
                event="authz_denied",
                actor_id=actor_id,
                target_id=target_id,
                old_roles=None,
                new_roles=sorted(matched_names),
                severity="high",
                request_id=request_id,
            )
            await self._user_role_repository.commit()
            raise PrivilegeEscalationError()

        old_role_names = await self._user_role_repository.list_role_names_for_user(target_id)

        if _ADMIN_ROLE_NAME in old_role_names and _ADMIN_ROLE_NAME not in matched_names:
            admin_rows = await self._role_repository.get_by_names([_ADMIN_ROLE_NAME])
            if admin_rows:
                remaining_admins = await self._user_role_repository.count_active_admins_excluding(
                    admin_role_id=admin_rows[0].id, excluding_user_id=target_id
                )
                if remaining_admins == 0:
                    raise LastAdminError()

        role_ids = [role.id for role in matched_roles]
        await self._user_role_repository.replace_for_user(user_id=target_id, role_ids=role_ids)
        await self._user_role_repository.create_admin_audit_log_entry(
            event="roles_replaced",
            actor_id=actor_id,
            target_id=target_id,
            old_roles=old_role_names,
            new_roles=sorted(matched_names),
            severity=None,
            request_id=request_id,
        )
        await self._user_role_repository.commit()

        settings = get_settings()
        await self._permission_epoch_cache.set_perm_epoch(
            target_id, ttl_seconds=settings.perm_epoch_ttl_seconds
        )

        return ReplaceUserRolesResponse(roles=sorted(matched_names))

    async def resolve_role_ids_for_grant(
        self,
        *,
        actor_id: uuid.UUID,
        actor_scopes: set[str],
        role_names: list[str],
        request_id: str,
    ) -> list[uuid.UUID]:
        """US-3.1 FR-8: the same privilege-escalation check
        `replace_user_roles` performs inline, exposed as an independent
        method for `admin_users.service`'s create-user flow (a target
        user's *initial* role grant, not a replacement of an existing
        set) to call.

        Deliberately a fresh implementation rather than an extraction from
        `replace_user_roles` — that method's checks are entangled with
        replacement-specific concerns (self-target, last-admin-on-removal)
        this call site has no equivalent for, and touching an already-
        shipped, already-tested method for a same-day feature carries
        needless regression risk (see US-011-plan-review.md's finding on
        the sibling `raise_if_last_admin` method below).

        Any name in `role_names` that doesn't match a real role is
        silently excluded from the returned id list, not rejected — this
        story's spec has no FR/AC for an unknown-role-name case at
        creation (unlike US-3.2's FR-4 for role replacement). Documented
        limitation, not a fabricated requirement — flagged in
        US-011-implementation-plan.md's follow-ups.
        """
        matched_roles = await self._role_repository.get_by_names(role_names)
        requested_permissions = {
            permission.scope for role in matched_roles for permission in role.permissions
        }
        if not requested_permissions.issubset(actor_scopes):
            await self._user_role_repository.create_admin_audit_log_entry(
                event="authz_denied",
                actor_id=actor_id,
                target_id=None,
                old_roles=None,
                new_roles=sorted(role.name for role in matched_roles),
                severity="high",
                request_id=request_id,
            )
            await self._user_role_repository.commit()
            raise PrivilegeEscalationError()

        return [role.id for role in matched_roles]

    async def raise_if_last_admin(self, target_user_id: uuid.UUID) -> None:
        """US-3.1 FR-16: raises `LastAdminError` if `target_user_id` holds
        the `admin` role and is the only active account holding it.

        Additive only — deliberately **not** called from
        `replace_user_roles`. That method's own inline last-admin check
        (above) is conditioned on "the *new* role set excludes admin";
        this method's condition is broader ("does the target hold admin
        at all"), and wiring it into `replace_user_roles` unconditionally
        would incorrectly reject a replacement that keeps `admin` in the
        set (e.g. `{admin}` -> `{admin, auditor}` for the sole admin) —
        caught during `plan-reviewer`'s advisor cross-check 2026-09-01,
        see US-011-plan-review.md's Risk Realism finding.
        """
        old_role_names = await self._user_role_repository.list_role_names_for_user(target_user_id)
        if _ADMIN_ROLE_NAME not in old_role_names:
            return

        admin_rows = await self._role_repository.get_by_names([_ADMIN_ROLE_NAME])
        if not admin_rows:
            return

        remaining_admins = await self._user_role_repository.count_active_admins_excluding(
            admin_role_id=admin_rows[0].id, excluding_user_id=target_user_id
        )
        if remaining_admins == 0:
            raise LastAdminError()
