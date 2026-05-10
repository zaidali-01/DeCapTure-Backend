from pydantic import BaseModel
from datetime import date
from typing import Optional

class DailyAccountsCreate(BaseModel):
    business_id: int
    date: date
    cost: float
    revenue: float
    sales: int
    salary_cost: float
    operational_cost: float
    miscellaneous: float


class DailyAccountsResponse(DailyAccountsCreate):
    id: int

    class Config:
        from_attributes = True


class DailyAccountsUpdate(BaseModel):
    cost: Optional[float] = None
    revenue: Optional[float] = None
    sales: Optional[int] = None
    salary_cost: Optional[float] = None
    operational_cost: Optional[float] = None
    miscellaneous: Optional[float] = None


class AccountsSummary(BaseModel):
    total_revenue: float
    total_cost: float
    total_salary_cost: float
    total_operational_cost: float
    total_miscellaneous: float
    total_sales: int
    net_profit: float
    period_days: int


class DailyAccountsFilter(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
