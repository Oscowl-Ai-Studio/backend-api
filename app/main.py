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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
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
@app.post("/workspaces/", response_model=schemas.Workspace)
def create_workspace(
    workspace: schemas.WorkspaceCreate, 
    background_tasks: BackgroundTasks,  # ← Injected BackgroundTasks here
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        print(f"Creating workspace for user ID: {current_user.id}")

        if hasattr(workspace, 'model_dump'):
            new_data = workspace.model_dump()
        else:
            new_data = workspace.dict()

        # Creates row - will default to WorkspaceStatus.CREATING automatically
        db_workspace = models.Workspace(
            **new_data, 
            owner_id=current_user.id
        )

        db.add(db_workspace)
        db.commit()
        db.refresh(db_workspace)

        # Trigger the provisioning background worker asynchronously!
        # Pass database.SessionLocal so the background thread can safely create its own connection context.
        background_tasks.add_task(provision_workspace, db_workspace.id, database.SessionLocal)

        return db_workspace

    except Exception as e:
        print(f"!!! WORKSPACE POST ERROR: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workspaces/", response_model=List[schemas.Workspace])
def list_workspaces(db: Session = Depends(get_db)):
    return db.query(models.Workspace).all()

@app.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, db: Session = Depends(get_db)):
    workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    db.delete(workspace)
    db.commit() 
    return {"message": "Workspace deleted successfully"}