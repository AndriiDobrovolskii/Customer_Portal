import pytest

from app.core.security import hash_password, verify_password

pytestmark = pytest.mark.unit


async def test_verify_password_correct_password_returns_true() -> None:
    # Arrange
    hashed = await hash_password("Str0ng!Pass1")

    # Act
    result = await verify_password("Str0ng!Pass1", hashed)

    # Assert
    assert result is True


async def test_verify_password_wrong_password_returns_false() -> None:
    # Arrange
    hashed = await hash_password("Str0ng!Pass1")

    # Act
    result = await verify_password("WrongPassword1!", hashed)

    # Assert
    assert result is False


async def test_verify_password_garbage_hash_returns_false() -> None:
    # Act
    result = await verify_password("Str0ng!Pass1", "not-a-real-hash")

    # Assert
    assert result is False
