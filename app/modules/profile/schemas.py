import uuid
import zoneinfo
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator


# Placeholder set pending product confirmation — no authoritative locale list
# exists anywhere in this codebase or its docs yet.
class SupportedLocale(StrEnum):
    EN_US = "en-US"
    EN_GB = "en-GB"


_VALID_TIMEZONES = zoneinfo.available_timezones()


class ProfileUpdate(BaseModel):
    """Note: `current_password` is only valid alongside `email`. That is a
    cross-field policy rule, not a syntactic one, so per AGENTS.md §4
    ("Structured multi-field validation") it is checked in the service, not
    here — a schema-level model_validator can't attach the failure to the
    `current_password` field, only to the model as a whole.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    locale: SupportedLocale | None = None
    timezone: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    current_password: SecretStr | None = None

    @field_validator("timezone")
    @classmethod
    def _timezone_must_be_a_known_iana_name(cls, value: str | None) -> str | None:
        if value is not None and value not in _VALID_TIMEZONES:
            msg = f"'{value}' is not a recognized IANA timezone name"
            raise ValueError(msg)
        return value


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    pending_email: str | None
    display_name: str | None
    locale: str | None
    timezone: str | None
    avatar_url: str | None
    email_verified: bool
    created_at: datetime


class ConfirmEmailChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str | None = None


class ConfirmEmailChangeResponse(BaseModel):
    email: str
