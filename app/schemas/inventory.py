from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    business_id: int
    price: float
    quantity: int


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    business_id: int
    price: float
    quantity: int

    class Config:
        from_attributes = True