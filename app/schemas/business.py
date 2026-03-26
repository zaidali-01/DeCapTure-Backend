from pydantic import BaseModel
from typing import Optional

class BusinessCreate(BaseModel):
    name: str
    industry: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class BusinessResponse(BaseModel):
    id: int
    name: str
    industry: str | None
    description: str | None
    phone: str | None
    email: str | None

    class Config:
        from_attributes = True