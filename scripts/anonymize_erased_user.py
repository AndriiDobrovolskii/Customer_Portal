"""AU-AC8/FR-8's `[gate]`-marked erasure script (OD-2/OD-13/OD-19). A
minimal, provisional version of the still-unbuilt US-1.4 DA-AC9 retention
job — the legal/DPO anonymize-vs-hard-delete policy question stays open
separately (OD-9); this script picks "anonymize," matching BR-007's own
leaning, scoped only to what AU-AC8 needs to prove.

Not wired to any scheduler — invoked with an explicit target user id:

    python scripts/anonymize_erased_user.py <user-id>

Anonymizes the target `users` row and redacts direct identifiers on that
user's existing audit rows:

- `auth_audit_log.ip` -> redacted for that user's rows.

Does NOT redact `profile_audit_log.old_value`/`new_value` (OD-13's
originally committed mechanism) — **OD-20 (resolved 2026-09-02):**
`profile_audit_log` carries a DB-level `BEFORE UPDATE OR DELETE` trigger
(`profile_audit_log_deny_mutation`, from an earlier story) that
unconditionally raises on any mutation, confirmed by actually running
this script's redaction SQL against it. OD-13's UPDATE-based mechanism is
technically impossible as designed. Disabling that trigger, even
transactionally, was considered and explicitly rejected by the user as
an architectural anti-pattern overriding another story's already-shipped
integrity guarantee — deferred to a separate architectural review rather
than worked around here. `display_name` values embedded in that table's
`old_value`/`new_value` for an erased user remain unredacted until that
review lands.

Deliberately does NOT touch `audit_log` itself (OD-19's own reasoning):
`audit_log_row_hash()` is computed over `(previous_hash, occurred_at,
actor_id, event, target_id, payload)` — mutating any of those in place
would break AU-AC7's tamper-evidence chain. Under staged OD-14 this
story's own two event types (`audit_log_viewed`, the `audit:read`-denial
event) retain `actor_id` as an opaque UUID (AU-AC8's own third clause)
and carry no PII in `payload` (query filter parameters only), so there is
nothing to redact there for this story's scope. `payload` JSONB scanning
for embedded identifiers in other tables (OD-8) remains open, separately,
and is not addressed here.

`admin_audit_log`/`account_lifecycle_audit_log` are also left untouched:
neither stores email/display_name/ip (verified against their models),
so AU-AC8's three named identifiers don't appear there for this user.
"""

import asyncio
import logging
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import create_engine_and_sessionmaker

logger = logging.getLogger(__name__)


async def anonymize_erased_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text("UPDATE users SET email = :anon_email, display_name = NULL WHERE id = :user_id"),
        {"anon_email": f"deleted-{user_id}@anonymized.invalid", "user_id": user_id},
    )
    await session.execute(
        text("UPDATE auth_audit_log SET ip = 'redacted' WHERE actor_id = :user_id"),
        {"user_id": user_id},
    )
    # profile_audit_log is deliberately not touched here — see this
    # module's docstring, OD-20.


async def main(argv: list[str]) -> int:
    if len(argv) != 2:
        logger.error("usage: anonymize_erased_user.py <user-id>")
        return 2
    try:
        user_id = uuid.UUID(argv[1])
    except ValueError:
        logger.error("invalid user id: %s", argv[1])
        return 2

    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    try:
        async with session_factory() as session:
            await anonymize_erased_user(session, user_id)
            await session.commit()
    finally:
        await engine.dispose()

    logger.info("anonymize_erased_user: complete for user_id=%s", user_id)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main(sys.argv)))
