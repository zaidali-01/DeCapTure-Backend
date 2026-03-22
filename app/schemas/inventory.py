from pydantic import BaseModel
from typing import Optional

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    quantity: int = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    quantity: int
    business_id: int

    class Config:
        from_attributes = True