import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.tests import mockdata
from backend.src.database.user import (
    User,
    Authentication,
    InvalidLogin,
    PasswordAuthentication
)


@pytest.mark.dependency(name="test_create_user")
async def test_create_user(session: AsyncSession) -> None:
    user = await User.create(
        session,
        email=mockdata.user.email,
        name=mockdata.user.name,
        description=mockdata.user.description
    )
    assert user.email == mockdata.user.email
    assert user.name == mockdata.user.name
    assert user.description == mockdata.user.description
    assert user.is_disabled is False
    assert user.is_deleted is False


@pytest.mark.dependency(depends=["test_create_user"])
async def test_query_user(session: AsyncSession) -> None:
    user_queried_by_email = await User.query(session, email=mockdata.user.email)
    assert user_queried_by_email is not None
    user_queried_by_id = await User.query(session, id=str(user_queried_by_email.id))
    assert user_queried_by_email == user_queried_by_id


async def test_query_nonexist_user(session: AsyncSession) -> None:
    user_not_exist = await User.query(session, email="ghost@404.com")
    assert user_not_exist is None


async def test_list_user_without_authentication(user: User) -> None:
    auths = await user.list_supported_authentication()
    assert not auths


@pytest.mark.dependency(name="test_create_password_authentication")
async def test_create_password_authentication(session: AsyncSession, user: User) -> None:
    auth = await PasswordAuthentication.create(session, user=user, password=mockdata.password_auth.password)
    assert auth is not None
    assert auth.hashed_password != mockdata.password_auth.password


async def test_list_user_with_authentication(user: User) -> None:
    auths = await user.list_supported_authentication()
    assert any(auth.bitmask == PasswordAuthentication.bitmask for auth in auths)


@pytest.mark.dependency(depends=["test_create_password_authentication"])
async def test_authenticate_user_wrong_password(session: AsyncSession) -> None:
    with pytest.raises(InvalidLogin):
        await Authentication.authenticate(
            session,
            PasswordAuthentication.bitmask,
            email=mockdata.user.email,
            password="this_is_a_wrong_password"
        )


@pytest.mark.dependency(depends=["test_create_password_authentication"])
async def test_authenticate_user_password(session: AsyncSession, user: User) -> None:
    expected_user = await Authentication.authenticate(
        session,
        PasswordAuthentication.bitmask,
        email=mockdata.user.email,
        password=mockdata.password_auth.password
    )
    assert user == expected_user


@pytest.mark.dependency(depends=["test_create_password_authentication"])
async def test_reset_password(session: AsyncSession, user: User) -> None:
    auth = await PasswordAuthentication.query(session, email=user.email)
    if not auth:
        raise RuntimeError
    await auth.reset_password(session, password="a_super_secret")

    # Authenticate after reseting
    expected_user = await Authentication.authenticate(
        session,
        PasswordAuthentication.bitmask,
        email=mockdata.user.email,
        password="a_super_secret"
    )
    assert user == expected_user


@pytest.mark.dependency(depends=["test_create_password_authentication"])
async def test_remove_user_authentication(session: AsyncSession, user: User) -> None:
    auth = await PasswordAuthentication.query(session, email=user.email)
    if not auth:
        raise RuntimeError
    await auth.delete(session)
    auths = await user.list_supported_authentication()
    assert not auths

    # Try to auth after deletion
    with pytest.raises(InvalidLogin):
        await Authentication.authenticate(
            session,
            PasswordAuthentication.bitmask,
            email=mockdata.user.email,
            password=mockdata.password_auth.password
        )


async def test_authenticate_non_exist_user(session: AsyncSession) -> None:
    with pytest.raises(InvalidLogin):
        await Authentication.authenticate(
            session,
            PasswordAuthentication.bitmask,
            email="ghost@404.com",
            password="a_supper_secret"
        )
