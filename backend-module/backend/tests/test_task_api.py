from backend.src.database.user import (
    User
)
from backend.src.database.task import (
    Task,
    TaskStatus
)
from backend.src import settings

import uuid
import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession
from httpx import AsyncClient


async def test_get_not_exist_task(
    api: AsyncClient,
    token: str
) -> None:
    """Test retrieval of a non-existent task."""

    response = await api.get(
        f"/task/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_get_task_unauthorized(
    session: AsyncSession,
    api: AsyncClient,
    token: str
) -> None:
    """Test retrieval of a task without authorization."""
    # Create a task owned by a different user
    tracker = await Task.create(
        session,
        celery_task_id="test-task-id",
        owner_id=uuid.uuid4()  # Random owner ID
    )
    response = await api.get(
        f"/task/{tracker.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    await tracker.update(session)

    # Track should remain in PENDING state as we don't have a real Celery task
    assert tracker.status == TaskStatus.PENDING


async def test_send_task_and_get_result(
    session: AsyncSession,
    api: AsyncClient,
    user: User,
    token: str
) -> None:
    """Create a simple test task and gathering result with API."""
    task = settings.CELERY.send_task("awwh")
    tracker = await Task.create(
        session,
        celery_task_id=task.id,
        owner_id=user.id
    )
    await asyncio.sleep(1)  # Sleep for a while
    response = await api.get(
        f"/task/{tracker.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    
    # Task should already been finished
    assert response.json()["status"] == "success"
