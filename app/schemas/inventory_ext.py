from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    business_id: int
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True


class SupplierCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SupplierResponse(BaseModel):
    id: int
    business_id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]

    class Config:
        from_attributes = True


class POItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity_ordered: int
    unit_cost: float


class POItemResponse(BaseModel):
    id: int
    product_id: Optional[int]
    product_name: str
    quantity_ordered: int
    quantity_received: int
    unit_cost: float

    class Config:
        from_attributes = True


class PurchaseOrderCreate(BaseModel):
    supplier_id: Optional[int] = None
    order_date: date
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[POItemCreate]


class PurchaseOrderStatusUpdate(BaseModel):
    status: str
    received_date: Optional[date] = None


class PurchaseOrderResponse(BaseModel):
    id: int
    business_id: int
    supplier_id: Optional[int]
    created_by: int
    status: str
    order_date: date
    expected_date: Optional[date]
    received_date: Optional[date]
    notes: Optional[str]
    total_cost: Optional[float] = None

    class Config:
        from_attributes = True
