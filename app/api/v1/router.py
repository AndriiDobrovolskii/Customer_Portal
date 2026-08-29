from fastapi import APIRouter

from app.modules.email_verification.router import router as email_verification_router
from app.modules.users.router import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(users_router)
router.include_router(email_verification_router)
