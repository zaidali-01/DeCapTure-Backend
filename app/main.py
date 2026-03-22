from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.models import *  
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="Your API",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "API Running 🚀"}