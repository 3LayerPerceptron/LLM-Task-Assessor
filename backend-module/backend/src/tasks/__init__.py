from backend.src.config import settings

import asyncio
import logging
import typing as t
import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.src.database import engine
from backend.src.database.grade import GradingJob, GradingStatus

logger = logging.getLogger(__name__)
celery = settings.CELERY


# ------------------------------------------------------------------
# Async DB helpers (called from sync Celery task via asyncio.run)
# ------------------------------------------------------------------

async def _update_job_start(job_id: str, celery_task_id: str) -> None:
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_id(session, uuid.UUID(job_id))
        if job:
            await job.start(session, celery_task_id=celery_task_id)
            await session.commit()


async def _update_job_done(job_id: str, grade: float, feedback: str) -> None:
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_id(session, uuid.UUID(job_id))
        if job:
            await job.finish(session, grade=grade, feedback=feedback)
            await session.commit()


async def _update_job_error(job_id: str) -> None:
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_id(session, uuid.UUID(job_id))
        if job:
            await job.fail(session)
            await session.commit()


# ------------------------------------------------------------------
# Celery grading task — imports llm_agents directly (same process)
# ------------------------------------------------------------------

@celery.task(name="grade_submission", bind=True, max_retries=3)
def grade_submission(
    self,
    *,
    job_id: str,
    submission_id: int,
    content: str,
    task_description: str,
    max_grade: float,
) -> dict:
    """Grade a text submission using the LLM agent (direct import)."""
    from llm_agents import GeneratorJudgeBuilder

    logger.info("grade_submission started: job=%s submission=%s", job_id, submission_id)
    asyncio.run(_update_job_start(job_id, celery_task_id=self.request.id))

    try:
        builder = GeneratorJudgeBuilder()
        graph   = builder.workflow.compile()

        result = graph.invoke({
            "assignment":       task_description,
            "solution":         content,
            "max_grade":        max_grade,
            "generator_output": "",
            "proposed_grade":   0.0,
            "judge_output":     "",
            "satisfaction":     0.0,
            "coherence":        0.0,
            "style":            0.0,
            "retry_count":      0,
            "final_decision":   "",
        })
    except Exception as exc:
        logger.error("LLM grading failed for job %s: %s", job_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            asyncio.run(_update_job_error(job_id))
            raise

    grade    = float(result.get("proposed_grade", 0.0))
    feedback = str(result.get("generator_output", ""))

    asyncio.run(_update_job_done(job_id, grade=grade, feedback=feedback))
    logger.info("grade_submission done: job=%s grade=%.1f", job_id, grade)

    return {"grade": grade, "feedback": feedback}


# ------------------------------------------------------------------
# Test-only stubs
# ------------------------------------------------------------------

if settings.ENVIRONMENT == "test":
    @celery.task(name="awwh")
    def awwh() -> bool:
        return True

    @celery.task(name="oops")
    def oops() -> t.NoReturn:
        raise RuntimeError("oops")
