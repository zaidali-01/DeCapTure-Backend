from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.schemas.business import BusinessCreate


async def list_businesses(db: AsyncSession) -> list[Business]:
    result = await db.execute(select(Business).order_by(Business.id.desc()))
    return list(result.scalars().all())


async def get_business(db: AsyncSession, business_id: int) -> Business | None:
    return await db.get(Business, business_id)


async def create_business(db: AsyncSession, payload: BusinessCreate) -> Business:
    business = Business(
        name=payload.name,
        industry=payload.industry,
        description=payload.description,
        phone=payload.phone,
        email=payload.email,
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business
