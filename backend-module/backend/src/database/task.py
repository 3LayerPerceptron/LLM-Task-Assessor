import typing_extensions as te
import uuid
import enum
from datetime import datetime, timezone

from backend.src.config import settings

from sqlmodel import SQLModel, Field, Column
from sqlmodel import Enum as SqlEnum
from sqlmodel.ext.asyncio.session import AsyncSession
from celery.result import AsyncResult


@enum.unique
class TaskStatus(str, enum.Enum):
    """Status of a resource processing task."""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


# Final states where we can stop tracking the task
TaskStatusFinal = {
    TaskStatus.SUCCESS,
    TaskStatus.FAILURE,
    TaskStatus.REVOKED
}


class Task(SQLModel, table=True):
    __table_args__ = {'extend_existing': True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    celery_task_id: str = Field(index=True, unique=True)
    celery_task_result: str | None = Field(default=None)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        sa_column=Column(SqlEnum(TaskStatus)),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    updated_at: datetime | None = Field(default=None, nullable=True)

    @classmethod
    async def create(cls, session: AsyncSession, *, celery_task_id: str, owner_id: uuid.UUID) -> te.Self:
        """Create a new task to track Celery worker execution."""
        task = cls(celery_task_id=celery_task_id, owner_id=owner_id)
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task

    @classmethod
    async def query(cls, session: AsyncSession, id: str) -> te.Self | None:
        """Query a task by its ID."""
        return await session.get(cls, uuid.UUID(id))

    async def update(self, session: AsyncSession) -> te.Self:
        """Update the task."""
        # Once the task is already failed or success or revoked, we can stop tracking it
        if self.status in TaskStatusFinal:
            return self

        # Track Celery task result and update timestamp
        result = AsyncResult(self.celery_task_id, app=settings.CELERY)
        if result.state != self.status:
            self.status = TaskStatus(result.state.lower())
            self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if self.status == TaskStatus.SUCCESS:
                self.celery_task_result = str(result.get())

            # Commit changes if there are any updates
            session.add(self)
            await session.commit()
            await session.refresh(self)
        return self
