"""Cron entry point — delete unbound attachments past the 24h purge window (FR-7).

Not wired to any in-process scheduler. Invoke externally, e.g. a daily
cron line:

    0 4 * * *  cd /srv/customer-portal && .venv/bin/python scripts/purge_unbound_attachments.py

Exit code 0 on success (including zero purged); non-zero on failure, so
cron can alert on it. Talks to `AttachmentRepository` directly rather than
`TicketService` — the purge sweep needs no business validation (no
idempotency/rate-limit/audit concerns), and constructing the full
`TicketService` would force wiring five unrelated `create_ticket`
collaborators for an operation that touches none of them.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.session import create_engine_and_sessionmaker
from app.modules.support.repository import AttachmentRepository

logger = logging.getLogger(__name__)

_UNBOUND_ATTACHMENT_PURGE_AFTER_HOURS = 24  # FR-7's last sentence


async def main() -> int:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    try:
        async with session_factory() as session:
            repository = AttachmentRepository(session)
            cutoff = datetime.now(UTC) - timedelta(hours=_UNBOUND_ATTACHMENT_PURGE_AFTER_HOURS)
            candidates = await repository.find_unbound_older_than(cutoff)
            purged_count = await repository.purge([attachment.id for attachment in candidates])
            await repository.commit()
        logger.info("purge_unbound_attachments complete: purged %d attachment(s)", purged_count)
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main()))
