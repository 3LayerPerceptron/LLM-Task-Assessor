from backend.tests import mockdata
from backend.src.database.user import User, Group

from sqlmodel.ext.asyncio.session import AsyncSession


async def test_create_delete_group(session: AsyncSession) -> None:
    group = await Group.create(
        session,
        name=mockdata.group.name,
        description=mockdata.group.description
    )
    assert group.name == group.name
    assert group.description == group.description
    await group.delete(session)
    group = await Group.query(session, name=group.name)
    assert group is None


async def test_list_groups(session: AsyncSession, group: Group) -> None:
    groups = await Group.list(session)
    assert any(g.name == group.name for g in groups)


async def test_query_group_by_name(session: AsyncSession, group: Group) -> None:
    queried_group = await Group.query(session, name=group.name)
    assert queried_group is not None


async def test_add_and_remove_user_group(session: AsyncSession, user: User, group: Group) -> None:
    # Add user to group
    await group.add_user(session, user=user)

    # Verify user is in group
    await session.refresh(user, attribute_names=["groups"])
    assert any(group.name == group.name for group in user.groups)

    # Remove user from group
    await group.remove_user(session, user=user)

    # Verify user is no longer in group
    await session.refresh(user, attribute_names=["groups"])
    assert all(group.name != group.name for group in user.groups)
