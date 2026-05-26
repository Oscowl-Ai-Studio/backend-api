from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime # Added Boolean and DateTime
from sqlalchemy.orm import relationship
from datetime import datetime # Added for the created_at timestamp
from .database import Base

class User(Base):
    """
    Translates the 'users' table plan into a SQLAlchemy model.
    Includes fields for Basic Auth and relationships.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False) 

    # Relationship to Workspaces (One-to-Many)
    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # --- ADD THIS LINE ---
    template = Column(String, nullable=True, default="default") 
    
    status = Column(String, default="creating")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="workspaces")