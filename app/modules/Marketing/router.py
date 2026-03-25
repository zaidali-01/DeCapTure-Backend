from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.modules.Users.service import get_current_user
from app.modules.Marketing.service import (
    add_customer_contact,
    list_customers,
    send_marketing_message,
    check_business_access,
    send_marketing_to_single_contact
)
from app.schemas.contact import CustomerContactCreate
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/marketing", tags=["Marketing"])


@router.post("/customers")
async def create_customer(
    business_id: int,
    data: CustomerContactCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await check_business_access(db, current_user.id, business_id)
    return await add_customer_contact(db, business_id, data)


@router.get("/customers")
async def get_customers(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await check_business_access(db, current_user.id, business_id)
    customers = await list_customers(db, business_id)
    return {"customers": customers}


@router.post("/send")
async def send_marketing(
    business_id: int,
    message: str,
    channel: str = Query(..., description="email or whatsapp"),
    contact_ids: Optional[List[int]] = Query(None, description="Optional list of contact IDs"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send marketing message to all customers or specific contacts.
    """
    results = await send_marketing_message(
        db=db,
        user_id=current_user.id,
        business_id=business_id,
        message_content=message,
        channel=channel,
        contact_ids=contact_ids
    )
    return {"results": results}

@router.post("/send/{contact_id}")
async def send_to_single(
    business_id: int,
    contact_id: int,
    message: str,
    channel: str = Query(..., description="email or whatsapp"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send marketing message to a single customer.
    """
    result = await send_marketing_to_single_contact(
        db=db,
        user_id=current_user.id,
        business_id=business_id,
        contact_id=contact_id,
        message_content=message,
        channel=channel
    )
    return {"result": result}


@router.delete("/customers/{contact_id}")
async def remove_customer(
    business_id: int,
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a customer contact from the directory
    """
    await check_business_access(db, current_user.id, business_id)

    result = await db.execute(
        """
        DELETE FROM customer_contact 
        WHERE contact_id = :contact_id
        """,
        {"contact_id": contact_id}
    )
    await db.commit()
    return {"message": "Customer removed successfully"}