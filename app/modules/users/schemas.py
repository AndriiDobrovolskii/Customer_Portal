import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class UserStatus(StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    password: SecretStr | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    status: UserStatus
    created_at: datetime = Field(serialization_alias="createdAt")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: SecretStr = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 -- OAuth2 field name, not a secret
    expires_in: int
    # FR-6/OD-4: only present while the account is a privileged role within
    # its 14-day MFA-enrolment grace period. Absent (None) otherwise -
    # never a synthetic/past date for a non-grace-period login.
    mfa_enrollment_deadline: datetime | None = None


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int
    mfa_enrollment_deadline: datetime | None = None


class MfaRequiredResponse(BaseModel):
    """FR-3 login-challenge branch - the alternate 200 body POST
    /v1/auth/login returns instead of LoginResponse when mfa_enabled is
    true. No access/refresh token is issued at this point.
    """

    mfa_required: Literal[True] = True
    mfa_token: str


class PasswordResetRequestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


class PasswordResetRequestResponse(BaseModel):
    message: Literal["If an account exists, an email has been sent"] = (
        "If an account exists, an email has been sent"
    )


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    # Deliberately no min_length here (AGENTS.md §4.4.5): PR-AC5 requires
    # short/breached/reused to all surface through one unified
    # PasswordPolicyError (`password-policy` slug, one `errors` entry per
    # failed rule) — a schema-level length constraint would short-circuit
    # before the other two checks ever run and produce a different error
    # shape entirely (FastAPI's generic validation-failed envelope).
    new_password: SecretStr


class MfaEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr = Field(min_length=1)


class MfaEnrollResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^\d{6}$")


class MfaActivateResponse(BaseModel):
    recovery_codes: list[str]


class MfaVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mfa_token: str
    # No pattern constraint (unlike MfaActivateRequest.code): FR-7 accepts
    # either a 6-digit TOTP code or a recovery code (a different, longer
    # format) in this same field - a 6-digit pattern here would reject
    # every valid recovery code before the service layer ever sees it.
    code: str = Field(min_length=1)


class MfaVerifyResponse(BaseModel):
    """Identical shape to LoginResponse, per FR-3 (MF-AC3: "completes the
    login exactly as LI-AC1"). A separate class, not a reused import,
    since the two responses are independently derived from their own ACs
    and may diverge later without one silently changing the other.
    """

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 -- OAuth2 field name, not a secret
    expires_in: int


class MfaDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr = Field(min_length=1)
    # A 6-digit TOTP code only - whether a recovery code is also accepted
    # here is an open question (US-2.5-api-design.md Open Questions #2),
    # not decided by this schema.
    code: str = Field(pattern=r"^\d{6}$")


class SessionLocation(BaseModel):
    city: str | None = None
    country: str | None = None


class SessionEntry(BaseModel):
    """FR-1: one live refresh-token family. Composed by the service from a
    repository row plus the geo-IP/device-label lookups (US-2.6-db-design.md
    - "current-state row" + "created_at" per family) - not a direct
    `from_attributes` passthrough of any single ORM row, so no ConfigDict
    is set here.
    """

    family_id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    location: SessionLocation | None
    device_label: str
    is_current: bool


class SessionListResponse(BaseModel):
    sessions: list[SessionEntry]
