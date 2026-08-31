from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.core.dependencies import get_request_id
from app.modules.users.dependencies import (
    CurrentUserAllowRevokedDep,
    CurrentUserDep,
    UserServiceDep,
)
from app.modules.users.schemas import LoginRequest, LoginResponse, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate, service: UserServiceDep, response: Response
) -> UserRead:
    user = await service.register_user(payload)
    response.headers["Location"] = f"/api/v1/users/{user.id}"
    return user


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    service: UserServiceDep,
    response: Response,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> LoginResponse:
    login_response, raw_refresh_token = await service.authenticate_user(
        payload,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )
    # Path matches this app's actual deployed route prefix (/api/v1/auth/...,
    # per app/api/v1/router.py), not the source story's documented /v1/auth
    # — the cookie must scope to where the browser will actually send it.
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        path="/api/v1/auth",
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return login_response


@router.post("/logout", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: CurrentUserAllowRevokedDep,
    service: UserServiceDep,
    response: Response,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    await service.logout(
        jti=current_user.jti,
        user_id=current_user.user_id,
        refresh_token=refresh_token,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )
    # Cleared only when a refresh cookie was actually present on the
    # request (resolved OD-6) — path must match the cookie set by /login.
    if refresh_token is not None:
        response.delete_cookie(
            key="refresh_token",
            path="/api/v1/auth",
            httponly=True,
            secure=True,
            samesite="strict",
        )


@router.post("/logout-all", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: CurrentUserDep,
    service: UserServiceDep,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> None:
    await service.logout_all(
        user_id=current_user.user_id,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )
