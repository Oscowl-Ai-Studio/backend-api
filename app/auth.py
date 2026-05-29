import os
from datetime import datetime, timezone, timedelta  # ← Updated timezone here
from typing import Optional
from jose import jwt, JWTError
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse  # ← Added this import
from fastapi.security import APIKeyHeader 
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from . import database, models

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "my_super_secret_key")
ALGORITHM = "HS256"

# --- THIS IS THE CHANGE ---
# name="Authorization" tells Swagger to send the token in the headers
# This will show the "Value" box you are looking for
oauth2_scheme = APIKeyHeader(name="Authorization", auto_error=False)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)  # ← Changed here
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception

    try:
        # If the user pasted "Bearer <token>" into the Value box, we need to remove "Bearer "
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.username == username).first()
    
    # Failsafe for your admin user
    if user is None and username == "admin":
        return models.User(id=1, username="admin", email="admin@example.com")
        
    if user is None:
        raise credentials_exception
    return user

class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 1. Allow public paths
        public_prefixes = ["/auth/github/login", "/login", "/health", "/docs", "/openapi.json"]
        if any(path.startswith(prefix) for prefix in public_prefixes):
            return await call_next(request)

        # 2. Allow GET requests to workspaces (public viewing)
        if request.method == "GET" and path.startswith("/workspaces"):
            return await call_next(request)

        # 3. Check for the Authorization Header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # Changed from raise HTTPException to return JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required: No token provided"}
            )

        # 4. ROBUST TOKEN EXTRACTION
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = auth_header  

        # 5. VALIDATION
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return await call_next(request)
        except Exception as e:
            print(f"Token Error: {e}") 
            # Changed from raise HTTPException to return JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"}
            )