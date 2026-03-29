from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Optional
import uuid

from sqlmodel import SQLModel, Field, select
from sqlmodel.ext.asyncio.session import AsyncSession


class GradingStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    ERROR      = "error"


class GradingJob(SQLModel, table=True):
    __tablename__ = "grading_jobs"

    id:              uuid.UUID      = Field(default_factory=uuid.uuid4, primary_key=True)
    submission_id:   int            = Field(unique=True, index=True)
    content:         str
    task_description: str
    max_grade:       float
    celery_task_id:  Optional[str]  = Field(default=None, index=True)
    status:          GradingStatus  = Field(default=GradingStatus.PENDING)
    grade:           Optional[float] = None
    feedback:        Optional[str]  = None
    created_at:      datetime       = Field(default_factory=datetime.utcnow)
    updated_at:      Optional[datetime] = None

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        submission_id: int,
        content: str,
        task_description: str,
        max_grade: float,
    ) -> "GradingJob":
        job = cls(
            submission_id=submission_id,
            content=content,
            task_description=task_description,
            max_grade=max_grade,
        )
        session.add(job)
        await session.flush()
        await session.refresh(job)
        return job

    @classmethod
    async def get_by_submission_id(
        cls, session: AsyncSession, submission_id: int
    ) -> Optional["GradingJob"]:
        result = await session.exec(
            select(cls).where(cls.submission_id == submission_id)
        )
        return result.one_or_none()

    @classmethod
    async def get_by_id(
        cls, session: AsyncSession, job_id: uuid.UUID
    ) -> Optional["GradingJob"]:
        result = await session.exec(select(cls).where(cls.id == job_id))
        return result.one_or_none()

    # ------------------------------------------------------------------
    # Instance-level helpers
    # ------------------------------------------------------------------

    async def start(self, session: AsyncSession, celery_task_id: str) -> None:
        self.celery_task_id = celery_task_id
        self.status = GradingStatus.PROCESSING
        self.updated_at = datetime.utcnow()
        session.add(self)
        await session.flush()

    async def finish(
        self,
        session: AsyncSession,
        *,
        grade: float,
        feedback: str,
    ) -> None:
        self.grade = grade
        self.feedback = feedback
        self.status = GradingStatus.DONE
        self.updated_at = datetime.utcnow()
        session.add(self)
        await session.flush()

    async def fail(self, session: AsyncSession) -> None:
        self.status = GradingStatus.ERROR
        self.updated_at = datetime.utcnow()
        session.add(self)
        await session.flush()
