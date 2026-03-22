from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict

from app.modules.POS.service import (
    create_product, get_products, update_product, delete_product,
    create_sale, list_sales, get_sale_details
)
from app.modules.Users.service import get_current_user
from app.modules.Business.service import get_user_businesses
from app.schemas.inventory import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.sales import SaleCreate, SaleResponse
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/pos", tags=["POS"])


async def get_user_business_id(current_user: User, db: AsyncSession):
    businesses = await get_user_businesses(db, current_user.id)
    if not businesses:
        raise HTTPException(status_code=400, detail="No business found for current user")
    return businesses[0].id


@router.post("/inventory", response_model=ProductResponse)
async def add_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await get_user_business_id(current_user, db)
    return await create_product(db, business_id, data)


@router.get("/inventory", response_model=List[ProductResponse])
async def list_inventory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await get_user_business_id(current_user, db)
    return await get_products(db, business_id)


@router.put("/inventory/{product_id}", response_model=ProductResponse)
async def update_inventory(
    product_id: int,
    data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await get_user_business_id(current_user, db)
    return await update_product(db, product_id, business_id, data)


@router.delete("/inventory/{product_id}")
async def delete_inventory(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await get_user_business_id(current_user, db)
    return await delete_product(db, product_id, business_id)


@router.post("/sales", response_model=SaleResponse)
async def create_new_sale(
    data: SaleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await get_user_business_id(current_user, db)
    return await create_sale(db, current_user.id, business_id, data)


@router.get("/sales", response_model=List[Dict])
async def list_all_sales(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await get_user_business_id(current_user, db)
    sales = await list_sales(db, business_id)
    result = []
    for s in sales:
        result.append({
            "id": s.id,
            "user_id": s.user_id,
            "payment_method": s.payment_method,
            "transaction_id": s.transaction_id,
            "created_at": s.created_at
        })
    return result


@router.get("/sales/{sale_id}", response_model=Dict)
async def sale_details(
    sale_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    business_id = await get_user_business_id(current_user, db)
    return await get_sale_details(db, sale_id, business_id)