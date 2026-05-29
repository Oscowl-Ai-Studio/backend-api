from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List

# ==========================================
# USER SCHEMAS
# ==========================================

class UserBase(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "sunsung_dev"}, description="The unique username for account identification")
    email: EmailStr = Field(..., json_schema_extra={"example": "sunsung@example.com"}, description="The primary communication email address")

class UserCreate(UserBase):
    password: str = Field(..., json_schema_extra={"example": "SecurePassword123!"}, description="The raw password string, hashed before saving")

class User(UserBase):
    id: int = Field(..., json_schema_extra={"example": 1}, description="The unique auto-incremented database ID")
    
    # This line below fixes warning 1!
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# WORKSPACE SCHEMAS
# ==========================================

class WorkspaceBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Data-Analysis-Pod"}, description="The display name of the developer workspace")
    description: Optional[str] = Field(None, json_schema_extra={"example": "Jupyter notebook instance for model evaluation"}, description="Detailed purpose of the workspace environment")

class WorkspaceCreate(WorkspaceBase):
    pass  

class Workspace(WorkspaceBase):
    id: int = Field(..., json_schema_extra={"example": 42}, description="The unique identification number of the workspace")
    owner_id: int = Field(..., json_schema_extra={"example": 1}, description="The database ID of the user who owns this workspace")

    # This line below fixes warning 2!
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# AUTH & TOKEN SCHEMAS
# ==========================================

class Token(BaseModel):
    access_token: str = Field(..., json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}, description="The signed JWT access token")
    token_type: str = Field(..., json_schema_extra={"example": "bearer"}, description="The token validation type wrapper")

class LoginRequest(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "admin"}, description="Account username")
    password: str = Field(..., json_schema_extra={"example": "password123"}, description="Account password")