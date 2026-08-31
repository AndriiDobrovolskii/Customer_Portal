import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
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


# Not real credentials — pay comparable Argon2id verification cost only.
# Deliberately two distinct values (stored vs. attempted): hashing and
# verifying the *same* value would always return True, which doesn't match
# what a real wrong-password verification actually does.
_DUMMY_STORED_PASSWORD = "dummy-stored-value"  # noqa: S105  # pragma: allowlist secret
_DUMMY_ATTEMPT_PASSWORD = "dummy-attempt-value"  # noqa: S105  # pragma: allowlist secret
_dummy_hash_cache: str | None = None


async def verify_password_dummy() -> bool:
    """Pays the same Argon2id verification cost as `verify_password` when no
    account matched, so response timing doesn't reveal account existence
    (LI-AC3). Always returns False (the attempted value never matches the
    stored one). The dummy hash is computed lazily against current
    `settings.argon2_*` parameters on first use and cached, rather than a
    hardcoded string computed once at old parameter values, so it can never
    drift out of step with the parameters real verification actually uses.
    """
    global _dummy_hash_cache
    if _dummy_hash_cache is None:
        _dummy_hash_cache = await hash_password(_DUMMY_STORED_PASSWORD)
    return await verify_password(_DUMMY_ATTEMPT_PASSWORD, _dummy_hash_cache)


def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash). The raw value is returned to the
    caller once (as the cookie); only the SHA-256 hash is ever persisted,
    matching US-2.3's Assumption #5 token design.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
    return raw_token, token_hash


class InvalidTokenError(Exception):
    """Raised when an access token fails to decode or verify.

    Deliberately a plain exception, not a ProblemError: app.core stays
    domain-free (§3), so translating this into a 401 happens in the module
    that calls decode_access_token.
    """


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    jti: uuid.UUID
    exp: datetime


def encode_access_token(*, user_id: uuid.UUID, jti: uuid.UUID) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {"sub": str(user_id), "jti": str(jti), "exp": expires_at}
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm]
        )
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            jti=uuid.UUID(payload["jti"]),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError from exc
