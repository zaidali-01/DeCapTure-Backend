from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.accounts import DailyAccounts
from app.models.crm import Lead
from app.models.employee import Attendance, Employee
from app.models.inventory import ProductInventory


def _get_groq():
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        return Groq(api_key=settings.GROQ_API_KEY)
    except Exception:
        return None


async def _build_business_snapshot(db: AsyncSession, business_id: int) -> dict:
    """Gather key metrics to feed to the AI."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    prev_thirty_start = thirty_days_ago - timedelta(days=30)

    curr = await db.execute(
        select(
            func.coalesce(func.sum(DailyAccounts.revenue), 0),
            (
                func.coalesce(func.sum(DailyAccounts.cost), 0)
                + func.coalesce(func.sum(DailyAccounts.salary_cost), 0)
                + func.coalesce(func.sum(DailyAccounts.operational_cost), 0)
                + func.coalesce(func.sum(DailyAccounts.miscellaneous), 0)
            ),
            func.coalesce(func.sum(DailyAccounts.sales), 0),
        ).where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date >= thirty_days_ago,
            DailyAccounts.date <= today,
        )
    )
    curr_row = curr.one()

    prev = await db.execute(
        select(
            func.coalesce(func.sum(DailyAccounts.revenue), 0),
            func.coalesce(func.sum(DailyAccounts.sales), 0),
        ).where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date >= prev_thirty_start,
            DailyAccounts.date < thirty_days_ago,
        )
    )
    prev_row = prev.one()

    low_stock = await db.execute(
        select(ProductInventory.name, ProductInventory.quantity).where(
            ProductInventory.business_id == business_id,
            ProductInventory.quantity <= 5,
        )
    )
    low_stock_items = [{"name": r.name, "qty": r.quantity} for r in low_stock.all()]

    pipeline = await db.execute(
        select(Lead.stage, func.count(Lead.id))
        .where(Lead.business_id == business_id)
        .group_by(Lead.stage)
    )
    pipeline_data = {r[0]: r[1] for r in pipeline.all()}

    month_start = date(today.year, today.month, 1)
    att = await db.execute(
        select(Attendance.status, func.count(Attendance.id))
        .join(Employee, Employee.id == Attendance.employee_id)
        .where(
            Employee.business_id == business_id,
            Attendance.date >= month_start,
        )
        .group_by(Attendance.status)
    )
    attendance_data = {r[0]: r[1] for r in att.all()}

    curr_revenue = float(curr_row[0])
    curr_expenses = float(curr_row[1])
    prev_revenue = float(prev_row[0])
    revenue_change = (
        ((curr_revenue - prev_revenue) / prev_revenue * 100)
        if prev_revenue > 0
        else 0
    )

    return {
        "period": "last_30_days",
        "revenue": curr_revenue,
        "expenses": curr_expenses,
        "profit": curr_revenue - curr_expenses,
        "total_sales": int(curr_row[2]),
        "prev_revenue": prev_revenue,
        "revenue_change_pct": round(revenue_change, 1),
        "low_stock_items": low_stock_items,
        "crm_pipeline": pipeline_data,
        "attendance_summary": attendance_data,
    }


async def generate_insights(
    db: AsyncSession,
    business_id: int,
    focus: str = "general",
) -> dict:
    """
    focus options: "general" | "sales" | "inventory" | "employees" | "crm"
    """
    groq = _get_groq()
    snapshot = await _build_business_snapshot(db, business_id)

    if not groq:
        return {
            "snapshot": snapshot,
            "insights": "AI insights require GROQ_API_KEY to be configured.",
            "recommendations": [],
        }

    focus_instruction = {
        "general": "Give a balanced overview of the business health.",
        "sales": "Focus on sales trends, revenue, and growth opportunities.",
        "inventory": "Focus on inventory levels, low stock risks, and ordering advice.",
        "employees": "Focus on attendance patterns and workforce efficiency.",
        "crm": "Focus on the sales pipeline and lead conversion opportunities.",
    }.get(focus, "Give a balanced overview.")

    prompt = f"""
You are a business intelligence analyst. A business owner has shared their last 30 days of data.
Analyze this and provide:
1. A concise 2-3 sentence executive summary
2. Exactly 3 specific, actionable recommendations (numbered list)
3. One key risk to watch

{focus_instruction}

DATA:
- Revenue (last 30 days): {snapshot['revenue']:,.0f}
- Expenses: {snapshot['expenses']:,.0f}
- Net profit: {snapshot['profit']:,.0f}
- Total sales transactions: {snapshot['total_sales']}
- Revenue vs previous 30 days: {snapshot['revenue_change_pct']:+.1f}%
- Low stock items (<=5 units): {snapshot['low_stock_items']}
- CRM pipeline by stage: {snapshot['crm_pipeline']}
- Attendance this month: {snapshot['attendance_summary']}

Respond in plain English. Be direct and specific. No fluff.
Format: Summary paragraph, then numbered recommendations, then Risk: line.
"""

    response = groq.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.4,
    )
    ai_text = response.choices[0].message.content

    return {
        "snapshot": snapshot,
        "insights": ai_text,
        "focus": focus,
    }


async def forecast_revenue(
    db: AsyncSession,
    business_id: int,
    days_ahead: int = 7,
) -> dict:
    """
    Simple linear trend extrapolation + AI commentary.
    Uses last 30 days of data to forecast next N days.
    """
    today = date.today()
    start = today - timedelta(days=30)

    result = await db.execute(
        select(DailyAccounts.date, DailyAccounts.revenue)
        .where(
            DailyAccounts.business_id == business_id,
            DailyAccounts.date >= start,
        )
        .order_by(DailyAccounts.date.asc())
    )
    records = result.all()

    if len(records) < 7:
        return {"error": "Not enough historical data for forecasting (need at least 7 days)"}

    revenues = [float(r.revenue or 0) for r in records]
    n = len(revenues)
    avg = sum(revenues) / n
    x_mean = (n - 1) / 2
    numerator = sum((i - x_mean) * (revenues[i] - avg) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0

    forecast = []
    last_date = records[-1].date
    for i in range(1, days_ahead + 1):
        projected = max(0, revenues[-1] + slope * i)
        forecast.append(
            {
                "date": str(last_date + timedelta(days=i)),
                "projected_revenue": round(projected, 2),
            }
        )

    groq = _get_groq()
    commentary = "AI commentary requires GROQ_API_KEY."
    if groq:
        trend_dir = "upward" if slope > 0 else "downward" if slope < 0 else "flat"
        prompt = (
            f"A business has a {trend_dir} revenue trend with a daily slope of "
            f"{slope:.1f}. Average daily revenue: {avg:.0f}. "
            f"Forecast for next {days_ahead} days: {forecast}. "
            f"In 2 sentences, what should the owner focus on?"
        )
        r = groq.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.3,
        )
        commentary = r.choices[0].message.content

    return {
        "historical_days": n,
        "average_daily_revenue": round(avg, 2),
        "trend_slope": round(slope, 2),
        "forecast": forecast,
        "ai_commentary": commentary,
    }
