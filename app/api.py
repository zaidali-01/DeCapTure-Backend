from fastapi import APIRouter

from app.modules.Users.router import router as users_router
from app.modules.Business.router import router as business_router
from app.modules.POS.router import router as pos_router

api_router = APIRouter()

api_router.include_router(users_router)
api_router.include_router(business_router)
api_router.include_router(pos_router)