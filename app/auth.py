import os
from datetime import datetime, timedelta
from jose import jwt
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "my_super_secret_key")
ALGORITHM = "HS256"

# Function to ISSUE tokens
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Middleware for VALIDATION
class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. DEFINE PUBLIC PATHS
        # These routes will bypass the JWT check
        public_paths = [
            "/auth/github/login", 
            "/health",           # Added for your connection test
            "/docs", 
            "/openapi.json", 
            "/favicon.ico"
        ]

        # 2. CHECK IF PATH IS PUBLIC OR A GET REQUEST TO WORKSPACES
        # We allow GET requests to /workspaces/ so the UI can list them
        is_public = request.url.path in public_paths
        is_workspace_get = (request.method == "GET" and request.url.path.startswith("/workspaces/"))

        if is_public or is_workspace_get:
            return await call_next(request)

        # 3. PROTECT ALL OTHER REQUESTS (POST, DELETE, PUT)
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Authentication required: Missing or invalid token"
            )

        token = auth_header.split(" ")[1]
        
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid or expired token"
            )

        return await call_next(request)