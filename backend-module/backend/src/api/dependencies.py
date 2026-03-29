from backend.src.config import settings
from backend.src.database import engine
from backend.src.database.user import User
from backend.src.api.models import JWTTokenPayload
from backend.src.api import (
    InvalidAccessToken,
    AccessTokenExpired
)

import typing as t

import jwt
import redis
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession


TokenRequired = OAuth2PasswordBearer(
    tokenUrl=f"/api/{settings.API_VERSION}/auth/token")


async def _get_session() -> t.AsyncGenerator[AsyncSession, None]:
    """Provide a new database session.

    Hence wre are using async context manager to ensure proper cleanup,
    no matter if the request was successful or raised an error.
    """
    async with AsyncSession(engine) as session:
        yield session

SessionRequired = t.Annotated[AsyncSession, Depends(_get_session)]


async def _get_current_user(session: SessionRequired, token: str = Depends(TokenRequired)) -> User:
    """Get the current user based on the provided JWT token."""
    try:
        decoded_jwt_token = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=settings.JWT_ALGORITHM,
            options={
                "verify_exp": False
            }
        )
        payload = JWTTokenPayload.model_validate(decoded_jwt_token)
    except AccessTokenExpired:
        raise HTTPException(401, "access token has expired")
    except (jwt.PyJWTError, InvalidAccessToken):
        raise HTTPException(403, "invalid credentials")

    # Get user from the database
    user = await User.query(session, id=payload.sub)
    if user is None or user.is_disabled or user.is_deleted:
        raise HTTPException(422, "inactive user")
    return user


UserRequired = t.Annotated[User, Depends(_get_current_user)]


class UserGroupsRequired:
    """Dependency to ensure the current user belongs to a specific group."""

    def __init__(self, *expected_groups: str):
        self.expected_groups = expected_groups
        if not expected_groups:
            raise ValueError("at least one group must be specified")

    async def __call__(self, session: SessionRequired, user: UserRequired) -> User:
        await session.refresh(user, attribute_names=["groups"])
        user_groups = {group.name for group in user.groups}
        if not any(group in user_groups for group in self.expected_groups):
            raise HTTPException(403, "user does not match any group expected")
        return user


class OAuthStateRequired:
    """Dependency for checking if the state parameter matches the previously submitted one."""

    @classmethod
    async def record_state(cls, state: str, url: str, ttl: int = settings.OAUTH_CLIENT_STATE_TTL) -> None:
        """Record state and url in Redis with TTL."""
        await settings.REDIS.set(
            name=f"oauth:state:{state}",
            value=url,
            ex=ttl,
            nx=True
        )

    async def __call__(self, state: str) -> None:
        """Access state, verify and deactive it."""
        with settings.REDIS.pipeline() as pipe:
            try:
                pipe.watch(state)
                url = pipe.get(state)
                if url is None:
                    pipe.unwatch()
                    raise HTTPException(403, "cannot find corresponded state")
                pipe.multi()
                pipe.delete(state)
                pipe.execute()
            except redis.WatchError:
                raise HTTPException(403, "cannot find corresponded state")
