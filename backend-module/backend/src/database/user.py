from backend.src import settings
from backend.src.database import (
    InvalidAuthenticationMethod,
    InvalidLogin
)

import typing as t
import typing_extensions as te
import uuid
from datetime import datetime, timezone, timedelta
import secrets

from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Relationship, select
from sqlmodel.ext.asyncio.session import AsyncSession
from passlib.context import CryptContext


PasswordContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserGroup(SQLModel, table=True):
    user_id: uuid.UUID = Field(
        nullable=False, foreign_key="user.id", primary_key=True
    )
    group_id: uuid.UUID = Field(
        nullable=False, foreign_key="group.id", primary_key=True, ondelete="CASCADE"
    )

    time_created: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc).replace(tzinfo=None),
        nullable=False
    )


class Group(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=255)
    description: str | None = Field(default=None, max_length=1024)

    time_created: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc).replace(tzinfo=None),
        nullable=False
    )

    users: t.List["User"] = Relationship(
        back_populates="groups", link_model=UserGroup
    )

    @classmethod
    async def create(cls, session: AsyncSession, *, name: str, **extra_fields: t.Any) -> te.Self:
        """Create a new group."""
        group = cls(name=name, **extra_fields)
        session.add(group)
        await session.commit()
        await session.refresh(group)
        return group

    async def delete(self, session: AsyncSession) -> None:
        """Delete the group."""
        await session.delete(self)
        await session.commit()

    @classmethod
    async def list(cls, session: AsyncSession) -> t.List[te.Self]:
        """List all groups."""
        groups = await session.exec(select(cls))
        return list(groups.unique().all())

    @classmethod
    async def query(cls, session: AsyncSession, *, id: str | None = None, name: str | None = None) -> te.Self | None:
        """Query group by id or name."""
        if id:
            return await session.get(cls, id)
        if name:
            group = await session.exec(
                select(cls).where(cls.name == name)
            )
            return group.first() if group else None
        return None

    async def add_user(self, session: AsyncSession, *, user: "User") -> None:
        """Add a user to the group."""
        await session.refresh(self, attribute_names=["users"])
        if user not in self.users:
            self.users.append(user)
            session.add(self)
            await session.commit()
            await session.refresh(self, attribute_names=["users"])

    async def remove_user(self, session: AsyncSession, *, user: "User") -> None:
        """Remove a user from the group."""
        await session.refresh(self, attribute_names=["users"])
        if user in self.users:
            self.users.remove(user)
            session.add(self)
            await session.commit()
            await session.refresh(self)
            await session.refresh(self, attribute_names=["users"])


class Authentication(SQLModel):
    bitmask: t.ClassVar[int]
    identifier: t.ClassVar[str]

    @classmethod
    async def authenticate(cls, session: AsyncSession, bitmask: int, **kwargs) -> "User":
        """Call sub-class authenticate function using bitmask."""
        for ct in cls.__subclasses__():
            if ct.bitmask == bitmask:
                return await ct.authenticate(session, **kwargs)
        raise InvalidAuthenticationMethod(
            "cannot find authentication method with given bitmask")


class PasswordAuthentication(Authentication, table=True):
    bitmask: t.ClassVar[int] = 0
    identifier: t.ClassVar[str] = "Password"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        nullable=False, foreign_key="user.id", primary_key=True)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    hashed_password: str = Field(nullable=False)

    @classmethod
    async def query(cls, session: AsyncSession, *, email: str) -> te.Self | None:
        """Query password authentication by email."""
        query = await session.exec(select(cls).where(cls.email == email))
        return query.first()

    @classmethod
    async def create(cls, session: AsyncSession, *, user: "User", password: str) -> te.Self:
        """Create a new password authentication."""
        hashed_password = cls._hash_password(plain_password=password)
        auth = cls(user_id=user.id, email=user.email,
                   hashed_password=hashed_password)
        session.add(auth)
        await session.commit()
        await session.refresh(auth)
        await user.bind_auth_method(session, auth=auth)
        await session.refresh(auth)
        return auth

    async def reset_password(self, session: AsyncSession, *, password: str) -> None:
        """Reset password."""
        await session.refresh(self)
        self.hashed_password = self._hash_password(plain_password=password)
        session.add(self)
        await session.commit()
        await session.refresh(self)

    async def delete(self, session: AsyncSession) -> None:
        """Unbind current authentication method and delete it."""
        user = await User.query(session, id=str(self.user_id))
        if not user:
            raise InvalidLogin("internal error - unmatched login method")
        await user.unbind_auth_method(session, auth=self)
        await session.delete(self)
        await session.flush()

    @classmethod
    async def authenticate(cls, session: AsyncSession, *, email: str, password: str) -> "User":
        """Authenticate user by email and password."""
        auth = await cls.query(session, email=email)
        if auth is None:
            raise InvalidLogin("invalid email or password")
        if not auth._validate_plain_password(plain_password=password):
            raise InvalidLogin("invalid email or password")
        user = await User.query(session, id=str(auth.user_id))
        if user is None:
            raise InvalidLogin("internal error - unmatched login method")
        if user.is_disabled or user.is_deleted:
            raise InvalidLogin("user account is disabled or deleted")
        return user

    def _validate_plain_password(self, *, plain_password: str) -> bool:
        """Validate password with salt using hash algorithm."""
        return PasswordContext.verify(plain_password, self.hashed_password)

    @staticmethod
    def _hash_password(*, plain_password: str) -> str:
        """Hash password with salt using hash algorithm."""
        return PasswordContext.hash(plain_password)


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)

    is_disabled: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    time_created: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    time_updated: datetime | None = Field(default=None)
    time_deleted: datetime | None = Field(default=None)

    auth_methods_bitmask: int = Field(default=0)

    groups: t.List[Group] = Relationship(
        back_populates="users", link_model=UserGroup
    )

    @classmethod
    async def create(cls, session: AsyncSession, *, email: str, **extra_fields: t.Any) -> te.Self:
        """Create a new user."""
        user = cls(
            email=email,
            **extra_fields
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def delete(self, session: AsyncSession) -> None:
        """Soft delete the user by setting is_deleted to True and updating time_deleted."""
        self.is_deleted = True
        self.time_deleted = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(self)
        await session.commit()
        await session.refresh(self)

    @classmethod
    async def query(cls, session: AsyncSession, *, id: str | None = None, email: str | None = None) -> te.Self | None:
        """Query user by id or email."""
        if id:
            return await session.get(cls, uuid.UUID(id))
        if email:
            user = await session.exec(
                select(cls).where(cls.email == email)
            )
            return user.first() if user else None
        return None

    async def bind_auth_method(self, session: AsyncSession, *, auth: Authentication) -> None:
        """Add an authentication method to the user."""
        await session.refresh(self)
        self.auth_methods_bitmask |= 1 << auth.bitmask
        session.add(self)
        await session.commit()
        await session.refresh(self)

    async def unbind_auth_method(self, session: AsyncSession, *, auth: Authentication) -> None:
        """Remove an authentication method from the user."""
        self.auth_methods_bitmask &= ~(1 << auth.bitmask)
        session.add(self)
        await session.commit()
        await session.refresh(self)

    async def list_supported_authentication(self) -> t.List[t.Type[Authentication]]:
        """List all authentication methods support by this user."""
        supported_auth_methods: t.List[t.Type[Authentication]] = []
        for ct in Authentication.__subclasses__():
            if 1 << ct.bitmask & self.auth_methods_bitmask:
                supported_auth_methods.append(ct)
        return supported_auth_methods


class RefreshToken(SQLModel, table=True):
    user_id: uuid.UUID = Field(
        nullable=False, foreign_key="user.id", primary_key=True)
    content: str = Field(nullable=False, primary_key=True)

    time_created: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    valid_before: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).replace(tzinfo=None) + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        ),
        nullable=False
    )

    @classmethod
    async def query(cls, session: AsyncSession, *, content: str | None = None, user: User | None = None) -> te.Self | None:
        """Query a refresh token by token or user."""
        if content is None and user is None:
            return None
        if content:
            query = await session.exec(select(cls).where(cls.content == content))
            return query.first()
        if user:
            await session.refresh(user)
            query = await session.exec(select(cls).where(cls.user_id == user.id))
            return query.first()

    @classmethod
    async def create(cls, session: AsyncSession, *, user: User) -> te.Self:
        """Create or update refresh token for corresponded user."""
        token = await cls.query(session, user=user)
        if token:
            token.content = secrets.token_hex(32)
            token.time_created = datetime.now(
                timezone.utc).replace(tzinfo=None)
            token.valid_before = token.time_created + timedelta(
                minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
            )
        else:
            await session.refresh(user)
            token = cls(user_id=user.id, content=secrets.token_hex(32))
        session.add(token)
        await session.commit()
        return token

    async def delete(self, session: AsyncSession) -> None:
        """Delete refresh token for logging out."""
        await session.delete(self)
        await session.flush()
        await session.commit()
