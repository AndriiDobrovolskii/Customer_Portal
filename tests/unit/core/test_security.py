import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

import app.core.security as security
from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    decode_access_token,
    encode_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
    verify_password_dummy,
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
    token = encode_access_token(user_id=user_id, jti=jti, scopes=["users:read"])
    claims = decode_access_token(token)

    # Assert
    assert claims.user_id == user_id
    assert claims.jti == jti
    assert claims.scopes == ["users:read"]


def test_decode_access_token_missing_scopes_claim_defaults_empty() -> None:
    # Arrange: a token minted before US-3.2, with no "scopes" key at all.
    settings = get_settings()
    payload = {
        "sub": str(uuid.uuid4()),
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(UTC) + timedelta(seconds=60),
    }
    token = jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )

    # Act
    claims = decode_access_token(token)

    # Assert
    assert claims.scopes == []


def test_decode_access_token_tampered_signature_raises_invalid_token() -> None:
    # Arrange: flip a character in the middle of the signature, not the
    # very last one — the final base64 character of a 32-byte HMAC-SHA256
    # signature only carries 4 significant bits (2-byte tail group), so
    # some character pairs there decode to the same effective byte value
    # and the corruption is silently absorbed, making a last-char flip
    # occasionally (and non-deterministically) fail to actually tamper
    # the signature.
    token = encode_access_token(user_id=uuid.uuid4(), jti=uuid.uuid4(), scopes=[])
    signature_start = token.rindex(".") + 1
    flip_index = signature_start + (len(token) - signature_start) // 2
    flipped_char = "a" if token[flip_index] != "a" else "b"
    tampered = token[:flip_index] + flipped_char + token[flip_index + 1 :]

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


# --- LI-AC3: dummy verification for anti-enumeration timing parity --------


async def test_dummy_verify_password_comparable_cost_to_real_verification() -> None:
    # Arrange — reset the module-level cache so this test observes the real
    # first-call hashing path, not a value left over from another test.
    security._dummy_hash_cache = None

    # Act
    result = await verify_password_dummy()

    # Assert: never matches (it's not a real credential), and the cost is
    # comparable to a real verification because it went through the exact
    # same Argon2id hash-then-verify path — not a shortcut/no-op. Asserting
    # a real argon2id-shaped hash was produced and cached proves this
    # structurally, without a flaky wall-clock timing threshold (AGENTS.md
    # §5 forbids non-deterministic time-dependent assertions).
    assert result is False
    assert security._dummy_hash_cache is not None
    assert security._dummy_hash_cache.startswith("$argon2id$")


async def test_dummy_verify_password_reuses_cached_hash_across_calls() -> None:
    # Arrange
    security._dummy_hash_cache = None
    await verify_password_dummy()
    cached_after_first_call = security._dummy_hash_cache

    # Act
    await verify_password_dummy()

    # Assert: the dummy hash is computed once and reused, not re-hashed on
    # every call — only the (fast) verify step repeats per call.
    assert security._dummy_hash_cache == cached_after_first_call


# --- Resolved OD-9: refresh-token raw value + hash generation -------------


def test_generate_refresh_token_returns_distinct_raw_and_hash() -> None:
    # Act
    raw_token, token_hash = generate_refresh_token()

    # Assert
    assert raw_token != token_hash
    assert len(raw_token) > 0
    assert len(token_hash) == 64  # SHA-256 hex digest length
    assert token_hash == hashlib.sha256(raw_token.encode("ascii")).hexdigest()


def test_generate_refresh_token_is_random_each_call() -> None:
    # Act
    first_raw, first_hash = generate_refresh_token()
    second_raw, second_hash = generate_refresh_token()

    # Assert
    assert first_raw != second_raw
    assert first_hash != second_hash
