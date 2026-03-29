import pytest
import asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.src.config import settings
from backend.src.database.task import (
    Task,
    TaskStatus
)
from backend.src.database.user import User


async def test_create_successful_task(session: AsyncSession, user: User) -> None:
    task = settings.CELERY.send_task("awwh")
    tracker = await Task.create(session, celery_task_id=task.id, owner_id=user.id)
    await session.refresh(user)
    assert tracker.status == TaskStatus.PENDING
    assert tracker.celery_task_id == task.id
    assert tracker.owner_id == user.id

    # Wait for task to complete
    await asyncio.sleep(1)
    await tracker.update(session)

    # Check if task finished ans result collected
    assert tracker.status == TaskStatus.SUCCESS
    assert tracker.celery_task_result == "True"


async def test_create_failed_task(session: AsyncSession, user: User) -> None:
    task = settings.CELERY.send_task("oops")
    await session.refresh(user)
    tracker = await Task.create(session, celery_task_id=task.id, owner_id=user.id)
    await session.refresh(user)
    assert tracker.status == TaskStatus.PENDING
    assert tracker.celery_task_id == task.id
    assert tracker.owner_id == user.id

    # Wait for task to complete
    await asyncio.sleep(1)
    await tracker.update(session)

    # Check if task finished ans result collected
    assert tracker.status == TaskStatus.FAILURE


async def test_query_task(session: AsyncSession, user: User) -> None:
    await session.refresh(user)
    query = select(Task).where(Task.owner_id == user.id)
    tracker = (await session.exec(query)).first()
    assert tracker is not None

    # Query task using tracker id
    expected = await Task.query(session, id=str(tracker.id))
    assert expected is not None


async def test_track_multiple_times_task(session: AsyncSession, user: User) -> None:
    await session.refresh(user)
    query = select(Task).where(Task.owner_id == user.id)
    tracker = (await session.exec(query)).first()
    assert tracker is not None

    # Update finished task again and check if status changed
    current_status = tracker.status
    await tracker.update(session)
    assert tracker.status == current_status
