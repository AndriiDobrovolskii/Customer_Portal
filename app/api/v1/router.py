from fastapi import APIRouter

from app.modules.account.router import router as account_router
from app.modules.email_verification.router import router as email_verification_router
from app.modules.profile.router import router as profile_router
from app.modules.users.router import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(users_router)
router.include_router(email_verification_router)
router.include_router(profile_router)
router.include_router(account_router)
