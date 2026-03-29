from backend.src.exception import BackendException
from backend.src.config import settings

import logging

from fastapi import APIRouter


logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"/{settings.API_VERSION}")


class APIException(BackendException):
    _base_code: int = 20000


class InvalidAccessToken(APIException):
    _code: int = 1001


class AccessTokenExpired(APIException):
    _code: int = 1002


@router.get("/healthy", summary="Health Check")
async def healthy() -> bool:
    return True


def init() -> APIRouter:
    from backend.src.api.routes import grade
    router.include_router(grade.router)
    logger.debug("api initialized")
    return router
