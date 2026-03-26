from pydantic import BaseModel
from typing import List

class SaleItem(BaseModel):
    listing_id: int
    quantity: int

class SaleCreate(BaseModel):
    payment_method: str
    transaction_id: str
    items: List[SaleItem]

class SaleResponse(BaseModel):
    id: int
    user_id: int
    payment_method: str
    transaction_id: str

    class Config:
        from_attributes = True