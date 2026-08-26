from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserService:
    repository = UserRepository(session)
    return UserService(repository)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
