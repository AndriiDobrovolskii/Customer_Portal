from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, get_email_sender
from app.db.dependencies import get_db_session
from app.modules.email_verification.dependencies import EmailVerificationServiceDep
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    issuer: EmailVerificationServiceDep,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> UserService:
    repository = UserRepository(session)
    return UserService(repository, issuer, email_sender)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
