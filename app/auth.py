import os
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import jwt
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from . import database, models

SECRET_KEY = os.getenv("SECRET_KEY", "sprint3-secret-123")
ALGORITHM = "HS256"
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# HTTPBearer automatically generates the elegant "Authorize (Lock icon)" box in your Swagger docs!
oauth2_scheme = HTTPBearer(auto_error=False)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token missing")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user = db.query(models.User).filter(models.User.username == username).first()
        
        # Failsafe for your local admin tester account if user table is fresh/empty
        if not user and username == "admin":
            return models.User(id=1, username="admin", email="admin@example.com")
            
        if not user: 
            raise Exception()
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

# GitHub OAuth Network Communications Drivers
async def get_github_access_token(code: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://github.com/login/oauth/access_token",
            params={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code},
            headers={"Accept": "application/json"}
        )
        return res.json().get("access_token")

async def get_github_user_info(token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
        return res.json()


class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 1. ALLOW public authentication and core documentation paths without restriction
        if any(path.startswith(p) for p in ["/auth/github", "/login", "/docs", "/openapi.json", "/health"]):
            return await call_next(request)
        
        # 2. Allow public access ONLY to the listing route to match infra's workspace view rule
        if request.method == "GET" and (path == "/workspaces" or path == "/workspaces/"):
            return await call_next(request)
            
        # 3. Traefik Gateway Routing Exception: Allow traffic straight to the active container pods
        # This keeps backend auth from dropping proxied connections to individual code-server/ttyd instances
        if path.startswith("/workspace/"):
            return await call_next(request)
        
        if request.method == "OPTIONS":
            return await call_next(request)

        # 4. Check tokens on all explicit CRUD execution routes (Files, Terminal WebSockets)
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized: No header provided"})
        
        try:
            token = auth_header.split(" ")[-1]
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return await call_next(request)
        except:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized: Invalid token"})