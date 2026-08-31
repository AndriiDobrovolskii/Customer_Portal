from pydantic import BaseModel, ConfigDict


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str | None = None


class VerifyEmailResponse(BaseModel):
    email_verified: bool


class ResendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None


class ResendResponse(BaseModel):
    message: str
