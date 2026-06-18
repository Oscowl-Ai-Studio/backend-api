import os
import time
import logging
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks  # ← Added BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List

# Internal imports
from . import models, schemas, database, auth

# Set up a logger to view provisioning logs in your terminal
logger = logging.getLogger("uvicorn")

# Initialize Database tables
from sqlalchemy.ext.asyncio import AsyncEngine  # ← Add this import near your other imports

# Initialize Database tables cleanly depending on engine type
if isinstance(database.engine, AsyncEngine):
    # If the engine is async, tables are typically managed by Alembic, 
    # so we pass here during a synchronous test collection.
    pass
else:
    # Fallback for synchronous test engines
    models.Base.metadata.create_all(bind=database.engine)
    

app = FastAPI(title="Workspace API - AI Studio")

# --- CORS Middleware ---
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Local React/NextJS default
    "http://localhost:5173",  # Local Vite default
]

# If the infrastructure team defines a FRONTEND_URL in the production environment variables, append it
env_frontend_url = os.environ.get("FRONTEND_URL")
if env_frontend_url:
    ALLOWED_ORIGINS.append(env_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Register JWT Middleware (Protects your routes)
app.add_middleware(auth.JWTMiddleware)

# Database Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- CONTAINER PROVISIONING STUB FUNCTION ---
def provision_workspace(workspace_id: int, db_session_factory):
    """
    Simulates asynchronous workspace container provisioning.
    Logs actions, waits to simulate a pod creation delay, and updates database status.
    """
    # 1. Mandatory Log print statement
    logger.info(f"Provisioning workspace {workspace_id}")
    
    # 2. Simulate background task runtime delay (e.g., waiting for K8s)
    time.sleep(2)
    
    # 3. Spin up an isolated session to update the status safely in the background thread
    db = db_session_factory()
    try:
        db_workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
        if db_workspace:
            db_workspace.status = models.WorkspaceStatus.RUNNING
            db.commit()
            logger.info(f"Workspace {workspace_id} has been provisioned successfully and is now running.")
    finally:
        db.close()


# --- 1. Health Check ---
@app.get("/health")
def health_check():
    return {"status": "success", "message": "Backend is alive and connected!"}

# --- 2. Basic Auth Endpoint (Stub Login) ---
@app.post("/login")
def login(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    if login_data.username == "admin" and login_data.password == "password123":
        user = db.query(models.User).filter(models.User.username == "admin").first()
        
        if not user:
            user = models.User(
                id=1,
                username="admin", 
                email="admin@example.com", 
                hashed_password="hashed_password"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        access_token = auth.create_access_token(data={"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer"}
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

# --- 3. GitHub Login ---
@app.get("/auth/github/login")
def github_login():
    client_id = "YOUR_GITHUB_CLIENT_ID" 
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo"
    return RedirectResponse(url=github_auth_url)

# --- 4. Protected Workspace Routes ---
# 🌟 REPLACE YOUR OLD POST ROUTE WITH THIS ENTIRE BLOCK BELOW:
@app.post("/workspaces", response_model=schemas.Workspace)
def create_workspace(
    workspace: schemas.WorkspaceCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    # 🔐 1. Enforce safety check for the authenticated user
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authentication credentials missing or invalid"
        )
    try:
        print(f"Creating workspace for user ID: {current_user.id}")

        if hasattr(workspace, 'model_dump'):
            new_data = workspace.model_dump()
        else:
            new_data = workspace.dict()

        # 🌟 2. Explicitly define fields, passing a clean string for the status
        db_workspace = models.Workspace(
            name=new_data.get("name"),
            description=new_data.get("description"),
            status="creating",  # 🎯 Explicit string prevents native PostgreSQL Enum crashes!
            owner_id=current_user.id
        )

        db.add(db_workspace)
        db.commit()
        db.refresh(db_workspace)

        # Trigger the provisioning background worker asynchronously!
        background_tasks.add_task(provision_workspace, db_workspace.id, database.SessionLocal)

        return db_workspace

    except Exception as e:
        print(f"!!! WORKSPACE POST ERROR: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/workspaces", response_model=List[schemas.Workspace])
def list_workspaces(db: Session = Depends(get_db)):
    try:
        # 1. Try to fetch real rows from the database
        workspaces = db.query(models.Workspace).all()
        
        # 2. If database is connected but has NO entries yet, return a mock array
        if not workspaces:
            logger.info("Database is connected but empty. Returning fallback mock data.")
            return [
                {
                    "id": 1, 
                    "name": "Mock Workspace (Empty DB)", 
                    "status": "RUNNING", 
                    "owner_id": 1, 
                    "description": "Fallback entry because your database table has no data rows yet."
                }
            ]
            
        # 3. If there are actual entries in the DB, return them safely
        return workspaces

    except Exception as e:
        # 4. If the database crashes or is completely offline, intercept the crash and return mock data
        logger.error(f"DB Offline fallback triggered: {e}")
        return [
            {
                "id": 999, 
                "name": "Mock Workspace (DB Offline)", 
                "status": "RUNNING", 
                "owner_id": 1, 
                "description": "Fail-safe mock entry because the application cannot communicate with the database server."
            }
        ]
@app.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, db: Session = Depends(get_db)):
    workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    db.delete(workspace)
    db.commit() 
    return {"message": "Workspace deleted successfully"}