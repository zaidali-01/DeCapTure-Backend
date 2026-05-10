from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StoreListingCreate(BaseModel):
    product_id: int
    is_published: bool = False
    listing_type: str = "product"
    headline: Optional[str] = None
    display_description: Optional[str] = None


class StoreListingUpdate(BaseModel):
    is_published: Optional[bool] = None
    listing_type: Optional[str] = None
    headline: Optional[str] = None
    display_description: Optional[str] = None


class StoreListingImageResponse(BaseModel):
    id: int
    file_path: str
    sort_order: int = 0

    class Config:
        from_attributes = True


class StoreListingResponse(BaseModel):
    id: Optional[int] = None
    business_id: int
    product_id: int
    is_published: bool
    listing_type: str = "product"
    headline: Optional[str]
    display_description: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    product_name: str
    product_description: Optional[str] = None
    product_price: float
    product_quantity: int
    business_name: Optional[str] = None
    images: List[StoreListingImageResponse] = []


class StoreOrderItemCreate(BaseModel):
    listing_id: int
    quantity: int = Field(..., ge=1)


class StoreOrderCreate(BaseModel):
    business_id: int
    buyer_name: str
    buyer_phone: str
    buyer_email: str
    items: List[StoreOrderItemCreate]


class StoreOrderItemResponse(BaseModel):
    id: int
    product_id: Optional[int]
    product_name_snapshot: str
    unit_price_snapshot: float
    quantity: int

    class Config:
        from_attributes = True


class StoreOrderResponse(BaseModel):
    id: int
    business_id: int
    buyer_user_id: Optional[int]
    fulfilled_sale_id: Optional[int] = None
    buyer_name: str
    buyer_phone: str
    buyer_email: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[StoreOrderItemResponse] = []
    business_name: Optional[str] = None


class StoreOrderStatusUpdate(BaseModel):
    status: str


class PublicBusinessResponse(BaseModel):
    id: int
    name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    published_listing_count: int = 0
    has_store_bot: bool = False
    store_bot_id: Optional[int] = None
