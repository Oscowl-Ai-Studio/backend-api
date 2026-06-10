import enum  # ← 1. ADDED THIS IMPORT AT THE TOP
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Enum  # ← 2. ADDED Enum HERE
from sqlalchemy.orm import relationship
from .database import Base

# 3. DEFINE THE STATUS LIFECYCLE ENUM
class WorkspaceStatus(str, enum.Enum):
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"

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
    """
    Translates the 'workspaces' table plan into a SQLAlchemy model.
    Includes a Foreign Key linking it to the owner.
    """
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # 4. ADDED STATUS COLUMN WITH A DEFAULT VALUE OF 'creating'
    status = Column(
        Enum(WorkspaceStatus), 
        default=WorkspaceStatus.CREATING, 
        nullable=False
    )
    
    # Foreign Key (The link between tables)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Back-relationship to the User
    owner = relationship("User", back_populates="workspaces")