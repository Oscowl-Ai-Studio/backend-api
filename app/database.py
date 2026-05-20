#import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
#from dotenv import load_dotenv

# 1. Load variables from the .env file
#load_dotenv()

# PASTE YOUR AZURE STRING HERE
#DATABASE_URL = "postgresql://postgresql:OSCOWL@123@postgresqldatabasevathsalya.postgres.database.azure.com:5432/postgres?sslmode=require"

# Build the connection string using the environment variables
#user = os.getenv("PGUSER")
#password = os.getenv("PGPASSWORD")
#host = os.getenv("PGHOST")
#port = os.getenv("PGPORT")
#db = os.getenv("PGDATABASE")
#ssl = os.getenv("PGSSLMODE")

DATABASE_URL = "postgresql://postgresql:OSCOWL%40123@postgresqldatabasevathsalya.postgres.database.azure.com:5432/postgres?sslmode=require"
print(f"DEBUG: Using DATABASE_URL: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()