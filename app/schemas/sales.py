from pydantic import BaseModel
from datetime import datetime

class SalesCreate(BaseModel):
    user_id: int
    payment_method: str
    salesman_id: int | None = None
    transaction_id: str | None = None


class SalesResponse(BaseModel):
    id: int
    user_id: int
    payment_method: str
    salesman_id: int | None
    transaction_id: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True