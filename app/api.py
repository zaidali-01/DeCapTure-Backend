from fastapi import FastAPI
from app.modules.Business.router import router as businesses_router
from app.modules.Communications.router import router as communications_router


def register_routes(app: FastAPI) -> None:
    app.include_router(businesses_router)
    app.include_router(communications_router)
