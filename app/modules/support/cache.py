import json
import uuid
from typing import NamedTuple

from redis.asyncio import Redis

from app.core.cache_keys import idempotency_key, ticket_create_rate_key, ticket_reply_rate_key


class IdempotencyEnvelope(NamedTuple):
    request_hash: str
    ticket_id: uuid.UUID | None


class TicketIdempotencyCache:
    """FR-4 / US-4.1-db-design.md's atomic `SET NX EX` claim/replay gate.

    Deliberately a low-level primitive, not a single raising `claim_or_get`
    call: `AGENTS.md` §3 states gateways "return `None` or empty and raise
    nothing" — the hash-mismatch/poll-exhaustion branching and the domain
    exceptions they produce belong in `TicketService.create_ticket`, which
    is also where `US-4.1-db-design.md` itself places "the service GETs the
    existing envelope and branches."
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def claim(
        self, *, user_id: uuid.UUID, key: str, request_hash: str, ttl_seconds: int
    ) -> bool:
        """Atomic `SET NX EX`. True: this call claimed the key (sole writer,
        proceed as a new request). False: the key already exists — the
        caller must `get_envelope` to see why.
        """
        envelope = json.dumps({"request_hash": request_hash, "ticket_id": None})
        result = await self._client.set(
            idempotency_key(user_id, key), envelope, nx=True, ex=ttl_seconds
        )
        return bool(result)

    async def get_envelope(self, *, user_id: uuid.UUID, key: str) -> IdempotencyEnvelope | None:
        """None when the key does not exist (expired, or never claimed)."""
        raw = await self._client.get(idempotency_key(user_id, key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        data = json.loads(raw)
        raw_ticket_id = data["ticket_id"]
        return IdempotencyEnvelope(
            request_hash=data["request_hash"],
            ticket_id=uuid.UUID(raw_ticket_id) if raw_ticket_id is not None else None,
        )

    async def resolve(
        self,
        *,
        user_id: uuid.UUID,
        key: str,
        request_hash: str,
        ticket_id: uuid.UUID,
        ttl_seconds: int,
    ) -> None:
        """Overwrites the claimed key with the created ticket's id (plain
        `SET`, no `NX` — only the request that won the original claim calls
        this), same TTL. Only the caller that won `claim` may call this.
        """
        envelope = json.dumps({"request_hash": request_hash, "ticket_id": str(ticket_id)})
        await self._client.set(idempotency_key(user_id, key), envelope, ex=ttl_seconds)

    async def release(self, *, user_id: uuid.UUID, key: str) -> None:
        """Deletes a claimed-but-never-resolved key. Found while building
        `TicketService.create_ticket` (T6): without this, a request that
        wins `claim` but then fails validation (e.g. `AttachmentNotOwnedError`)
        before reaching `resolve` would leave the key stuck at `ticket_id:
        null` for the rest of its TTL — every retry with the same
        `Idempotency-Key` would then hit the bounded-poll path and exhaust it
        every time, a self-inflicted denial-of-service against the caller's
        own key. Called by the service on any failure path after `claim`
        succeeds and before `resolve` would otherwise run.
        """
        await self._client.delete(idempotency_key(user_id, key))


class TicketCreationRateLimitCache:
    """FR-6: `ticket_create_rate:{user_id}`, the identical pipelined
    `INCR`+`EXPIRE` shape `LoginThrottleCache._incr_with_ttl` already uses
    (`app/modules/users/cache.py`) — advisory rate-limit state, no DB-backed
    source of truth to degrade to, so this gateway does not catch client
    errors itself.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def record_and_check(self, user_id: uuid.UUID, *, window_seconds: int) -> int:
        key = ticket_create_rate_key(user_id)
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = await pipe.execute()
        return int(count)

    async def get_retry_after_seconds(self, user_id: uuid.UUID) -> int:
        ttl = await self._client.ttl(ticket_create_rate_key(user_id))
        return max(int(ttl), 0)


class TicketReplyRateLimitCache:
    """NFR (30/hour): `ticket_reply_rate:{user_id}`, the identical pipelined
    `INCR`+`EXPIRE` shape as `TicketCreationRateLimitCache` - a distinct
    Valkey key so this reply rate limit never shares a counter with ticket
    creation's own 30/hour limit (Risk 6's independence requirement).
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def record_and_check(self, user_id: uuid.UUID, *, window_seconds: int) -> int:
        key = ticket_reply_rate_key(user_id)
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = await pipe.execute()
        return int(count)

    async def get_retry_after_seconds(self, user_id: uuid.UUID) -> int:
        ttl = await self._client.ttl(ticket_reply_rate_key(user_id))
        return max(int(ttl), 0)
