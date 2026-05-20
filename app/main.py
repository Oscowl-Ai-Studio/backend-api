from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
import logging

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

# Register JWT Middleware (Protects your routes)
app.add_middleware(auth.JWTMiddleware)

# Database Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 1. Health Check ---
@app.get("/health")
def health_check():
    return {"status": "success", "message": "Backend is alive and connected!"}

# --- 2. Task: Basic Auth Endpoint (Stub Login) ---
# Credentials: username: admin / password: password123
@app.post("/login")
def login(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    if login_data.username == "admin" and login_data.password == "password123":
        # 1. Check if the admin exists in the ACTUAL database
        user = db.query(models.User).filter(models.User.username == "admin").first()
        
        # 2. If not, SAVE them to the database now
        if not user:
            user = models.User(
                id=1, # Match the failsafe ID
                username="admin", 
                email="admin@example.com", 
                hashed_password="hashed_password"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # 3. Now create the token
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
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        # 1. Print for debugging (check your terminal after clicking Execute)
        print(f"Creating workspace for user ID: {current_user.id}")

        # 2. Prepare the data
        # Check Pydantic version and convert to dict
        if hasattr(workspace, 'model_dump'):
            new_data = workspace.model_dump() # Pydantic v2
        else:
            new_data = workspace.dict()       # Pydantic v1

        # 3. Create the Database Object and manually add owner_id
        db_workspace = models.Workspace(
            **new_data, 
            owner_id=current_user.id
        )

        db.add(db_workspace)
        db.commit()
        db.refresh(db_workspace)
        return db_workspace

    except Exception as e:
        # This will show the real error in your terminal
        print(f"!!! WORKSPACE POST ERROR: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workspaces/", response_model=List[schemas.Workspace])
def list_workspaces(db: Session = Depends(get_db)):
    # This is also protected by the middleware but doesn't need current_user logic
    return db.query(models.Workspace).all()

@app.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, db: Session = Depends(get_db)):
    workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    db.delete(workspace)
    db.commit() 
    return {"message": "Workspace deleted successfully"}