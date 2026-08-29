import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_verification_email(self, *, to: str, raw_token: str) -> None: ...


class LoggingEmailSender:
    """No-op sender that logs dispatch without a real mail provider.

    Never logs `to` or `raw_token` — the raw token is a bearer credential and
    must never appear in application logs.
    """

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        logger.info("verification email dispatched")


def get_email_sender() -> EmailSender:
    return LoggingEmailSender()
