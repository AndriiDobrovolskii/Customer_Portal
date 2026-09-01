import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_verification_email(self, *, to: str, raw_token: str) -> None: ...

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None: ...

    async def send_email_change_notice(self, *, to: str) -> None: ...

    async def send_refresh_reuse_alert(self, *, to: str) -> None: ...


class LoggingEmailSender:
    """No-op sender that logs dispatch without a real mail provider.

    Never logs `to` or `raw_token` — the raw token is a bearer credential and
    must never appear in application logs.
    """

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        logger.info("verification email dispatched")

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None:
        logger.info("email change confirmation dispatched")

    async def send_email_change_notice(self, *, to: str) -> None:
        logger.info("email change notice dispatched")

    async def send_refresh_reuse_alert(self, *, to: str) -> None:
        logger.info("refresh reuse alert dispatched")


def get_email_sender() -> EmailSender:
    return LoggingEmailSender()
