from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.models.user import User
from app.models.module import UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password, decode_access_token
from app.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


async def create_user(db: AsyncSession, user: UserCreate):
    result = await db.execute(select(User).where(User.email == user.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    db.add(UserRole(
        user_id=new_user.id,
        role="customer",
        business_id=None
    ))
    await db.commit()

    return new_user


async def authenticate_user(db: AsyncSession, email: str, password: str):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("user_id")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


async def get_users(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()


async def get_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def update_user(db: AsyncSession, user_id: int, data: UserUpdate):
    user = await get_user(db, user_id)

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            name=data.name if data.name else user.name,
            email=data.email if data.email else user.email,
            password=hash_password(data.password) if data.password else user.password
        )
    )
    await db.commit()

    return await get_user(db, user_id)


async def delete_user(db: AsyncSession, user_id: int):
    user = await get_user(db, user_id)

    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return {"message": "User deleted successfully"}


async def has_role(db, user_id: int, business_id: int, roles: list):
    from app.models.module import UserRole
    from sqlalchemy import select

    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id
        )
    )
    user_roles = result.scalars().all()

    return any(r.role in roles for r in user_roles)