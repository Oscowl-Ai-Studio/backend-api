from app.database import engine
from sqlalchemy import text

print("Connecting to local database...")
try:
    with engine.connect() as conn:
        # This converts your status column from the old Enum type to a flexible String layout
        conn.execute(text("ALTER TABLE workspaces ALTER COLUMN status TYPE VARCHAR(255);"))
        conn.commit()
    print("🎉 Success! Your local database column was successfully converted to a standard string layout!")
except Exception as e:
    print(f"❌ Error updating database: {e}")