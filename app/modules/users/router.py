import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.core.dependencies import get_request_id
from app.modules.users.dependencies import (
    CurrentUserAllowEnrollmentScopedDep,
    CurrentUserAllowRevokedDep,
    CurrentUserDep,
    UserServiceDep,
)
from app.modules.users.schemas import (
    LoginRequest,
    LoginResponse,
    MfaActivateRequest,
    MfaActivateResponse,
    MfaDisableRequest,
    MfaEnrollRequest,
    MfaEnrollResponse,
    MfaRequiredResponse,
    MfaVerifyRequest,
    MfaVerifyResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    PasswordResetRequestResponse,
    RefreshResponse,
    SessionListResponse,
    UserCreate,
    UserRead,
)

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


@router.post(
    "/login", response_model=LoginResponse | MfaRequiredResponse, status_code=status.HTTP_200_OK
)
async def login(
    payload: LoginRequest,
    service: UserServiceDep,
    response: Response,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> LoginResponse | MfaRequiredResponse:
    login_response, raw_refresh_token = await service.authenticate_user(
        payload,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )
    # US-009 MF-AC3: no refresh token is issued on the MFA-challenge branch
    # (raw_refresh_token is None), so no cookie is set - the client must
    # call /mfa/verify to actually complete the login.
    if raw_refresh_token is not None:
        # Path matches this app's actual deployed route prefix
        # (/api/v1/auth/..., per app/api/v1/router.py), not the source
        # story's documented /v1/auth — the cookie must scope to where the
        # browser will actually send it.
        response.set_cookie(
            key="refresh_token",
            value=raw_refresh_token,
            path="/api/v1/auth",
            httponly=True,
            secure=True,
            samesite="strict",
        )
    return login_response


@router.post("/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    service: UserServiceDep,
    response: Response,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
    refresh_token_cookie: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> RefreshResponse:
    refresh_response, raw_refresh_token = await service.rotate_refresh_token(
        refresh_token_cookie,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )
    # Same cookie attributes login's own Set-Cookie already uses (see the
    # comment there) — this endpoint's sole credential is this cookie, not
    # a Bearer token, so there is no CurrentUserDep on this route.
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        path="/api/v1/auth",
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return refresh_response


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


@router.get("/sessions", response_model=SessionListResponse, status_code=status.HTTP_200_OK)
async def list_sessions(
    current_user: CurrentUserDep,
    service: UserServiceDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> SessionListResponse:
    return await service.list_sessions(user_id=current_user.user_id, refresh_cookie=refresh_token)


@router.delete("/sessions/{family_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    family_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: UserServiceDep,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    await service.revoke_session(
        user_id=current_user.user_id,
        family_id=family_id,
        refresh_cookie=refresh_token,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    payload: PasswordResetRequestRequest,
    service: UserServiceDep,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> PasswordResetRequestResponse:
    return await service.request_password_reset(
        payload,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )


@router.post("/mfa/enroll", response_model=MfaEnrollResponse, status_code=status.HTTP_200_OK)
async def enroll_mfa(
    payload: MfaEnrollRequest,
    current_user: CurrentUserAllowEnrollmentScopedDep,
    service: UserServiceDep,
) -> MfaEnrollResponse:
    return await service.enroll_mfa(current_user.user_id, payload)


@router.post("/mfa/activate", response_model=MfaActivateResponse, status_code=status.HTTP_200_OK)
async def activate_mfa(
    payload: MfaActivateRequest,
    current_user: CurrentUserAllowEnrollmentScopedDep,
    service: UserServiceDep,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> MfaActivateResponse:
    return await service.activate_mfa(
        current_user.user_id,
        payload,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )


@router.post("/mfa/verify", response_model=MfaVerifyResponse, status_code=status.HTTP_200_OK)
async def verify_mfa(
    payload: MfaVerifyRequest,
    service: UserServiceDep,
    response: Response,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> MfaVerifyResponse:
    # No CurrentUserDep: the credential for this endpoint is the mfa_token
    # in the request body (FR-3), not a bearer access token — same shape as
    # password-reset/confirm's body-carried token, not a security scheme.
    verify_response, raw_refresh_token = await service.verify_mfa(
        payload,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )
    # Same cookie attributes /login and /refresh already use (MF-AC3:
    # "completes the login exactly as LI-AC1").
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        path="/api/v1/auth",
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return verify_response


@router.delete("/mfa", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    payload: MfaDisableRequest,
    current_user: CurrentUserDep,
    service: UserServiceDep,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> None:
    await service.disable_mfa(
        current_user.user_id,
        payload,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )


@router.post("/password-reset/confirm", response_model=None, status_code=status.HTTP_200_OK)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    service: UserServiceDep,
    request: Request,
    request_id: Annotated[str, Depends(get_request_id)],
) -> Response:
    await service.confirm_password_reset(
        payload,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
    )
    # A bare `-> None` return still serializes to a literal `"null"` JSON
    # body at 200 (unlike 204, which FastAPI always sends bodiless
    # regardless of the return value) — the source story's Success column
    # states 200 with no response schema, so this returns a genuinely empty
    # body explicitly rather than relying on that.
    return Response(status_code=status.HTTP_200_OK)
