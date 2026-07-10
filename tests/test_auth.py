import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)

# FIXED: Removed @pytest.mark.asyncio because TestClient runs synchronously here
@patch("app.auth.get_github_access_token", new_callable=AsyncMock)
@patch("app.auth.get_github_user_info", new_callable=AsyncMock)
def test_github_callback_success(mock_user_info, mock_access_token):
    """Test successful GitHub login and redirection with JWT token"""
    
    # 1. Setup mock responses
    mock_access_token.return_value = "mock_github_access_token_123"
    mock_user_info.return_value = {
        "login": "TestDeveloper",
        "email": "test@example.com"
    }
    
    # 2. Simulate hitting the callback endpoint with a temporary code
    response = client.get("/auth/github/callback?code=fake_github_code", follow_redirects=False)
    
    # 3. Assertions
    assert response.status_code == 307  # Redirect status code
    assert "callback?token=" in response.headers["location"]
    
    # Ensure our auth functions were actually invoked
    mock_access_token.assert_called_once_with("fake_github_code")
    mock_user_info.assert_called_once_with("mock_github_access_token_123")


# FIXED: Removed @pytest.mark.asyncio because TestClient runs synchronously here
@patch("app.auth.get_github_access_token", new_callable=AsyncMock)
def test_github_callback_handshake_failed(mock_access_token):
    """Test graceful handling when GitHub rejects the auth code"""
    
    # Simulate a bad token exchange response payload from GitHub
    mock_access_token.return_value = {"error": "bad_verification_code"}
    
    response = client.get("/auth/github/callback?code=expired_code", follow_redirects=False)
    
    assert response.status_code == 307
    assert "error=github_handshake_failed" in response.headers["location"]