from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

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
    # REQUIRED: This matches the 'template' field we added to the model
    template: Optional[str] = "default"

class WorkspaceCreate(WorkspaceBase):
    """Schema for creating a workspace"""
    pass

class Workspace(WorkspaceBase):
    """Schema for the API response (Includes ID and Status)"""
    id: int
    owner_id: int
    status: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Authentication Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    """Schema for the JSON login body"""
    username: str
    password: str