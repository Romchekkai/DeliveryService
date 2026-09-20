from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from user_service.domain.entities.user import User
from user_service.domain.exceptions import UserAlreadyExistsError, UserNotFoundError
from user_service.domain.value_objects.email import Email
from user_service.domain.value_objects.password_hash import PasswordHash
from user_service.domain.value_objects.role import Role
from user_service.domain.value_objects.status import Status
from user_service.infrastructure.db.repositories import SqlAlchemyUserRepository


def new_user(email: str = "repo@example.com") -> User:
    return User.register(Email(email), PasswordHash("bcrypt-hash"))


@pytest.fixture
def repo(session: AsyncSession) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


async def test_add_and_get_by_email(repo: SqlAlchemyUserRepository) -> None:
    user = new_user()
    await repo.add(user)

    found = await repo.get_by_email(Email("repo@example.com"))

    assert found is not None
    assert found.id == user.id
    assert found.password_hash == PasswordHash("bcrypt-hash")
    assert found.role is Role.USER
    assert found.status is Status.ACTIVE


async def test_get_by_email_unknown_returns_none(repo: SqlAlchemyUserRepository) -> None:
    assert await repo.get_by_email(Email("nobody@example.com")) is None


async def test_add_duplicate_email_raises(repo: SqlAlchemyUserRepository) -> None:
    await repo.add(new_user("dup@example.com"))

    with pytest.raises(UserAlreadyExistsError):
        await repo.add(new_user("dup@example.com"))


async def test_repository_is_usable_after_duplicate_error(repo: SqlAlchemyUserRepository) -> None:
    await repo.add(new_user("dup@example.com"))
    with pytest.raises(UserAlreadyExistsError):
        await repo.add(new_user("dup@example.com"))

    await repo.add(new_user("other@example.com"))  # the session was rolled back, not poisoned

    assert await repo.exists_with_email(Email("other@example.com"))


async def test_exists_with_email(repo: SqlAlchemyUserRepository) -> None:
    await repo.add(new_user("exists@example.com"))

    assert await repo.exists_with_email(Email("exists@example.com")) is True
    assert await repo.exists_with_email(Email("missing@example.com")) is False


async def test_get_by_id(repo: SqlAlchemyUserRepository) -> None:
    user = new_user()
    await repo.add(user)

    found = await repo.get_by_id(user.id)

    assert found is not None and found.email == user.email


async def test_get_by_id_unknown_returns_none(repo: SqlAlchemyUserRepository) -> None:
    assert await repo.get_by_id(uuid4()) is None


async def test_update_user(repo: SqlAlchemyUserRepository, session: AsyncSession) -> None:
    user = new_user()
    await repo.add(user)

    user.block()
    user.password_hash = PasswordHash("new-hash")
    await repo.update(user)
    session.expire_all()

    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.status is Status.BLOCKED
    assert found.password_hash == PasswordHash("new-hash")


async def test_update_role(repo: SqlAlchemyUserRepository) -> None:
    user = new_user()
    await repo.add(user)

    user.change_role(Role.ADMIN)
    await repo.update(user)

    found = await repo.get_by_id(user.id)
    assert found is not None and found.role is Role.ADMIN


async def test_update_missing_raises(repo: SqlAlchemyUserRepository) -> None:
    with pytest.raises(UserNotFoundError):
        await repo.update(new_user())
