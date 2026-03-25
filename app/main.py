from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.core.database import engine, Base
from app.models import *
from app.api import register_routes


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


async def apply_startup_schema_fixes() -> None:
    # create_all() will not alter existing tables, so patch known missing columns.
    statements = [
        """
        ALTER TABLE IF EXISTS business_documents
        ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE IF EXISTS communication_messages
        ADD COLUMN IF NOT EXISTS sources JSON
        """,
    ]

    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_startup_schema_fixes()
    yield


app = FastAPI(title="DeCapTure API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app)


@app.get("/health")
async def health():
    db_ok = False
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
    }


@app.get("/health/routes")
async def health_routes():
    routes = []
    for route in app.routes:
        methods = sorted(list(getattr(route, "methods", []) - {"HEAD", "OPTIONS"}))
        if not methods:
            continue
        routes.append(
            {
                "path": route.path,
                "methods": methods,
                "name": route.name,
            }
        )

    return {
        "count": len(routes),
        "routes": sorted(routes, key=lambda item: item["path"]),
    }


@app.get("/customer", include_in_schema=False)
async def customer_page():
    return FileResponse(FRONTEND_DIR / "customer.html")


@app.get("/owner", include_in_schema=False)
async def owner_page():
    return FileResponse(FRONTEND_DIR / "owner.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/")
async def root():
    return {"message": "API Running 🚀"}
