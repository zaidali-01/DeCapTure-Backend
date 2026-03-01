from pydantic import BaseModel
from datetime import datetime

class CustomerContactCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None


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