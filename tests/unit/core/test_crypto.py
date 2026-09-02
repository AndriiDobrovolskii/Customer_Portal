import base64

import pytest
from cryptography.exceptions import InvalidTag

from app.core.crypto import decrypt_mfa_secret, encrypt_mfa_secret

pytestmark = pytest.mark.unit


def test_encrypt_decrypt_mfa_secret_round_trip() -> None:
    # Arrange
    plaintext = b"a-totp-secret-value-1234"

    # Act
    ciphertext = encrypt_mfa_secret(plaintext)
    decrypted = decrypt_mfa_secret(ciphertext)

    # Assert
    assert decrypted == plaintext
    assert ciphertext != plaintext


def test_encrypt_mfa_secret_is_random_each_call() -> None:
    # Arrange
    plaintext = b"same-plaintext-both-times"

    # Act
    first = encrypt_mfa_secret(plaintext)
    second = encrypt_mfa_secret(plaintext)

    # Assert: distinct nonces produce distinct ciphertext for the same input.
    assert first != second


def test_decrypt_mfa_secret_wrong_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    from app.core.config import get_settings

    ciphertext = encrypt_mfa_secret(b"secret-under-key-one")
    get_settings.cache_clear()
    other_key = base64.urlsafe_b64encode(b"a-completely-different-32-byte-k").decode()
    monkeypatch.setenv("MFA_SECRET_ENCRYPTION_KEY", other_key)
    get_settings.cache_clear()

    # Act & Assert
    with pytest.raises(InvalidTag):
        decrypt_mfa_secret(ciphertext)

    get_settings.cache_clear()


def test_decrypt_mfa_secret_tampered_ciphertext_raises() -> None:
    # Arrange
    ciphertext = encrypt_mfa_secret(b"tamper-with-me")
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 0xFF])

    # Act & Assert
    with pytest.raises(InvalidTag):
        decrypt_mfa_secret(tampered)
