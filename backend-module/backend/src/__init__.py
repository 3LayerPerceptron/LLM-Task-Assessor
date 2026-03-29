from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.config import settings
from backend.src.database import init as init_db
from backend.src.api import init as init_api


import logging
from contextlib import asynccontextmanager


logger = logging.getLogger()
logger.setLevel(settings.LOG_LEVEL)

for handler in settings.LOG_HANDLERS:
    logger.addHandler(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    # NOTE: shutdown handler (if any) goes here


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    version=settings.API_VERSION,
    docs_url=f"/api/{settings.API_VERSION}/docs",
    openapi_url=f"/api/{settings.API_VERSION}/openapi.json"
)

app.include_router(init_api(), prefix="/api")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.rstrip("/") for origin in settings.CORS_ORIGINS
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
