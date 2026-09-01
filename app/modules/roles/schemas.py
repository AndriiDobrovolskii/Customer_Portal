from pydantic import BaseModel, ConfigDict


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    permissions: list[str]


class RoleCatalogueResponse(BaseModel):
    roles: list[RoleSummary]


class ReplaceUserRolesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str]


class ReplaceUserRolesResponse(BaseModel):
    roles: list[str]
