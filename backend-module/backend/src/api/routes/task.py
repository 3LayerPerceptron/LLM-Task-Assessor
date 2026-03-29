import logging
from datetime import datetime

from backend.src.api import dependencies
from backend.src.database.task import (
    Task,
    TaskStatus
)

import uuid
from sqlmodel import SQLModel
from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/task", tags=["task"])
logger = logging.getLogger(__name__)


class TaskResult(SQLModel):
    """Task information returned to frontend."""
    id: uuid.UUID
    celery_task_result: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


@router.get(
    "/{id}",
    summary="Get task by ID",
    description="Retrieve a task status by its ID."
)
async def get_task_by_id(
    id: str,
    session: dependencies.SessionRequired,
    user: dependencies.UserRequired
) -> TaskResult:
    task = await Task.query(session, id=id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    await session.refresh(user)
    if task.owner_id != user.id:
        raise HTTPException(status_code=403, detail="not authorized access")
    await task.update(session)
    return TaskResult(**task.model_dump(include={
        "id", "celery_task_result", "status", "created_at", "updated_at"
    }))
