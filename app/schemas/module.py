from pydantic import BaseModel
from typing import Optional, Dict


class ModuleBase(BaseModel):
    name: str
    category: Optional[str] = None


class ModuleCreate(ModuleBase):
    pass


class ModuleResponse(ModuleBase):
    id: int

    class Config:
        from_attributes = True


class ModuleAssign(BaseModel):
    module_id: int


class ModuleBusinessResponse(BaseModel):
    id: int
    business_id: int
    module_id: int

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    user_id: int
    business_id: int
    role: str
    rules: Optional[Dict] = {}
    salary: Optional[int] = None


class RoleResponse(BaseModel):
    id: int
    user_id: int
    business_id: Optional[int]
    role: str
    rules: Optional[Dict]
    salary: Optional[int]

    class Config:
        from_attributes = True