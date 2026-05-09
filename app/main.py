from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.api import api_router
from app.core.database import Base, engine
from app.models import *  # noqa: F401,F403


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
        """
        CREATE TABLE IF NOT EXISTS escalation_requests (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL
                REFERENCES communication_sessions(id) ON DELETE CASCADE,
            business_id INTEGER NOT NULL
                REFERENCES businesses(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT NOW(),
            agent_user_id INTEGER REFERENCES users(id),
            resolved_at TIMESTAMP
        )
        """,
        # Employees
        """
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            designation VARCHAR(100),
            department VARCHAR(100),
            joined_date DATE,
            salary INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            status VARCHAR(20) DEFAULT 'present',
            check_in TIMESTAMP,
            check_out TIMESTAMP,
            notes TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS leave_requests (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            leave_type VARCHAR(50),
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            reason TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            applied_at TIMESTAMP DEFAULT NOW(),
            reviewed_at TIMESTAMP
        )
        """,
        # CRM
        """
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            contact_id INTEGER REFERENCES customer_contact(contact_id) ON DELETE SET NULL,
            name VARCHAR(150) NOT NULL,
            email VARCHAR(120),
            phone VARCHAR(20),
            source VARCHAR(80),
            stage VARCHAR(50) DEFAULT 'new',
            value INTEGER DEFAULT 0,
            notes TEXT,
            assigned_to INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS customer_notes (
            id SERIAL PRIMARY KEY,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            contact_id INTEGER NOT NULL
                REFERENCES customer_contact(contact_id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS follow_ups (
            id SERIAL PRIMARY KEY,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
            contact_id INTEGER REFERENCES customer_contact(contact_id) ON DELETE SET NULL,
            assigned_to INTEGER NOT NULL REFERENCES users(id),
            title VARCHAR(200) NOT NULL,
            due_date DATE NOT NULL,
            is_done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS product_categories (
            id SERIAL PRIMARY KEY,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        ALTER TABLE product_inventory
        ADD COLUMN IF NOT EXISTS category_id INTEGER
        REFERENCES product_categories(id) ON DELETE SET NULL
        """,
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name VARCHAR(150) NOT NULL,
            email VARCHAR(120),
            phone VARCHAR(20),
            address TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id SERIAL PRIMARY KEY,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            created_by INTEGER NOT NULL REFERENCES users(id),
            status VARCHAR(30) DEFAULT 'pending',
            order_date DATE NOT NULL,
            expected_date DATE,
            received_date DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id SERIAL PRIMARY KEY,
            purchase_order_id INTEGER NOT NULL
                REFERENCES purchase_orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES product_inventory(id) ON DELETE SET NULL,
            product_name VARCHAR(150) NOT NULL,
            quantity_ordered INTEGER NOT NULL,
            quantity_received INTEGER DEFAULT 0,
            unit_cost NUMERIC(12,2) NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            type VARCHAR(60) NOT NULL,
            title VARCHAR(200) NOT NULL,
            body TEXT,
            is_read BOOLEAN DEFAULT FALSE,
            entity_type VARCHAR(60),
            entity_id INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            business_id INTEGER REFERENCES businesses(id) ON DELETE SET NULL,
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(60),
            entity_id INTEGER,
            detail JSONB,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS loyalty_accounts (
            id SERIAL PRIMARY KEY,
            contact_id INTEGER NOT NULL UNIQUE
                REFERENCES customer_contact(contact_id) ON DELETE CASCADE,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            points INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_redeemed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS loyalty_transactions (
            id SERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL
                REFERENCES loyalty_accounts(id) ON DELETE CASCADE,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            type VARCHAR(20) NOT NULL,
            points INTEGER NOT NULL,
            reference VARCHAR(100),
            note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS kpi_targets (
            id SERIAL PRIMARY KEY,
            business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            revenue_target NUMERIC(14,2) DEFAULT 0,
            sales_target INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
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


allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]

app = FastAPI(title="DeCapTure API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

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
