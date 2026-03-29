from backend.src.config import settings
from backend.src.database import engine

import typing as t

from fastapi import Depends, Header, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession


async def _get_session() -> t.AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session


SessionRequired = t.Annotated[AsyncSession, Depends(_get_session)]


async def _verify_token(authorization: t.Annotated[str | None, Header()] = None) -> None:
    """Verify the static bearer token sent by Moodle."""
    if not authorization:
        raise HTTPException(401, "missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "invalid Authorization header format")
    if parts[1] != settings.API_TOKEN:
        raise HTTPException(401, "invalid API token")


TokenRequired = Depends(_verify_token)
