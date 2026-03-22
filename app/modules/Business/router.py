from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.business import BusinessCreate, BusinessUpdate
from app.modules.Business.service import create_business, get_user_businesses, update_business, delete_business
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
    businesses = await get_user_businesses(db, current_user.id)
    return {"businesses": businesses}


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
