import pytest
from user_service.application.dto.user_dto import RegisterUserInputDTO
from user_service.application.use_cases.register_user import RegisterUser
from user_service.domain.exceptions import UserAlreadyExistsError
from user_service.domain.value_objects.email import Email
from user_service.domain.value_objects.role import Role
from user_service.domain.value_objects.status import Status

from tests.fakes.repositories import InMemoryUserRepository
from tests.fakes.security import FakePasswordHasher


@pytest.fixture
def repo() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def use_case(repo: InMemoryUserRepository) -> RegisterUser:
    return RegisterUser(user_repository=repo, password_hasher=FakePasswordHasher())


async def test_register_success(use_case: RegisterUser, repo: InMemoryUserRepository) -> None:
    result = await use_case.execute(RegisterUserInputDTO("new@example.com", "password123"))

    assert result.email == "new@example.com"
    assert result.role is Role.USER
    assert result.status is Status.ACTIVE
    assert result.id in repo.users


async def test_register_hashes_password(
    use_case: RegisterUser, repo: InMemoryUserRepository
) -> None:
    await use_case.execute(RegisterUserInputDTO("new@example.com", "password123"))

    stored = await repo.get_by_email(Email("new@example.com"))
    assert stored is not None
    assert stored.password_hash.value != "password123"
    assert stored.password_hash.value == FakePasswordHasher().hash_password("password123")


async def test_register_duplicate_email_raises(
    use_case: RegisterUser, repo: InMemoryUserRepository
) -> None:
    await use_case.execute(RegisterUserInputDTO("dup@example.com", "password123"))

    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(RegisterUserInputDTO("dup@example.com", "another-pass"))
    assert len(repo.users) == 1


async def test_register_invalid_email_raises_value_error(
    use_case: RegisterUser, repo: InMemoryUserRepository
) -> None:
    with pytest.raises(ValueError):
        await use_case.execute(RegisterUserInputDTO("not-an-email", "password123"))
    assert repo.users == {}
