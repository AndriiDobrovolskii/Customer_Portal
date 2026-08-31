# Data Layer Patterns — Exemplars

## Models: `app/modules/users/models.py`, `app/modules/profile/models.py`

- `User`, `UserSession`, `EmailChangeToken`, `ProfileAuditLog` — every column is `Mapped[]`/`mapped_column()` with explicit type, length, nullability, and either a Python `default=` (for values like `uuid.uuid4` the app must generate) or a `server_default=` (for DB-computed values like `func.now()`, `false()`). Nothing is left to an implicit type-level default.
- `UserSession.user_id` shows the standard FK shape: `ForeignKey("users.id", ondelete="CASCADE")`, `nullable=False`, `index=True` when the column is queried by by that key.
- `ProfileAuditLog.actor_id` shows the deliberate *absence* of a FK, with a comment explaining why ("the row must survive deletion of the actor's account") — a reminder that not every foreign-key-shaped column should actually be a `ForeignKey()`; follow the DB design's stated constraint, don't infer one.
- **No `relationship()` exists anywhere in this codebase yet.** Every cross-entity read (`get_by_id` on `User`, then a separate query against `EmailChangeToken`) is done as two explicit repository calls, not a loaded relationship. This is a valid, currently-universal pattern — only introduce `relationship()` + eager loading when the DB design explicitly calls for one endpoint to return nested data in a single response.

## Repository: `app/modules/users/repository.py`, `app/modules/profile/repository.py`

- Constructor takes only `session: AsyncSession` — no other collaborator.
- `create()` — `session.add()`, then `flush()` inside a `try`/`except IntegrityError`, rolling back and returning `None` on conflict. This is the canonical create-with-uniqueness-conflict shape.
- `apply_email_change()` (profile) — same try/except/rollback shape but returning `bool`, with a docstring stating exactly which race condition the `False` return covers.
- `consume_email_change_token()` (profile) — an atomic-consume pattern via `UPDATE ... WHERE consumed_at IS NULL ... RETURNING id`, checked against `None` — the idiomatic SQLAlchemy 2.0 way to do a check-and-set without a separate read-then-write race.
- `commit()` — identical one-line passthrough (`await self._session.commit()`) in every repository in this codebase. Copy this shape exactly; do not invent a variant (e.g. accepting a bool for "commit or rollback").

## Cache gateway skeleton (no in-repo exemplar — built fresh from AGENTS.md §3)

```python
from __future__ import annotations

import uuid
from typing import Final

from glide import GlideClient  # or this project's actual async Valkey client type

_USER_PROFILE_TTL_SECONDS: Final = 300


def _user_profile_key(user_id: uuid.UUID) -> str:
    return f"user:{user_id}:profile"


class ProfileCacheGateway:
    def __init__(self, client: GlideClient) -> None:
        self._client = client

    async def get_profile(self, user_id: uuid.UUID) -> dict[str, str] | None:
        # Never authoritative: caller falls back to the DB on None, including
        # on a connection error caught here and translated to None.
        try:
            raw = await self._client.get(_user_profile_key(user_id))
        except Exception:  # narrow to the client's actual exception type in real code
            return None
        return _decode(raw) if raw is not None else None

    async def set_profile(self, user_id: uuid.UUID, value: dict[str, str]) -> None:
        await self._client.set(
            _user_profile_key(user_id), _encode(value), ex=_USER_PROFILE_TTL_SECONDS
        )


class TokenDenylistCacheGateway:
    def __init__(self, client: GlideClient) -> None:
        self._client = client

    async def is_denied(self, jti: uuid.UUID) -> bool:
        # Fails CLOSED: an unreachable cache must never be read as "not denied."
        try:
            return await self._client.exists(f"denylist:{jti}") == 1
        except Exception:  # narrow to the client's actual exception type in real code
            return True
```

Replace the placeholder client import/type with whatever this project's actual async Valkey client is once one is chosen (`AGENTS.md` §2 specifies "Async client only, always injected" but does not pin a specific library) — treat introducing that dependency as the kind of decision `AGENTS.md` §1 says needs proposing, not silently picked by this skill.
