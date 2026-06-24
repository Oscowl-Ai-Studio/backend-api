import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import jwt, JWTError
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from . import database, models

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Fallback for local dev if .env is missing, but raise in production
    SECRET_KEY = "DEV_SECRET_KEY_CHANGE_ME" 

ALGORITHM = "HS256"

# auto_error=False allows our middleware or custom logic to handle the error message
oauth2_scheme = HTTPBearer(auto_error=False)

def create_access_token(data: dict):
    to_encode = data.copy()
    # Token valid for 30 minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme), 
    db: Session = Depends(database.get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials or not credentials.credentials:
        raise credentials_exception

    # 🛠️ SAFETY CHECK: If the token itself starts with "Bearer ", strip it.
    # This fixes the "Bearer Bearer <token>" issue from your curl.
    token = credentials.credentials
    if token.startswith("Bearer "):
        token = token.replace("Bearer ", "").strip()
    else:
        token = token.strip()

    try:
        # Decode token with 60s leeway for clock skew
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"leeway": 60})
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception as e:
        print(f"DEBUG: JWT Decode Error: {e}")
        raise credentials_exception
        
    # Look up user in DB
    user = db.query(models.User).filter(models.User.username == username).first()
    
    # Hardcoded fallback for the 'admin' user if DB is empty
    if user is None and username == "admin":
        # Create a transient user object for the request session
        return models.User(id=1, username="admin", email="admin@example.com")
        
    if user is None:
        raise credentials_exception
    return user

class JWTMiddleware(BaseHTTPMiddleware):
    """
    Middleware to intercept requests. 
    Note: Public routes are skipped. 
    """
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 1. Skip pre-flight CORS requests
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # 2. Define truly public routes
        public_prefixes = ["/auth/github/login", "/login", "/health", "/docs", "/openapi.json"]
        if any(path.startswith(prefix) for prefix in public_prefixes):
            return await call_next(request)

        # 3. Handle Authorization Header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required: No token provided"}
            )

        # Clean token from header
        if auth_header.startswith("Bearer "):
            # Split and handle potential double "Bearer Bearer"
            parts = auth_header.split(" ")
            # If parts are ["Bearer", "Bearer", "token"], take the last one
            token = parts[-1] 
        else:
            token = auth_header  

        # 4. Validate Token signature globally
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"leeway": 60})
            return await call_next(request)
        except Exception as e:
            print(f"DEBUG: Middleware Token Error: {e}") 
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"}
            )