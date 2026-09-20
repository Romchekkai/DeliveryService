from datetime import datetime, timedelta, timezone

import pytest
from user_service.application.dto.token_dto import RefreshTokenInputDTO, TokenPairOutputDTO
from user_service.application.dto.user_dto import LoginInputDTO, RegisterUserInputDTO
from user_service.application.use_cases.authenticate_user import AuthenticateUserUseCase
from user_service.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from user_service.application.use_cases.register_user import RegisterUser
from user_service.domain.exceptions import InvalidTokenError
from user_service.domain.value_objects.email import Email

from tests.fakes.repositories import InMemoryRefreshTokenRepository, InMemoryUserRepository
from tests.fakes.security import FakePasswordHasher, FakeRefreshTokenHasher, FakeTokenService

EMAIL = "refresh@example.com"
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
) -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(
        user_repository=users,
        refresh_token_repository=refresh_repo,
        token_service=FakeTokenService(),
        refresh_token_hasher=refresh_hasher,
    )


@pytest.fixture
async def tokens(
    users: InMemoryUserRepository,
    refresh_repo: InMemoryRefreshTokenRepository,
    refresh_hasher: FakeRefreshTokenHasher,
) -> TokenPairOutputDTO:
    await RegisterUser(users, FakePasswordHasher()).execute(RegisterUserInputDTO(EMAIL, PASSWORD))
    login = AuthenticateUserUseCase(
        user_repository=users,
        refresh_token_repository=refresh_repo,
        password_hasher=FakePasswordHasher(),
        token_service=FakeTokenService(),
        refresh_token_hasher=refresh_hasher,
    )
    return await login.execute(LoginInputDTO(EMAIL, PASSWORD))


async def test_refresh_success(
    use_case: RefreshAccessTokenUseCase, tokens: TokenPairOutputDTO
) -> None:
    result = await use_case.execute(RefreshTokenInputDTO(tokens.refresh_token))

    assert result.access_token.startswith("access::")
    assert result.refresh_token != tokens.refresh_token


async def test_refresh_rotates_token(
    use_case: RefreshAccessTokenUseCase,
    tokens: TokenPairOutputDTO,
    refresh_repo: InMemoryRefreshTokenRepository,
    refresh_hasher: FakeRefreshTokenHasher,
) -> None:
    result = await use_case.execute(RefreshTokenInputDTO(tokens.refresh_token))

    old = await refresh_repo.get_by_hash(refresh_hasher.hash(tokens.refresh_token))
    new = await refresh_repo.get_by_hash(refresh_hasher.hash(result.refresh_token))
    assert old is not None and old.revoked
    assert new is not None and new.is_valid()


async def test_refresh_invalid_token(use_case: RefreshAccessTokenUseCase) -> None:
    with pytest.raises(InvalidTokenError):
        await use_case.execute(RefreshTokenInputDTO("does-not-exist"))


async def test_refresh_reused_token_fails(
    use_case: RefreshAccessTokenUseCase, tokens: TokenPairOutputDTO
) -> None:
    await use_case.execute(RefreshTokenInputDTO(tokens.refresh_token))

    with pytest.raises(InvalidTokenError):
        await use_case.execute(RefreshTokenInputDTO(tokens.refresh_token))


async def test_refresh_expired_token_fails(
    use_case: RefreshAccessTokenUseCase,
    tokens: TokenPairOutputDTO,
    refresh_repo: InMemoryRefreshTokenRepository,
    refresh_hasher: FakeRefreshTokenHasher,
) -> None:
    stored = await refresh_repo.get_by_hash(refresh_hasher.hash(tokens.refresh_token))
    assert stored is not None
    stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(RefreshTokenInputDTO(tokens.refresh_token))


async def test_refresh_for_blocked_user_fails(
    use_case: RefreshAccessTokenUseCase,
    tokens: TokenPairOutputDTO,
    users: InMemoryUserRepository,
) -> None:
    user = await users.get_by_email(Email(EMAIL))
    assert user is not None
    user.block()

    with pytest.raises(InvalidTokenError):
        await use_case.execute(RefreshTokenInputDTO(tokens.refresh_token))


async def test_refresh_for_deleted_user_fails(
    use_case: RefreshAccessTokenUseCase,
    tokens: TokenPairOutputDTO,
    users: InMemoryUserRepository,
) -> None:
    users.users.clear()

    with pytest.raises(InvalidTokenError):
        await use_case.execute(RefreshTokenInputDTO(tokens.refresh_token))
