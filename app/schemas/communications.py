from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class DocumentResponse(BaseModel):
    id: int
    business_id: int
    filename: str
    chunk_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    business_id: int
    customer_name: Optional[str] = None


class SessionResponse(BaseModel):
    id: int
    business_id: int
    customer_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageSend(BaseModel):
    session_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    sources: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AskResponse(BaseModel):
    message_id: int
    session_id: int
    answer: str
    sources: List[str]