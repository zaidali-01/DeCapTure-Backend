from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.modules.Audit import service
from app.modules.Business.service import get_user_businesses
from app.modules.Users.service import get_current_user, has_role

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/")
async def get_logs(
    business_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await get_user_businesses(db, current_user.id)
    businesses = data.get("businesses", []) if isinstance(data, dict) else data or []
    if not businesses:
        raise HTTPException(status_code=400, detail="No business found")
    resolved_id = business_id or businesses[0].id

    if not await has_role(
        db,
        current_user.id,
        resolved_id,
        ["business_owner", "manager"],
    ):
        raise HTTPException(status_code=403, detail="Not authorized")

    return await service.get_audit_logs(
        db,
        resolved_id,
        user_id,
        action,
        entity_type,
        limit,
        offset,
    )
