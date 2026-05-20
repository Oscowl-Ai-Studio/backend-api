from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
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
    hashed_password = Column(String, nullable=False) # Necessary for the Auth Task

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
    
    # Foreign Key (The link between tables)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Back-relationship to the User
    owner = relationship("User", back_populates="workspaces")