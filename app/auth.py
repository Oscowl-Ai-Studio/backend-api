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
    raise RuntimeError("PRODUCTION ERROR: SECRET_KEY environment variable is not set!")

ALGORITHM = "HS256"

# 🎯 PRODUCTION FIX: Changed from APIKeyHeader to HTTPBearer.
# This natively configures Swagger UI to show a clean "Bearer" input box
# and automatically prepends "Bearer " to requests correctly.
oauth2_scheme = HTTPBearer(auto_error=False)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials or not credentials.credentials:
        raise credentials_exception

    token = credentials.credentials.strip()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception as e:
        print(f"get_current_user JWT Decode Error: {e}")
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
        
        # 🎯 1. PRODUCTION MUST: Safely allow browser CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # 2. Allow public endpoints to skip token validation
        public_prefixes = ["/auth/github/login", "/login", "/health", "/docs", "/openapi.json"]
        if any(path.startswith(prefix) for prefix in public_prefixes):
            return await call_next(request)

        # 3. Allow public GET requests to read workspaces
        if request.method == "GET" and path.startswith("/workspaces"):
            return await call_next(request)

        # 🎯 PRODUCTION SECURITY: Completely removed the "referer" bypass check.
        # Every modification request (POST, PUT, DELETE) MUST have a valid token.

        # 4. Check for the Authorization Header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required: No token provided"}
            )

        # 5. Extract token from header
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = auth_header  

        # 6. Validate Token Cryptography
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return await call_next(request)
        except Exception as e:
            print(f"Token Error: {e}") 
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"}
            )