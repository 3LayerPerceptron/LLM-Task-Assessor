"""Tests for POST /api/v1/aigrades and GET /api/v1/aigrades."""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


SUBMIT_PAYLOAD = {
    "submission_id":    1001,
    "content":          "The speed of light is 3×10^8 m/s.",
    "task_description": "Explain the speed of light.",
    "max_grade":        10.0,
}


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_requires_auth(api: AsyncClient):
    r = await api.post("/aigrades", json=SUBMIT_PAYLOAD)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_submit_rejects_bad_token(api: AsyncClient, bad_auth_headers: dict):
    r = await api.post("/aigrades", json=SUBMIT_PAYLOAD, headers=bad_auth_headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_poll_requires_auth(api: AsyncClient):
    r = await api.get("/aigrades", params={"submissionid": 9999})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Submit — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_creates_job(api: AsyncClient, auth_headers: dict):
    mock_task = MagicMock()
    mock_task.id = "celery-task-abc"

    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        r = await api.post("/aigrades", json={**SUBMIT_PAYLOAD, "submission_id": 2001}, headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["submission_id"] == 2001
    assert data["status"] == "pending"
    assert "job_id" in data
    mock_fn.delay.assert_called_once()


@pytest.mark.asyncio
async def test_submit_requeues_existing(api: AsyncClient, auth_headers: dict):
    """Submitting the same submission_id twice re-queues it."""
    mock_task = MagicMock()
    mock_task.id = "celery-task-xyz"

    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        # First submission
        r1 = await api.post("/aigrades", json={**SUBMIT_PAYLOAD, "submission_id": 3001}, headers=auth_headers)
        # Second submission (re-queue)
        r2 = await api.post("/aigrades", json={**SUBMIT_PAYLOAD, "submission_id": 3001}, headers=auth_headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["submission_id"] == 3001


# ---------------------------------------------------------------------------
# Poll — not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_not_found(api: AsyncClient, auth_headers: dict):
    r = await api.get("/aigrades", params={"submissionid": 99999}, headers=auth_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Poll — pending (not ready)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_pending(api: AsyncClient, auth_headers: dict):
    mock_task = MagicMock()
    mock_task.id = "celery-task-pending"

    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        await api.post("/aigrades", json={**SUBMIT_PAYLOAD, "submission_id": 4001}, headers=auth_headers)

    r = await api.get("/aigrades", params={"submissionid": 4001}, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["ready"] is False
    assert data["grade"] is None
    assert data["feedback"] is None


# ---------------------------------------------------------------------------
# Health check (no auth required)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(api: AsyncClient):
    r = await api.get("/healthy")
    assert r.status_code == 200
    assert r.json() is True
