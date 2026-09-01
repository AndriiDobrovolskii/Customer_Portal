from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, get_email_sender
from app.core.revocation_cache import PermissionEpochCache, RevocationCache
from app.db.dependencies import get_db_session, get_valkey_client
from app.modules.account.dependencies import AccountServiceDep
from app.modules.email_verification.dependencies import EmailVerificationServiceDep
from app.modules.roles.repository import RoleRepository, UserRoleRepository
from app.modules.roles.service import RoleService
from app.modules.users.cache import (
    LoginThrottleCache,
    PasswordResetRateLimitCache,
    RefreshRateLimitCache,
)
from app.modules.users.exceptions import UnauthenticatedError
from app.modules.users.repository import UserRepository
from app.modules.users.service import AuthenticatedUser, UserService


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    issuer: EmailVerificationServiceDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    valkey_client: Annotated[Redis, Depends(get_valkey_client)],
    # AccountService is injected purely as the AccountServiceProtocol
    # collaborator (reactivate_account) for resolved OD-10/DA-AC8, mirroring
    # profile/dependencies.py's own cross-module UserServiceDep injection.
    account_service: AccountServiceDep,
) -> UserService:
    repository = UserRepository(session)
    revocation_cache = RevocationCache(valkey_client)
    throttle_cache = LoginThrottleCache(valkey_client)
    refresh_rate_limit_cache = RefreshRateLimitCache(valkey_client)
    password_reset_rate_limit_cache = PasswordResetRateLimitCache(valkey_client)
    permission_epoch_cache = PermissionEpochCache(valkey_client)
    # Built directly, not via roles.dependencies.RoleServiceDep: that module
    # imports CurrentUserDep from this one (for its require_scope check),
    # so importing RoleServiceDep back here would be a circular import.
    # roles.repository/roles.service have no such reverse dependency.
    role_service = RoleService(
        RoleRepository(session), UserRoleRepository(session), permission_epoch_cache
    )
    return UserService(
        repository,
        issuer,
        email_sender,
        revocation_cache,
        throttle_cache,
        account_service,
        refresh_rate_limit_cache,
        password_reset_rate_limit_cache,
        permission_epoch_cache,
        role_service,
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)], service: UserServiceDep
) -> AuthenticatedUser:
    authenticated_user = await service.get_authenticated_user(token)
    if authenticated_user is None:
        raise UnauthenticatedError
    return authenticated_user


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


async def get_current_user_allow_revoked(
    token: Annotated[str, Depends(_oauth2_scheme)], service: UserServiceDep
) -> AuthenticatedUser:
    """Resolved OD-2 (US-2.2): used by `POST /v1/auth/logout` only, so a
    repeat logout call is idempotent (LO-AC4) rather than 401ing. A
    deliberately separate function from `get_current_user` — not a shared
    one with a query-param flag — so this leniency can never leak into
    another route by an accidental call-site change; every other route
    keeps depending on `get_current_user`/`CurrentUserDep` unchanged.
    """
    authenticated_user = await service.get_authenticated_user(token, allow_revoked=True)
    if authenticated_user is None:
        raise UnauthenticatedError
    return authenticated_user


CurrentUserAllowRevokedDep = Annotated[AuthenticatedUser, Depends(get_current_user_allow_revoked)]
