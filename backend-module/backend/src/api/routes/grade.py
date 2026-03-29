from backend.src.api.dependencies import SessionRequired, TokenRequired
from backend.src.database.grade import GradingJob, GradingStatus
from backend.src.tasks import grade_submission

import uuid
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aigrades", tags=["grading"])


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------

class SubmitRequest(BaseModel):
    submission_id:    int
    content:          str
    task_description: str
    max_grade:        float = 100.0


class SubmitResponse(BaseModel):
    job_id:        str
    submission_id: int
    status:        str


class PollResponse(BaseModel):
    ready:    bool
    grade:    float | None = None
    feedback: str   | None = None


# ------------------------------------------------------------------
# POST /api/v1/aigrades  — Moodle sends a new submission for grading
# ------------------------------------------------------------------

@router.post("", response_model=SubmitResponse, dependencies=[TokenRequired])
async def submit_submission(body: SubmitRequest, session: SessionRequired) -> SubmitResponse:
    """Receive a text submission from Moodle and queue it for AI grading."""

    existing = await GradingJob.get_by_submission_id(session, body.submission_id)
    if existing:
        # Re-queue: reset status and dispatch a fresh Celery task.
        existing.status = GradingStatus.PENDING
        existing.grade = None
        existing.feedback = None
        existing.celery_task_id = None
        session.add(existing)
        await session.flush()
        job = existing
    else:
        job = await GradingJob.create(
            session,
            submission_id=body.submission_id,
            content=body.content,
            task_description=body.task_description,
            max_grade=body.max_grade,
        )

    await session.commit()
    await session.refresh(job)

    # Dispatch Celery task.
    task = grade_submission.delay(
        job_id=str(job.id),
        submission_id=job.submission_id,
        content=job.content,
        task_description=job.task_description,
        max_grade=job.max_grade,
    )
    logger.info("dispatched grade_submission task %s for submission %s", task.id, job.submission_id)

    return SubmitResponse(
        job_id=str(job.id),
        submission_id=job.submission_id,
        status=job.status.value,
    )


# ------------------------------------------------------------------
# GET /api/v1/aigrades?submissionid=123  — Moodle polls for result
# ------------------------------------------------------------------

@router.get("", response_model=PollResponse, dependencies=[TokenRequired])
async def poll_result(
    session: SessionRequired,
    submissionid: int = Query(..., description="Moodle submission ID"),
) -> PollResponse:
    """Return the current grading result for a submission."""

    job = await GradingJob.get_by_submission_id(session, submissionid)
    if job is None:
        raise HTTPException(404, f"no grading job found for submissionid={submissionid}")

    ready = job.status == GradingStatus.DONE
    return PollResponse(
        ready=ready,
        grade=job.grade if ready else None,
        feedback=job.feedback if ready else None,
    )
