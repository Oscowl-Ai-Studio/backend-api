from app.database import engine
from app.models import Base
from sqlalchemy import text

def fix_database():
    print("Connecting to database...")
    with engine.connect() as conn:
        try:
            print("Cleaning up old data...")
            # Drop tables to clear the 'NotNull' and 'Missing Column' errors
            conn.execute(text("DROP TABLE IF EXISTS workspaces CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
            conn.commit()
            print("Old tables dropped.")

            print("Recreating tables from models.py...")
            # This creates the tables fresh with the 'username' and 'description' columns
            Base.metadata.create_all(bind=engine)
            print("SUCCESS: Tables recreated successfully!")
            
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    fix_database()
