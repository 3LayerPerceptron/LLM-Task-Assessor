"""
Integration tests for the grading pipeline.

Tests the full flow:
  POST /aigrades  →  GradingJob created in DB  →  Celery task dispatched
  Celery task runs (LLM agent mocked)  →  DB updated to DONE
  GET  /aigrades?submissionid=X  →  ready=true, grade, feedback returned

The LLM agent (llm_agents.GeneratorJudgeBuilder) and Celery async execution
are mocked so tests run without external services.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.src.database.grade import GradingJob, GradingStatus
from backend.src.database import engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_celery_task_id() -> str:
    return str(uuid.uuid4())


async def _set_job_done(submission_id: int, grade: float, feedback: str) -> None:
    """Directly write a DONE result into the DB (simulates Celery task completing)."""
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_submission_id(session, submission_id)
        assert job is not None, f"job for submission {submission_id} not found"
        await job.finish(session, grade=grade, feedback=feedback)
        await session.commit()


# ---------------------------------------------------------------------------
# Full pipeline: submit → task runs → poll returns result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pipeline(api: AsyncClient, auth_headers: dict):
    """
    Submit a text submission, simulate the Celery task writing the result,
    then poll and verify the response is ready with grade and feedback.
    """
    submission_id = 9001
    mock_task = MagicMock()
    mock_task.id = _fake_celery_task_id()

    # 1. Submit
    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        r = await api.post("/aigrades", json={
            "submission_id":    submission_id,
            "content":          "The mitochondria is the powerhouse of the cell.",
            "task_description": "Explain what the mitochondria does.",
            "max_grade":        10.0,
        }, headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["submission_id"] == submission_id
    assert data["status"] == "pending"
    job_id = data["job_id"]
    assert job_id

    # 2. Poll before task completes — should be not ready
    r = await api.get("/aigrades", params={"submissionid": submission_id}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ready"] is False

    # 3. Simulate Celery task completing (write result directly to DB)
    await _set_job_done(submission_id, grade=9.0, feedback="Excellent explanation.")

    # 4. Poll after task completes — should be ready
    r = await api.get("/aigrades", params={"submissionid": submission_id}, headers=auth_headers)
    assert r.status_code == 200
    result = r.json()
    assert result["ready"] is True
    assert result["grade"] == 9.0
    assert result["feedback"] == "Excellent explanation."


@pytest.mark.asyncio
async def test_resubmit_resets_to_pending(api: AsyncClient, auth_headers: dict):
    """
    Submitting the same submission_id again after it was DONE resets it to pending.
    """
    submission_id = 9002
    mock_task = MagicMock()
    mock_task.id = _fake_celery_task_id()

    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        await api.post("/aigrades", json={
            "submission_id":    submission_id,
            "content":          "First attempt.",
            "task_description": "Describe photosynthesis.",
            "max_grade":        10.0,
        }, headers=auth_headers)

    # Simulate task done
    await _set_job_done(submission_id, grade=5.0, feedback="Partial answer.")

    r = await api.get("/aigrades", params={"submissionid": submission_id}, headers=auth_headers)
    assert r.json()["ready"] is True

    # Resubmit (e.g. student edited and resubmitted)
    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        r = await api.post("/aigrades", json={
            "submission_id":    submission_id,
            "content":          "Improved attempt.",
            "task_description": "Describe photosynthesis.",
            "max_grade":        10.0,
        }, headers=auth_headers)

    assert r.status_code == 200
    assert r.json()["status"] == "pending"

    # Poll — should be back to not ready (pending)
    r = await api.get("/aigrades", params={"submissionid": submission_id}, headers=auth_headers)
    assert r.json()["ready"] is False


@pytest.mark.asyncio
async def test_error_status_not_ready(api: AsyncClient, auth_headers: dict):
    """
    A job in ERROR state is returned as ready=False (not a valid result).
    """
    submission_id = 9003
    mock_task = MagicMock()
    mock_task.id = _fake_celery_task_id()

    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        await api.post("/aigrades", json={
            "submission_id":    submission_id,
            "content":          "Some answer.",
            "task_description": "Some task.",
            "max_grade":        10.0,
        }, headers=auth_headers)

    # Simulate task failing
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_submission_id(session, submission_id)
        await job.fail(session)
        await session.commit()

    r = await api.get("/aigrades", params={"submissionid": submission_id}, headers=auth_headers)
    assert r.status_code == 200
    result = r.json()
    assert result["ready"] is False
    assert result["grade"] is None


def test_celery_task_calls_llm_agent():
    """
    Unit test: grade_submission Celery task calls GeneratorJudgeBuilder
    with the correct arguments and writes the result to DB.

    The async DB helpers and the LLM builder are mocked so this runs
    without an event loop or external services.
    """
    from backend.src.tasks import grade_submission

    job_id        = str(uuid.uuid4())
    submission_id = 9004

    fake_result = {
        "generator_output": "Good answer, water is indeed H2O.",
        "proposed_grade":   8.5,
        "satisfaction":     0.95,
        "final_decision":   "Accepted",
    }

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = fake_result

    mock_builder = MagicMock()
    mock_builder.workflow.compile.return_value = mock_graph

    with patch("llm_agents.GeneratorJudgeBuilder", return_value=mock_builder), \
         patch("backend.src.tasks._update_job_start") as mock_start, \
         patch("backend.src.tasks._update_job_done")  as mock_done, \
         patch("backend.src.tasks.asyncio.run") as mock_run:

        # Make asyncio.run just call the coroutine's send(None) — enough for
        # the mocked helpers which return immediately.
        def _noop_run(coro):
            try:
                coro.send(None)
            except StopIteration as exc:
                return exc.value
        mock_run.side_effect = _noop_run

        result = grade_submission.run(
            job_id=job_id,
            submission_id=submission_id,
            content="Water is H2O.",
            task_description="Describe water.",
            max_grade=10.0,
        )

    # Builder was called
    mock_builder.workflow.compile.assert_called_once()
    mock_graph.invoke.assert_called_once()

    # Verify invoke received correct state
    call_state = mock_graph.invoke.call_args[0][0]
    assert call_state["assignment"] == "Describe water."
    assert call_state["solution"]   == "Water is H2O."
    assert call_state["max_grade"]  == 10.0

    # Task returned grade and feedback
    assert result["grade"]    == 8.5
    assert result["feedback"] == "Good answer, water is indeed H2O."

    # asyncio.run was called for start and done (not error)
    assert mock_run.call_count == 2


@pytest.mark.asyncio
async def test_multiple_submissions_independent(api: AsyncClient, auth_headers: dict):
    """
    Multiple submissions are tracked independently — polling one does not
    affect another.
    """
    mock_task = MagicMock()
    mock_task.id = _fake_celery_task_id()

    with patch("backend.src.api.routes.grade.grade_submission") as mock_fn:
        mock_fn.delay.return_value = mock_task
        for sid in (9010, 9011, 9012):
            await api.post("/aigrades", json={
                "submission_id":    sid,
                "content":          f"Answer for {sid}",
                "task_description": "Generic task",
                "max_grade":        10.0,
            }, headers=auth_headers)

    # Complete only submission 9011
    await _set_job_done(9011, grade=7.0, feedback="Good.")

    r9010 = await api.get("/aigrades", params={"submissionid": 9010}, headers=auth_headers)
    r9011 = await api.get("/aigrades", params={"submissionid": 9011}, headers=auth_headers)
    r9012 = await api.get("/aigrades", params={"submissionid": 9012}, headers=auth_headers)

    assert r9010.json()["ready"] is False
    assert r9011.json()["ready"] is True
    assert r9011.json()["grade"] == 7.0
    assert r9012.json()["ready"] is False
