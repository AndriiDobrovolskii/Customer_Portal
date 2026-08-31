from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Response, status
from pydantic import JsonValue

from app.core.dependencies import get_request_id
from app.modules.profile.dependencies import ProfileServiceDep
from app.modules.profile.schemas import (
    ConfirmEmailChangeRequest,
    ConfirmEmailChangeResponse,
    ProfileRead,
    ProfileUpdate,
)
from app.modules.users.dependencies import CurrentUserDep

router = APIRouter(prefix="/profile", tags=["profile"])


@router.patch(
    "",
    response_model=ProfileRead,
    status_code=status.HTTP_200_OK,
    responses={202: {"model": ProfileRead, "description": "Email change initiated"}},
    openapi_extra={
        "requestBody": {
            "content": {"application/json": {"schema": ProfileUpdate.model_json_schema()}}
        }
    },
)
async def update_profile(
    response: Response,
    current_user: CurrentUserDep,
    service: ProfileServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
    body: Annotated[dict[str, JsonValue], Body()],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ProfileRead:
    profile, etag, email_change_initiated = await service.apply_partial_update(
        user_id=current_user.user_id, raw_body=body, if_match=if_match, request_id=request_id
    )
    if email_change_initiated:
        response.status_code = status.HTTP_202_ACCEPTED
    else:
        response.headers["ETag"] = etag
    return profile


@router.post(
    "/confirm-email-change",
    response_model=ConfirmEmailChangeResponse,
    status_code=status.HTTP_200_OK,
)
async def confirm_email_change(
    payload: ConfirmEmailChangeRequest,
    service: ProfileServiceDep,
    request_id: Annotated[str, Depends(get_request_id)],
    authorization: Annotated[str | None, Header()] = None,
) -> ConfirmEmailChangeResponse:
    return await service.confirm_email_change(
        raw_token=payload.token, authorization=authorization, request_id=request_id
    )
