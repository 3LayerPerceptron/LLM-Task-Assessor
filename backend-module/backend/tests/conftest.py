import pytest_asyncio as pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

import typing as t

from backend.src import app
from backend.src.config import settings
from backend.src.database import init, engine


@pytest.fixture(scope="session", autouse=True)
async def session() -> t.AsyncGenerator[AsyncSession, None]:
    """Initialize DB and provide a session for the whole test session."""
    async with AsyncSession(engine) as session:
        await init()
        yield session


@pytest.fixture(scope="module")
async def api() -> t.AsyncGenerator[AsyncClient, None]:
    """ASGI test client with the correct base URL."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=f"http://testserver/api/{settings.API_VERSION}",
    ) as client:
        yield client


@pytest.fixture
def auth_headers() -> dict:
    """Authorization header with the configured API token."""
    return {"Authorization": f"Bearer {settings.API_TOKEN}"}


@pytest.fixture
def bad_auth_headers() -> dict:
    return {"Authorization": "Bearer wrong-token"}
