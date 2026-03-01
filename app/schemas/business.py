from pydantic import BaseModel

class BusinessCreate(BaseModel):
    name: str
    industry: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None


class BusinessResponse(BaseModel):
    id: int
    name: str
    industry: str | None
    description: str | None
    phone: str | None
    email: str | None

    class Config:
        from_attributes = True