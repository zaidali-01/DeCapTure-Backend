from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.models import *          # ensures all models are registered with Base
from app.api import register_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Your API",
    version="1.0.0",
    lifespan=lifespan,
)

register_routes(app)


@app.get("/")
async def root():
    return {"message": "API Running 🚀"}