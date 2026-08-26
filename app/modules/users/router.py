from fastapi import APIRouter, Response, status

from app.modules.users.dependencies import UserServiceDep
from app.modules.users.schemas import UserCreate, UserRead

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate, service: UserServiceDep, response: Response
) -> UserRead:
    user = await service.register_user(payload)
    response.headers["Location"] = f"/v1/users/{user.id}"
    return user
