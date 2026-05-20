from pydantic import BaseModel, EmailStr
from typing import Optional, List

# --- User Schemas ---
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    class Config:
        from_attributes = True

# --- Workspace Schemas ---
class WorkspaceBase(BaseModel):
    name: str
    description: Optional[str] = None

class WorkspaceCreate(WorkspaceBase):
    pass

class Workspace(WorkspaceBase):
    id: int
    owner_id: int
    class Config:
        from_attributes = True

# --- Token Schema ---
class Token(BaseModel):
    access_token: str
    token_type: str

# --- THE MISSING CLASS: LoginRequest ---
# This is what main.py is looking for
class LoginRequest(BaseModel):
    username: str
    password: str