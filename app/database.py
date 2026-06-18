import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv  # 🌟 1. Import load_dotenv

# 🌟 2. Explicitly load the environment file variables
load_dotenv()

# 🌟 3. This will now grab the Azure URL perfectly from your .env file!
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/postgres")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 3})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()