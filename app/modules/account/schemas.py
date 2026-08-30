from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, SecretStr


class DeactivateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr | None = None


class DeactivationStatus(StrEnum):
    DEACTIVATED = "deactivated"


class DeactivateAccountResponse(BaseModel):
    status: DeactivationStatus
    deactivated_at: datetime
