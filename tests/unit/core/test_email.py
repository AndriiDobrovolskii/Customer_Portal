import logging

import pytest

from app.core.email import LoggingEmailSender, get_email_sender

pytestmark = pytest.mark.unit


async def test_logging_email_sender_never_logs_token_or_address(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    sender = LoggingEmailSender()

    # Act
    with caplog.at_level(logging.INFO):
        await sender.send_verification_email(to="user@example.com", raw_token="super-secret-token")

    # Assert
    assert "super-secret-token" not in caplog.text
    assert "user@example.com" not in caplog.text


def test_get_email_sender_returns_logging_email_sender() -> None:
    # Act
    sender = get_email_sender()

    # Assert
    assert isinstance(sender, LoggingEmailSender)
