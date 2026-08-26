import bcrypt
from anyio import to_thread

from app.core.config import get_settings


def _hash_password_sync(password: str) -> str:
    settings = get_settings()
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def hash_password(password: str) -> str:
    return await to_thread.run_sync(_hash_password_sync, password)
