import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.cache_keys import revoke_before_key


class RevocationCache:
    """The single read/write surface for `revoke_before:{user_id}`.

    Core, not module-owned: `business-glossary.md` names three writers
    (deactivation, logout-everywhere, password reset) across three
    different modules, and `users` reads it on every authenticated
    request — no single module owns this the way it owns its own
    `cache.py`, so it lives beside `app.core.security`'s other
    cross-cutting auth primitives instead.

    A token-denylist signal: per AGENTS.md §3, the cache is never the
    source of truth *except* the denylist, which fails closed. This class
    deliberately does not catch Valkey connection errors — an outage must
    surface to the caller, which fails the request closed, rather than
    being swallowed here and silently treated as "not revoked".
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def set_revoke_before(self, user_id: uuid.UUID, *, ttl_seconds: int) -> None:
        await self._client.set(
            revoke_before_key(user_id), datetime.now(UTC).isoformat(), ex=ttl_seconds
        )

    async def get_revoke_before(self, user_id: uuid.UUID) -> datetime | None:
        raw = await self._client.get(revoke_before_key(user_id))
        if raw is None:
            return None
        # decode_responses=True on the client guarantees str at runtime;
        # the installed stub still types redis.get()'s return as bytes|str.
        if isinstance(raw, bytes):
            raw = raw.decode()
        return datetime.fromisoformat(raw)
