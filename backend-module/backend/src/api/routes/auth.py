from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import SQLModel

from backend.src.api.models import JWTToken
from backend.src.api import dependencies
from backend.src.config import settings
from backend.src.database.user import (
    User,
    InvalidLogin,
    Authentication,
    PasswordAuthentication
)

import typing as t
import uuid
import logging


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


UnauthorizedResponses: t.Dict = {
    401: {"description": "access token expired"},
    403: {"description": "invalid credentials"},
    422: {"description": "inactive user"},
}


class GroupInfo(SQLModel):
    """Group information returned to frontend."""
    id: uuid.UUID
    name: str
    description: str | None = None


class UserInfo(SQLModel):
    """User information returned to frontend."""
    id: uuid.UUID
    email: str
    name: str | None = None
    description: str | None = None
    groups: t.List[GroupInfo] = []


class UserPasswordRegistration(SQLModel):
    """User registration information."""
    email: str
    name: str | None = None
    password: str


@router.post(
    "/basic/login",
    summary="Generate JWT Token using Password authentication",
    description="Generate a JWT token for user authentication.",
    responses=UnauthorizedResponses
)
async def generate_token(
    session: dependencies.SessionRequired,
    form: t.Annotated[OAuth2PasswordRequestForm, Depends()]
) -> JWTToken:
    """Generate a JWT token for user authentication."""
    try:
        user = await Authentication.authenticate(
            session,
            bitmask=PasswordAuthentication.bitmask,
            email=form.username,
            password=form.password
        )
    except InvalidLogin as error:
        raise HTTPException(401, f"invalid credentials - {error}")
    if user.is_disabled or user.is_deleted:
        raise HTTPException(422, "inactive user")
    return await JWTToken.create(session, user)


@router.get(
    "/me",
    summary="Get Current User",
    description="Retrieve the current authenticated user's information.",
    responses=UnauthorizedResponses
)
async def read_current_user(
    session: dependencies.SessionRequired,
    user: dependencies.UserRequired
) -> UserInfo:
    """Retrieve the current authenticated user's information."""
    await session.refresh(user, attribute_names=["groups"])
    groups = [
        GroupInfo(**group.model_dump(include={"id", "name", "description"}))
        for group in user.groups
    ]
    return UserInfo(
        **user.model_dump(include={"id", "email", "name", "description"}),
        groups=groups
    )


@router.post(
    "/basic/register",
    summary="Register User login with password",
    description="Register a new user."
)
async def register_user(
    session: dependencies.SessionRequired,
    form: UserPasswordRegistration
) -> UserInfo:
    """Register a new user."""
    user = await User.create(
        session,
        email=form.email,
        name=form.name
    )
    if not user:
        raise HTTPException(400, "user registration failed")
    auth = await PasswordAuthentication.create(
        session,
        user=user,
        password=form.password
    )
    await user.bind_auth_method(session, auth=auth)
    return UserInfo(**user.model_dump())


@router.post(
    "/token/refresh",
    summary="Refresh access token using refresh token"
)
async def refresh_access_token(
    session: dependencies.SessionRequired,
    refresh_token: str
) -> JWTToken:
    """Refresh acccess token."""
    try:
        token = await JWTToken.refresh(session, content=refresh_token)
        return token
    except ValueError as error:
        raise HTTPException(403, f"{str(error)}")


@router.post(
    "/logout",
    summary="Logout current user"
)
async def logout(
    session: dependencies.SessionRequired,
    user: dependencies.UserRequired
) -> Response:
    """Logout and redirect user to homepage."""
    await JWTToken.destroy(session, user)
    return Response(status_code=200)


class OAuthRedirectURL(SQLModel):
    """Redirect user to OAuth server."""
    name: str = settings.OAUTH_SERVER_NAME
    url: str


@router.get(
    "/oauth/redirect",
    summary="Get OAuth2 login redirect URL",
    description="Redirect to given URL for authtication."
)
async def redirect_oauth_login() -> OAuthRedirectURL:
    """Redirect user to OAuth server site."""
    url, state = settings.OAUTH.create_authorization_url(
        url=settings.OAUTH_SERVER_URL
    )
    await dependencies.OAuthStateRequired.record_state(state, url)
    return OAuthRedirectURL(url=url)


@router.get(
    "/oauth/login",
    summary="Login user callback",
    description="This endpoint should be redirected to by OAuth server."
)
async def oauth_login_callback() -> JWTToken:
    """
    1. Get code from OAuth server.
    2. Get access token using code from OAuth server.
    3. Get user info from OAuth server using access token.
        3.1. Create new user and OAuth login method for user;
        3.2. Merge OAuth login method for current user;
    4. Generate JWTToken for logged in user
    """
    ...


if settings.ENVIRONMENT == "test":
    logger.info("including test-only routes: /auth/confidential")

    @router.get(
        "/confidential",
        summary="Confidential Endpoint",
        description="A confidential endpoint accessible only to users in the 'test-group' group.",
        dependencies=[Depends(dependencies.UserGroupsRequired("test-group"))],
    )
    async def confidential(user: dependencies.UserRequired) -> t.List[GroupInfo]:
        return [
            GroupInfo(
                **group.model_dump(include={"id", "name", "description"})
            ) for group in user.groups
        ]
