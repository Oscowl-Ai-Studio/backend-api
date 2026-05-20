# Workspace API - AI Studio Backend

This is the backend API for the AI Studio project. It handles user authentication and workspace management using FastAPI and PostgreSQL.

## 🚀 Features
- **FastAPI Framework**: High-performance Python API.
- **JWT Authentication**: Secure login with protected routes.
- **Database Schema**: Managed with SQLAlchemy (PostgreSQL/Azure/Neon).
- **Swagger Documentation**: Interactive API testing at `/docs`.

## 🛠️ Setup Instructions

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd backend-api
```

### 2. Set up Virtual Environment
```bash
python -m venv venv
source venv/Scripts/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Database Sync
To establish the tables in your database, run:
```bash
python sync_db.py
```

### 4. Run the Application
```bash
uvicorn app.main:app --reload
```

## 🔑 Authentication (Stub Login)
For testing purposes, use the following credentials in the `/login` endpoint:
- **Username**: `admin`
- **Password**: `password123`

**Note**: After logging in, copy the `access_token` and use it in the Swagger Authorize button as: `Bearer <your_token>`.

## 📁 Project Structure
- `app/main.py`: API routes and logic.
- `app/models.py`: SQLAlchemy Database models.
- `app/auth.py`: JWT and Middleware security logic.
- `app/schemas.py`: Pydantic data validation.
