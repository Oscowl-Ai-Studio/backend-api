from pydantic import BaseModel
from typing import Optional, List

class WorkspaceBase(BaseModel):
    name: str
    description: Optional[str] = None

class WorkspaceCreate(WorkspaceBase):
    pass

class Workspace(WorkspaceBase):
    id: int
    status: str
    owner_id: int
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str