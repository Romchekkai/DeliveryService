from uuid import uuid4

import pytest
from user_service.application.use_cases.get_user_by_id import GetUserByIdUseCase
from user_service.domain.entities.user import User
from user_service.domain.exceptions import UserNotFoundError
from user_service.domain.value_objects.email import Email
from user_service.domain.value_objects.password_hash import PasswordHash
from user_service.domain.value_objects.role import Role
from user_service.domain.value_objects.status import Status

from tests.fakes.repositories import InMemoryUserRepository


async def test_get_user_success() -> None:
    repo = InMemoryUserRepository()
    user = User.register(Email("me@example.com"), PasswordHash("h"))
    await repo.add(user)

    result = await GetUserByIdUseCase(repo).execute(user.id)

    assert result.id == user.id
    assert result.email == "me@example.com"
    assert result.role is Role.USER
    assert result.status is Status.ACTIVE


async def test_get_user_not_found() -> None:
    with pytest.raises(UserNotFoundError):
        await GetUserByIdUseCase(InMemoryUserRepository()).execute(uuid4())
