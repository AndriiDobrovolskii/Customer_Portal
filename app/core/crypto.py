import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

# 96-bit nonce: the AES-GCM standard/recommended size (NIST SP 800-38D).
_NONCE_SIZE_BYTES = 12


def _load_key() -> bytes:
    settings = get_settings()
    return base64.urlsafe_b64decode(settings.mfa_secret_encryption_key.get_secret_value())


def encrypt_mfa_secret(plaintext: bytes) -> bytes:
    """OD-2: envelope encryption stand-in for the TOTP secret - AES-GCM
    with a key from settings, documented as a dev-only stand-in for a
    real KMS-managed key in production. Returns `nonce || ciphertext`
    (the ciphertext already includes the GCM authentication tag), so
    `decrypt_mfa_secret` needs no separately-stored state.
    """
    key = _load_key()
    nonce = os.urandom(_NONCE_SIZE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_mfa_secret(ciphertext: bytes) -> bytes:
    """Raises `cryptography.exceptions.InvalidTag` if the key is wrong or
    the ciphertext was tampered with (AES-GCM authenticates as well as
    encrypts) - the caller never needs to distinguish "wrong key" from
    "corrupted data", both are equally a hard failure.
    """
    key = _load_key()
    nonce, actual_ciphertext = ciphertext[:_NONCE_SIZE_BYTES], ciphertext[_NONCE_SIZE_BYTES:]
    return AESGCM(key).decrypt(nonce, actual_ciphertext, None)
