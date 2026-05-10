from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class DocumentResponse(BaseModel):
    id: int
    business_id: int
    chatbot_id: Optional[int] = None
    filename: str
    chunk_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    business_id: Optional[int] = None
    chatbot_id: Optional[int] = None
    customer_name: Optional[str] = None


class SessionResponse(BaseModel):
    id: int
    business_id: int
    chatbot_id: Optional[int] = None
    customer_user_id: Optional[int] = None
    customer_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionSummaryResponse(BaseModel):
    id: int
    business_id: int
    chatbot_id: Optional[int] = None
    customer_user_id: Optional[int] = None
    customer_name: Optional[str] = None
    created_at: datetime
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    escalation_status: str = "none"


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


class EscalationCreate(BaseModel):
    session_id: int


class EscalationResponse(BaseModel):
    id: int
    session_id: int
    business_id: int
    status: str
    requested_at: datetime
    agent_user_id: Optional[int] = None

    class Config:
        from_attributes = True


class HumanMessageSend(BaseModel):
    session_id: int
    content: str
    role: str  # "user" or "agent"


class ChatbotCreate(BaseModel):
    business_id: int
    name: str
    system_prompt: Optional[str] = None


class ChatbotUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None


class ChatbotResponse(BaseModel):
    id: int
    business_id: int
    name: str
    system_prompt: Optional[str] = None
    is_store_bot: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
