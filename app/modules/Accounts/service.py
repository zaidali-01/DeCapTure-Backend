from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import DailyAccounts
from app.schemas.accounts import DailyAccountsCreate, DailyAccountsUpdate


async def upsert_daily_accounts(
    db: AsyncSession,
    business_id: int,
    data: DailyAccountsCreate,
) -> DailyAccounts:
    """Create or update a daily record. If record for that date exists, merge it."""
    result = await db.execute(
        select(DailyAccounts).where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date == data.date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.cost = data.cost
        existing.revenue = data.revenue
        existing.sales = data.sales
        existing.salary_cost = data.salary_cost
        existing.operational_cost = data.operational_cost
        existing.miscellaneous = data.miscellaneous
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    record = DailyAccounts(
        business_id=business_id,
        **data.dict(exclude={"business_id"}),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_daily_accounts(
    db: AsyncSession,
    business_id: int,
    start_date: date = None,
    end_date: date = None,
) -> list:
    query = select(DailyAccounts).where(DailyAccounts.business_id == business_id)
    if start_date:
        query = query.where(DailyAccounts.date >= start_date)
    if end_date:
        query = query.where(DailyAccounts.date <= end_date)
    query = query.order_by(DailyAccounts.date.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def get_single_day(
    db: AsyncSession,
    business_id: int,
    record_id: int,
) -> DailyAccounts:
    result = await db.execute(
        select(DailyAccounts).where(
            DailyAccounts.id == record_id,
            DailyAccounts.business_id == business_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


async def update_daily_accounts(
    db: AsyncSession,
    business_id: int,
    record_id: int,
    data: DailyAccountsUpdate,
) -> DailyAccounts:
    record = await get_single_day(db, business_id, record_id)
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_daily_accounts(
    db: AsyncSession,
    business_id: int,
    record_id: int,
) -> dict:
    await get_single_day(db, business_id, record_id)
    await db.execute(delete(DailyAccounts).where(DailyAccounts.id == record_id))
    await db.commit()
    return {"message": "Record deleted"}


async def get_summary(
    db: AsyncSession,
    business_id: int,
    start_date: date = None,
    end_date: date = None,
) -> dict:
    query = select(
        func.coalesce(func.sum(DailyAccounts.revenue), 0).label("total_revenue"),
        func.coalesce(func.sum(DailyAccounts.cost), 0).label("total_cost"),
        func.coalesce(func.sum(DailyAccounts.salary_cost), 0).label("total_salary_cost"),
        func.coalesce(func.sum(DailyAccounts.operational_cost), 0).label(
            "total_operational_cost"
        ),
        func.coalesce(func.sum(DailyAccounts.miscellaneous), 0).label(
            "total_miscellaneous"
        ),
        func.coalesce(func.sum(DailyAccounts.sales), 0).label("total_sales"),
        func.count(DailyAccounts.id).label("period_days"),
    ).where(DailyAccounts.business_id == business_id)

    if start_date:
        query = query.where(DailyAccounts.date >= start_date)
    if end_date:
        query = query.where(DailyAccounts.date <= end_date)

    result = await db.execute(query)
    row = result.one()

    total_expenses = (
        float(row.total_cost)
        + float(row.total_salary_cost)
        + float(row.total_operational_cost)
        + float(row.total_miscellaneous)
    )
    net_profit = float(row.total_revenue) - total_expenses

    return {
        "total_revenue": float(row.total_revenue),
        "total_cost": float(row.total_cost),
        "total_salary_cost": float(row.total_salary_cost),
        "total_operational_cost": float(row.total_operational_cost),
        "total_miscellaneous": float(row.total_miscellaneous),
        "total_sales": int(row.total_sales),
        "net_profit": net_profit,
        "period_days": int(row.period_days),
    }


async def get_revenue_trend(
    db: AsyncSession,
    business_id: int,
    days: int = 30,
) -> list:
    """Return daily revenue + profit for the last N days for charting."""
    start = date.today() - timedelta(days=days)
    result = await db.execute(
        select(DailyAccounts)
        .where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date >= start,
        )
        .order_by(DailyAccounts.date.asc())
    )
    records = result.scalars().all()
    return [
        {
            "date": str(r.date),
            "revenue": float(r.revenue or 0),
            "cost": float(
                (r.cost or 0)
                + (r.salary_cost or 0)
                + (r.operational_cost or 0)
                + (r.miscellaneous or 0)
            ),
            "profit": float(r.revenue or 0)
            - float(
                (r.cost or 0)
                + (r.salary_cost or 0)
                + (r.operational_cost or 0)
                + (r.miscellaneous or 0)
            ),
            "sales": int(r.sales or 0),
        }
        for r in records
    ]
