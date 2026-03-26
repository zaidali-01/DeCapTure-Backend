from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException
from typing import List, Optional
import smtplib
import httpx
from email.message import EmailMessage

from app.models.contact import CustomerContact, ContactCredentials
from app.models.module import UserRole
from app.models.business import Business
from app.core.config import settings
from app.schemas.contact import CustomerContactCreate


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


async def generate_marketing_message(
    business_name: str,
    channel: str,
    prompt: Optional[str] = None,
) -> str:
    """
    Call Groq LLM API to generate marketing message dynamically.
    """
    if not settings.GROQ_API_KEY:
        base = f"Hello from {business_name}! Check out our latest offers via {channel}."
        if prompt:
            base = f"{base} {prompt}"
        return base

    url = "https://api.groq.com/v1/llm"  # Example Groq endpoint
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
    base_prompt = (
        f"Generate a short, persuasive {channel} marketing message for the business "
        f"'{business_name}' targeting existing customers. Keep it under 45 words."
    )
    if prompt:
        base_prompt = f"{base_prompt} The marketer shared this brief: {prompt}"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"prompt": base_prompt}, headers=headers, timeout=30)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="LLM message generation failed")
        data = response.json()
        return data.get("text", "Hello from our business!")


async def add_customer_contact(db: AsyncSession, business_id: int, data: CustomerContactCreate):
    contact = CustomerContact(
        business_id=business_id,
        name=data.name,
        email=data.email,
        phone=data.phone
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def list_customers(db: AsyncSession, business_id: int):
    result = await db.execute(
        select(CustomerContact).where(CustomerContact.business_id == business_id)
    )
    return result.scalars().all()


async def send_marketing_message(
    db: AsyncSession,
    user_id: int,
    business_id: int,
    channel: str,
    message_content: Optional[str] = None,
    contact_ids: Optional[List[int]] = None,
    use_ai: bool = False,
):
    await check_business_access(db, user_id, business_id)

    result = await db.execute(
        select(ContactCredentials).where(ContactCredentials.business_id == business_id)
    )
    credentials = result.scalar_one_or_none()
    if not credentials:
        raise HTTPException(status_code=400, detail="Business credentials not configured")

    business = await db.get(Business, business_id)
    business_name = business.name if business else "your business"

    contacts_query = select(CustomerContact).where(CustomerContact.business_id == business_id)
    if contact_ids:
        contacts_query = contacts_query.where(CustomerContact.contact_id.in_(contact_ids))

    contacts = (await db.execute(contacts_query)).scalars().all()
    if not contacts:
        raise HTTPException(status_code=404, detail="No contacts available for this campaign")

    provided_text = message_content.strip() if message_content else None
    if not use_ai and not provided_text:
        raise HTTPException(status_code=400, detail="Message content is required when AI mode is disabled")

    manual_message = provided_text if not use_ai else None
    ai_prompt = provided_text if use_ai else None
    ai_message_cache: Optional[str] = None

    results = []
    for contact in contacts:
        status = "failed"
        try:
            current_message = manual_message
            if use_ai:
                if not ai_message_cache:
                    ai_message_cache = await generate_marketing_message(
                        business_name=business_name,
                        channel=channel,
                        prompt=ai_prompt,
                    )
                current_message = ai_message_cache
            if not current_message:
                raise HTTPException(status_code=400, detail="Unable to prepare campaign message")

            if channel == "email" and contact.email:
                msg = EmailMessage()
                msg["Subject"] = "Marketing Message"
                msg["From"] = credentials.smtp_token 
                msg["To"] = contact.email
                msg.set_content(current_message)

                with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
                    smtp.starttls()
                    smtp.login(credentials.smtp_token, "SMTP_PASSWORD_PLACEHOLDER")
                    smtp.send_message(msg)
                status = "sent"

            elif channel == "whatsapp" and contact.phone:
                # Placeholder for WhatsApp API integration
                # e.g., using Twilio / WhatsApp API with credentials.whatsapp_token
                status = "sent"
            else:
                status = "skipped: missing channel details"

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
    channel: str,
    message_content: Optional[str] = None,
    use_ai: bool = False,
):
    return await send_marketing_message(
        db=db,
        user_id=user_id,
        business_id=business_id,
        channel=channel,
        message_content=message_content,
        contact_ids=[contact_id],
        use_ai=use_ai,
    )