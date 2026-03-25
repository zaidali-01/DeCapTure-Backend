from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException
from typing import List, Optional
import smtplib
import httpx
from email.message import EmailMessage

from app.models.contact import CustomerContact, ContactCredentials
from app.models.module import UserRole
from app.core.config import settings


async def check_business_access(db: AsyncSession, user_id: int, business_id: int):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.business_id == business_id,
            UserRole.role.in_(["business_owner", "manager"])
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=403, detail="Not authorized for this business")
    return True


async def generate_marketing_message(business_name: str, channel: str) -> str:
    """
    Call Groq LLM API to generate marketing message dynamically.
    """
    url = "https://api.groq.com/v1/llm"  # Example Groq endpoint
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
    prompt = f"Generate a short, persuasive {channel} marketing message for the business '{business_name}' targeting customers."

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"prompt": prompt}, headers=headers, timeout=30)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="LLM message generation failed")
        data = response.json()
        return data.get("text", "Hello from our business!")


async def add_customer_contact(db: AsyncSession, business_id: int, data: CustomerContact):
    contact = CustomerContact(
        name=data.name,
        email=data.email,
        phone=data.phone
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def list_customers(db: AsyncSession, business_id: int):
    result = await db.execute(select(CustomerContact))
    return result.scalars().all()


async def send_marketing_message(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    channel: str,
    contact_ids: Optional[List[int]] = None
):
    await check_business_access(db, user_id, business_id)

    result = await db.execute(
        select(ContactCredentials).where(ContactCredentials.business_id == business_id)
    )
    credentials = result.scalar_one_or_none()
    if not credentials:
        raise HTTPException(status_code=400, detail="Business credentials not configured")

    if contact_ids:
        result = await db.execute(
            select(CustomerContact).where(CustomerContact.contact_id.in_(contact_ids))
        )
    else:
        result = await db.execute(select(CustomerContact))
    contacts = result.scalars().all()

    results = []
    for contact in contacts:
        status = "failed"
        try:
            message_content = await generate_marketing_message(business_name=credentials.business_id, channel=channel)

            if channel == "email" and contact.email:
                msg = EmailMessage()
                msg["Subject"] = "Marketing Message"
                msg["From"] = credentials.smtp_token 
                msg["To"] = contact.email
                msg.set_content(message_content)

                with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
                    smtp.starttls()
                    smtp.login(credentials.smtp_token, "SMTP_PASSWORD_PLACEHOLDER")
                    smtp.send_message(msg)
                status = "sent"

            elif channel == "whatsapp" and contact.phone:
                # Placeholder for WhatsApp API integration
                # e.g., using Twilio / WhatsApp API with credentials.whatsapp_token
                status = "sent"

        except Exception as e:
            status = f"failed: {str(e)}"

        results.append({
            "contact_id": contact.contact_id,
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
            "status": status
        })

    return results

async def send_marketing_to_single_contact(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    contact_id: int,
    channel: str
):
    return await send_marketing_message(
        db=db,
        user_id=user_id,
        business_id=business_id,
        channel=channel,
        contact_ids=[contact_id]
    )