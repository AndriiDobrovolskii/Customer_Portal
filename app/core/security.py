from anyio import to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError

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


def _verify_password_sync(password: str, hashed_password: str) -> bool:
    hasher = PasswordHasher()
    try:
        return hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHash):
        return False


async def verify_password(password: str, hashed_password: str) -> bool:
    return await to_thread.run_sync(_verify_password_sync, password, hashed_password)
