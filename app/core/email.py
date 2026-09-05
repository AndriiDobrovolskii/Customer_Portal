import logging
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_verification_email(self, *, to: str, raw_token: str) -> None: ...

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None: ...

    async def send_email_change_notice(self, *, to: str) -> None: ...

    async def send_refresh_reuse_alert(self, *, to: str) -> None: ...

    async def send_password_reset_email(self, *, to: str, raw_token: str) -> None: ...

    async def send_password_reset_notice(self, *, to: str) -> None: ...

    async def send_mfa_recovery_used_notice(self, *, to: str) -> None: ...

    async def send_invitation_email(self, *, to: str, raw_token: str) -> None: ...

    async def send_ticket_created_email(self, *, to: str, ticket_number: str) -> None: ...

    async def send_ticket_reply_notification(self, *, to: str, ticket_number: str) -> None: ...

    async def send_ticket_reply_queue_notification(self, *, ticket_number: str) -> None: ...


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

    async def send_password_reset_email(self, *, to: str, raw_token: str) -> None:
        logger.info("password reset email dispatched")

    async def send_password_reset_notice(self, *, to: str) -> None:
        logger.info("password reset notice dispatched")

    async def send_mfa_recovery_used_notice(self, *, to: str) -> None:
        logger.info("mfa recovery-code-used notice dispatched")

    async def send_invitation_email(self, *, to: str, raw_token: str) -> None:
        logger.info("invitation email dispatched")

    async def send_ticket_created_email(self, *, to: str, ticket_number: str) -> None:
        logger.info("ticket created email dispatched")

    async def send_ticket_reply_notification(self, *, to: str, ticket_number: str) -> None:
        logger.info("ticket reply notification dispatched")

    async def send_ticket_reply_queue_notification(self, *, ticket_number: str) -> None:
        # No `to` parameter — the recipient is the fixed support-queue
        # address (Resolution OD-2), read from settings here rather than
        # passed by the caller, so the service does not need to know it
        # just to ask for the queue to be notified (implementation-plan
        # Architectural Change #8). Not user PII, so logging it (unlike
        # `to` above) does not violate this class's own discipline.
        logger.info(
            "ticket reply queue notification dispatched to %s",
            get_settings().support_queue_email,
        )


def get_email_sender() -> EmailSender:
    return LoggingEmailSender()
