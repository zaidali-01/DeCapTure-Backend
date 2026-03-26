from fastapi import FastAPI
from app.modules.Business.router import router as businesses_router
from app.modules.Communications.router import router as communications_router


def register_routes(app: FastAPI) -> None:
    app.include_router(businesses_router)
    app.include_router(communications_router)
    app.include_router(chatbot_router, prefix="/api/v1")
    # app.include_router(pos_router, prefix="/api/v1")
from fastapi import APIRouter

from app.modules.Users.router import router as users_router
from app.modules.Business.router import router as business_router
from app.modules.POS.router import router as pos_router
from app.modules.Marketing.router import router as marketing_router

api_router = APIRouter()

api_router.include_router(users_router)
api_router.include_router(business_router)
api_router.include_router(pos_router)
api_router.include_router(marketing_router)
