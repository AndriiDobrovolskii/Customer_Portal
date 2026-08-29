import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    decode_access_token,
    encode_access_token,
    hash_password,
    verify_password,
)

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


def test_encode_decode_access_token_round_trip() -> None:
    # Arrange
    user_id = uuid.uuid4()
    jti = uuid.uuid4()

    # Act
    token = encode_access_token(user_id=user_id, jti=jti)
    claims = decode_access_token(token)

    # Assert
    assert claims.user_id == user_id
    assert claims.jti == jti


def test_decode_access_token_tampered_signature_raises_invalid_token() -> None:
    # Arrange
    token = encode_access_token(user_id=uuid.uuid4(), jti=uuid.uuid4())
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    # Act & Assert
    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)


def test_decode_access_token_expired_raises_invalid_token() -> None:
    # Arrange
    settings = get_settings()
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(UTC) - timedelta(seconds=1),
    }
    token = jwt.encode(
        expired_payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    # Act & Assert
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_access_token_malformed_raises_invalid_token() -> None:
    # Act & Assert
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt-at-all")
