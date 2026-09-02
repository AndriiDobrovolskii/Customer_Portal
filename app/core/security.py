import base64
import hashlib
import hmac
import secrets
import struct
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from anyio import to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError

from app.core.config import get_settings


def _hash_password_sync(password: str) -> str:
    settings = get_settings()
    hasher = PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost_kb,
        parallelism=settings.argon2_parallelism,
    )
    return hasher.hash(password)


async def hash_password(password: str) -> str:
    return await to_thread.run_sync(_hash_password_sync, password)


def _verify_password_sync(password: str, hashed_password: str) -> bool:
    hasher = PasswordHasher()
    try:
        return hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHash):
        return False


async def verify_password(password: str, hashed_password: str) -> bool:
    return await to_thread.run_sync(_verify_password_sync, password, hashed_password)


# Not real credentials — pay comparable Argon2id verification cost only.
# Deliberately two distinct values (stored vs. attempted): hashing and
# verifying the *same* value would always return True, which doesn't match
# what a real wrong-password verification actually does.
_DUMMY_STORED_PASSWORD = "dummy-stored-value"  # noqa: S105  # pragma: allowlist secret
_DUMMY_ATTEMPT_PASSWORD = "dummy-attempt-value"  # noqa: S105  # pragma: allowlist secret
_dummy_hash_cache: str | None = None


async def verify_password_dummy() -> bool:
    """Pays the same Argon2id verification cost as `verify_password` when no
    account matched, so response timing doesn't reveal account existence
    (LI-AC3). Always returns False (the attempted value never matches the
    stored one). The dummy hash is computed lazily against current
    `settings.argon2_*` parameters on first use and cached, rather than a
    hardcoded string computed once at old parameter values, so it can never
    drift out of step with the parameters real verification actually uses.
    """
    global _dummy_hash_cache
    if _dummy_hash_cache is None:
        _dummy_hash_cache = await hash_password(_DUMMY_STORED_PASSWORD)
    return await verify_password(_DUMMY_ATTEMPT_PASSWORD, _dummy_hash_cache)


def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hex digest of a refresh token's raw value — the lookup key
    persisted in `refresh_tokens.token_hash`. Shared by both issuance
    (`generate_refresh_token`, below) and lookup of an already-issued
    token presented back later (US-2.2 logout, resolved OD-3), so the two
    call sites can never compute the hash differently.
    """
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash). The raw value is returned to the
    caller once (as the cookie); only the SHA-256 hash is ever persisted,
    matching US-2.3's Assumption #5 token design.
    """
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_refresh_token(raw_token)


class InvalidTokenError(Exception):
    """Raised when an access token fails to decode or verify.

    Deliberately a plain exception, not a ProblemError: app.core stays
    domain-free (§3), so translating this into a 401 happens in the module
    that calls decode_access_token.
    """


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    jti: uuid.UUID
    exp: datetime
    scopes: list[str]
    # US-009 FR-6/FR-7: true only while the account must complete MFA
    # enrolment before reaching any endpoint other than enroll/activate.
    mfa_enrollment_required: bool = False


def encode_access_token(
    *,
    user_id: uuid.UUID,
    jti: uuid.UUID,
    scopes: list[str],
    mfa_enrollment_required: bool = False,
) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "exp": expires_at,
        "scopes": scopes,
        "mfa_enrollment_required": mfa_enrollment_required,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm]
        )
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            jti=uuid.UUID(payload["jti"]),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            # Absent on a token minted before this story (US-3.2): defaults
            # to no scopes rather than raising InvalidTokenError, so an
            # already-issued token stays valid for identity/revocation
            # checks until it naturally expires.
            scopes=list(payload.get("scopes", [])),
            # Absent on a token minted before US-2.5: defaults to false
            # (full access), same "don't retroactively restrict an
            # already-issued token" precedent as scopes above.
            mfa_enrollment_required=bool(payload.get("mfa_enrollment_required", False)),
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError from exc


def generate_mfa_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash), same shape as
    generate_refresh_token() - the raw value is returned to the caller
    once (in the login-challenge response body), only the SHA-256 hash is
    ever persisted (as a Valkey key, per US-009 FR-3/OD resolution).
    """
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_mfa_token(raw_token)


def hash_mfa_token(raw_token: str) -> str:
    """A distinct function from hash_refresh_token, even though both are a
    SHA-256 hex digest, so the two token domains (mfa_token vs refresh
    token) can never be hashed interchangeably by a copy-paste mistake.
    """
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


_TOTP_ISSUER = "Customer Portal"
_TOTP_DIGITS = 6
_TOTP_STEP_SECONDS = 30
_TOTP_SKEW_STEPS = 1  # +-1 step (MF-AC4), no wider


def generate_totp_secret() -> bytes:
    """RFC 6238 TOTP secret - 20 random bytes (160 bits), RFC 4226's
    recommended minimum HMAC-SHA1 key length.
    """
    return secrets.token_bytes(20)


def encode_totp_secret(secret: bytes) -> str:
    """Base32, no padding - the wire format authenticator apps and this
    story's own MfaEnrollResponse.secret field both expect.
    """
    return base64.b32encode(secret).decode().rstrip("=")


def build_otpauth_uri(*, secret: bytes, account_email: str) -> str:
    """otpauth:// URI encoding the RFC 6238 params explicitly (algorithm,
    digits, period) rather than relying on a client's defaults (spec-
    review Medium finding, US-009 FR-1) - the client renders this into a
    QR code itself (OD-3), no separate image field.
    """
    encoded_secret = encode_totp_secret(secret)
    label = urllib.parse.quote(f"{_TOTP_ISSUER}:{account_email}")
    query = urllib.parse.urlencode(
        {
            "secret": encoded_secret,
            "issuer": _TOTP_ISSUER,
            "algorithm": "SHA1",
            "digits": _TOTP_DIGITS,
            "period": _TOTP_STEP_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def _hotp(secret: bytes, counter: int) -> str:
    """RFC 4226 HOTP, the primitive TOTP (RFC 6238) is built on."""
    counter_bytes = struct.pack(">Q", counter)
    digest = hmac.new(secret, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10**_TOTP_DIGITS)).zfill(_TOTP_DIGITS)


def current_totp_step(*, at: datetime | None = None) -> int:
    moment = at or datetime.now(UTC)
    return int(moment.timestamp() // _TOTP_STEP_SECONDS)


def verify_totp_code(secret: bytes, code: str, *, at: datetime | None = None) -> int | None:
    """MF-AC4: a +-1 time-step skew window is accepted, no wider. Returns
    the matched step number (for FR-4's replay-protection keying) on
    success, None on failure. Constant-time comparison per the spec's
    Non-Functional Requirements ("code comparison MUST be constant-time").
    """
    current_step = current_totp_step(at=at)
    for offset in range(-_TOTP_SKEW_STEPS, _TOTP_SKEW_STEPS + 1):
        step = current_step + offset
        expected = _hotp(secret, step)
        if hmac.compare_digest(expected, code):
            return step
    return None
