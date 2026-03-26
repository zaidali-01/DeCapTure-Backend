from pydantic import BaseModel
from datetime import datetime


# ── Document upload ───────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: int
    business_id: int
    filename: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ── Chat session ──────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    business_id: int
    customer_name: str | None = None


class SessionResponse(BaseModel):
    id: int
    business_id: int
    customer_name: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Messages ──────────────────────────────────────────────────────────────────

class MessageSend(BaseModel):
    """Payload the customer sends."""
    session_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReplyResponse(BaseModel):
    """What the chatbot returns."""
    message_id: int          # id of the saved assistant message
    session_id: int
    reply: str