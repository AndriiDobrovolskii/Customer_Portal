import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class UserStatus(StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    password: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    status: UserStatus
    created_at: datetime = Field(serialization_alias="createdAt")
