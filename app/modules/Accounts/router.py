from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.Accounts import service
from app.modules.Business.service import get_user_businesses
from app.modules.Users.service import get_current_user, has_role
from app.schemas.accounts import (
    DailyAccountsCreate,
    DailyAccountsResponse,
    DailyAccountsUpdate,
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


async def resolve_business(current_user, db, requested_business_id):
    data = await get_user_businesses(db, current_user.id)
    businesses = data.get("businesses", []) if isinstance(data, dict) else data or []
    if not businesses:
        raise HTTPException(status_code=400, detail="No business found")
    if requested_business_id:
        if any(b.id == requested_business_id for b in businesses):
            return requested_business_id
        raise HTTPException(status_code=404, detail="Business not found")
    return businesses[0].id


@router.post("/", response_model=DailyAccountsResponse)
async def create_or_update(
    data: DailyAccountsCreate,
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
    data.business_id = business_id
    return await service.upsert_daily_accounts(db, business_id, data)


@router.get("/", response_model=List[DailyAccountsResponse])
async def list_accounts(
    business_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.get_daily_accounts(db, business_id, start_date, end_date)


@router.get("/summary")
async def summary(
    business_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.get_summary(db, business_id, start_date, end_date)


@router.get("/trend")
async def revenue_trend(
    business_id: Optional[int] = Query(None),
    days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.get_revenue_trend(db, business_id, days)


@router.put("/{record_id}", response_model=DailyAccountsResponse)
async def update_record(
    record_id: int,
    data: DailyAccountsUpdate,
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
    return await service.update_daily_accounts(db, business_id, record_id, data)


@router.delete("/{record_id}")
async def delete_record(
    record_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(db, current_user.id, business_id, ["business_owner"]):
        raise HTTPException(status_code=403, detail="Only owner can delete")
    return await service.delete_daily_accounts(db, business_id, record_id)
