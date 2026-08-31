from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, get_email_sender
from app.db.dependencies import get_db_session
from app.modules.email_verification.repository import EmailVerificationRepository
from app.modules.email_verification.service import EmailVerificationService


def get_email_verification_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> EmailVerificationService:
    repository = EmailVerificationRepository(session)
    return EmailVerificationService(repository, email_sender=email_sender)


EmailVerificationServiceDep = Annotated[
    EmailVerificationService, Depends(get_email_verification_service)
]
