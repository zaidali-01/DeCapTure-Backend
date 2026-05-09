from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.Business.service import get_user_businesses
from app.modules.Loyalty import service
from app.modules.Users.service import get_current_user, has_role

router = APIRouter(prefix="/loyalty", tags=["Loyalty"])


class RedeemRequest(BaseModel):
    contact_id: int
    points: int


class AdjustRequest(BaseModel):
    contact_id: int
    points: int
    note: str


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


@router.post("/redeem")
async def redeem_points(
    data: RedeemRequest,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.redeem_points(db, data.contact_id, business_id, data.points)


@router.post("/adjust")
async def adjust_points(
    data: AdjustRequest,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    if not await has_role(db, current_user.id, business_id, ["business_owner"]):
        raise HTTPException(status_code=403, detail="Only owner can adjust points")
    return await service.manual_adjust(
        db,
        data.contact_id,
        business_id,
        data.points,
        data.note,
    )


@router.get("/{contact_id}")
async def get_loyalty_account(
    contact_id: int,
    business_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    business_id = await resolve_business(current_user, db, business_id)
    return await service.get_account_by_contact(db, contact_id, business_id)
