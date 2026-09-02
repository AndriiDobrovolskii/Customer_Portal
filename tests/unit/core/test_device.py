import pytest

from app.core.device import resolve_device_label

pytestmark = pytest.mark.unit

_CHROME_WINDOWS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def test_device_label_parses_known_user_agent() -> None:
    # Act
    label = resolve_device_label(_CHROME_WINDOWS_UA)

    # Assert
    assert label == "Chrome on Windows"


def test_device_label_missing_header_returns_unknown() -> None:
    # Act
    label = resolve_device_label(None)

    # Assert
    assert label == "Unknown device"


def test_device_label_unparseable_header_returns_unknown() -> None:
    # Act
    label = resolve_device_label("not-a-real-user-agent-string")

    # Assert
    assert label == "Unknown device"
