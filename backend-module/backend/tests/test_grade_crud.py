"""Tests for GradingJob database model."""
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.src.database.grade import GradingJob, GradingStatus


JOB_PARAMS = dict(
    content="The answer is 42.",
    task_description="What is the answer to everything?",
    max_grade=100.0,
)


@pytest.mark.asyncio
async def test_create_job(session: AsyncSession):
    job = await GradingJob.create(session, submission_id=5001, **JOB_PARAMS)
    # Capture all fields before commit — commit expires the ORM object.
    job_id            = job.id
    job_submission_id = job.submission_id
    job_status        = job.status
    job_grade         = job.grade
    job_feedback      = job.feedback
    job_celery_id     = job.celery_task_id
    await session.commit()

    assert job_id is not None
    assert job_submission_id == 5001
    assert job_status == GradingStatus.PENDING
    assert job_grade is None
    assert job_feedback is None
    assert job_celery_id is None


@pytest.mark.asyncio
async def test_get_by_submission_id(session: AsyncSession):
    await GradingJob.create(session, submission_id=5002, **JOB_PARAMS)
    await session.commit()

    found = await GradingJob.get_by_submission_id(session, 5002)
    assert found is not None
    assert found.submission_id == 5002


@pytest.mark.asyncio
async def test_get_by_id(session: AsyncSession):
    job = await GradingJob.create(session, submission_id=5003, **JOB_PARAMS)
    job_id = job.id
    await session.commit()

    found = await GradingJob.get_by_id(session, job_id)
    assert found is not None
    assert found.id == job_id


@pytest.mark.asyncio
async def test_start_sets_processing(session: AsyncSession):
    job = await GradingJob.create(session, submission_id=5004, **JOB_PARAMS)
    job_id = job.id
    await session.commit()

    job = await GradingJob.get_by_id(session, job_id)
    await job.start(session, celery_task_id="celery-abc-123")
    await session.commit()

    refreshed = await GradingJob.get_by_id(session, job_id)
    assert refreshed.status == GradingStatus.PROCESSING
    assert refreshed.celery_task_id == "celery-abc-123"
    assert refreshed.updated_at is not None


@pytest.mark.asyncio
async def test_finish_sets_done(session: AsyncSession):
    job = await GradingJob.create(session, submission_id=5005, **JOB_PARAMS)
    job_id = job.id
    await session.commit()

    job = await GradingJob.get_by_id(session, job_id)
    await job.finish(session, grade=85.0, feedback="Good work.")
    await session.commit()

    refreshed = await GradingJob.get_by_id(session, job_id)
    assert refreshed.status == GradingStatus.DONE
    assert refreshed.grade == 85.0
    assert refreshed.feedback == "Good work."


@pytest.mark.asyncio
async def test_fail_sets_error(session: AsyncSession):
    job = await GradingJob.create(session, submission_id=5006, **JOB_PARAMS)
    job_id = job.id
    await session.commit()

    job = await GradingJob.get_by_id(session, job_id)
    await job.fail(session)
    await session.commit()

    refreshed = await GradingJob.get_by_id(session, job_id)
    assert refreshed.status == GradingStatus.ERROR


@pytest.mark.asyncio
async def test_get_missing_returns_none(session: AsyncSession):
    missing = await GradingJob.get_by_submission_id(session, 99999)
    assert missing is None
