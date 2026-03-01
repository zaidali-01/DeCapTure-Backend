from pydantic import BaseModel
from datetime import date

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