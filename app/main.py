from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
import logging
import time # Added for provisioning simulation

# Internal imports
from . import models, schemas, database, auth

# Initialize Database tables
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

# Register JWT Middleware
app.add_middleware(auth.JWTMiddleware)

# Database Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 1. Provisioning Stub (Sprint 2 Requirement) ---
def provision_workspace(workspace_id: int):
    """
    Simulates Kubernetes provisioning. 
    Logs the action and updates status to 'running' after a delay.
    """
    db = database.SessionLocal()
    try:
        print(f"--- Provisioning workspace {workspace_id} ---")
        time.sleep(10)  # Simulate container setup time
        workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
        if workspace and workspace.status != "deleted":
            workspace.status = "running"
            db.commit()
            print(f"--- Workspace {workspace_id} is now RUNNING ---")
    finally:
        db.close()

# --- 2. Health Check ---
@app.get("/health")
def health_check():
    return {"status": "success", "message": "Backend is alive and connected!"}

# --- 3. Login Endpoint (Stub Login) ---
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

# --- 4. FULL CRUD FOR WORKSPACES ---

# CREATE (POST)
@app.post("/workspaces/", response_model=schemas.Workspace)
def create_workspace(
    workspace: schemas.WorkspaceCreate, 
    background_tasks: BackgroundTasks, # Added for provisioning
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        workspace_data = workspace.model_dump() if hasattr(workspace, 'model_dump') else workspace.dict()
        
        # Store in DB with status 'creating'
        db_workspace = models.Workspace(
            **workspace_data, 
            owner_id=current_user.id,
            status="creating" # Lifecycle start
        )

        db.add(db_workspace)
        db.commit()
        db.refresh(db_workspace)

        # Trigger Asynchronous Provisioning
        background_tasks.add_task(provision_workspace, db_workspace.id)
        
        return db_workspace

    except Exception as e:
        print(f"!!! WORKSPACE POST ERROR: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# LIST (GET) - Extracts user ID from JWT
@app.get("/workspaces/", response_model=List[schemas.Workspace])
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Filter by authenticated user and only show non-deleted workspaces
    return db.query(models.Workspace).filter(
        models.Workspace.owner_id == current_user.id,
        models.Workspace.is_active == True
    ).all()

# GET SINGLE WORKSPACE
@app.get("/workspaces/{workspace_id}", response_model=schemas.Workspace)
def get_workspace(
    workspace_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    workspace = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id,
        models.Workspace.owner_id == current_user.id,
        models.Workspace.is_active == True
    ).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

# DELETE (Soft Delete)
@app.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    workspace = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id,
        models.Workspace.owner_id == current_user.id
    ).first()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # IMPLEMENT SOFT DELETE
    workspace.is_active = False
    workspace.status = "deleted"
    db.commit() 
    
    return {"message": "Workspace soft-deleted successfully"}

# GitHub Login Redirect
@app.get("/auth/github/login")
def github_login():
    client_id = "YOUR_GITHUB_CLIENT_ID" 
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo"
    return RedirectResponse(url=github_auth_url)