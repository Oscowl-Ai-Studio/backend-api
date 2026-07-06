import logging
import time
from typing import List
import asyncio  # Needed for async file streaming loops
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from . import models, schemas, database, auth, k8s_manager

# Setup logging
logger = logging.getLogger("uvicorn")

# Initialize Database tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI Studio - Sprint 3 Backend")

# 1. CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# 2. JWT Middleware (Protects all routes except Auth and Docs)
app.add_middleware(auth.JWTMiddleware)

# Database Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- GitHub OAuth Routes ---

@app.get("/auth/github")
async def github_login():
    """Redirects user to GitHub for authorization"""
    url = f"https://github.com/login/oauth/authorize?client_id={auth.GITHUB_CLIENT_ID}&scope=user:email"
    return RedirectResponse(url=url)

@app.get("/auth/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """Exchanges code for token, fetches user info, and returns our JWT"""
    try:
        # 1. Exchange code for GitHub Access Token
        access_token = await auth.get_github_access_token(code)
        
        # If code was already used or expired, GitHub returns None
        if not access_token:
            logger.error("GitHub exchange failed: Code already used or expired.")
            return RedirectResponse(url=f"{auth.FRONTEND_URL}/login?error=invalid_code")

        # 2. Get User Info from GitHub
        gh_user = await auth.get_github_user_info(access_token)
        username = gh_user.get("login")
        if not username:
            raise HTTPException(status_code=400, detail="Invalid GitHub user data")

        # 3. Create or Get User in our Database
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            email = gh_user.get("email") or await auth.get_github_emails(access_token)
            user = models.User(username=username, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)

        # 4. Generate our internal JWT token
        token = auth.create_access_token(data={"sub": user.username})
        
        # 5. Redirect to Frontend Dashboard
        return RedirectResponse(url=f"{auth.FRONTEND_URL}/callback?token={token}")

    except Exception as e:
        logger.error(f"Callback Error: {e}")
        return JSONResponse(status_code=500, content={"detail": "Authentication failed"})

# --- Workspace & K8s Integration ---

def provision_task(workspace_id: int, username: str, db_factory):
    """
    Background Task: 
    - Triggers K8s creation.
    - Polls status until 'Running'.
    - Updates DB to 'running' or 'error'.
    """
    # Step 1: Trigger K8s pod creation
    k8s_manager.create_workspace_pod(workspace_id, username)
    
    # Step 2: Polling Loop (Sprint 3 Requirement)
    max_retries = 30  # Try for 60 seconds
    is_running = False
    
    for _ in range(max_retries):
        time.sleep(2)
        current_status = k8s_manager.get_pod_status(workspace_id)
        if current_status == "Running":
            is_running = True
            break
        if current_status in ["Failed", "Error"]:
            break
    
    # Step 3: Final DB update
    db = db_factory()
    try:
        ws = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
        if ws:
            ws.status = "running" if is_running else "error"
            db.commit()
            logger.info(f"Workspace {workspace_id} updated to {ws.status}")
    finally:
        db.close()

@app.post("/workspaces", response_model=schemas.Workspace)
def create_workspace(
    ws: schemas.WorkspaceCreate, 
    bg: BackgroundTasks, 
    db: Session = Depends(get_db), 
    user: models.User = Depends(auth.get_current_user)
):
    # Create DB entry with status 'provisioning'
    db_ws = models.Workspace(
        name=ws.name, 
        description=ws.description, 
        owner_id=user.id,
        status="provisioning"
    )
    db.add(db_ws)
    db.commit()
    db.refresh(db_ws)
    
    # Trigger background provisioning
    bg.add_task(provision_task, db_ws.id, user.username, database.SessionLocal)
    
    return db_ws

@app.get("/workspaces", response_model=List[schemas.Workspace])
def list_workspaces(db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    return db.query(models.Workspace).filter(models.Workspace.owner_id == user.id).all()

@app.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    ws = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id, 
        models.Workspace.owner_id == user.id
    ).first()
    
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    k8s_manager.delete_workspace_pod(workspace_id)
    db.delete(ws)
    db.commit()
    return {"status": "deleted"}

# --- File API ---

@app.get("/workspaces/{workspace_id}/files")
def get_files(
    workspace_id: int, 
    path: str = "/home/coder", 
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Returns directory listing from inside the running container"""
    # 1. Verify ownership
    ws = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id, 
        models.Workspace.owner_id == user.id
    ).first()
    
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # 2. STATUS CHECK: Refuse if not yet running (Sprint 3 Logic)
    if ws.status != "running":
        raise HTTPException(
            status_code=400, 
            detail=f"Workspace is currently {ws.status}. Please wait until it is 'running'."
        )

    # 3. Fetch files from K8s container
    try:
        files = k8s_manager.list_files(workspace_id, path)
        return {"path": path, "files": files}
    except Exception as e:
        logger.error(f"File API Error: {e}")
        raise HTTPException(status_code=500, detail="Could not reach container file system")


@app.post("/workspaces/{workspace_id}/files")
def write_file(
    workspace_id: int,
    path: str,
    file_data: schemas.FileWriteRequest,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Writes content into a file path inside the running container"""
    ws = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id,
        models.Workspace.owner_id == user.id
    ).first()
    
    if not ws or ws.status != "running":
        raise HTTPException(status_code=400, detail="Workspace must be actively running.")

    try:
        k8s_manager.write_file_contents(workspace_id, path, file_data.content)
        return {"status": "success", "message": f"File at {path} updated."}
    except Exception as e:
        logger.error(f"File Write Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to write file inside container.")


@app.delete("/workspaces/{workspace_id}/files")
def delete_file(
    workspace_id: int,
    path: str,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes a file or directory path inside the running container"""
    ws = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id,
        models.Workspace.owner_id == user.id
    ).first()
    
    if not ws or ws.status != "running":
        raise HTTPException(status_code=400, detail="Workspace must be actively running.")

    try:
        k8s_manager.delete_container_file(workspace_id, path)
        return {"status": "success", "message": f"Deleted {path}."}
    except Exception as e:
        logger.error(f"File Deletion Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete target container file.")

# --- WebSocket Terminal API ---

@app.websocket("/workspaces/{workspace_id}/terminal")
async def terminal_websocket_proxy(websocket: WebSocket, workspace_id: int):
    """WebSocket tunnel proxying terminal interactions into the container pod"""
    await websocket.accept()
    
    try:
        async with k8s_manager.connect_pod_terminal_stream(workspace_id) as pod_stream:
            
            async def stream_container_output_to_frontend():
                try:
                    while True:
                        output_bytes = await pod_stream.read()
                        if not output_bytes:
                            break
                        await websocket.send_text(output_bytes.decode(errors="replace"))
                except Exception:
                    pass

            asyncio.create_task(stream_container_output_to_frontend())

            while True:
                frontend_keystroke_data = await websocket.receive_text()
                await pod_stream.write(frontend_keystroke_data.encode())

    except WebSocketDisconnect:
        logger.info(f"Terminal connection closed for workspace {workspace_id}")
    except Exception as e:
        logger.error(f"WebSocket Proxy Core Failure: {e}")
        await websocket.close(code=1011)

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy"}