from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.Business import service
from app.schemas.business import BusinessCreate, BusinessResponse


router = APIRouter(prefix="/businesses", tags=["Businesses"])


@router.get("", response_model=list[BusinessResponse], summary="List all businesses")
async def list_businesses(db: AsyncSession = Depends(get_db)):
    return await service.list_businesses(db)


@router.post(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a business",
)
async def create_business(
    payload: BusinessCreate,
    db: AsyncSession = Depends(get_db),
):
    return await service.create_business(db, payload)


@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
    summary="Get a business by id",
)
async def get_business(
    business_id: int,
    db: AsyncSession = Depends(get_db),
):
    business = await service.get_business(db, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return business
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.schemas.business import BusinessCreate, BusinessUpdate
from app.modules.Business.service import (
    create_business,
    get_user_businesses,
    update_business,
    delete_business,
    add_module_to_business,
    remove_module_from_business,
    get_business_modules,
    assign_role,
    update_business_credentials
)
from app.modules.Users.service import get_current_user
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/business", tags=["Business"])


@router.post("/register")
async def register_business(
    data: BusinessCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await create_business(db, current_user.id, data)


@router.get("/my-businesses")
async def my_businesses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_user_businesses(db, current_user.id)


@router.put("/update/{business_id}")
async def update(
    business_id: int,
    data: BusinessUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await update_business(db, business_id, current_user.id, data)


@router.delete("/delete/{business_id}")
async def delete(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await delete_business(db, business_id, current_user.id)


@router.post("/assign-role")
async def assign_role_to_user(
    target_user_id: int,
    business_id: int,
    role: str,
    rules: Optional[dict] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await assign_role(db, current_user.id, target_user_id, business_id, role, rules)


@router.post("/{business_id}/modules/{module_id}")
async def add_module(
    business_id: int,
    module_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await add_module_to_business(db, current_user.id, business_id, module_id)


@router.delete("/{business_id}/modules/{module_id}")
async def remove_module(
    business_id: int,
    module_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await remove_module_from_business(db, current_user.id, business_id, module_id)


@router.get("/{business_id}/modules")
async def list_modules(
    business_id: int,
    db: AsyncSession = Depends(get_db)
):
    return await get_business_modules(db, business_id)

@router.put("/update-credentials/{business_id}")
async def update_credentials(
    business_id: int,
    smtp_token: Optional[str] = None,
    whatsapp_token: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await update_business_credentials(db, current_user.id, business_id, smtp_token, whatsapp_token)
