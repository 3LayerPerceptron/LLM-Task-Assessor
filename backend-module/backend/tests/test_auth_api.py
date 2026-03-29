from backend.src import settings
from backend.src.database.user import User
from backend.src.api.models import JWTToken

from datetime import datetime, timezone, timedelta

import jwt
from httpx import AsyncClient


async def test_nonexistent_access_token(api: AsyncClient) -> None:
    """Test access to protected route without token."""
    response = await api.get(f"/auth/me")
    assert response.status_code == 401


async def test_invalid_login(api: AsyncClient, user: User) -> None:
    """Test login with invalid credentials."""
    response = await api.post(
        "/auth/basic/login",
        data={
            "username": user.email,
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401


async def test_get_current_user(
    api: AsyncClient,
    token: str
) -> None:
    """Test retrieval of current user information."""
    response = await api.get(
        f"/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()
    data = response.json()
    assert "email" in data
    assert "name" in data
    assert "description" in data
    assert "groups" in data


async def test_group_privelege(
    api: AsyncClient,
    token: str
) -> None:
    """Test access to a route requiring specific group membership."""
    response = await api.get(
        f"/auth/confidential",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


async def test_user_password_registration(
    api: AsyncClient
) -> None:
    """Test user registration."""
    response = await api.post(
        "/auth/basic/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "password"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "name" in data
    assert "description" in data
    assert "groups" in data

    # Login test for just created user
    response = await api.post(
        "/auth/basic/login",
        data={
            "username": "test@example.com",
            "password": "password"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


async def test_invalid_access_token(
    api: AsyncClient
) -> None:
    """Test invalid access token."""
    response = await api.get(
        "/auth/me",
        headers={"Authorization": f"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImlhdCI6MTUxNjIzOTAyMn0.KMUFsIDTnFmyG3nMiGM6H9FNFUROf3wh7SmqJp-QV30"}
    )
    assert response.status_code == 403


async def test_expired_access_token(
    api: AsyncClient,
    user: User
) -> None:
    """Test expired access token."""
    now = datetime.now(timezone.utc)
    access_token = jwt.encode(
        payload={
            "sub": str(user.id),
            "iat": now - timedelta(seconds=60),
            "exp": now - timedelta(seconds=30)
        },
        key=settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    response = await api.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 401


async def test_invalid_refresh_token(
    api: AsyncClient
) -> None:
    """Test refresh access token with invalid refresh token."""
    response = await api.post(
        "/auth/token/refresh",
        params={
            "refresh_token": "this is not a valid refresh token"
        }
    )
    assert response.status_code == 403


async def test_refresh_token(
    api: AsyncClient,
    jwt: JWTToken
) -> None:
    """Test refresh access token normally."""
    response = await api.post(
        "/auth/token/refresh",
        params={
            "refresh_token": jwt.refresh_token
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    access_token = data["access_token"]

    # Test if new access token could be used
    response = await api.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200


async def test_loggout(
    api: AsyncClient,
    jwt: JWTToken
) -> None:
    """Test logout user."""
    response = await api.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {jwt.access_token}"}
    )
    assert response.status_code == 200

    # Try to refresh access token again
    response = await api.post(
        "/auth/token/refresh",
        params={
            "refresh_token": jwt.refresh_token
        }
    )
    assert response.status_code == 403
