import csv
import io
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticBase
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.accounts import DailyAccounts
from app.models.contact import CustomerContact
from app.models.crm import Lead
from app.models.employee import Employee
from app.models.inventory import ProductInventory
from app.models.kpi import KPITarget
from app.models.sales import SalesInventoryBridge
from app.models.user import User
from app.modules.Analytics.insights import forecast_revenue, generate_insights
from app.modules.Business.service import get_user_businesses
from app.modules.Users.service import get_current_user, has_role

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class KPICreate(PydanticBase):
    year: int
    month: int
    revenue_target: float
    sales_target: int


async def resolve_business(current_user, db, business_id):
    data = await get_user_businesses(db, current_user.id)
    businesses = data.get("businesses", []) if isinstance(data, dict) else data or []
    if not businesses:
        raise HTTPException(status_code=400, detail="No business found")
    if business_id:
        if any(b.id == business_id for b in businesses):
            return business_id
        raise HTTPException(status_code=404, detail="Business not found")
    return businesses[0].id


@router.get("/dashboard")
async def dashboard(
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Single endpoint that returns everything the frontend dashboard needs.
    All queries run in parallel conceptually - written as sequential awaits.
    """
    business_id = await resolve_business(current_user, db, business_id)

    today = date.today()
    month_start = date(today.year, today.month, 1)

    today_result = await db.execute(
        select(DailyAccounts).where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date == today,
        )
    )
    today_rec = today_result.scalar_one_or_none()
    today_revenue = float(today_rec.revenue or 0) if today_rec else 0.0
    today_sales = int(today_rec.sales or 0) if today_rec else 0

    month_result = await db.execute(
        select(
            func.coalesce(func.sum(DailyAccounts.revenue), 0).label(
                "monthly_revenue"
            ),
            (
                func.coalesce(func.sum(DailyAccounts.cost), 0)
                + func.coalesce(func.sum(DailyAccounts.salary_cost), 0)
                + func.coalesce(func.sum(DailyAccounts.operational_cost), 0)
                + func.coalesce(func.sum(DailyAccounts.miscellaneous), 0)
            ).label("monthly_expenses"),
            func.coalesce(func.sum(DailyAccounts.sales), 0).label("monthly_sales"),
        ).where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date >= month_start,
            DailyAccounts.date <= today,
        )
    )
    month_row = month_result.one()
    monthly_revenue = float(month_row.monthly_revenue)
    monthly_expenses = float(month_row.monthly_expenses)
    monthly_sales = int(month_row.monthly_sales)

    inv_result = await db.execute(
        select(func.count(ProductInventory.id)).where(
            ProductInventory.business_id == business_id
        )
    )
    total_products = inv_result.scalar() or 0

    low_stock_result = await db.execute(
        select(ProductInventory).where(
            ProductInventory.business_id == business_id,
            ProductInventory.quantity <= 5,
        )
    )
    low_stock_items = [
        {"id": p.id, "name": p.name, "quantity": p.quantity}
        for p in low_stock_result.scalars().all()
    ]

    lead_result = await db.execute(
        select(Lead.stage, func.count(Lead.id))
        .where(Lead.business_id == business_id)
        .group_by(Lead.stage)
    )
    leads_by_stage = {row[0]: row[1] for row in lead_result.all()}

    cust_result = await db.execute(
        select(func.count(CustomerContact.contact_id)).where(
            CustomerContact.business_id == business_id
        )
    )
    total_customers = cust_result.scalar() or 0

    emp_result = await db.execute(
        select(func.count(Employee.id)).where(
            Employee.business_id == business_id,
            Employee.is_active == True,
        )
    )
    total_employees = emp_result.scalar() or 0

    seven_days_ago = today - timedelta(days=6)
    trend_result = await db.execute(
        select(DailyAccounts.date, DailyAccounts.revenue, DailyAccounts.sales)
        .where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date >= seven_days_ago,
        )
        .order_by(DailyAccounts.date.asc())
    )
    trend = [
        {
            "date": str(r.date),
            "revenue": float(r.revenue or 0),
            "sales": int(r.sales or 0),
        }
        for r in trend_result.all()
    ]

    return {
        "today": {
            "revenue": today_revenue,
            "sales": today_sales,
        },
        "this_month": {
            "revenue": monthly_revenue,
            "expenses": monthly_expenses,
            "profit": monthly_revenue - monthly_expenses,
            "sales": monthly_sales,
        },
        "inventory": {
            "total_products": total_products,
            "low_stock_count": len(low_stock_items),
            "low_stock_items": low_stock_items,
        },
        "crm": {
            "leads_by_stage": leads_by_stage,
            "total_customers": total_customers,
        },
        "employees": {
            "active_count": total_employees,
        },
        "revenue_trend_7d": trend,
    }


@router.get("/top-products")
async def top_products(
    business_id: Optional[int] = Query(None),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Top N products by total quantity sold."""
    business_id = await resolve_business(current_user, db, business_id)
    result = await db.execute(
        select(
            ProductInventory.id,
            ProductInventory.name,
            ProductInventory.price,
            func.coalesce(func.sum(SalesInventoryBridge.quantity), 0).label(
                "total_sold"
            ),
        )
        .join(
            SalesInventoryBridge,
            SalesInventoryBridge.listing_id == ProductInventory.id,
            isouter=True,
        )
        .where(ProductInventory.business_id == business_id)
        .group_by(ProductInventory.id, ProductInventory.name, ProductInventory.price)
        .order_by(func.sum(SalesInventoryBridge.quantity).desc().nullslast())
        .limit(limit)
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "price": float(r.price or 0),
            "total_sold": int(r.total_sold),
        }
        for r in result.all()
    ]


@router.get("/insights")
async def business_insights(
    business_id: Optional[int] = Query(None),
    focus: str = Query(
        "general",
        description="general | sales | inventory | employees | crm",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI-generated business intelligence using Groq LLM.
    Returns data snapshot + natural language analysis + recommendations.
    """
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    return await generate_insights(db, business_id, focus)


@router.get("/forecast")
async def revenue_forecast(
    business_id: Optional[int] = Query(None),
    days_ahead: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revenue forecast using linear trend extrapolation + AI commentary.
    """
    business_id = await resolve_business(current_user, db, business_id)
    return await forecast_revenue(db, business_id, days_ahead)


@router.get("/search")
async def global_search(
    q: str = Query(..., min_length=2, description="Search query"),
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search across products, customers, leads, and employees simultaneously.
    Returns categorized results.
    """
    from app.models.user import User as UserModel

    business_id = await resolve_business(current_user, db, business_id)
    term = f"%{q}%"
    results = {}

    prod = await db.execute(
        select(ProductInventory)
        .where(
            ProductInventory.business_id == business_id,
            or_(
                ProductInventory.name.ilike(term),
                ProductInventory.description.ilike(term),
            ),
        )
        .limit(10)
    )
    results["products"] = [
        {
            "id": p.id,
            "name": p.name,
            "price": float(p.price or 0),
            "quantity": p.quantity,
        }
        for p in prod.scalars().all()
    ]

    cust = await db.execute(
        select(CustomerContact)
        .where(
            CustomerContact.business_id == business_id,
            or_(
                CustomerContact.name.ilike(term),
                CustomerContact.email.ilike(term),
                CustomerContact.phone.ilike(term),
            ),
        )
        .limit(10)
    )
    results["customers"] = [
        {
            "id": c.contact_id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
        }
        for c in cust.scalars().all()
    ]

    leads = await db.execute(
        select(Lead)
        .where(
            Lead.business_id == business_id,
            or_(
                Lead.name.ilike(term),
                Lead.email.ilike(term),
                Lead.notes.ilike(term),
            ),
        )
        .limit(10)
    )
    results["leads"] = [
        {"id": l.id, "name": l.name, "stage": l.stage, "value": l.value}
        for l in leads.scalars().all()
    ]

    emps = await db.execute(
        select(Employee)
        .join(UserModel, UserModel.id == Employee.user_id)
        .where(
            Employee.business_id == business_id,
            or_(
                UserModel.name.ilike(term),
                Employee.designation.ilike(term),
                Employee.department.ilike(term),
            ),
        )
        .limit(10)
    )
    results["employees"] = [
        {
            "id": e.id,
            "user_id": e.user_id,
            "designation": e.designation,
            "department": e.department,
        }
        for e in emps.scalars().all()
    ]

    total = sum(len(v) for v in results.values())
    return {"query": q, "total_results": total, "results": results}


@router.post("/kpi")
async def set_kpi_target(
    data: KPICreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(db, current_user.id, business_id, ["business_owner"]):
        raise HTTPException(status_code=403, detail="Only owner can set KPI targets")

    if data.month < 1 or data.month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    existing = await db.execute(
        select(KPITarget).where(
            KPITarget.business_id == business_id,
            KPITarget.year == data.year,
            KPITarget.month == data.month,
        )
    )
    kpi = existing.scalar_one_or_none()
    if kpi:
        kpi.revenue_target = data.revenue_target
        kpi.sales_target = data.sales_target
    else:
        kpi = KPITarget(business_id=business_id, **data.dict())
    db.add(kpi)
    await db.commit()
    await db.refresh(kpi)
    return kpi


@router.get("/kpi/progress")
async def kpi_progress(
    business_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Live KPI progress: actual vs target for the given month."""
    import calendar

    business_id = await resolve_business(current_user, db, business_id)
    today = date.today()
    y = year or today.year
    m = month or today.month
    if m < 1 or m > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    kpi_result = await db.execute(
        select(KPITarget).where(
            KPITarget.business_id == business_id,
            KPITarget.year == y,
            KPITarget.month == m,
        )
    )
    kpi = kpi_result.scalar_one_or_none()

    month_start = date(y, m, 1)
    month_end = date(y, m, calendar.monthrange(y, m)[1])

    actual = await db.execute(
        select(
            func.coalesce(func.sum(DailyAccounts.revenue), 0),
            func.coalesce(func.sum(DailyAccounts.sales), 0),
        ).where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date >= month_start,
            DailyAccounts.date <= min(month_end, today),
        )
    )
    actual_row = actual.one()
    actual_revenue = float(actual_row[0])
    actual_sales = int(actual_row[1])

    revenue_target = float(kpi.revenue_target) if kpi else 0
    sales_target = int(kpi.sales_target) if kpi else 0

    return {
        "year": y,
        "month": m,
        "revenue": {
            "target": revenue_target,
            "actual": actual_revenue,
            "pct": round((actual_revenue / revenue_target * 100), 1)
            if revenue_target > 0
            else None,
            "remaining": max(0, revenue_target - actual_revenue),
        },
        "sales": {
            "target": sales_target,
            "actual": actual_sales,
            "pct": round((actual_sales / sales_target * 100), 1)
            if sales_target > 0
            else None,
            "remaining": max(0, sales_target - actual_sales),
        },
    }


@router.get("/export/sales")
async def export_sales_csv(
    business_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export daily accounts data as CSV."""
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not authorized")

    query = select(DailyAccounts).where(DailyAccounts.business_id == business_id)
    if start_date:
        query = query.where(DailyAccounts.date >= start_date)
    if end_date:
        query = query.where(DailyAccounts.date <= end_date)
    query = query.order_by(DailyAccounts.date.asc())

    result = await db.execute(query)
    records = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date",
        "Revenue",
        "Cost",
        "Salary Cost",
        "Operational Cost",
        "Miscellaneous",
        "Sales",
        "Total Expenses",
        "Net Profit",
    ])

    for r in records:
        expenses = (
            float(r.cost or 0)
            + float(r.salary_cost or 0)
            + float(r.operational_cost or 0)
            + float(r.miscellaneous or 0)
        )
        writer.writerow([
            r.date,
            float(r.revenue or 0),
            float(r.cost or 0),
            float(r.salary_cost or 0),
            float(r.operational_cost or 0),
            float(r.miscellaneous or 0),
            r.sales or 0,
            round(expenses, 2),
            round(float(r.revenue or 0) - expenses, 2),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales_export.csv"},
    )


@router.get("/export/inventory")
async def export_inventory_csv(
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    result = await db.execute(
        select(ProductInventory)
        .where(ProductInventory.business_id == business_id)
        .order_by(ProductInventory.name.asc())
    )
    products = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Description", "Price", "Quantity", "Stock Value"])
    for p in products:
        writer.writerow([
            p.id,
            p.name,
            p.description or "",
            float(p.price or 0),
            p.quantity or 0,
            round(float(p.price or 0) * (p.quantity or 0), 2),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_export.csv"},
    )
