from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.Business.service import get_user_businesses
from app.modules.Suppliers import service
from app.modules.Users.service import get_current_user, has_role
from app.schemas.inventory_ext import (
    CategoryCreate,
    CategoryResponse,
    PurchaseOrderCreate,
    PurchaseOrderStatusUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


async def resolve_business(current_user, db, business_id):
    data = await get_user_businesses(db, current_user.id)
    businesses = data.get("businesses", []) if isinstance(data, dict) else data or []
    if not businesses:
        raise HTTPException(status_code=400, detail="No business found")
    if business_id:
        if any(b.id == business_id for b in businesses):
            return business_id
        raise HTTPException(status_code=404, detail="Business not found")
    return businesses[0].id


@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.create_category(db, business_id, data)


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.list_categories(db, business_id)


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.delete_category(db, category_id, business_id)


@router.post("/", response_model=SupplierResponse)
async def create_supplier(
    data: SupplierCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.create_supplier(db, business_id, data)


@router.get("/", response_model=List[SupplierResponse])
async def list_suppliers(
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.list_suppliers(db, business_id)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.update_supplier(db, supplier_id, business_id, data)


@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.delete_supplier(db, supplier_id, business_id)


@router.post("/orders")
async def create_po(
    data: PurchaseOrderCreate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    return await service.create_purchase_order(db, business_id, current_user.id, data)


@router.get("/orders")
async def list_orders(
    business_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.list_purchase_orders(db, business_id, status)


@router.get("/orders/{po_id}")
async def get_order(
    po_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.get_purchase_order_detail(db, po_id, business_id)


@router.put("/orders/{po_id}/status")
async def update_order_status(
    po_id: int,
    data: PurchaseOrderStatusUpdate,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(
        db,
        current_user.id,
        business_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    return await service.update_po_status(db, po_id, business_id, data)
