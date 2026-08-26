from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, email: str, hashed_password: str, status: str) -> User | None:
        user = User(email=email, hashed_password=hashed_password, status=status)
        self._session.add(user)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return None
        return user

    async def commit(self) -> None:
        await self._session.commit()
