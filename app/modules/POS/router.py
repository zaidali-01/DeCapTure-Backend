from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional

from app.modules.POS.service import (
    create_product, get_products, update_product, delete_product,
    create_sale, list_sales, get_sale_details, get_product_by_id, buy_product
)
from app.modules.Users.service import get_current_user, has_role
from app.modules.Business.service import get_user_businesses
from app.schemas.inventory import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.sales import SaleCreate, SaleResponse
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/pos", tags=["POS"])


async def resolve_business_id(current_user, db, requested_business_id):
    businesses_data = await get_user_businesses(db, current_user.id)
    if isinstance(businesses_data, dict):
        businesses = businesses_data.get("businesses", [])
    else:
        businesses = businesses_data or []

    if not businesses:
        raise HTTPException(status_code=400, detail="No business found")

    if requested_business_id:
        for b in businesses:
            if b.id == requested_business_id:
                return requested_business_id
        raise HTTPException(status_code=404, detail="Business not found")

    return businesses[0].id


@router.post("/inventory", response_model=ProductResponse)
async def add_product(
    data: ProductCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)

    if not await has_role(db, current_user.id, business_id, ["business_owner", "manager"]):
        raise HTTPException(403, "Not allowed")

    return await create_product(db, business_id, data)


@router.get("/inventory", response_model=List[ProductResponse])
async def list_inventory(
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)
    return await get_products(db, business_id)


@router.get("/inventory/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)
    return await get_product_by_id(db, product_id, business_id)


@router.put("/inventory/{product_id}", response_model=ProductResponse)
async def update_inventory(
    product_id: int,
    data: ProductUpdate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)

    if not await has_role(db, current_user.id, business_id, ["business_owner", "manager"]):
        raise HTTPException(403, "Not allowed")

    return await update_product(db, product_id, business_id, data)


@router.delete("/inventory/{product_id}")
async def delete_inventory(
    product_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)

    if not await has_role(db, current_user.id, business_id, ["business_owner"]):
        raise HTTPException(403, "Only owner can delete")

    return await delete_product(db, product_id, business_id)


@router.post("/sales", response_model=SaleResponse)
async def create_new_sale(
    data: SaleCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)

    if not await has_role(db, current_user.id, business_id, ["business_owner", "manager", "cashier"]):
        raise HTTPException(403, "Not allowed")

    return await create_sale(db, current_user.id, business_id, data)


@router.get("/sales", response_model=List[Dict])
async def list_all_sales(
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)

    if not await has_role(db, current_user.id, business_id, ["business_owner", "manager"]):
        raise HTTPException(403, "Not allowed")

    sales = await list_sales(db, business_id)
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "payment_method": s.payment_method,
            "transaction_id": s.transaction_id,
            "created_at": s.created_at
        }
        for s in sales
    ]


@router.get("/sales/{sale_id}", response_model=Dict)
async def sale_details(
    sale_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)

    if not await has_role(db, current_user.id, business_id, ["business_owner", "manager"]):
        raise HTTPException(403, "Not allowed")

    return await get_sale_details(db, sale_id, business_id)


@router.post("/buy")
async def buy(
    product_id: int,
    quantity: int = 1,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await resolve_business_id(current_user, db, business_id)

    return await buy_product(db, current_user.id, business_id, product_id, quantity)