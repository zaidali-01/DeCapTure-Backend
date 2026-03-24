from fastapi import FastAPI
from app.modules.Communications.router import router as chatbot_router

# Import other module routers here as you build them out, e.g.:
# from app.modules.POS.router import router as pos_router

def register_routes(app: FastAPI) -> None:
    app.include_router(chatbot_router, prefix="/api/v1")
    # app.include_router(pos_router, prefix="/api/v1")