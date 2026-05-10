from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.Store import service
from app.modules.Users.service import get_current_user
from app.schemas.store import (
    PublicBusinessResponse,
    StoreListingResponse,
    StoreOrderCreate,
    StoreOrderResponse,
    StoreOrderStatusUpdate,
    StoreListingUpdate,
)

router = APIRouter(prefix="/store", tags=["Store"])


@router.get("/businesses", response_model=List[PublicBusinessResponse])
async def public_businesses(db: AsyncSession = Depends(get_db)):
    return await service.list_public_businesses(db)


@router.get("/businesses/{business_id}", response_model=PublicBusinessResponse)
async def public_business_detail(
    business_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_public_business(db, business_id)


@router.get("/listings", response_model=List[StoreListingResponse])
async def public_listings(
    business_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_public_listings(db, business_id, search)


@router.get("/listings/{listing_id}", response_model=StoreListingResponse)
async def public_listing_detail(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_public_listing(db, listing_id)


@router.get("/business/{business_id}/listings", response_model=List[StoreListingResponse])
async def public_business_listings(
    business_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await service.list_public_listings(db, business_id, None)


@router.post("/orders", response_model=StoreOrderResponse)
async def create_order(
    payload: StoreOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_store_order(db, current_user.id, payload)


@router.get("/orders/me", response_model=List[StoreOrderResponse])
async def my_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_user_store_orders(db, current_user.id)


@router.get("/admin/{business_id}/listings", response_model=List[StoreListingResponse])
async def business_listings(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_business_store_listings(db, current_user.id, business_id)


@router.put("/admin/{business_id}/products/{product_id}", response_model=StoreListingResponse)
async def update_listing(
    business_id: int,
    product_id: int,
    payload: StoreListingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.upsert_store_listing(db, current_user.id, business_id, product_id, payload)


@router.post("/admin/{business_id}/products/{product_id}/images", response_model=StoreListingResponse)
async def upload_listing_images(
    business_id: int,
    product_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.upload_listing_images(
        db,
        current_user.id,
        business_id,
        product_id,
        files,
    )


@router.delete("/admin/{business_id}/products/{product_id}/images/{image_id}", response_model=StoreListingResponse)
async def delete_listing_image(
    business_id: int,
    product_id: int,
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.delete_listing_image(
        db,
        current_user.id,
        business_id,
        product_id,
        image_id,
    )


@router.get("/admin/{business_id}/orders", response_model=List[StoreOrderResponse])
async def business_orders(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_business_store_orders(db, current_user.id, business_id)


@router.put("/admin/{business_id}/orders/{order_id}", response_model=StoreOrderResponse)
async def update_order_status(
    business_id: int,
    order_id: int,
    payload: StoreOrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_store_order_status(
        db,
        current_user.id,
        business_id,
        order_id,
        payload.status,
    )
