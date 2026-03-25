from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from fastapi import HTTPException

from app.models.business import Business, UserBusinessBridge
from app.schemas.business import BusinessCreate, BusinessUpdate


async def create_business(db: AsyncSession, user_id: int, data: BusinessCreate):
    """
    Create a new business and link it to a user
    """
    new_business = Business(
        name=data.name,
        industry=data.industry,
        description=data.description,
        phone=data.phone,
        email=data.email
    )
    db.add(new_business)
    await db.commit()
    await db.refresh(new_business)

    bridge = UserBusinessBridge(user_id=user_id, business_id=new_business.id)
    db.add(bridge)
    await db.commit()
    return new_business


async def get_user_businesses(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Business)
        .join(UserBusinessBridge, Business.id == UserBusinessBridge.business_id)
        .where(UserBusinessBridge.user_id == user_id)
    )
    return result.scalars().all()


async def update_business(db: AsyncSession, business_id: int, user_id: int, data: BusinessUpdate):
    result = await db.execute(
        select(UserBusinessBridge).where(
            UserBusinessBridge.business_id == business_id,
            UserBusinessBridge.user_id == user_id
        )
    )
    bridge = result.scalar_one_or_none()
    if not bridge:
        raise HTTPException(status_code=403, detail="Not authorized to update this business")

    await db.execute(
        update(Business)
        .where(Business.id == business_id)
        .values(
            name=data.name,
            industry=data.industry,
            description=data.description,
            phone=data.phone,
            email=data.email
        )
    )
    await db.commit()

    result = await db.execute(select(Business).where(Business.id == business_id))
    return result.scalar_one()


async def delete_business(db: AsyncSession, business_id: int, user_id: int):
    result = await db.execute(
        select(UserBusinessBridge).where(
            UserBusinessBridge.business_id == business_id,
            UserBusinessBridge.user_id == user_id
        )
    )
    bridge = result.scalar_one_or_none()
    if not bridge:
        raise HTTPException(status_code=403, detail="Not authorized to delete this business")

    await db.execute(delete(UserBusinessBridge).where(UserBusinessBridge.business_id == business_id))
    await db.execute(delete(Business).where(Business.id == business_id))
    await db.commit()
    return {"message": "Business deleted successfully"}