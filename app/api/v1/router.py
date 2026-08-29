from fastapi import APIRouter

from app.modules.users.router import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(users_router)
