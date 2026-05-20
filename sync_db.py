from app.database import engine
from app.models import Base
import app.models as models  # Ensures models are loaded before sync

def sync_database():
    print("--- Database Schema Sync ---")
    print("Connecting to your cloud database...")
    
    try:
        # This command translates your SQLAlchemy models into actual SQL tables
        # It creates 'users' and 'workspaces' with their relationships
        Base.metadata.create_all(bind=engine)
        print("SUCCESS: Tables 'users' and 'workspaces' created successfully!")
        
    except Exception as e:
        print(f"ERROR: Failed to sync database: {e}")

if __name__ == "__main__":
    sync_database()
