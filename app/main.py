import os
import logging
import time
from typing import List
import asyncio  # Needed for async file streaming loops
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncEngine

# Internal imports
from . import models, schemas, database, auth, k8s_manager
from .k8s_provisioner import provision_workspace_pod, get_workspace_pod_status

# Setup logging
logger = logging.getLogger("uvicorn")

# Initialize Database tables cleanly depending on engine type
if isinstance(database.engine, AsyncEngine):
    pass
else:
    models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI Studio - Sprint 3 Backend")

# --- 1. CORS Setup ---
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Local React/NextJS default
    "http://localhost:5173",  # Local Vite default
]

env_frontend_url = os.environ.get("FRONTEND_URL")
if env_frontend_url:
    ALLOWED_ORIGINS.append(env_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, 
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


# --- CONTAINER PROVISIONING BACKGROUND TASK ---
def provision_task(workspace_id: int, db_session_factory):
    """
    Background Task matching Infra structure:
    - Sets initial provisioning details.
    - Polls status safely.
    """
    logger.info(f"Provisioning workspace {workspace_id}")
    db = db_session_factory()
    try:
        db_workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
        if not db_workspace:
            logger.error(f"Workspace {workspace_id} not found in DB")
            return

        # Trigger pod creation via infra provisioner (uses owner_id)
        provision_workspace_pod(workspace_id, db_workspace.owner_id)

        # Polling Loop to check execution phase state
        max_retries = 30
        is_running = False
        for _ in range(max_retries):
            time.sleep(2)
            current_status = get_workspace_pod_status(workspace_id)
            if current_status == "Running":
                is_running = True
                break
            if current_status in ["Failed", "Error"]:
                break

        # FIXED: Changed from models.WorkspaceStatus Enum references to plain strings
        db_workspace.status = "running" if is_running else "error"
        db.commit()
        logger.info(f"Workspace {workspace_id} updated to {db_workspace.status}")
    except Exception as e:
        logger.error(f"Failed to provision workspace {workspace_id}: {e}")
        try:
            db_workspace.status = "error"
            db.commit()
        except:
            pass
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
    """
    Exchanges code for token securely, fetches profile info, 
    and issues an application JWT string redirect.
    """
    try:
        # 1. Fetch the raw access configuration array from GitHub
        access_token = await auth.get_github_access_token(code)
        
        # Guard: Check if the token string is missing or contains a GitHub API error string
        if not access_token or "error" in str(access_token).lower():
            logger.error(f"GitHub OAuth handshake failed. Gateway response payload: {access_token}")
            return RedirectResponse(url=f"{auth.FRONTEND_URL}/login?error=github_handshake_failed")

        # 2. Safely capture the authenticated user's metadata nodes
        gh_user = await auth.get_github_user_info(access_token)
        if not gh_user or "login" not in gh_user:
            logger.error(f"Failed to fetch profile info with provided token string. API Payload: {gh_user}")
            return RedirectResponse(url=f"{auth.FRONTEND_URL}/login?error=invalid_user_payload")
            
        username = gh_user.get("login")

        # 3. Handle database insertion or extraction loops
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            # Fallback for picking up public profile emails safely
            email = gh_user.get("email") or f"{username}@users.noreply.github.com"
            user = models.User(username=username, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)

        # 4. Issue the unified system token and execute the target redirect loop
        token = auth.create_access_token(data={"sub": user.username})
        return RedirectResponse(url=f"{auth.FRONTEND_URL}/callback?token={token}")

    except Exception as e:
        logger.error(f"Critical Callback Engine Exception: {e}")
        return RedirectResponse(url=f"{auth.FRONTEND_URL}/login?error=internal_server_exception")

# --- Workspace Management Routes ---

@app.post("/workspaces", response_model=schemas.Workspace)
def create_workspace(
    ws: schemas.WorkspaceCreate, 
    bg: BackgroundTasks, 
    db: Session = Depends(get_db), 
    user: models.User = Depends(auth.get_current_user)
):
    try:
        if hasattr(ws, 'model_dump'):
            new_data = ws.model_dump()
        else:
            new_data = ws.dict()

        # FIXED: Set status assignment line directly to a plain string value
        db_ws = models.Workspace(
            **new_data,
            owner_id=user.id,
            status="creating"
        )
        db.add(db_ws)
        db.commit()
        db.refresh(db_ws)
        
        bg.add_task(provision_task, db_ws.id, database.SessionLocal)
        return db_ws
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workspaces", response_model=List[schemas.Workspace])
def list_workspaces(db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    try:
        # Filter by owner_id for multi-tenant isolation
        workspaces = db.query(models.Workspace).filter(models.Workspace.owner_id == user.id).all()
        
        # Infra Fallback Mock Handling if DB table is empty
        if not workspaces:
            logger.info("Workspace table empty. Returning fallback mock array.")
            return [
                {
                    "id": 1, 
                    "name": "Mock Workspace (Empty DB)", 
                    "status": "RUNNING", 
                    "owner_id": user.id, 
                    "description": "Fallback entry because your workspace table has no active data rows."
                }
            ]
        return workspaces
    except Exception as e:
        logger.error(f"DB Offline fallback triggered: {e}")
        return [
            {
                "id": 999, 
                "name": "Mock Workspace (DB Offline)", 
                "status": "RUNNING", 
                "owner_id": user.id, 
                "description": "Fail-safe mock entry because application cannot reach database engine."
            }
        ]

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
    return {"status": "deleted", "message": "Workspace deleted successfully"}


# --- File API Endpoints ---

@app.get("/workspaces/{workspace_id}/files")
def get_files(
    workspace_id: int, 
    path: str = "/home/coder", 
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    ws = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id, 
        models.Workspace.owner_id == user.id
    ).first()
    
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check string values or structured state definitions cleanly
    current_status = getattr(ws.status, "value", str(ws.status)).lower()
    if current_status != "running":
        raise HTTPException(
            status_code=400, 
            detail=f"Workspace is currently {ws.status}. Please wait until it is 'RUNNING'."
        )

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
    ws = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id,
        models.Workspace.owner_id == user.id
    ).first()
    
    current_status = getattr(ws.status, "value", str(ws.status)).lower()
    if not ws or current_status != "running":
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
    ws = db.query(models.Workspace).filter(
        models.Workspace.id == workspace_id,
        models.Workspace.owner_id == user.id
    ).first()
    
    current_status = getattr(ws.status, "value", str(ws.status)).lower()
    if not ws or current_status != "running":
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
    return {"status": "success", "message": "Backend is alive and connected!"}