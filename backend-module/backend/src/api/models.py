from backend.src.config import settings
from backend.src.database.user import (
    User,
    RefreshToken
)
from backend.src.api import (
    InvalidAccessToken,
    AccessTokenExpired
)

import typing_extensions as te
from datetime import datetime, timezone, timedelta

import jwt
from sqlmodel import SQLModel
from pydantic import model_validator
from sqlmodel.ext.asyncio.session import AsyncSession


class JWTTokenPayload(SQLModel):
    sub: str
    iat: datetime
    exp: datetime

    @model_validator(mode="after")
    def validate_token_timestamp(self) -> te.Self:
        now = datetime.now(timezone.utc)
        if self.exp < now:
            raise AccessTokenExpired(f"expired at {self.exp}")
        if self.iat > now:
            raise InvalidAccessToken("token was issued in the future")
        return self


class JWTToken(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    @classmethod
    async def create(cls, session: AsyncSession, user: User) -> te.Self:
        """Create a new JWT token."""
        refresh_token = await RefreshToken.create(session, user=user)
        now = datetime.now(timezone.utc)
        await session.refresh(user)
        payload = JWTTokenPayload(
            sub=str(user.id), iat=now,
            exp=now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        access_token = jwt.encode(
            payload.model_dump(),
            key=settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        await session.refresh(refresh_token)
        return cls(
            access_token=access_token,
            refresh_token=refresh_token.content
        )

    @classmethod
    async def refresh(cls, session: AsyncSession, content: str) -> te.Self:
        """Refresh access token by refresh token."""
        refresh_token = await RefreshToken.query(session, content=content)
        if not refresh_token:
            raise ValueError("refresh token not found")
        now = datetime.now(timezone.utc)
        if refresh_token.valid_before <= now.replace(tzinfo=None):
            raise ValueError("refresh token expired, please re-login")
        payload = JWTTokenPayload(
            sub=str(refresh_token.user_id), iat=now,
            exp=now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        access_token = jwt.encode(
            payload.model_dump(),
            key=settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return cls(
            access_token=access_token,
            refresh_token=refresh_token.content
        )

    @staticmethod
    async def destroy(session: AsyncSession, user: User) -> None:
        """Destroy refresh token for user logging out."""
        refresh_token = await RefreshToken.query(session, user=user)
        if not refresh_token:
            return
        await refresh_token.delete(session)
