"""Cron entry point — delete unverified accounts past the purge window.

Not wired to any in-process scheduler. Invoke externally, e.g. a daily
cron line:

    0 3 * * *  cd /srv/customer-portal && .venv/bin/python scripts/purge_unverified_accounts.py

Exit code 0 on success (including zero purged); non-zero on failure, so
cron can alert on it.
"""

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import create_engine_and_sessionmaker
from app.modules.email_verification.repository import EmailVerificationRepository
from app.modules.email_verification.service import EmailVerificationService

logger = logging.getLogger(__name__)


async def main() -> int:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    try:
        async with session_factory() as session:
            service = EmailVerificationService(EmailVerificationRepository(session))
            purged_count = await service.purge_unverified_accounts()
        logger.info("purge_unverified_accounts complete: purged %d account(s)", purged_count)
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main()))
