import os
import time
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError


# We define the variables directly here to avoid system environment conflicts
#DB_USER = "utkarshasalokhe"
#DB_PASS = "Ups292001"
#DB_HOST = "db"
#DB_PORT = "5432"
#DB_NAME = "utkarshasalokhe_db"

DATABASE_URL = f"postgresql://utkarshasalokhe:Ups292001@db:5432/utkarshasalokhe_db"

#print(f"DEBUG: Attempting to connect to: {DATABASE_URL}")

# Retry logic to wait for the database
def create_engine_with_retry():
    while True:
        try:
            engine = create_engine(DATABASE_URL)
            engine.connect()
            print("Successfully connected to the database!")
            return engine
        except OperationalError:
            print("Database not ready, waiting 2 seconds...")
            time.sleep(2)

engine = create_engine_with_retry()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()