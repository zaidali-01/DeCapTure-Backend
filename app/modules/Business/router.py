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
