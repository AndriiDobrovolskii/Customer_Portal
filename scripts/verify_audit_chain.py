"""AU-AC7/FR-7's `[gate]`-marked chain-verification job. Not wired to any
in-process scheduler (this project's own `scripts/purge_unverified_accounts.py`
precedent) — invoke externally, e.g. on demand or a periodic cron line:

    cd /srv/customer-portal && .venv/bin/python scripts/verify_audit_chain.py

Reports "intact" (exit 0) if `audit_log`'s hash chain is unbroken, or the
exact row at which it breaks (exit 1) — either a `previous_hash` that
doesn't match the prior row's `row_hash` (a row was inserted, deleted, or
reordered), or a `row_hash` that no longer matches its own row's
recomputed hash (a row's fields were altered in place after insertion).
"""

import asyncio
import hashlib
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import create_engine_and_sessionmaker

logger = logging.getLogger(__name__)

# Matches the trigger's own genesis rule (OD-17, migration
# 57a978462b74_add_audit_log_and_history_view.py): the very first row ever
# inserted seeds `previous_hash` from the hex-encoded SHA-256 of the empty
# string.
GENESIS_SENTINEL = hashlib.sha256(b"").hexdigest()

# Walking rows in this order (ascending) exactly reverses the trigger's own
# seed query (`ORDER BY occurred_at DESC, id DESC LIMIT 1`) — each row's
# immediate predecessor in this list is the exact row the trigger seeded it
# from, including across any gaps (OD-17's "skip empty days" needs no
# special-casing here: a gap in `occurred_at` values doesn't break the
# adjacency between whichever two rows actually exist on either side of it).
_SELECT_CHAIN_SQL = """
SELECT id, occurred_at, event, previous_hash, row_hash,
       audit_log_row_hash(previous_hash, occurred_at, actor_id, event, target_id, payload)
           AS expected_row_hash
FROM audit_log
ORDER BY occurred_at ASC, id ASC
"""


@dataclass(frozen=True, slots=True)
class ChainRow:
    id: uuid.UUID
    occurred_at: datetime
    event: str
    previous_hash: str
    row_hash: str
    # Recomputed by the same `audit_log_row_hash()` SQL function the
    # trigger itself calls (migration 57a978462b74) — deliberately not
    # reimplemented in Python, so this verifier can never drift from the
    # trigger's own serialization of `payload`/etc.
    expected_row_hash: str


@dataclass(frozen=True, slots=True)
class ChainBreak:
    id: uuid.UUID
    occurred_at: datetime
    event: str
    reason: str  # "previous_hash_mismatch" | "row_hash_mismatch"


def verify_chain(rows: Sequence[ChainRow]) -> ChainBreak | None:
    """Pure function, no I/O — unit-tested against hand-built `ChainRow`
    fixtures (T7b), not a real database.

    Returns the *first* break found, matching AU-AC7's own wording ("the
    exact row at which the chain breaks," singular) — deliberate, not a
    limitation to fix. A clean second run after a fix proves that break is
    gone, not that no other row is compromised; re-run after every fix.

    Known limitation, not addressed by this story: deleting the chain's
    own *tail* row (or a contiguous suffix ending at the tail) leaves the
    remaining rows internally consistent — nothing here would detect it.
    Doing so would need a checkpoint the chain doesn't currently have (a
    recorded expected-tail hash, or a monotonic sequence column), which is
    new schema beyond this story's scope. Disclosed, not silently absent —
    see US-3.3-traceability-matrix.md's AU-AC7 rows.
    """
    expected_previous_hash = GENESIS_SENTINEL
    for row in rows:
        if row.previous_hash != expected_previous_hash:
            return ChainBreak(
                id=row.id,
                occurred_at=row.occurred_at,
                event=row.event,
                reason="previous_hash_mismatch",
            )
        if row.row_hash != row.expected_row_hash:
            return ChainBreak(
                id=row.id,
                occurred_at=row.occurred_at,
                event=row.event,
                reason="row_hash_mismatch",
            )
        expected_previous_hash = row.row_hash
    return None


async def _fetch_chain(session: AsyncSession) -> list[ChainRow]:
    """Loads the entire `audit_log` table into memory — fine at this
    story's scope (no scale requirement stated for the verifier in the
    implementation plan), but this becomes the retention window's own row
    count once AU-AC9's 400-day retention job exists. Not addressed here;
    named so it's a known tradeoff, not a surprise later.
    """
    result = await session.execute(text(_SELECT_CHAIN_SQL))
    return [
        ChainRow(
            id=row.id,
            occurred_at=row.occurred_at,
            event=row.event,
            previous_hash=row.previous_hash,
            row_hash=row.row_hash,
            expected_row_hash=row.expected_row_hash,
        )
        for row in result.all()
    ]


async def main() -> int:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    try:
        async with session_factory() as session:
            rows = await _fetch_chain(session)
        broken_at = verify_chain(rows)
    finally:
        await engine.dispose()

    if broken_at is None:
        logger.info("verify_audit_chain: intact (%d row(s))", len(rows))
        return 0

    logger.error(
        "verify_audit_chain: BROKEN at id=%s occurred_at=%s event=%s reason=%s",
        broken_at.id,
        broken_at.occurred_at,
        broken_at.event,
        broken_at.reason,
    )
    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main()))
