from backend.src.exception import BackendException
from backend.src.config import settings

import logging

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Import models so SQLModel.metadata picks them up before create_all.
from backend.src.database.grade import GradingJob  # noqa: F401

logger = logging.getLogger(__name__)
engine = create_async_engine(str(settings.DATABASE_URI))


async def init() -> AsyncEngine:
    """Initialize database — create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.debug("database initialized")
    return engine


class DatabaseException(BackendException):
    _base_code: int = 20000


class DuplicateSubmission(DatabaseException):
    """Raised when a grading job for this submission_id already exists."""
    _code: int = 1001


class JobNotFound(DatabaseException):
    """Raised when a grading job cannot be found."""
    _code: int = 1002
