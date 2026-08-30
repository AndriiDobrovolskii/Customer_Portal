from fastapi import APIRouter, status

from app.modules.account.dependencies import AccountServiceDep
from app.modules.account.schemas import DeactivateAccountRequest, DeactivateAccountResponse
from app.modules.users.dependencies import CurrentUserDep

router = APIRouter(prefix="/account", tags=["account"])


@router.post(
    "/deactivate", response_model=DeactivateAccountResponse, status_code=status.HTTP_200_OK
)
async def deactivate_account(
    payload: DeactivateAccountRequest,
    current_user: CurrentUserDep,
    service: AccountServiceDep,
) -> DeactivateAccountResponse:
    return await service.deactivate_account(user_id=current_user.user_id, payload=payload)
