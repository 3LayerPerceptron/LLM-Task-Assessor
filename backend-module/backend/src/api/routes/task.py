import logging
from datetime import datetime
from backend.src.api import dependencies
from backend.src.database.task import Task, TaskStatus
import uuid
from sqlmodel import SQLModel
from fastapi import APIRouter, HTTPException
from backend.src.tasks import grade_assignment  # Импорт таски

router = APIRouter(prefix="/task", tags=["task"])
logger = logging.getLogger(__name__)

class TaskCreateRequest(SQLModel):
    assignment: str
    solution: str
    max_grade: float

class TaskResult(SQLModel):
    id: uuid.UUID
    celery_task_id: str
    celery_task_result: str | None = None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime | None = None

@router.post("/", summary="Submit grading task (NO AUTH)")
async def submit_task(
    request: TaskCreateRequest,
    session: dependencies.SessionRequired
) -> TaskResult:
    logger.info(f"Received task: {request.assignment[:50]}...")
    
    # Запускаем асинхронно
    celery_task = grade_assignment.delay(
        assignment=request.assignment,
        solution=request.solution,
        max_grade=request.max_grade
    )
    
    # Создаём запись в БД (без владельца)
    task = await Task.create(
        session,
        celery_task_id=celery_task.id,
        owner_id=None 
    )
    
    logger.info(f"Task created: {task.id}, Celery ID: {celery_task.id}")
    return TaskResult(**task.model_dump(include={
        "id", "celery_task_id", "celery_task_result", "status", "created_at", "updated_at"
    }))

@router.get("/{id}", summary="Get task status")
async def get_task_by_id(
    id: str,
    session: dependencies.SessionRequired
) -> TaskResult:
    task = await Task.query(session, id=id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    
    # Обновляем статус из Celery
    await task.update(session)
    
    return TaskResult(**task.model_dump(include={
        "id", "celery_task_id", "celery_task_result", "status", "created_at", "updated_at"
    }))