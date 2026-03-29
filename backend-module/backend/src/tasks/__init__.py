from backend.src.config import settings

import asyncio
import logging
import typing as t
import uuid

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.src.database.grade import GradingJob, GradingStatus

logger = logging.getLogger(__name__)
celery = settings.CELERY


def _make_engine():
    """Create a fresh async engine for each asyncio.run() call.

    The module-level engine in backend.src.database is bound to the FastAPI
    event loop.  Celery workers call asyncio.run() which creates a NEW loop,
    so we must create a fresh engine each time to avoid
    'Future attached to a different loop' errors.
    """
    from backend.src.config import settings as s
    return create_async_engine(str(s.DATABASE_URI))


# ------------------------------------------------------------------
# Async DB helpers (called from sync Celery task via asyncio.run)
# ------------------------------------------------------------------

async def _update_job_start(job_id: str, celery_task_id: str) -> None:
    engine = _make_engine()
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_id(session, uuid.UUID(job_id))
        if job:
            await job.start(session, celery_task_id=celery_task_id)
            await session.commit()
    await engine.dispose()


async def _update_job_done(job_id: str, grade: float, feedback: str) -> None:
    engine = _make_engine()
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_id(session, uuid.UUID(job_id))
        if job:
            await job.finish(session, grade=grade, feedback=feedback)
            await session.commit()
    await engine.dispose()


async def _update_job_error(job_id: str) -> None:
    engine = _make_engine()
    async with AsyncSession(engine) as session:
        job = await GradingJob.get_by_id(session, uuid.UUID(job_id))
        if job:
            await job.fail(session)
            await session.commit()
    await engine.dispose()


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

    logger.info("[task] started: job=%s submission=%s", job_id, submission_id)
    asyncio.run(_update_job_start(job_id, celery_task_id=self.request.id))
    logger.info("[task] DB status set to PROCESSING: job=%s", job_id)

    try:
        logger.info("[task] building LLM pipeline for job=%s", job_id)
        builder = GeneratorJudgeBuilder()
        graph   = builder.workflow.compile()
        logger.info("[task] invoking LLM graph for job=%s", job_id)

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
        logger.info("[task] LLM graph finished: job=%s result_keys=%s", job_id, list(result.keys()))
    except Exception as exc:
        logger.error("[task] LLM grading FAILED for job=%s attempt=%d: %s",
                     job_id, self.request.retries, exc, exc_info=True)
        try:
            raise self.retry(exc=exc, countdown=10)
        except self.MaxRetriesExceededError:
            logger.error("[task] max retries exceeded for job=%s, marking ERROR", job_id)
            asyncio.run(_update_job_error(job_id))
            raise

    grade    = float(result.get("proposed_grade", 0.0))
    feedback = str(result.get("generator_output", ""))

    asyncio.run(_update_job_done(job_id, grade=grade, feedback=feedback))
    logger.info("[task] done: job=%s grade=%.1f feedback_len=%d", job_id, grade, len(feedback))

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
