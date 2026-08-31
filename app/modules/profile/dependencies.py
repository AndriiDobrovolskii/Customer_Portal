from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailSender, get_email_sender
from app.db.dependencies import get_db_session
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.service import ProfileService
from app.modules.users.dependencies import UserServiceDep


def get_profile_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    # UserService is injected purely as the SessionRevokerProtocol
    # collaborator (revoke_other_sessions) for UP-AC11 — a temporary home
    # pending a future shared `auth` module (see docs/ARCHITECTURE.md §3.4).
    session_revoker: UserServiceDep,
) -> ProfileService:
    repository = ProfileRepository(session)
    return ProfileService(repository, session_revoker, email_sender=email_sender)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
