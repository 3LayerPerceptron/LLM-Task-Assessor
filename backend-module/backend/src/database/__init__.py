from backend.src.exception import BackendException
from backend.src.config import settings

import logging

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

logger = logging.getLogger(__name__)
engine = create_async_engine(str(settings.DATABASE_URI))


async def init() -> AsyncEngine:
    """Initialize database connection."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.debug("database initialized")
    return engine


class DatabaseException(BackendException):
    """Base Exception for database error."""
    _base_code: int = 20000


class InvalidAuthenticationMethod(DatabaseException):
    """Raise when given bitmask not corresponded to any auth method."""
    _code: int = 1001


class InvalidLogin(DatabaseException):
    """Raise when user login invalid."""
    _code: int = 1002
