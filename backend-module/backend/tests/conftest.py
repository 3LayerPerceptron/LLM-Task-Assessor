import pytest_asyncio as pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from httpx import ASGITransport, AsyncClient

import typing as t

from backend.src import app
from backend.tests import mockdata
from backend.src.config import settings
from backend.src.integration.client import (
    APIClient,
    MoodleConfig
)
from backend.src.database import init, engine
from backend.src.database.user import (
    User,
    Group
)
from backend.src.api.models import (
    JWTToken
)


@pytest.fixture(scope="session")
async def nothing() -> None:
    """Nothing will be provided by this fixture. Liternally nothing."""
    return None


@pytest.fixture(scope="session")
async def config() -> MoodleConfig:
    """Moodle configuration for tests."""
    return MoodleConfig(
        username=settings.MOODLE_USERNAME,
        password=settings.MOODLE_PASSWORD,
        base_url=settings.MOODLE_BASE_URL,
        service=settings.MOODLE_SERVICE,
    )


@pytest.fixture(scope="session")
async def client(config: MoodleConfig) -> t.AsyncGenerator[APIClient, None]:
    """Moodle API client for tests."""
    async with APIClient(config) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
async def session() -> t.AsyncGenerator[AsyncSession, None]:
    """Fixture to initialize and provide a database session for tests."""
    async with AsyncSession(engine) as session:
        await init()
        yield session


@pytest.fixture(scope="module")
async def group(session: AsyncSession) -> t.AsyncGenerator[Group, None]:
    """Generate mock group data."""
    group = await Group.query(session, name=mockdata.group.name)
    if not group:
        group = await Group.create(
            session,
            name=mockdata.group.name,
            description=mockdata.group.description
        )
    await session.refresh(group)
    yield group
    await session.delete(group)
    await session.flush()


@pytest.fixture(scope="module")
async def user(group: Group, session: AsyncSession) -> t.AsyncGenerator[User, None]:
    """Generate or query currently existed mock user for testing."""
    user = await User.query(session, email=mockdata.user.email)
    if not user:
        user = await User.create(
            session,
            email=mockdata.user.email,
            name=mockdata.user.name,
            description=mockdata.user.description
        )
    await session.refresh(user)
    await group.add_user(session, user=user)
    yield user
    await session.delete(user)
    await session.flush()


@pytest.fixture(scope="function")
async def token(session: AsyncSession, user: User) -> str:
    """Generate JWT Token for testing."""
    token = await JWTToken.create(session, user=user)
    return token.access_token


@pytest.fixture(scope="function")
async def jwt(session: AsyncSession, user: User) -> JWTToken:
    """Generate JWT Token for testing."""
    token = await JWTToken.create(session, user=user)
    return token


@pytest.fixture(scope="module")
async def api() -> t.AsyncGenerator[AsyncClient, None]:
    """Fixture to provide a TestClient for API testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=f"http://{settings.PROJECT_NAME}.test/api/{settings.API_VERSION}",
    ) as client:
        yield client
