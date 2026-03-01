from pydantic import BaseModel

class ModuleCreate(BaseModel):
    name: str
    category: str


class ModuleResponse(BaseModel):
    id: int
    name: str
    category: str

    class Config:
        from_attributes = True