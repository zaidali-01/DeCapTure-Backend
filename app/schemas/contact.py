from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional


class CommunicationCreate(BaseModel):
    contact_id: int
    message: str


class CommunicationResponse(BaseModel):
    id: int
    contact_id: int
    message: str
    date: datetime

    class Config:
        from_attributes = True


class CustomerContactCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class CustomerContactResponse(CustomerContactCreate):
    contact_id: int

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    subject: Optional[str] = None        # For email
    content: str                          # Message content
    contact_ids: Optional[List[int]] = None  # Individual send; None = send to all
    channel: str                           # "email" or "whatsapp"


class MessageResponse(BaseModel):
    contact_id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    status: str       # "sent" or "failed"
