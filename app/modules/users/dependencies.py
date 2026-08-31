from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, get_email_sender
from app.core.revocation_cache import RevocationCache
from app.db.dependencies import get_db_session, get_valkey_client
from app.modules.email_verification.dependencies import EmailVerificationServiceDep
from app.modules.users.exceptions import UnauthenticatedError
from app.modules.users.repository import UserRepository
from app.modules.users.service import AuthenticatedUser, UserService


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    issuer: EmailVerificationServiceDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    valkey_client: Annotated[Redis, Depends(get_valkey_client)],
) -> UserService:
    repository = UserRepository(session)
    revocation_cache = RevocationCache(valkey_client)
    return UserService(repository, issuer, email_sender, revocation_cache)


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
