import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# 1. Update the scheme from 'postgresql://' to 'postgresql+asyncpg://'
# Note: Azure requires '?ssl=require' for asyncpg instead of '?sslmode=require'
DATABASE_URL = "postgresql+asyncpg://postgresql:********@postgresqldatabasevathsalya.postgres.database.azure.com:5432/postgres?ssl=require"

print(f"DEBUG: Using Async DATABASE_URL: {DATABASE_URL}")

# 2. Create the Async Engine
engine = create_async_engine(
    DATABASE_URL, 
    echo=True, # Logs generated SQL queries to your terminal (great for debugging)
    pool_pre_ping=True # Ensures disconnected connections are automatically re-established
)

# 3. Create the Async Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 4. Declarative base for models
Base = declarative_base()

# 5. Async dependency for FastAPI routers
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()