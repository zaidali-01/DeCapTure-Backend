from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from fastapi import HTTPException

from app.models.contact import ContactCredentials
from app.models.business import Business, UserBusinessBridge
from app.models.module import UserRole, Module, ModuleBusinessBridge
from app.schemas.business import BusinessCreate, BusinessUpdate


async def create_business(db: AsyncSession, user_id: int, data: BusinessCreate, smtp_token: str = None, whatsapp_token: str = None):
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

    db.add(UserBusinessBridge(user_id=user_id, business_id=new_business.id))

    db.add(UserRole(
        user_id=user_id,
        business_id=new_business.id,
        role="business_owner",
        rules={"full_access": True}
    ))

    db.add(ContactCredentials(
        business_id=new_business.id,
        smtp_token=smtp_token,
        whatsapp_token=whatsapp_token
    ))

    await db.commit()
    return new_business


async def get_user_businesses(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Business)
        .join(UserBusinessBridge, Business.id == UserBusinessBridge.business_id)
        .where(UserBusinessBridge.user_id == user_id)
    )
    return result.scalars().all()


async def assign_role(
    db: AsyncSession,
    owner_id: int,
    target_user_id: int,
    business_id: int,
    role: str,
    rules: dict = None
):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == owner_id,
            UserRole.business_id == business_id,
            UserRole.role == "business_owner"
        )
    )
    owner = result.scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=403, detail="Only owner can assign roles")

    db.add(UserRole(
        user_id=target_user_id,
        business_id=business_id,
        role=role,
        rules=rules or {}
    ))
    await db.commit()

    return {"message": f"{role} role assigned successfully"}


async def add_module_to_business(db: AsyncSession, user_id: int, business_id: int, module_id: int):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id,
            UserRole.role == "business_owner"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only owner can add modules")

    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(404, "Module not found")

    existing = await db.execute(
        select(ModuleBusinessBridge).where(
            ModuleBusinessBridge.business_id == business_id,
            ModuleBusinessBridge.module_id == module_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Module already added")

    db.add(ModuleBusinessBridge(
        business_id=business_id,
        module_id=module_id
    ))
    await db.commit()

    return {"message": "Module added successfully"}


async def remove_module_from_business(db: AsyncSession, user_id: int, business_id: int, module_id: int):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id,
            UserRole.role == "business_owner"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only owner can remove modules")

    existing = await db.execute(
        select(ModuleBusinessBridge).where(
            ModuleBusinessBridge.business_id == business_id,
            ModuleBusinessBridge.module_id == module_id
        )
    )
    bridge = existing.scalar_one_or_none()
    if not bridge:
        raise HTTPException(404, "Module not assigned to business")

    await db.execute(
        delete(ModuleBusinessBridge).where(ModuleBusinessBridge.id == bridge.id)
    )
    await db.commit()

    return {"message": "Module removed successfully"}


async def get_business_modules(db: AsyncSession, business_id: int):
    result = await db.execute(
        select(Module)
        .join(ModuleBusinessBridge, Module.id == ModuleBusinessBridge.module_id)
        .where(ModuleBusinessBridge.business_id == business_id)
    )
    return result.scalars().all()


async def update_business(db: AsyncSession, business_id: int, user_id: int, data: BusinessUpdate):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id,
            UserRole.role == "business_owner"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only owner can update business")

    await db.execute(
        update(Business)
        .where(Business.id == business_id)
        .values(**data.dict(exclude_unset=True))
    )
    await db.commit()

    result = await db.execute(select(Business).where(Business.id == business_id))
    return result.scalar_one()


async def delete_business(db: AsyncSession, business_id: int, user_id: int):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id,
            UserRole.role == "business_owner"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only owner can delete business")

    await db.execute(delete(Business).where(Business.id == business_id))
    await db.commit()

    return {"message": "Business deleted successfully"}


async def update_business_credentials(db: AsyncSession, user_id: int, business_id: int, smtp_token: str = None, whatsapp_token: str = None):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id,
            UserRole.role == "business_owner"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, "Only owner can update credentials")

    credentials = await db.execute(
        select(ContactCredentials).where(ContactCredentials.business_id == business_id)
    )
    creds = credentials.scalar_one_or_none()
    if not creds:
        db.add(ContactCredentials(
            business_id=business_id,
            smtp_token=smtp_token,
            whatsapp_token=whatsapp_token
        ))
    else:
        await db.execute(
            update(ContactCredentials)
            .where(ContactCredentials.id == creds.id)
            .values(
                smtp_token=smtp_token if smtp_token else creds.smtp_token,
                whatsapp_token=whatsapp_token if whatsapp_token else creds.whatsapp_token
            )
        )
    await db.commit()
    return {"message": "Credentials updated successfully"}
