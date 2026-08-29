from anyio import to_thread
from argon2 import PasswordHasher

from app.core.config import get_settings


def _hash_password_sync(password: str) -> str:
    settings = get_settings()
    hasher = PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost_kb,
        parallelism=settings.argon2_parallelism,
    )
    return hasher.hash(password)


async def hash_password(password: str) -> str:
    return await to_thread.run_sync(_hash_password_sync, password)
