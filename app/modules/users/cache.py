import uuid

from redis.asyncio import Redis

from app.core.cache_keys import login_fail_account_key, login_fail_ip_key


class LoginThrottleCache:
    """Brute-force throttle counters for POST /v1/auth/login (FR-5).

    Advisory rate-limit state, not a security denylist: unlike
    RevocationCache, there is no DB-backed source of truth to degrade to on
    a Valkey outage, so this gateway does not catch client errors itself —
    the service decides how to handle an outage, per AGENTS.md §3's default
    (only the token denylist fails closed).

    increment/expire run as one atomic pipeline so a concurrent failed
    login from the same account/IP never loses an update to a lost race
    between INCR and EXPIRE (plan risk: throttle-counter concurrency).
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def record_account_failure(self, user_id: uuid.UUID, *, window_seconds: int) -> int:
        return await self._incr_with_ttl(login_fail_account_key(user_id), window_seconds)

    async def record_ip_failure(self, ip: str, *, window_seconds: int) -> int:
        return await self._incr_with_ttl(login_fail_ip_key(ip), window_seconds)

    async def get_account_failure_count(self, user_id: uuid.UUID) -> int:
        return await self._get_count(login_fail_account_key(user_id))

    async def get_ip_failure_count(self, ip: str) -> int:
        return await self._get_count(login_fail_ip_key(ip))

    async def get_account_retry_after_seconds(self, user_id: uuid.UUID) -> int:
        return await self._get_ttl(login_fail_account_key(user_id))

    async def get_ip_retry_after_seconds(self, ip: str) -> int:
        return await self._get_ttl(login_fail_ip_key(ip))

    async def reset_account_failures(self, user_id: uuid.UUID) -> None:
        # Resolved OD-5: only the account counter resets on a successful
        # login; the per-IP counter is deliberately left alone, since one
        # IP can serve many accounts and a success on one shouldn't clear
        # failure history that may reflect a different attacker on it.
        await self._client.delete(login_fail_account_key(user_id))

    async def _incr_with_ttl(self, key: str, window_seconds: int) -> int:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = await pipe.execute()
        return int(count)

    async def _get_count(self, key: str) -> int:
        raw = await self._client.get(key)
        return int(raw) if raw is not None else 0

    async def _get_ttl(self, key: str) -> int:
        ttl = await self._client.ttl(key)
        return max(int(ttl), 0)
