from backend.src.exception import BackendException
from backend.src.config import settings

import logging

from fastapi import APIRouter


logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"/{settings.API_VERSION}")


class APIException(BackendException):
    """Base Exception for API error."""
    _base_code: int = 20000


class InvalidAccessToken(APIException):
    _code: int = 1001


class AccessTokenExpired(APIException):
    _code: int = 1002


@router.get("/healthy", summary="Health Check", description="Check the health status of the API.")
async def healthy() -> bool:
    """Health check endpoint to verify that the API is running."""
    result = settings.CELERY.send_task("awwh")
    return result.get(timeout=10)


def init() -> APIRouter:
    from backend.src.api.routes import task
    from backend.src.api.routes import auth
    router.include_router(task.router)
    router.include_router(auth.router)
    logger.debug("api initialized")
    return router
