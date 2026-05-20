from app.database import engine
try:
    with engine.connect() as conn:
        print("SUCCESS! Connected to Azure!")
except Exception as e:
    print(f"FAILED: {e}")