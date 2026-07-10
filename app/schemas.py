from pydantic import BaseModel, ConfigDict
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
    
    # FIXED: Replaced class-based Config with the clean Pydantic V2 ConfigDict wrapper
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    
# --- Added for Sprint 3 File API Task ---
class FileWriteRequest(BaseModel):
    content: str