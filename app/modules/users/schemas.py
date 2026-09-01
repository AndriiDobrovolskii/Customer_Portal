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


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


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
