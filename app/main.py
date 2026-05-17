from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database, auth

# Initialize Database
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Workspace API")

# --- CORS Middleware: The "Bridge" ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the Authentication Middleware
app.add_middleware(auth.JWTMiddleware)

def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

# --- Health Check: Proof of connection for your manager ---
@app.get("/health")
def health_check():
    return {"status": "success", "message": "Backend and Frontend are connected!"}

# --- Updated Login Route: Now accepts GET to allow browser redirects ---
@app.get("/auth/github/login")
def login():
    # This redirects the user to the GitHub authorization page
    # Replace 'YOUR_GITHUB_CLIENT_ID' with your actual GitHub App Client ID
    client_id = "YOUR_GITHUB_CLIENT_ID" 
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo"
    return RedirectResponse(url=github_auth_url)

# --- Keep your existing Workspace routes ---
@app.post("/workspaces/", response_model=schemas.Workspace)
def create_workspace(workspace: schemas.WorkspaceCreate, db: Session = Depends(get_db)):
    db_workspace = models.Workspace(**workspace.dict())
    db.add(db_workspace)
    db.commit()
    db.refresh(db_workspace)
    return db_workspace

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