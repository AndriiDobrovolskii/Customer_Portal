from fastapi import APIRouter, status

from app.modules.email_verification.dependencies import EmailVerificationServiceDep
from app.modules.email_verification.schemas import (
    ResendRequest,
    ResendResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/verify-email", response_model=VerifyEmailResponse, status_code=status.HTTP_200_OK)
async def verify_email(
    payload: VerifyEmailRequest, service: EmailVerificationServiceDep
) -> VerifyEmailResponse:
    return await service.verify_email(payload.token)


@router.post("/verify-email/resend", response_model=ResendResponse, status_code=status.HTTP_200_OK)
async def resend_verification(
    payload: ResendRequest, service: EmailVerificationServiceDep
) -> ResendResponse:
    return await service.resend_verification(payload.email)
