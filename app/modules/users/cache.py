import uuid

from redis.asyncio import Redis

from app.core.cache_keys import (
    login_fail_account_key,
    login_fail_ip_key,
    mfa_token_key,
    mfa_used_step_key,
    mfa_verify_attempts_key,
    password_reset_account_hourly_key,
    password_reset_cooldown_key,
    password_reset_ip_hourly_key,
    refresh_rate_limit_key,
)


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


class RefreshRateLimitCache:
    """Per-family_id request counter for POST /v1/auth/refresh (resolved OD-1).

    Advisory rate-limit state, same class of gateway as LoginThrottleCache:
    no DB-backed source of truth to degrade to on a Valkey outage, so this
    gateway does not catch client errors itself — the service decides how
    to handle an outage, per AGENTS.md §3's default (only the token
    denylist fails closed).
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def record_request(self, family_id: uuid.UUID, *, window_seconds: int) -> int:
        key = refresh_rate_limit_key(family_id)
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = await pipe.execute()
        return int(count)

    async def get_request_count(self, family_id: uuid.UUID) -> int:
        raw = await self._client.get(refresh_rate_limit_key(family_id))
        return int(raw) if raw is not None else 0

    async def get_retry_after_seconds(self, family_id: uuid.UUID) -> int:
        ttl = await self._client.ttl(refresh_rate_limit_key(family_id))
        return max(int(ttl), 0)


class PasswordResetRateLimitCache:
    """Three-limit request throttle for POST /v1/auth/password-reset/request
    (resolved OD-2): a 60 s per-account cooldown, a 5/hour per-account
    limit, and a 10/hour per-IP limit, checked by the service in that order.

    The account-scoped counters are keyed by a hash of the normalized email,
    not `user_id` — FR-3's anti-enumeration requirement means these limits
    must apply identically to an unknown email, which has no `user_id`
    (plan.md's Architectural Change #2). The cooldown and hourly counters
    use separate keys (not one counter read two ways) since they need
    different TTLs.

    Same advisory-rate-limit class as `LoginThrottleCache`/
    `RefreshRateLimitCache`: no DB-backed source of truth to degrade to on a
    Valkey outage, so this gateway does not catch client errors itself.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def record_cooldown_attempt(self, email_hash: str, *, window_seconds: int) -> int:
        return await self._incr_with_ttl(password_reset_cooldown_key(email_hash), window_seconds)

    async def get_cooldown_retry_after_seconds(self, email_hash: str) -> int:
        return await self._get_ttl(password_reset_cooldown_key(email_hash))

    async def record_account_attempt(self, email_hash: str, *, window_seconds: int) -> int:
        return await self._incr_with_ttl(
            password_reset_account_hourly_key(email_hash), window_seconds
        )

    async def get_account_retry_after_seconds(self, email_hash: str) -> int:
        return await self._get_ttl(password_reset_account_hourly_key(email_hash))

    async def record_ip_attempt(self, ip: str, *, window_seconds: int) -> int:
        return await self._incr_with_ttl(password_reset_ip_hourly_key(ip), window_seconds)

    async def get_ip_retry_after_seconds(self, ip: str) -> int:
        return await self._get_ttl(password_reset_ip_hourly_key(ip))

    async def _incr_with_ttl(self, key: str, window_seconds: int) -> int:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = await pipe.execute()
        return int(count)

    async def _get_ttl(self, key: str) -> int:
        ttl = await self._client.ttl(key)
        return max(int(ttl), 0)


class MfaTokenCache:
    """Valkey-backed opaque `mfa_token` (FR-3) - single-use via `GETDEL`,
    not a JWT (see docs/plans/US-009-implementation-plan.md Architectural
    Change #3). Not fail-closed like RevocationCache: an unreachable
    Valkey means the token can't be found, which is the same outward
    behavior as an already-invalid token (401), not a security bypass.

    `get_user_id` is the non-destructive read used on every `/verify`
    call to resolve which account is being challenged (survives repeated
    wrong-code attempts up to the lockout threshold). `consume` is the
    atomic destructive read used only once a code has been confirmed
    correct, so two concurrent successful requests against the same
    token can never both complete the login.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def issue(self, token_hash: str, *, user_id: uuid.UUID, ttl_seconds: int) -> None:
        await self._client.set(mfa_token_key(token_hash), str(user_id), ex=ttl_seconds)

    async def get_user_id(self, token_hash: str) -> uuid.UUID | None:
        raw = await self._client.get(mfa_token_key(token_hash))
        return self._parse_user_id(raw)

    async def consume(self, token_hash: str) -> uuid.UUID | None:
        raw = await self._client.getdel(mfa_token_key(token_hash))
        return self._parse_user_id(raw)

    @staticmethod
    def _parse_user_id(raw: bytes | str | None) -> uuid.UUID | None:
        if raw is None:
            return None
        # decode_responses=True on the client guarantees str at runtime;
        # the installed stub still types redis.get()'s return as bytes|str.
        if isinstance(raw, bytes):
            raw = raw.decode()
        return uuid.UUID(raw)

    async def record_failed_attempt(self, token_hash: str, *, window_seconds: int) -> int:
        return await self._incr_with_ttl(mfa_verify_attempts_key(token_hash), window_seconds)

    async def invalidate(self, token_hash: str) -> None:
        """FR-5: the 5th failed attempt deletes both the token and its own
        attempt counter - full re-authentication is required afterward,
        so nothing is left for a stale counter to apply to.
        """
        await self._client.delete(mfa_token_key(token_hash), mfa_verify_attempts_key(token_hash))

    async def _incr_with_ttl(self, key: str, window_seconds: int) -> int:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = await pipe.execute()
        return int(count)


class MfaReplayCache:
    """FR-4 replay protection: `mfa_used_step:{user_id}:{step}`, TTL one
    time step (30s). `SET NX` makes marking a step used atomic, so two
    concurrent verify calls at the same step can't both succeed.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def mark_step_used(self, user_id: uuid.UUID, *, step: int, ttl_seconds: int) -> bool:
        """Returns True if this step was not already used (and is now
        marked used); False if it was already used (a replay, MF-AC4).
        """
        result = await self._client.set(
            mfa_used_step_key(user_id, step), "1", nx=True, ex=ttl_seconds
        )
        return bool(result)
