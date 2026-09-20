import pytest
from user_service.application.dto.user_dto import LoginInputDTO, RegisterUserInputDTO
from user_service.application.use_cases.authenticate_user import AuthenticateUserUseCase
from user_service.application.use_cases.register_user import RegisterUser
from user_service.domain.exceptions import InvalidCredentialsError
from user_service.domain.value_objects.email import Email

from tests.fakes.repositories import InMemoryRefreshTokenRepository, InMemoryUserRepository
from tests.fakes.security import FakePasswordHasher, FakeRefreshTokenHasher, FakeTokenService

EMAIL = "login@example.com"
PASSWORD = "correct-password"


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def refresh_repo() -> InMemoryRefreshTokenRepository:
    return InMemoryRefreshTokenRepository()


@pytest.fixture
def refresh_hasher() -> FakeRefreshTokenHasher:
    return FakeRefreshTokenHasher()


@pytest.fixture
def use_case(
    users: InMemoryUserRepository,
    refresh_repo: InMemoryRefreshTokenRepository,
    refresh_hasher: FakeRefreshTokenHasher,
) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(
        user_repository=users,
        refresh_token_repository=refresh_repo,
        password_hasher=FakePasswordHasher(),
        token_service=FakeTokenService(),
        refresh_token_hasher=refresh_hasher,
    )


@pytest.fixture(autouse=True)
async def registered_user(users: InMemoryUserRepository) -> None:
    await RegisterUser(users, FakePasswordHasher()).execute(RegisterUserInputDTO(EMAIL, PASSWORD))


async def test_login_success(use_case: AuthenticateUserUseCase) -> None:
    result = await use_case.execute(LoginInputDTO(EMAIL, PASSWORD))

    assert result.access_token.startswith("access::")
    assert result.refresh_token
    assert result.token_type == "bearer"


async def test_login_saves_refresh_token_hash_not_raw_token(
    use_case: AuthenticateUserUseCase,
    users: InMemoryUserRepository,
    refresh_repo: InMemoryRefreshTokenRepository,
    refresh_hasher: FakeRefreshTokenHasher,
) -> None:
    result = await use_case.execute(LoginInputDTO(EMAIL, PASSWORD))

    user = await users.get_by_email(Email(EMAIL))
    assert user is not None
    [stored] = refresh_repo.tokens.values()
    assert stored.user_id == user.id
    assert stored.token_hash == refresh_hasher.hash(result.refresh_token)
    assert stored.token_hash != result.refresh_token
    assert stored.is_valid()


async def test_every_login_issues_a_new_refresh_token(
    use_case: AuthenticateUserUseCase, refresh_repo: InMemoryRefreshTokenRepository
) -> None:
    first = await use_case.execute(LoginInputDTO(EMAIL, PASSWORD))
    second = await use_case.execute(LoginInputDTO(EMAIL, PASSWORD))

    assert first.refresh_token != second.refresh_token
    assert len(refresh_repo.tokens) == 2


async def test_login_unknown_email(use_case: AuthenticateUserUseCase) -> None:
    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(LoginInputDTO("nobody@example.com", PASSWORD))


async def test_login_wrong_password(
    use_case: AuthenticateUserUseCase, refresh_repo: InMemoryRefreshTokenRepository
) -> None:
    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(LoginInputDTO(EMAIL, "wrong-password"))
    assert refresh_repo.tokens == {}


async def test_login_blocked_user(
    use_case: AuthenticateUserUseCase,
    users: InMemoryUserRepository,
    refresh_repo: InMemoryRefreshTokenRepository,
) -> None:
    user = await users.get_by_email(Email(EMAIL))
    assert user is not None
    user.block()

    with pytest.raises(InvalidCredentialsError, match="not active"):
        await use_case.execute(LoginInputDTO(EMAIL, PASSWORD))
    assert refresh_repo.tokens == {}
