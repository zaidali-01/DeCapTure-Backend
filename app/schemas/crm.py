from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class LeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    stage: str = "new"
    value: int = 0
    notes: Optional[str] = None
    assigned_to: Optional[int] = None
    contact_id: Optional[int] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    stage: Optional[str] = None
    value: Optional[int] = None
    notes: Optional[str] = None
    assigned_to: Optional[int] = None


class LeadResponse(BaseModel):
    id: int
    business_id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    source: Optional[str]
    stage: str
    value: int
    notes: Optional[str]
    assigned_to: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class NoteCreate(BaseModel):
    contact_id: int
    content: str


class NoteResponse(BaseModel):
    id: int
    contact_id: int
    business_id: int
    author_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class FollowUpCreate(BaseModel):
    title: str
    due_date: date
    assigned_to: int
    lead_id: Optional[int] = None
    contact_id: Optional[int] = None


class FollowUpUpdate(BaseModel):
    is_done: Optional[bool] = None
    due_date: Optional[date] = None
    title: Optional[str] = None


class FollowUpResponse(BaseModel):
    id: int
    business_id: int
    title: str
    due_date: date
    assigned_to: int
    lead_id: Optional[int]
    contact_id: Optional[int]
    is_done: bool
    created_at: datetime

    class Config:
        from_attributes = True
