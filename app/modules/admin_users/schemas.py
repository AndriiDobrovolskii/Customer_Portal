import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    """Shared item shape for list entries, single-fetch, create/update/
    deactivate responses (US-011-openapi.yaml `UserRead`). No password
    hash, token, or credential material, per FR-1/NFR-012.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    status: str
    roles: list[str]
    created_at: datetime
    last_login_at: datetime | None


class UserListResponse(BaseModel):
    items: list[UserRead]
    next_cursor: str | None = None


class CreateUserRequest(BaseModel):
    """No `password` property by design (FR-7): any request body containing
    one is rejected as an unknown field by `extra="forbid"`, with no
    separate check needed.
    """

    model_config = ConfigDict(extra="forbid")

    email: str
    display_name: str
    roles: list[str]


class UpdateUserRequest(BaseModel):
    """Editable whitelist reused from US-1.3's `ProfileUpdate` shape, minus
    `email`/`current_password` (email change is out of scope for this
    endpoint). `id`, `created_at`, `email_verified`, and `roles` are
    deliberately not declared here; the service checks the raw request
    body for them before this schema validates, so they resolve to
    `immutable-field` rather than `validation-failed` (mirrors
    `app/modules/profile/service.py`'s `_IMMUTABLE_FIELD_NAMES` check).
    `reason` is required per FR-9/OD-1 — every changed field's
    `admin_audit_log` row must carry one.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    locale: str | None = None
    timezone: str | None = None
    avatar_url: str | None = None
    reason: str = Field(min_length=1)


# The whitelist `UpdateUserRequest` represents — the only fields
# `update_user` may write, applied via `model_dump(exclude_unset=True)`.
# `reason` is excluded: it drives the audit-log write, not a `users`
# column.
ADMIN_USER_EDITABLE_FIELD_NAMES = frozenset({"display_name", "locale", "timezone", "avatar_url"})

# Checked against the raw request body before Pydantic validation so a
# submission naming one of these resolves to `immutable-field`, not the
# generic `validation-failed` an undeclared field (e.g. `email`) gets.
ADMIN_USER_IMMUTABLE_FIELD_NAMES = frozenset({"id", "created_at", "email_verified", "roles"})


class DeactivateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)


class ResendInviteResponse(BaseModel):
    """Generic body per FR-18/MU-AC18 — no fields specified by the story
    beyond "a generic body".
    """
