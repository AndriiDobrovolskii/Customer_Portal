import pytest

from app.core.config import Settings

pytestmark = pytest.mark.unit


def test_settings_default_verification_and_purge_values() -> None:
    # Arrange & Act
    settings = Settings()

    # Assert
    assert settings.verification_token_ttl_hours == 24
    assert settings.resend_cooldown_seconds == 60
    assert settings.unverified_account_purge_after_days == 7
