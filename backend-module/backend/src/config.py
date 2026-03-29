from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import RedisDsn, PostgresDsn, computed_field

import celery
import typing as t
import logging
import logging.handlers as lhandlers


class Settings(BaseSettings):

    PROJECT_NAME: str = "llm-task-assessor"
    ENVIRONMENT: t.Literal["test", "dev", "prod"] = "test"
    API_VERSION: str = "v1"

    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = 8000
    UVICORN_RELOAD: bool = False

    # Static bearer token Moodle sends in Authorization header.
    API_TOKEN: str = "changeme"

    CORS_ORIGINS: t.List[str] = ["*"]

    LOG_LEVEL: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    LOG_FORMAT: str = "[%(asctime)s] [%(levelname)s] %(message)s"
    LOG_FILE: str = "logs/llm-task-assessor.log"
    LOG_FILE_MAXSIZE: int = 1024 * 1024
    LOG_FILE_AUTOBACKUP: int = 10

    @computed_field
    @property
    def LOG_HANDLERS(self) -> t.List[logging.Handler]:
        handlers: t.List[logging.Handler] = [logging.StreamHandler()]
        if self.LOG_FILE:
            handlers.append(lhandlers.RotatingFileHandler(
                self.LOG_FILE,
                maxBytes=self.LOG_FILE_MAXSIZE,
                backupCount=self.LOG_FILE_AUTOBACKUP,
            ))
        return handlers

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "assessor"

    @computed_field
    @property
    def DATABASE_URI(self) -> PostgresDsn | str:
        if self.ENVIRONMENT == "test":
            return "sqlite+aiosqlite:///:memory:"
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    # Redis / Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_BROKER_DB: int = 0
    REDIS_PASSWORD: str = ""

    @computed_field
    @property
    def REDIS_BROKER_URI(self) -> RedisDsn:
        return RedisDsn.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            path=str(self.REDIS_BROKER_DB),
            password=self.REDIS_PASSWORD or None,
        )

    CELERY_TASK_QUEUE: str = "tasks"

    @computed_field
    @property
    def CELERY(self) -> celery.Celery:
        return celery.Celery(
            self.CELERY_TASK_QUEUE,
            broker=str(self.REDIS_BROKER_URI),
            backend=str(self.REDIS_BROKER_URI),
        )

    # LLM agent service URL (internal Docker network address)
    LLM_AGENT_URL: str = "http://llm-agent:8001"

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
